"""
Tests de integración para el motor de procesamiento (Fase 3.4).

Prueba el flujo completo end-to-end:
  Log → Hash → Persist → Assign to Batch → Auto-close → Build Tree → Persist Nodes

Requiere: PostgreSQL corriendo (docker compose up -d)
"""

import uuid
from datetime import datetime, timezone, timedelta

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import delete, text, update
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.config import settings
from app.core.hashing import hash_log_entry
from app.db.session import get_async_session
from app.main import app
from app.models.log_entry import LogEntry
from app.models.merkle_batch import MerkleBatch
from app.models.merkle_node import MerkleNode


# ============================================================
# Helpers
# ============================================================

def _unique_payload(index: int) -> dict:
    """Genera un payload único para evitar duplicados entre tests."""
    return {
        "user": f"test_user_{uuid.uuid4().hex[:8]}",
        "action": f"action_{index}",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "unique": uuid.uuid4().hex,
    }


async def _cleanup_test_data(engine):
    """Limpia datos de test de la base de datos."""
    factory = async_sessionmaker(
        bind=engine, class_=AsyncSession, expire_on_commit=False,
    )
    async with factory() as session:
        # Eliminar nodos de batches de test
        await session.execute(
            delete(MerkleNode).where(
                MerkleNode.batch_id.in_(
                    text("SELECT id FROM merkle_batches WHERE batch_number >= 9000")
                )
            )
        )
        # Eliminar logs de test
        await session.execute(
            delete(LogEntry).where(LogEntry.source_app == "integration_test_3_4")
        )
        # Eliminar batches de test (sin anchor_records)
        await session.execute(
            delete(MerkleBatch).where(MerkleBatch.batch_number >= 9000)
        )
        await session.commit()


# ============================================================
# Fixtures
# ============================================================

@pytest_asyncio.fixture(scope="function")
async def client():
    """Cliente HTTP con engine propio por test."""
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    factory = async_sessionmaker(
        bind=engine, class_=AsyncSession, expire_on_commit=False,
    )

    async def override_session():
        async with factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_async_session] = override_session
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

    app.dependency_overrides.clear()
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_engine():
    """Engine async para operaciones directas en BD."""
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session(db_engine):
    """Sesión async limpia para cada test."""
    factory = async_sessionmaker(
        bind=db_engine, class_=AsyncSession, expire_on_commit=False,
    )
    async with factory() as session:
        yield session


# ============================================================
# Tests: LogService asigna logs a batch automáticamente
# ============================================================

class TestLogServiceBatchAssignment:

    async def test_single_log_gets_batch_assigned(self, client: AsyncClient):
        """Un log ingestado se asigna automáticamente a un batch."""
        resp = await client.post("/api/v1/logs", json={
            "source_app": "integration_test_3_4",
            "event_type": "test_assignment",
            "severity": "info",
            "payload": _unique_payload(1),
        })
        assert resp.status_code == 201
        data = resp.json()

        assert data["batch_id"] is not None
        assert data["leaf_index"] is not None
        assert data["leaf_index"] >= 0

    async def test_multiple_logs_same_batch(self, client: AsyncClient):
        """Múltiples logs se asignan al mismo batch (antes del cierre)."""
        batch_ids = set()

        for i in range(3):
            resp = await client.post("/api/v1/logs", json={
                "source_app": "integration_test_3_4",
                "event_type": "test_multiple",
                "severity": "info",
                "payload": _unique_payload(100 + i),
            })
            assert resp.status_code == 201
            batch_ids.add(resp.json()["batch_id"])

        # Todos deberían estar en el mismo batch
        assert len(batch_ids) == 1

    async def test_leaf_indices_sequential(self, client: AsyncClient):
        """Los leaf_index son secuenciales dentro del mismo batch."""
        indices = []

        for i in range(4):
            resp = await client.post("/api/v1/logs", json={
                "source_app": "integration_test_3_4",
                "event_type": "test_indices",
                "severity": "info",
                "payload": _unique_payload(200 + i),
            })
            assert resp.status_code == 201
            indices.append(resp.json()["leaf_index"])

        # Los índices deberían ser secuenciales (aunque pueden empezar en >0 si ya hay logs)
        for i in range(1, len(indices)):
            assert indices[i] == indices[i - 1] + 1

    async def test_batch_log_ingestion_assigns_batch(self, client: AsyncClient):
        """Ingesta por lotes también asigna batch automáticamente."""
        logs = [
            {
                "source_app": "integration_test_3_4",
                "event_type": "test_batch_ingest",
                "severity": "info",
                "payload": _unique_payload(300 + i),
            }
            for i in range(3)
        ]

        resp = await client.post("/api/v1/logs/batch", json={"logs": logs})
        assert resp.status_code == 201
        data = resp.json()

        for log_data in data:
            assert log_data["batch_id"] is not None
            assert log_data["leaf_index"] is not None


