"""
Tests de integración para los endpoints de Verificación y Batches.

Estos tests necesitan un escenario completo:
1. Crear logs (ingesta)
2. Cerrar un batch (asignar logs + construir árbol + persistir nodos)
3. Probar proof generation y verification

Para simular el flujo completo, creamos datos directamente via repositorios.
"""

import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    create_async_engine,
    async_sessionmaker,
)

from app.config import settings
from app.core.hashing import hash_log_entry
from app.core.merkle_tree import MerkleTree
from app.core.proof import generate_proof, verify_proof
from app.db.session import get_async_session
from app.main import app
from app.models.log_entry import LogEntry
from app.models.merkle_batch import MerkleBatch
from app.models.merkle_node import MerkleNode


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
async def seeded_batch():
    """
    Crea un batch cerrado con 4 logs y su Merkle Tree persistido.

    Retorna dict con todos los datos para las pruebas.
    """
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    factory = async_sessionmaker(
        bind=engine, class_=AsyncSession, expire_on_commit=False,
    )

    async with factory() as session:
        # 1. Crear batch
        batch_id = uuid.uuid4()
        batch_number = 9000 + (uuid.uuid4().int % 1000)  # Único
        batch = MerkleBatch(
            id=batch_id,
            batch_number=batch_number,
            status="open",
            leaf_count=0,
        )
        session.add(batch)
        await session.flush()

        # 2. Crear 4 log entries con hashes
        log_data_list = [
            {"source_app": "test", "event_type": "login", "severity": "info",
             "payload": {"user": "alice", "unique": str(uuid.uuid4())}},
            {"source_app": "test", "event_type": "logout", "severity": "info",
             "payload": {"user": "bob", "unique": str(uuid.uuid4())}},
            {"source_app": "test", "event_type": "file_access", "severity": "warning",
             "payload": {"file": "/etc/passwd", "unique": str(uuid.uuid4())}},
            {"source_app": "test", "event_type": "db_query", "severity": "info",
             "payload": {"query": "SELECT *", "unique": str(uuid.uuid4())}},
        ]

        logs = []
        leaf_hashes = []
        for i, data in enumerate(log_data_list):
            content_hash = hash_log_entry(data)
            leaf_hashes.append(content_hash)
            log = LogEntry(
                id=uuid.uuid4(),
                source_app=data["source_app"],
                event_type=data["event_type"],
                severity=data["severity"],
                payload=data["payload"],
                content_hash=content_hash,
                batch_id=batch_id,
                leaf_index=i,
            )
            session.add(log)
            logs.append(log)

        await session.flush()

        # 3. Construir Merkle Tree
        tree = MerkleTree(leaf_hashes)
        merkle_root = tree.root

        # 4. Persistir nodos del árbol
        for level_idx, level_hashes in enumerate(tree.levels):
            for pos_idx, hash_value in enumerate(level_hashes):
                node = MerkleNode(
                    id=uuid.uuid4(),
                    batch_id=batch_id,
                    level=level_idx,
                    position=pos_idx,
                    hash_value=hash_value,
                )
                session.add(node)

        # 5. Cerrar el batch
        from datetime import datetime, timezone
        batch.status = "closed"
        batch.merkle_root = merkle_root
        batch.leaf_count = len(logs)
        batch.closed_at = datetime.now(timezone.utc)

        await session.commit()

    result = {
        "batch_id": batch_id,
        "batch_number": batch_number,
        "merkle_root": merkle_root,
        "logs": logs,
        "leaf_hashes": leaf_hashes,
        "tree": tree,
    }

    yield result

    # Cleanup — borrar los datos de test
    async with factory() as session:
        from sqlalchemy import delete
        await session.execute(
            delete(MerkleNode).where(MerkleNode.batch_id == batch_id)
        )
        await session.execute(
            delete(LogEntry).where(LogEntry.batch_id == batch_id)
        )
        await session.execute(
            delete(MerkleBatch).where(MerkleBatch.id == batch_id)
        )
        await session.commit()

    await engine.dispose()


# ============================================================
# Tests POST /api/v1/verify (stateless, no seeded batch needed)
# ============================================================

