"""
Fixtures compartidas para tests de integración.

Crea sesiones async con engine por test para evitar event loop issues.

Requiere: PostgreSQL corriendo (docker compose up -d)
"""

import uuid
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.config import settings
from app.models import LogEntry, MerkleBatch, MerkleNode, AnchorRecord


@pytest_asyncio.fixture(scope="function")
async def db_session():
    """
    Sesión async para cada test.

    Crea engine propio por test para evitar issues de event loop.
    Usa transacción con rollback para aislamiento.
    """
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async with engine.connect() as conn:
        trans = await conn.begin()
        session = AsyncSession(bind=conn, expire_on_commit=False)

        yield session

        await session.close()
        await trans.rollback()
    await engine.dispose()


# ============================================================
# Factory fixtures para crear entidades de prueba
# ============================================================

@pytest.fixture
def make_batch():
    """Factory para crear MerkleBatch de prueba."""
    _counter = [0]

    def _make(
        batch_number: int = None,
        status: str = "open",
        merkle_root: str = None,
        leaf_count: int = 0,
        prev_batch_root: str = None,
    ) -> MerkleBatch:
        _counter[0] += 1
        return MerkleBatch(
            id=uuid.uuid4(),
            batch_number=batch_number or _counter[0],
            status=status,
            merkle_root=merkle_root,
            leaf_count=leaf_count,
            prev_batch_root=prev_batch_root,
        )
    return _make


@pytest.fixture
def make_log_entry():
    """Factory para crear LogEntry de prueba."""
    _counter = [0]

    def _make(
        source_app: str = "test_app",
        event_type: str = "test_event",
        severity: str = "info",
        payload: dict = None,
        content_hash: str = None,
        batch_id=None,
        leaf_index: int = None,
    ) -> LogEntry:
        _counter[0] += 1
        return LogEntry(
            id=uuid.uuid4(),
            source_app=source_app,
            event_type=event_type,
            severity=severity,
            payload=payload or {"test": f"data_{_counter[0]}"},
            content_hash=content_hash or f"{_counter[0]:064x}",
            batch_id=batch_id,
            leaf_index=leaf_index,
            received_at=datetime.now(timezone.utc),
        )
    return _make


@pytest.fixture
def make_merkle_node():
    """Factory para crear MerkleNode de prueba."""
    def _make(
        batch_id=None,
        level: int = 0,
        position: int = 0,
        hash_value: str = None,
    ) -> MerkleNode:
        return MerkleNode(
            id=uuid.uuid4(),
            batch_id=batch_id,
            level=level,
            position=position,
            hash_value=hash_value or f"{uuid.uuid4().hex}{uuid.uuid4().hex}",
        )
    return _make


@pytest.fixture
def make_anchor_record():
    """Factory para crear AnchorRecord de prueba."""
    def _make(
        batch_id=None,
        merkle_root: str = None,
        anchor_type: str = "blockchain",
        tx_hash: str = None,
        network: str = "ganache",
    ) -> AnchorRecord:
        return AnchorRecord(
            id=uuid.uuid4(),
            batch_id=batch_id,
            merkle_root=merkle_root or f"{uuid.uuid4().hex}{uuid.uuid4().hex}",
            anchor_type=anchor_type,
            tx_hash=tx_hash or f"0x{uuid.uuid4().hex}",
            network=network,
        )
    return _make