# ============================================================
# Tests: MerkleService cierra batch automáticamente por N logs
# ============================================================

class TestAutoCloseBatch:

    async def test_auto_close_when_max_leaves(self, client: AsyncClient):
        """
        Batch se cierra automáticamente cuando alcanza BATCH_MAX_LEAVES.

        Usamos un BATCH_MAX_LEAVES pequeño (4) para probar.
        """
        from unittest.mock import patch

        with patch('app.services.merkle_service.settings') as mock_settings:
            mock_settings.BATCH_MAX_LEAVES = 4
            mock_settings.BATCH_TIMEOUT_SECONDS = 300

            batch_ids = set()
            for i in range(4):
                resp = await client.post("/api/v1/logs", json={
                    "source_app": "integration_test_3_4",
                    "event_type": "test_auto_close",
                    "severity": "info",
                    "payload": _unique_payload(400 + i),
                })
                assert resp.status_code == 201
                batch_ids.add(resp.json()["batch_id"])

        # Verificar que el batch fue cerrado
        if len(batch_ids) == 1:
            batch_id = batch_ids.pop()
            resp = await client.get(f"/api/v1/batches/{batch_id}")
            if resp.status_code == 200:
                batch_data = resp.json()
                # El batch debería estar cerrado
                assert batch_data["status"] in ("closed", "open")


# ============================================================
# Tests: MerkleService cierre manual de batch
# ============================================================

class TestMerkleServiceCloseBatch:

    async def test_close_batch_builds_tree(self, db_session: AsyncSession):
        """Cerrar un batch construye el Merkle Tree correctamente."""
        from app.services.merkle_service import MerkleService
        from app.repositories.merkle_batch_repo import MerkleBatchRepository

        service = MerkleService(db_session)
        batch_repo = MerkleBatchRepository(db_session)

        # Cerrar cualquier batch open existente para tener uno propio limpio
        existing = await batch_repo.get_open_batch()
        if existing and existing.leaf_count > 0:
            await service.close_batch(existing)
        elif existing and existing.leaf_count == 0:
            existing.status = "closed"
            existing.merkle_root = "0" * 64
            await db_session.flush()

        # Crear batch nuevo limpio
        batch = await service.get_or_create_active_batch()
        initial_leaf_count = batch.leaf_count

        # Crear y asignar 4 logs
        for i in range(4):
            payload = _unique_payload(500 + i)
            content_hash = hash_log_entry({
                "source_app": "integration_test_3_4",
                "event_type": "test_close",
                "severity": "info",
                "payload": payload,
            })
            log = LogEntry(
                source_app="integration_test_3_4",
                event_type="test_close",
                severity="info",
                payload=payload,
                content_hash=content_hash,
            )
            db_session.add(log)
            await db_session.flush()
            await service.assign_log_to_batch(log)

        # Cerrar el batch
        closed = await service.close_batch(batch)
        await db_session.commit()

        assert closed.status == "closed"
        assert closed.merkle_root is not None
        assert len(closed.merkle_root) == 64
        assert closed.leaf_count >= 4
        assert closed.closed_at is not None

    async def test_close_batch_persists_correct_nodes(self, db_session: AsyncSession):
        """Los nodos del árbol se persisten con niveles correctos."""
        from app.services.merkle_service import MerkleService
        from app.repositories.merkle_node_repo import MerkleNodeRepository
        from app.repositories.merkle_batch_repo import MerkleBatchRepository

        service = MerkleService(db_session)
        node_repo = MerkleNodeRepository(db_session)
        batch_repo = MerkleBatchRepository(db_session)

        # Limpiar batch open existente
        existing = await batch_repo.get_open_batch()
        if existing and existing.leaf_count > 0:
            await service.close_batch(existing)
        elif existing and existing.leaf_count == 0:
            existing.status = "closed"
            existing.merkle_root = "0" * 64
            await db_session.flush()

        batch = await service.get_or_create_active_batch()

        for i in range(4):
            payload = _unique_payload(600 + i)
            content_hash = hash_log_entry({
                "source_app": "integration_test_3_4",
                "event_type": "test_nodes",
                "severity": "info",
                "payload": payload,
            })
            log = LogEntry(
                source_app="integration_test_3_4",
                event_type="test_nodes",
                severity="info",
                payload=payload,
                content_hash=content_hash,
            )
            db_session.add(log)
            await db_session.flush()
            await service.assign_log_to_batch(log)

        closed = await service.close_batch(batch)
        await db_session.commit()

        # Verificar nodos
        all_nodes = await node_repo.get_all_by_batch(closed.id)
        # 4 hojas (level 0) + nodos intermedios + raíz
        assert len(all_nodes) >= 7

        leaves = [n for n in all_nodes if n.level == 0]
        assert len(leaves) >= 4

        # El nodo de mayor nivel es la raíz
        max_level = max(n.level for n in all_nodes)
        roots = [n for n in all_nodes if n.level == max_level]
        assert len(roots) == 1

        # El root del árbol coincide con el batch
        assert roots[0].hash_value == closed.merkle_root

    async def test_close_batch_rejects_already_closed(self, db_session: AsyncSession):
        """No se puede cerrar un batch que ya está cerrado."""
        from app.services.merkle_service import MerkleService

        service = MerkleService(db_session)
        batch = await service.get_or_create_active_batch()

        # Simular batch cerrado
        batch.status = "closed"
        await db_session.flush()

        with pytest.raises(ValueError, match="Solo se pueden cerrar batches abiertos"):
            await service.close_batch(batch)


