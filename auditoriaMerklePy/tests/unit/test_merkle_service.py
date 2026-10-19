"""
Tests unitarios para MerkleService y BatchScheduler.

Cubren:
- get_or_create_active_batch: obtener batch existente, crear nuevo, encadenamiento
- assign_log_to_batch: asignación correcta, auto-cierre por N logs
- close_batch: construcción de árbol, persistencia de nodos, validaciones
- close_expired_batches: cierre por timeout, omisión de batches vacíos
- BatchScheduler: start/stop
"""

import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from app.models.log_entry import LogEntry
from app.models.merkle_batch import MerkleBatch
from app.models.merkle_node import MerkleNode
from app.core.hashing import hash_log_entry


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture
def mock_session():
    """Mock de AsyncSession."""
    session = AsyncMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    return session


def _make_log(
    index: int,
    batch_id=None,
    leaf_index=None,
) -> LogEntry:
    """Helper para crear LogEntry de prueba con hash real."""
    payload = {"test": f"data_{index}", "index": index}
    content_hash = hash_log_entry({
        "source_app": "test_app",
        "event_type": "test_event",
        "severity": "info",
        "payload": payload,
    })
    log = LogEntry(
        id=uuid.uuid4(),
        source_app="test_app",
        event_type="test_event",
        severity="info",
        payload=payload,
        content_hash=content_hash,
        batch_id=batch_id,
        leaf_index=leaf_index,
        received_at=datetime.now(timezone.utc),
    )
    return log


def _make_batch(
    batch_number: int = 1,
    status: str = "open",
    leaf_count: int = 0,
    merkle_root: str = None,
    created_at: datetime = None,
) -> MerkleBatch:
    """Helper para crear MerkleBatch de prueba."""
    batch = MerkleBatch(
        id=uuid.uuid4(),
        batch_number=batch_number,
        status=status,
        leaf_count=leaf_count,
        merkle_root=merkle_root,
        created_at=created_at or datetime.now(timezone.utc),
    )
    return batch


# ============================================================
# Tests de get_or_create_active_batch
# ============================================================

class TestGetOrCreateActiveBatch:

    @pytest.mark.asyncio
    async def test_returns_existing_open_batch(self, mock_session):
        """Si ya hay un batch open, lo retorna."""
        from app.services.merkle_service import MerkleService

        existing = _make_batch(batch_number=5, leaf_count=3)

        service = MerkleService(mock_session)
        service.batch_repo.get_open_batch = AsyncMock(return_value=existing)

        result = await service.get_or_create_active_batch()

        assert result.id == existing.id
        assert result.batch_number == 5
        service.batch_repo.get_open_batch.assert_called_once()

    @pytest.mark.asyncio
    async def test_creates_new_batch_when_none_open(self, mock_session):
        """Si no hay batch open, crea uno nuevo."""
        from app.services.merkle_service import MerkleService

        service = MerkleService(mock_session)
        service.batch_repo.get_open_batch = AsyncMock(return_value=None)
        service.batch_repo.get_next_batch_number = AsyncMock(return_value=1)
        service.batch_repo.get_latest_batch = AsyncMock(return_value=None)
        service.batch_repo.create = AsyncMock(
            side_effect=lambda b: b
        )

        result = await service.get_or_create_active_batch()

        assert result.batch_number == 1
        assert result.status == "open"
        assert result.leaf_count == 0
        assert result.prev_batch_root is None

    @pytest.mark.asyncio
    async def test_chains_with_previous_batch(self, mock_session):
        """Nuevo batch encadena con el root del anterior."""
        from app.services.merkle_service import MerkleService

        prev_batch = _make_batch(
            batch_number=3,
            status="closed",
            merkle_root="abc123def456" * 5 + "abcd",
        )

        service = MerkleService(mock_session)
        service.batch_repo.get_open_batch = AsyncMock(return_value=None)
        service.batch_repo.get_next_batch_number = AsyncMock(return_value=4)
        service.batch_repo.get_latest_batch = AsyncMock(return_value=prev_batch)
        service.batch_repo.create = AsyncMock(
            side_effect=lambda b: b
        )

        result = await service.get_or_create_active_batch()

        assert result.batch_number == 4
        assert result.prev_batch_root == prev_batch.merkle_root


# ============================================================
# Tests de assign_log_to_batch
# ============================================================

