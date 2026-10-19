"""
Tests de integración para los endpoints de Auditoría.

Cubre:
- GET /api/v1/audit/integrity-check
- GET /api/v1/audit/report
- GET /api/v1/anchors
"""

import uuid
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    create_async_engine,
    async_sessionmaker,
)
from sqlalchemy import delete

from app.config import settings
from app.core.hashing import hash_log_entry
from app.core.merkle_tree import MerkleTree
from app.db.session import get_async_session
from app.main import app
from app.models.anchor_record import AnchorRecord
from app.models.log_entry import LogEntry
from app.models.merkle_batch import MerkleBatch
from app.models.merkle_node import MerkleNode


# ============================================================
# Helpers — seed y cleanup usando su propio engine (cerrado antes del test)
# ============================================================

async def _seed_audit_data() -> dict:
    """Crea datos de prueba en la BD y retorna metadata. Cierra el engine al salir."""
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    factory = async_sessionmaker(
        bind=engine, class_=AsyncSession, expire_on_commit=False,
    )

    batch_id = uuid.uuid4()
    batch_number = 8000 + (uuid.uuid4().int % 1000)
    anchor_id = uuid.uuid4()

    async with factory() as session:
        batch = MerkleBatch(
            id=batch_id, batch_number=batch_number,
            status="open", leaf_count=0,
        )
        session.add(batch)
        await session.flush()

        log_data_list = [
            {"source_app": "audit_test", "event_type": "a", "severity": "info",
             "payload": {"d": str(uuid.uuid4())}},
            {"source_app": "audit_test", "event_type": "b", "severity": "warning",
             "payload": {"d": str(uuid.uuid4())}},
            {"source_app": "audit_test", "event_type": "c", "severity": "info",
             "payload": {"d": str(uuid.uuid4())}},
            {"source_app": "audit_test", "event_type": "d", "severity": "error",
             "payload": {"d": str(uuid.uuid4())}},
        ]

        leaf_hashes = []
        for i, data in enumerate(log_data_list):
            ch = hash_log_entry(data)
            leaf_hashes.append(ch)
            session.add(LogEntry(
                id=uuid.uuid4(), source_app=data["source_app"],
                event_type=data["event_type"], severity=data["severity"],
                payload=data["payload"], content_hash=ch,
                batch_id=batch_id, leaf_index=i,
            ))
        await session.flush()

        tree = MerkleTree(leaf_hashes)
        for lv, hashes in enumerate(tree.levels):
            for pos, hv in enumerate(hashes):
                session.add(MerkleNode(
                    id=uuid.uuid4(), batch_id=batch_id,
                    level=lv, position=pos, hash_value=hv,
                ))

        batch.status = "anchored"
        batch.merkle_root = tree.root
        batch.leaf_count = 4
        batch.closed_at = datetime.now(timezone.utc)

        tx_hash = f"0x{uuid.uuid4().hex}"
        session.add(AnchorRecord(
            id=anchor_id, batch_id=batch_id, merkle_root=tree.root,
            anchor_type="blockchain", tx_hash=tx_hash,
            block_number=42, network="ganache",
            anchored_at=datetime.now(timezone.utc),
        ))
        await session.commit()

    await engine.dispose()

    return {
        "batch_id": batch_id,
        "batch_number": batch_number,
        "merkle_root": tree.root,
        "anchor_id": anchor_id,
        "anchor_tx": tx_hash,
    }


async def _cleanup_audit_data(batch_id: uuid.UUID):
    """Borra los datos de prueba."""
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    factory = async_sessionmaker(
        bind=engine, class_=AsyncSession, expire_on_commit=False,
    )
    async with factory() as session:
        await session.execute(delete(AnchorRecord).where(AnchorRecord.batch_id == batch_id))
        await session.execute(delete(MerkleNode).where(MerkleNode.batch_id == batch_id))
        await session.execute(delete(LogEntry).where(LogEntry.batch_id == batch_id))
        await session.execute(delete(MerkleBatch).where(MerkleBatch.id == batch_id))
        await session.commit()
    await engine.dispose()


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
async def seeded(client):
    """
    Seed datos ANTES del test y cleanup DESPUÉS.
    El engine del seed se cierra antes de que el test comience,
    evitando conflictos de event loop con el client.
    """
    data = await _seed_audit_data()
    yield data
    await _cleanup_audit_data(data["batch_id"])


# ============================================================
# Tests GET /api/v1/audit/integrity-check
# ============================================================