class TestVerifyEndpoint:
    """Tests del endpoint POST /api/v1/verify."""

    async def test_verify_valid_proof(self, client: AsyncClient):
        """Verificar una prueba válida retorna is_valid=True."""
        # Crear un árbol simple y generar la prueba
        leaves = [hash_log_entry({"test": f"leaf_{i}"}) for i in range(4)]
        tree = MerkleTree(leaves)
        proof = generate_proof(tree, 0)

        resp = await client.post("/api/v1/verify", json={
            "content_hash": leaves[0],
            "merkle_root": tree.root,
            "proof": [{"hash": s.hash, "position": s.position} for s in proof],
        })

        assert resp.status_code == 200
        data = resp.json()
        assert data["is_valid"] is True
        assert "válida" in data["message"]

    async def test_verify_invalid_proof(self, client: AsyncClient):
        """Prueba con root incorrecto retorna is_valid=False."""
        leaves = [hash_log_entry({"test": f"leaf_{i}"}) for i in range(4)]
        tree = MerkleTree(leaves)
        proof = generate_proof(tree, 0)

        fake_root = "a" * 64
        resp = await client.post("/api/v1/verify", json={
            "content_hash": leaves[0],
            "merkle_root": fake_root,
            "proof": [{"hash": s.hash, "position": s.position} for s in proof],
        })

        assert resp.status_code == 200
        data = resp.json()
        assert data["is_valid"] is False
        assert "inválida" in data["message"]

    async def test_verify_tampered_hash(self, client: AsyncClient):
        """Hash del contenido alterado falla la verificación."""
        leaves = [hash_log_entry({"test": f"leaf_{i}"}) for i in range(4)]
        tree = MerkleTree(leaves)
        proof = generate_proof(tree, 1)

        tampered_hash = "b" * 64
        resp = await client.post("/api/v1/verify", json={
            "content_hash": tampered_hash,
            "merkle_root": tree.root,
            "proof": [{"hash": s.hash, "position": s.position} for s in proof],
        })

        assert resp.status_code == 200
        assert resp.json()["is_valid"] is False

    async def test_verify_all_leaves(self, client: AsyncClient):
        """Todas las hojas de un árbol de 8 nodos verifican correctamente."""
        leaves = [hash_log_entry({"leaf": f"data_{i}"}) for i in range(8)]
        tree = MerkleTree(leaves)

        for i, leaf in enumerate(leaves):
            proof = generate_proof(tree, i)
            resp = await client.post("/api/v1/verify", json={
                "content_hash": leaf,
                "merkle_root": tree.root,
                "proof": [s.to_dict() for s in proof],
            })
            assert resp.status_code == 200
            assert resp.json()["is_valid"] is True, f"Leaf {i} failed"

    async def test_verify_empty_proof_single_leaf(self, client: AsyncClient):
        """Árbol de una hoja: prueba vacía, hoja = root."""
        leaf = hash_log_entry({"single": "leaf"})
        tree = MerkleTree([leaf])

        resp = await client.post("/api/v1/verify", json={
            "content_hash": leaf,
            "merkle_root": tree.root,
            "proof": [],
        })

        assert resp.status_code == 200
        assert resp.json()["is_valid"] is True

    async def test_verify_invalid_hash_length_422(self, client: AsyncClient):
        """Hash con longitud incorrecta retorna 422."""
        resp = await client.post("/api/v1/verify", json={
            "content_hash": "short",
            "merkle_root": "a" * 64,
            "proof": [],
        })
        assert resp.status_code == 422


# ============================================================
# Tests GET /api/v1/logs/{id}/proof
# ============================================================