class TestAssignLogToBatch:

    @pytest.mark.asyncio
    async def test_assigns_log_with_correct_index(self, mock_session):
        """Log se asigna con leaf_index = leaf_count actual del batch."""
        from app.services.merkle_service import MerkleService

        batch = _make_batch(batch_number=1, leaf_count=5)
        log = _make_log(index=1)

        service = MerkleService(mock_session)
        service.get_or_create_active_batch = AsyncMock(return_value=batch)

        # No debe cerrar (leaf_count=6 < 1024)
        with patch.object(service, 'close_batch', new_callable=AsyncMock) as mock_close:
            result = await service.assign_log_to_batch(log)

            assert log.batch_id == batch.id
            assert log.leaf_index == 5  # era leaf_count=5
            assert batch.leaf_count == 6
            mock_close.assert_not_called()

    @pytest.mark.asyncio
    async def test_auto_close_when_max_leaves_reached(self, mock_session):
        """Cuando el batch alcanza BATCH_MAX_LEAVES, se cierra automáticamente."""
        from app.services.merkle_service import MerkleService

        batch = _make_batch(batch_number=1, leaf_count=1023)
        log = _make_log(index=1)

        service = MerkleService(mock_session)
        service.get_or_create_active_batch = AsyncMock(return_value=batch)

        with patch.object(service, 'close_batch', new_callable=AsyncMock) as mock_close:
            with patch('app.services.merkle_service.settings') as mock_settings:
                mock_settings.BATCH_MAX_LEAVES = 1024
                await service.assign_log_to_batch(log)

                assert batch.leaf_count == 1024
                mock_close.assert_called_once_with(batch)


# ============================================================
# Tests de close_batch
# ============================================================

class TestCloseBatch:

    @pytest.mark.asyncio
    async def test_builds_tree_and_persists_nodes(self, mock_session):
        """Cierre construye el árbol y persiste todos los nodos."""
        from app.services.merkle_service import MerkleService

        batch = _make_batch(batch_number=1, leaf_count=4)
        logs = [_make_log(i, batch_id=batch.id, leaf_index=i) for i in range(4)]

        service = MerkleService(mock_session)
        service.log_repo.get_by_batch = AsyncMock(return_value=logs)
        service.node_repo.bulk_create = AsyncMock(
            side_effect=lambda nodes: nodes
        )

        # Mock close_batch del repo para devolver batch actualizado
        async def mock_close(batch, merkle_root, leaf_count):
            batch.status = "closed"
            batch.merkle_root = merkle_root
            batch.leaf_count = leaf_count
            batch.closed_at = datetime.now(timezone.utc)
            return batch

        service.batch_repo.close_batch = AsyncMock(side_effect=mock_close)

        result = await service.close_batch(batch)

        assert result.status == "closed"
        assert result.merkle_root is not None
        assert len(result.merkle_root) == 64  # SHA-256 hex
        service.node_repo.bulk_create.assert_called_once()

        # Verificar cantidad de nodos persistidos
        created_nodes = service.node_repo.bulk_create.call_args[0][0]
        # 4 hojas + 2 nivel 1 + 1 raíz = 7 nodos
        assert len(created_nodes) == 7

    @pytest.mark.asyncio
    async def test_rejects_non_open_batch(self, mock_session):
        """No se puede cerrar un batch que no está open."""
        from app.services.merkle_service import MerkleService

        batch = _make_batch(batch_number=1, status="closed")

        service = MerkleService(mock_session)

        with pytest.raises(ValueError, match="Solo se pueden cerrar batches abiertos"):
            await service.close_batch(batch)

    @pytest.mark.asyncio
    async def test_rejects_empty_batch(self, mock_session):
        """No se puede cerrar un batch sin logs."""
        from app.services.merkle_service import MerkleService

        batch = _make_batch(batch_number=1, leaf_count=0)

        service = MerkleService(mock_session)
        service.log_repo.get_by_batch = AsyncMock(return_value=[])

        with pytest.raises(ValueError, match="no tiene logs asignados"):
            await service.close_batch(batch)

    @pytest.mark.asyncio
    async def test_node_levels_are_correct(self, mock_session):
        """Los nodos persistidos tienen niveles y posiciones correctas."""
        from app.services.merkle_service import MerkleService

        batch = _make_batch(batch_number=1, leaf_count=2)
        logs = [_make_log(i, batch_id=batch.id, leaf_index=i) for i in range(2)]

        service = MerkleService(mock_session)
        service.log_repo.get_by_batch = AsyncMock(return_value=logs)
        service.node_repo.bulk_create = AsyncMock(
            side_effect=lambda nodes: nodes
        )

        async def mock_close(batch, merkle_root, leaf_count):
            batch.status = "closed"
            batch.merkle_root = merkle_root
            batch.leaf_count = leaf_count
            return batch

        service.batch_repo.close_batch = AsyncMock(side_effect=mock_close)

        await service.close_batch(batch)

        created_nodes = service.node_repo.bulk_create.call_args[0][0]
        # 2 hojas (level 0) + 1 raíz (level 1) = 3 nodos
        assert len(created_nodes) == 3

        leaves = [n for n in created_nodes if n.level == 0]
        roots = [n for n in created_nodes if n.level == 1]

        assert len(leaves) == 2
        assert len(roots) == 1
        assert leaves[0].position == 0
        assert leaves[1].position == 1
        assert roots[0].position == 0


