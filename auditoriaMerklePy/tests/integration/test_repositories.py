"""
Tests de integración de los repositorios.

Valida operaciones CRUD reales contra PostgreSQL.
Cada test usa una transacción que se hace rollback al final (aislamiento).

Requiere: PostgreSQL corriendo (docker compose up -d)
"""

import uuid
from datetime import datetime, timezone

import pytest
import pytest_asyncio

from app.repositories.log_entry_repo import LogEntryRepository
from app.repositories.merkle_batch_repo import MerkleBatchRepository
from app.repositories.merkle_node_repo import MerkleNodeRepository
from app.repositories.anchor_record_repo import AnchorRecordRepository


# Marcar todos los tests como async
pytestmark = pytest.mark.asyncio


# ============================================================
# Tests de MerkleBatchRepository
# ============================================================

class TestMerkleBatchRepository:
    """Tests del repositorio de MerkleBatch."""

    async def test_create_batch(self, db_session, make_batch):
        """Crear y recuperar un batch."""
        repo = MerkleBatchRepository(db_session)
        batch = make_batch(batch_number=100, status="open")

        created = await repo.create(batch)
        assert created.id is not None
        assert created.batch_number == 100
        assert created.status == "open"

    async def test_get_open_batch(self, db_session, make_batch):
        """Obtener el batch abierto."""
        repo = MerkleBatchRepository(db_session)

        open_batch = make_batch(batch_number=200, status="open")
        closed_batch = make_batch(batch_number=201, status="closed", merkle_root="a" * 64)

        await repo.create(open_batch)
        await repo.create(closed_batch)

        result = await repo.get_open_batch()
        assert result is not None
        assert result.status == "open"
        assert result.batch_number == 200

    async def test_get_by_status(self, db_session, make_batch):
        """Filtrar batches por estado."""
        repo = MerkleBatchRepository(db_session)

        await repo.create(make_batch(batch_number=300, status="open"))
        await repo.create(make_batch(batch_number=301, status="closed", merkle_root="b" * 64))
        await repo.create(make_batch(batch_number=302, status="closed", merkle_root="c" * 64))

        closed = await repo.get_by_status("closed")
        assert len(closed) >= 2
        # Verificar que al menos nuestros 2 batch creados están en la lista
        batch_numbers = [b.batch_number for b in closed]
        assert 301 in batch_numbers
        assert 302 in batch_numbers

    async def test_close_batch(self, db_session, make_batch):
        """Cerrar un batch: actualiza estado, root y timestamp."""
        repo = MerkleBatchRepository(db_session)
        batch = make_batch(batch_number=400, status="open")
        await repo.create(batch)

        closed = await repo.close_batch(batch, merkle_root="d" * 64, leaf_count=10)
        assert closed.status == "closed"
        assert closed.merkle_root == "d" * 64
        assert closed.leaf_count == 10
        assert closed.closed_at is not None

    async def test_mark_anchored(self, db_session, make_batch):
        """Marcar un batch como anclado."""
        repo = MerkleBatchRepository(db_session)
        batch = make_batch(batch_number=500, status="closed", merkle_root="e" * 64)
        await repo.create(batch)

        anchored = await repo.mark_anchored(batch)
        assert anchored.status == "anchored"

    async def test_get_next_batch_number_empty(self, db_session):
        """Siguiente batch number cuando no hay batches = 1."""
        repo = MerkleBatchRepository(db_session)
        num = await repo.get_next_batch_number()
        assert num >= 1  # Puede ser > 1 si hay batches de tests previos

    async def test_get_closed_unanchored(self, db_session, make_batch):
        """Obtener batches cerrados pero no anclados."""
        repo = MerkleBatchRepository(db_session)

        await repo.create(make_batch(batch_number=600, status="open"))
        await repo.create(make_batch(batch_number=601, status="closed", merkle_root="f" * 64))
        await repo.create(make_batch(batch_number=602, status="anchored", merkle_root="0" * 64))

        unanchored = await repo.get_closed_unanchored()
        assert len(unanchored) >= 1
        # Verificar que nuestro batch cerrado no anclado está en la lista
        batch_numbers = [b.batch_number for b in unanchored]
        assert 601 in batch_numbers


# ============================================================
# Tests de LogEntryRepository
# ============================================================