class TestGetLogProof:
    """Tests del endpoint GET /api/v1/logs/{id}/proof."""

    async def test_get_proof_success(self, client: AsyncClient, seeded_batch):
        """Obtener la prueba Merkle de un log del batch cerrado."""
        log = seeded_batch["logs"][0]
        resp = await client.get(f"/api/v1/logs/{log.id}/proof")

        assert resp.status_code == 200
        data = resp.json()
        assert data["log_id"] == str(log.id)
        assert data["content_hash"] == log.content_hash
        assert data["leaf_index"] == 0
        assert data["batch_id"] == str(seeded_batch["batch_id"])
        assert data["merkle_root"] == seeded_batch["merkle_root"]
        assert len(data["proof"]) > 0  # 4 hojas → 2 pasos

    async def test_proof_is_verifiable(self, client: AsyncClient, seeded_batch):
        """La prueba obtenida del endpoint verifica correctamente."""
        log = seeded_batch["logs"][1]

        # Obtener prueba
        proof_resp = await client.get(f"/api/v1/logs/{log.id}/proof")
        assert proof_resp.status_code == 200
        proof_data = proof_resp.json()

        # Verificar la prueba via el endpoint de verificación
        verify_resp = await client.post("/api/v1/verify", json={
            "content_hash": proof_data["content_hash"],
            "merkle_root": proof_data["merkle_root"],
            "proof": proof_data["proof"],
        })

        assert verify_resp.status_code == 200
        assert verify_resp.json()["is_valid"] is True

    async def test_all_logs_in_batch_verify(self, client: AsyncClient, seeded_batch):
        """Todas las hojas del batch generan proofs válidas."""
        for log in seeded_batch["logs"]:
            proof_resp = await client.get(f"/api/v1/logs/{log.id}/proof")
            assert proof_resp.status_code == 200
            proof_data = proof_resp.json()

            verify_resp = await client.post("/api/v1/verify", json={
                "content_hash": proof_data["content_hash"],
                "merkle_root": proof_data["merkle_root"],
                "proof": proof_data["proof"],
            })
            assert verify_resp.json()["is_valid"] is True

    async def test_get_proof_log_not_found(self, client: AsyncClient):
        """Log inexistente retorna 404."""
        fake_id = str(uuid.uuid4())
        resp = await client.get(f"/api/v1/logs/{fake_id}/proof")
        assert resp.status_code == 404

    async def test_get_proof_log_without_batch(self, client: AsyncClient):
        """Log en batch abierto (sin cerrar) retorna 409."""
        # Crear un log — ahora se asigna automáticamente a un batch open
        log_resp = await client.post("/api/v1/logs", json={
            "source_app": "test",
            "event_type": "no_batch",
            "severity": "info",
            "payload": {"test": str(uuid.uuid4())},
        })
        log_id = log_resp.json()["id"]

        # El log tiene batch_id, pero el batch no está cerrado
        resp = await client.get(f"/api/v1/logs/{log_id}/proof")
        assert resp.status_code == 409
        assert resp.json()["detail"]["error"] == "batch_no_cerrado"


# ============================================================
# Tests GET /api/v1/batches
# ============================================================

class TestListBatches:
    """Tests del endpoint GET /api/v1/batches."""

    async def test_list_batches_returns_200(self, client: AsyncClient):
        """Listar batches retorna 200 con estructura correcta."""
        resp = await client.get("/api/v1/batches")

        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data

    async def test_list_batches_includes_seeded(
        self, client: AsyncClient, seeded_batch
    ):
        """El batch cerrado aparece en el listado."""
        resp = await client.get("/api/v1/batches")
        data = resp.json()

        batch_ids = [item["id"] for item in data["items"]]
        assert str(seeded_batch["batch_id"]) in batch_ids

    async def test_list_batches_filter_by_status(
        self, client: AsyncClient, seeded_batch
    ):
        """Filtrar por status=closed retorna el batch cerrado."""
        resp = await client.get("/api/v1/batches", params={"status": "closed"})
        data = resp.json()

        for item in data["items"]:
            assert item["status"] == "closed"


# ============================================================
# Tests GET /api/v1/batches/{id}
# ============================================================

class TestGetBatchDetail:
    """Tests del endpoint GET /api/v1/batches/{id}."""

    async def test_get_batch_detail(self, client: AsyncClient, seeded_batch):
        """Detalle del batch incluye root, logs, nodos y anchors."""
        bid = seeded_batch["batch_id"]
        resp = await client.get(f"/api/v1/batches/{bid}")

        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == str(bid)
        assert data["batch_number"] == seeded_batch["batch_number"]
        assert data["status"] == "closed"
        assert data["merkle_root"] == seeded_batch["merkle_root"]
        assert data["leaf_count"] == 4
        assert data["log_count"] == 4
        assert data["node_count"] > 0  # nodos del árbol
        assert isinstance(data["anchors"], list)

    async def test_get_batch_not_found(self, client: AsyncClient):
        """Batch inexistente retorna 404."""
        fake_id = str(uuid.uuid4())
        resp = await client.get(f"/api/v1/batches/{fake_id}")

        assert resp.status_code == 404
        assert resp.json()["detail"]["error"] == "batch_no_encontrado"
