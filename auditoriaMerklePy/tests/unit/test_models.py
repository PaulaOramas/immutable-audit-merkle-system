"""
Tests unitarios de los modelos SQLAlchemy.

Valida la creación correcta de instancias, valores por defecto,
y representaciones __repr__.
No requieren base de datos.
"""

import uuid
from datetime import datetime, timezone

import pytest

from app.models import LogEntry, MerkleBatch, MerkleNode, AnchorRecord


class TestLogEntryModel:
    """Tests del modelo LogEntry."""

    def test_create_log_entry(self):
        """Crear un LogEntry con todos los campos."""
        log = LogEntry(
            id=uuid.uuid4(),
            source_app="test_app",
            event_type="login",
            severity="info",
            payload={"user": "admin"},
            content_hash="a" * 64,
        )
        assert log.source_app == "test_app"
        assert log.event_type == "login"
        assert log.severity == "info"
        assert log.content_hash == "a" * 64
        assert log.batch_id is None
        assert log.leaf_index is None

    def test_repr(self):
        """__repr__ produce string legible."""
        log = LogEntry(
            id=uuid.uuid4(),
            source_app="app_web",
            event_type="logout",
            severity="warning",
            payload={},
            content_hash="b" * 64,
        )
        r = repr(log)
        assert "LogEntry" in r
        assert "app_web" in r
        assert "logout" in r

    def test_tablename(self):
        """La tabla se llama log_entries."""
        assert LogEntry.__tablename__ == "log_entries"


class TestMerkleBatchModel:
    """Tests del modelo MerkleBatch."""

    def test_create_batch(self):
        """Crear un MerkleBatch con valores explícitos."""
        batch = MerkleBatch(
            id=uuid.uuid4(),
            batch_number=1,
            leaf_count=0,
            status="open",
        )
        assert batch.batch_number == 1
        assert batch.leaf_count == 0
        assert batch.status == "open"
        assert batch.merkle_root is None
        assert batch.prev_batch_root is None
        assert batch.closed_at is None

    def test_repr(self):
        """__repr__ produce string legible."""
        batch = MerkleBatch(
            id=uuid.uuid4(),
            batch_number=5,
            leaf_count=10,
            status="closed",
        )
        r = repr(batch)
        assert "MerkleBatch" in r
        assert "5" in r
        assert "closed" in r

    def test_tablename(self):
        assert MerkleBatch.__tablename__ == "merkle_batches"


class TestMerkleNodeModel:
    """Tests del modelo MerkleNode."""

    def test_create_leaf_node(self):
        """Crear un nodo hoja (level=0)."""
        node = MerkleNode(
            id=uuid.uuid4(),
            batch_id=uuid.uuid4(),
            level=0,
            position=0,
            hash_value="c" * 64,
        )
        assert node.level == 0
        assert node.position == 0
        assert node.left_child_id is None
        assert node.right_child_id is None

    def test_create_internal_node(self):
        """Crear un nodo interno con hijos."""
        left_id = uuid.uuid4()
        right_id = uuid.uuid4()
        node = MerkleNode(
            id=uuid.uuid4(),
            batch_id=uuid.uuid4(),
            level=1,
            position=0,
            hash_value="d" * 64,
            left_child_id=left_id,
            right_child_id=right_id,
        )
        assert node.level == 1
        assert node.left_child_id == left_id
        assert node.right_child_id == right_id

    def test_repr(self):
        node = MerkleNode(
            id=uuid.uuid4(),
            batch_id=uuid.uuid4(),
            level=2,
            position=1,
            hash_value="e" * 64,
        )
        r = repr(node)
        assert "MerkleNode" in r
        assert "level=2" in r

    def test_tablename(self):
        assert MerkleNode.__tablename__ == "merkle_nodes"


class TestAnchorRecordModel:
    """Tests del modelo AnchorRecord."""

    def test_create_blockchain_anchor(self):
        """Crear un anclaje de tipo blockchain."""
        anchor = AnchorRecord(
            id=uuid.uuid4(),
            batch_id=uuid.uuid4(),
            merkle_root="f" * 64,
            anchor_type="blockchain",
            tx_hash="0x" + "a" * 64,
            block_number=12345,
            network="ganache",
        )
        assert anchor.anchor_type == "blockchain"
        assert anchor.network == "ganache"
        assert anchor.block_number == 12345

    def test_create_tsa_anchor(self):
        """Crear un anclaje de tipo timestamp_authority."""
        anchor = AnchorRecord(
            id=uuid.uuid4(),
            batch_id=uuid.uuid4(),
            merkle_root="0" * 64,
            anchor_type="timestamp_authority",
        )
        assert anchor.anchor_type == "timestamp_authority"
        assert anchor.tx_hash is None
        assert anchor.network is None

    def test_repr(self):
        anchor = AnchorRecord(
            id=uuid.uuid4(),
            batch_id=uuid.uuid4(),
            merkle_root="1" * 64,
            anchor_type="blockchain",
            tx_hash="0x" + "b" * 64,
            network="sepolia",
        )
        r = repr(anchor)
        assert "AnchorRecord" in r
        assert "blockchain" in r
        assert "sepolia" in r

    def test_tablename(self):
        assert AnchorRecord.__tablename__ == "anchor_records"