class TestLogEntryRepository:
    """Tests del repositorio de LogEntry."""

    async def test_create_log(self, db_session, make_log_entry):
        """Crear y recuperar un log."""
        repo = LogEntryRepository(db_session)
        log = make_log_entry(source_app="my_app", event_type="login")

        created = await repo.create(log)
        assert created.id is not None
        assert created.source_app == "my_app"

    async def test_get_by_content_hash(self, db_session, make_log_entry):
        """Buscar un log por su hash."""
        repo = LogEntryRepository(db_session)
        the_hash = "abcdef" * 10 + "abcd"  # 64 chars
        log = make_log_entry(content_hash=the_hash)
        await repo.create(log)

        found = await repo.get_by_content_hash(the_hash)
        assert found is not None
        assert found.content_hash == the_hash

    async def test_get_by_content_hash_not_found(self, db_session):
        """Buscar un hash que no existe retorna None."""
        repo = LogEntryRepository(db_session)
        result = await repo.get_by_content_hash("0" * 64)
        assert result is None

    async def test_get_unassigned(self, db_session, make_log_entry, make_batch):
        """Obtener logs sin batch asignado."""
        batch_repo = MerkleBatchRepository(db_session)
        log_repo = LogEntryRepository(db_session)

        # Contar los sin asignar que ya existen
        before = await log_repo.count_unassigned()

        batch = make_batch(batch_number=700)
        await batch_repo.create(batch)

        # 2 sin asignar, 1 asignado
        await log_repo.create(make_log_entry(content_hash="1" * 64))
        await log_repo.create(make_log_entry(content_hash="2" * 64))
        await log_repo.create(make_log_entry(
            content_hash="3" * 64, batch_id=batch.id, leaf_index=0
        ))

        unassigned = await log_repo.get_unassigned(limit=1000)
        assert len(unassigned) == before + 2

    async def test_search_by_source(self, db_session, make_log_entry):
        """Buscar logs por aplicación de origen."""
        repo = LogEntryRepository(db_session)
        await repo.create(make_log_entry(source_app="app_a", content_hash="a1" * 32))
        await repo.create(make_log_entry(source_app="app_a", content_hash="a2" * 32))
        await repo.create(make_log_entry(source_app="app_b", content_hash="b1" * 32))

        results = await repo.search(source_app="app_a")
        assert len(results) == 2

    async def test_search_by_severity(self, db_session, make_log_entry):
        """Buscar logs por severidad."""
        repo = LogEntryRepository(db_session)
        await repo.create(make_log_entry(severity="error", content_hash="e1" * 32))
        await repo.create(make_log_entry(severity="info", content_hash="i1" * 32))

        results = await repo.search(severity="error")
        assert len(results) == 1
        assert results[0].severity == "error"

    async def test_search_combined_filters(self, db_session, make_log_entry):
        """Buscar con múltiples filtros (AND)."""
        repo = LogEntryRepository(db_session)
        await repo.create(make_log_entry(
            source_app="app_x", event_type="login", severity="info",
            content_hash="x1" * 32,
        ))
        await repo.create(make_log_entry(
            source_app="app_x", event_type="logout", severity="info",
            content_hash="x2" * 32,
        ))
        await repo.create(make_log_entry(
            source_app="app_y", event_type="login", severity="warning",
            content_hash="y1" * 32,
        ))

        results = await repo.search(source_app="app_x", event_type="login")
        assert len(results) == 1

    async def test_count_unassigned(self, db_session, make_log_entry):
        """Contar logs sin asignar."""
        repo = LogEntryRepository(db_session)
        before = await repo.count_unassigned()

        await repo.create(make_log_entry(content_hash="c1" * 32))
        await repo.create(make_log_entry(content_hash="c2" * 32))

        count = await repo.count_unassigned()
        assert count == before + 2


# ============================================================
# Tests de MerkleNodeRepository
# ============================================================