# ============================================================
# Tests de close_expired_batches
# ============================================================

class TestCloseExpiredBatches:

    @pytest.mark.asyncio
    async def test_closes_expired_batch(self, mock_session):
        """Cierra batch que ha excedido el timeout."""
        from app.services.merkle_service import MerkleService

        # Batch creado hace 10 minutos (> 5 min timeout)
        old_time = datetime.now(timezone.utc) - timedelta(minutes=10)
        batch = _make_batch(batch_number=1, leaf_count=3, created_at=old_time)

        service = MerkleService(mock_session)
        service.batch_repo.get_open_batch = AsyncMock(return_value=batch)

        with patch.object(service, 'close_batch', new_callable=AsyncMock, return_value=batch) as mock_close:
            with patch('app.services.merkle_service.settings') as mock_settings:
                mock_settings.BATCH_TIMEOUT_SECONDS = 300
                result = await service.close_expired_batches()

                assert len(result) == 1
                mock_close.assert_called_once_with(batch)

    @pytest.mark.asyncio
    async def test_skips_non_expired_batch(self, mock_session):
        """No cierra batch que no ha excedido el timeout."""
        from app.services.merkle_service import MerkleService

        # Batch creado hace 1 minuto (< 5 min timeout)
        recent_time = datetime.now(timezone.utc) - timedelta(minutes=1)
        batch = _make_batch(batch_number=1, leaf_count=3, created_at=recent_time)

        service = MerkleService(mock_session)
        service.batch_repo.get_open_batch = AsyncMock(return_value=batch)

        with patch('app.services.merkle_service.settings') as mock_settings:
            mock_settings.BATCH_TIMEOUT_SECONDS = 300
            result = await service.close_expired_batches()

            assert len(result) == 0

    @pytest.mark.asyncio
    async def test_skips_empty_expired_batch(self, mock_session):
        """No cierra batch expirado sin logs."""
        from app.services.merkle_service import MerkleService

        old_time = datetime.now(timezone.utc) - timedelta(minutes=10)
        batch = _make_batch(batch_number=1, leaf_count=0, created_at=old_time)

        service = MerkleService(mock_session)
        service.batch_repo.get_open_batch = AsyncMock(return_value=batch)

        with patch('app.services.merkle_service.settings') as mock_settings:
            mock_settings.BATCH_TIMEOUT_SECONDS = 300
            result = await service.close_expired_batches()

            assert len(result) == 0

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_open_batch(self, mock_session):
        """Si no hay batch open, retorna lista vacía."""
        from app.services.merkle_service import MerkleService

        service = MerkleService(mock_session)
        service.batch_repo.get_open_batch = AsyncMock(return_value=None)

        result = await service.close_expired_batches()

        assert result == []


# ============================================================
# Tests de BatchScheduler
# ============================================================

class TestBatchScheduler:

    def test_start_and_stop(self):
        """El scheduler se inicia y detiene correctamente."""
        from app.services.batch_scheduler import (
            start_scheduler, stop_scheduler, get_scheduler,
        )

        scheduler = start_scheduler()
        assert scheduler is not None
        assert scheduler.running is True
        assert get_scheduler() is scheduler

        stop_scheduler()
        assert get_scheduler() is None

    def test_start_idempotent(self):
        """Llamar start_scheduler dos veces no crea dos instancias."""
        from app.services.batch_scheduler import (
            start_scheduler, stop_scheduler, get_scheduler,
        )

        s1 = start_scheduler()
        s2 = start_scheduler()
        assert s1 is s2

        stop_scheduler()

    def test_stop_when_not_running(self):
        """Detener un scheduler no iniciado no lanza errores."""
        from app.services.batch_scheduler import stop_scheduler

        # No debería lanzar excepción
        stop_scheduler()