class TestIntegrityCheck:

    async def test_integrity_check_returns_200(self, client: AsyncClient):
        """Verificación masiva retorna 200 con estructura correcta."""
        resp = await client.get("/api/v1/audit/integrity-check")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_batches" in data
        assert "valid_batches" in data
        assert "invalid_batches" in data
        assert "skipped_batches" in data
        assert "overall_integrity" in data
        assert "checked_at" in data
        assert "details" in data

    async def test_integrity_valid_batch(self, client: AsyncClient, seeded):
        """Batch con integridad válida aparece como valid."""
        resp = await client.get("/api/v1/audit/integrity-check")
        data = resp.json()

        assert data["valid_batches"] >= 1
        assert data["invalid_batches"] == 0
        assert data["overall_integrity"] is True

        our = next(
            (d for d in data["details"] if d["batch_id"] == str(seeded["batch_id"])),
            None,
        )
        assert our is not None
        assert our["root_matches"] is True
        assert our["merkle_root"] == seeded["merkle_root"]

    async def test_integrity_detail_fields(self, client: AsyncClient, seeded):
        """Cada detalle tiene los campos requeridos."""
        resp = await client.get("/api/v1/audit/integrity-check")
        for d in resp.json()["details"]:
            assert "batch_id" in d
            assert "batch_number" in d
            assert "status" in d
            assert "leaf_count" in d


# ============================================================
# Tests GET /api/v1/audit/report
# ============================================================

class TestAuditReport:

    async def test_report_returns_200(self, client: AsyncClient):
        """Reporte retorna 200 con estructura correcta."""
        resp = await client.get("/api/v1/audit/report")
        assert resp.status_code == 200
        data = resp.json()
        assert "report_generated_at" in data
        assert "system_summary" in data
        assert "integrity_status" in data
        assert "batches" in data

    async def test_report_system_summary(self, client: AsyncClient, seeded):
        """Resumen tiene conteos correctos."""
        resp = await client.get("/api/v1/audit/report")
        s = resp.json()["system_summary"]
        assert s["total_logs"] >= 4
        assert s["total_batches"] >= 1
        assert s["total_anchors"] >= 1
        assert "open_batches" in s
        assert "unassigned_logs" in s

    async def test_report_integrity_status(self, client: AsyncClient, seeded):
        """Estado de integridad indica overall_integrity=True."""
        resp = await client.get("/api/v1/audit/report")
        i = resp.json()["integrity_status"]
        assert i["overall_integrity"] is True
        assert i["valid_batches"] >= 1
        assert i["invalid_batches"] == 0

    async def test_report_batch_detail(self, client: AsyncClient, seeded):
        """Reporte incluye batch con info de anclaje."""
        resp = await client.get("/api/v1/audit/report")
        our = next(
            (b for b in resp.json()["batches"]
             if b["batch_number"] == seeded["batch_number"]),
            None,
        )
        assert our is not None
        assert our["status"] == "anchored"
        assert our["leaf_count"] == 4
        assert our["merkle_root"] == seeded["merkle_root"]
        assert our["is_anchored"] is True
        assert our["anchor_tx"] == seeded["anchor_tx"]
        assert our["anchor_network"] == "ganache"


# ============================================================
# Tests GET /api/v1/anchors
# ============================================================

class TestListAnchors:

    async def test_list_anchors_returns_200(self, client: AsyncClient):
        """Listar anclajes retorna 200."""
        resp = await client.get("/api/v1/anchors")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data

    async def test_list_anchors_includes_seeded(self, client: AsyncClient, seeded):
        """El anclaje seed aparece en el listado."""
        resp = await client.get("/api/v1/anchors")
        data = resp.json()
        assert data["total"] >= 1
        ids = [i["id"] for i in data["items"]]
        assert str(seeded["anchor_id"]) in ids

    async def test_anchor_has_batch_number(self, client: AsyncClient, seeded):
        """Anclaje incluye batch_number."""
        resp = await client.get("/api/v1/anchors")
        our = next(
            (a for a in resp.json()["items"]
             if a["id"] == str(seeded["anchor_id"])),
            None,
        )
        assert our is not None
        assert our["batch_number"] == seeded["batch_number"]
        assert our["merkle_root"] == seeded["merkle_root"]
        assert our["anchor_type"] == "blockchain"
        assert our["network"] == "ganache"
        assert our["block_number"] == 42

    async def test_filter_by_network(self, client: AsyncClient, seeded):
        """Filtrar por network."""
        resp = await client.get("/api/v1/anchors", params={"network": "ganache"})
        for item in resp.json()["items"]:
            assert item["network"] == "ganache"

    async def test_filter_nonexistent_network(self, client: AsyncClient):
        """Red inexistente retorna vacío."""
        resp = await client.get("/api/v1/anchors", params={"network": "no_exist_net"})
        data = resp.json()
        assert data["total"] == 0
        assert data["items"] == []

    async def test_pagination_params(self, client: AsyncClient):
        """Paginación funciona."""
        resp = await client.get("/api/v1/anchors", params={"limit": 5, "offset": 0})
        data = resp.json()
        assert data["limit"] == 5
        assert data["offset"] == 0