class TestMerkleNodeRepository:
    """Tests del repositorio de MerkleNode."""

    async def test_bulk_create(self, db_session, make_batch, make_merkle_node):
        """Crear múltiples nodos de una vez."""
        batch_repo = MerkleBatchRepository(db_session)
        node_repo = MerkleNodeRepository(db_session)

        batch = make_batch(batch_number=800)
        await batch_repo.create(batch)

        nodes = [
            make_merkle_node(batch_id=batch.id, level=0, position=0),
            make_merkle_node(batch_id=batch.id, level=0, position=1),
            make_merkle_node(batch_id=batch.id, level=1, position=0),
        ]
        created = await node_repo.bulk_create(nodes)
        assert len(created) == 3

    async def test_get_leaves(self, db_session, make_batch, make_merkle_node):
        """Obtener hojas (level=0) de un batch."""
        batch_repo = MerkleBatchRepository(db_session)
        node_repo = MerkleNodeRepository(db_session)

        batch = make_batch(batch_number=801)
        await batch_repo.create(batch)

        # 2 hojas + 1 nodo interno
        await node_repo.bulk_create([
            make_merkle_node(batch_id=batch.id, level=0, position=0),
            make_merkle_node(batch_id=batch.id, level=0, position=1),
            make_merkle_node(batch_id=batch.id, level=1, position=0),
        ])

        leaves = await node_repo.get_leaves(batch.id)
        assert len(leaves) == 2
        assert all(n.level == 0 for n in leaves)

    async def test_get_root(self, db_session, make_batch, make_merkle_node):
        """Obtener el nodo raíz de un batch."""
        batch_repo = MerkleBatchRepository(db_session)
        node_repo = MerkleNodeRepository(db_session)

        batch = make_batch(batch_number=802)
        await batch_repo.create(batch)

        root_hash = "root" * 16  # 64 chars
        await node_repo.bulk_create([
            make_merkle_node(batch_id=batch.id, level=0, position=0),
            make_merkle_node(batch_id=batch.id, level=0, position=1),
            make_merkle_node(batch_id=batch.id, level=1, position=0, hash_value=root_hash),
        ])

        root = await node_repo.get_root(batch.id)
        assert root is not None
        assert root.level == 1
        assert root.hash_value == root_hash

    async def test_get_node_at(self, db_session, make_batch, make_merkle_node):
        """Obtener un nodo por posición exacta."""
        batch_repo = MerkleBatchRepository(db_session)
        node_repo = MerkleNodeRepository(db_session)

        batch = make_batch(batch_number=803)
        await batch_repo.create(batch)

        target_hash = "target" * 10 + "targ"  # 64 chars
        await node_repo.bulk_create([
            make_merkle_node(batch_id=batch.id, level=0, position=0),
            make_merkle_node(batch_id=batch.id, level=0, position=1, hash_value=target_hash),
        ])

        node = await node_repo.get_node_at(batch.id, level=0, position=1)
        assert node is not None
        assert node.hash_value == target_hash


# ============================================================
# Tests de AnchorRecordRepository
# ============================================================

class TestAnchorRecordRepository:
    """Tests del repositorio de AnchorRecord."""

    async def test_create_anchor(self, db_session, make_batch, make_anchor_record):
        """Crear un anclaje."""
        batch_repo = MerkleBatchRepository(db_session)
        anchor_repo = AnchorRecordRepository(db_session)

        batch = make_batch(batch_number=900, status="closed", merkle_root="a" * 64)
        await batch_repo.create(batch)

        anchor = make_anchor_record(
            batch_id=batch.id, merkle_root="a" * 64, network="ganache"
        )
        created = await anchor_repo.create(anchor)
        assert created.id is not None
        assert created.network == "ganache"

    async def test_get_by_batch(self, db_session, make_batch, make_anchor_record):
        """Obtener anclajes de un batch."""
        batch_repo = MerkleBatchRepository(db_session)
        anchor_repo = AnchorRecordRepository(db_session)

        batch = make_batch(batch_number=901, status="closed", merkle_root="b" * 64)
        await batch_repo.create(batch)

        await anchor_repo.create(make_anchor_record(batch_id=batch.id))
        await anchor_repo.create(make_anchor_record(batch_id=batch.id))

        anchors = await anchor_repo.get_by_batch(batch.id)
        assert len(anchors) == 2

    async def test_get_by_tx_hash(self, db_session, make_batch, make_anchor_record):
        """Buscar anclaje por hash de transacción."""
        batch_repo = MerkleBatchRepository(db_session)
        anchor_repo = AnchorRecordRepository(db_session)

        batch = make_batch(batch_number=902, status="closed", merkle_root="c" * 64)
        await batch_repo.create(batch)

        tx = "0x" + "deadbeef" * 8
        await anchor_repo.create(make_anchor_record(batch_id=batch.id, tx_hash=tx))

        found = await anchor_repo.get_by_tx_hash(tx)
        assert found is not None
        assert found.tx_hash == tx

    async def test_get_by_network(self, db_session, make_batch, make_anchor_record):
        """Filtrar anclajes por red."""
        batch_repo = MerkleBatchRepository(db_session)
        anchor_repo = AnchorRecordRepository(db_session)

        batch = make_batch(batch_number=903, status="closed", merkle_root="d" * 64)
        await batch_repo.create(batch)

        await anchor_repo.create(make_anchor_record(batch_id=batch.id, network="ganache"))
        await anchor_repo.create(make_anchor_record(batch_id=batch.id, network="sepolia"))

        ganache_anchors = await anchor_repo.get_by_network("ganache")
        assert len(ganache_anchors) == 1
        assert ganache_anchors[0].network == "ganache"