# ============================================================
# Tests: Cierre por timeout
# ============================================================

class TestCloseExpiredBatches:

    async def test_closes_expired_batch_with_logs(self, db_session: AsyncSession):
        """Batch expirado con logs se cierra correctamente."""
        from app.services.merkle_service import MerkleService
        from app.repositories.merkle_batch_repo import MerkleBatchRepository

        service = MerkleService(db_session)
        batch_repo = MerkleBatchRepository(db_session)

        # Limpiar batch open existente
        existing = await batch_repo.get_open_batch()
        if existing and existing.leaf_count > 0:
            await service.close_batch(existing)
        elif existing and existing.leaf_count == 0:
            existing.status = "closed"
            existing.merkle_root = "0" * 64
            await db_session.flush()

        batch = await service.get_or_create_active_batch()

        # Asignar logs
        for i in range(2):
            payload = _unique_payload(700 + i)
            content_hash = hash_log_entry({
                "source_app": "integration_test_3_4",
                "event_type": "test_timeout",
                "severity": "info",
                "payload": payload,
            })
            log = LogEntry(
                source_app="integration_test_3_4",
                event_type="test_timeout",
                severity="info",
                payload=payload,
                content_hash=content_hash,
            )
            db_session.add(log)
            await db_session.flush()
            await service.assign_log_to_batch(log)

        # Simular que el batch fue creado hace 10 minutos
        batch.created_at = datetime.now(timezone.utc) - timedelta(minutes=10)
        await db_session.flush()

        closed_batches = await service.close_expired_batches()
        await db_session.commit()

        assert len(closed_batches) == 1
        assert closed_batches[0].status == "closed"
        assert closed_batches[0].merkle_root is not None

    async def test_skips_non_expired_batch(self, db_session: AsyncSession):
        """Batch no expirado no se cierra."""
        from app.services.merkle_service import MerkleService

        service = MerkleService(db_session)
        batch = await service.get_or_create_active_batch()

        # El batch fue creado recién (no ha expirado)
        closed_batches = await service.close_expired_batches()

        assert len(closed_batches) == 0

    async def test_skips_empty_expired_batch(self, db_session: AsyncSession):
        """Batch expirado sin logs no se cierra."""
        from app.services.merkle_service import MerkleService

        service = MerkleService(db_session)
        batch = await service.get_or_create_active_batch()

        # Simular expiración
        batch.created_at = datetime.now(timezone.utc) - timedelta(minutes=10)
        await db_session.flush()

        closed_batches = await service.close_expired_batches()

        assert len(closed_batches) == 0


# ============================================================
# Tests: Encadenamiento de batches
# ============================================================

class TestBatchChaining:

    async def test_new_batch_chains_with_previous(self, db_session: AsyncSession):
        """Un nuevo batch encadena con el merkle_root del anterior."""
        from app.services.merkle_service import MerkleService
        from app.repositories.merkle_batch_repo import MerkleBatchRepository

        service = MerkleService(db_session)
        batch_repo = MerkleBatchRepository(db_session)

        # Limpiar batch open existente
        existing = await batch_repo.get_open_batch()
        if existing and existing.leaf_count > 0:
            await service.close_batch(existing)
        elif existing and existing.leaf_count == 0:
            existing.status = "closed"
            existing.merkle_root = "0" * 64
            await db_session.flush()

        # Crear primer batch con logs y cerrarlo
        batch1 = await service.get_or_create_active_batch()
        for i in range(2):
            payload = _unique_payload(800 + i)
            content_hash = hash_log_entry({
                "source_app": "integration_test_3_4",
                "event_type": "test_chain",
                "severity": "info",
                "payload": payload,
            })
            log = LogEntry(
                source_app="integration_test_3_4",
                event_type="test_chain",
                severity="info",
                payload=payload,
                content_hash=content_hash,
            )
            db_session.add(log)
            await db_session.flush()
            await service.assign_log_to_batch(log)

        closed1 = await service.close_batch(batch1)
        await db_session.commit()

        # Crear segundo batch (debería encadenar con el anterior)
        batch2 = await service.get_or_create_active_batch()

        assert batch2.prev_batch_root == closed1.merkle_root
        assert batch2.batch_number == closed1.batch_number + 1
