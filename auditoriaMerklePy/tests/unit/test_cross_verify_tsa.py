"""
Tests unitarios para Fase 4.4 (cross-verify) y 4.5 (TSA).
"""

import hashlib
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.services.anchor_service import (
    AnchorService,
    AnchorServiceError,
    TSAError,
)


def _make_mock_batch(
    status="anchored",
    merkle_root="abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
    batch_number=1,
):
    batch = MagicMock()
    batch.id = uuid4()
    batch.batch_number = batch_number
    batch.status = status
    batch.merkle_root = merkle_root
    return batch


def _make_mock_anchor(batch_id, anchor_type="blockchain"):
    anchor = MagicMock()
    anchor.id = uuid4()
    anchor.batch_id = batch_id
    anchor.anchor_type = anchor_type
    anchor.tx_hash = "abc123def456"
    anchor.block_number = 5
    anchor.network = "ganache"
    anchor.anchored_at = MagicMock()
    anchor.anchored_at.isoformat.return_value = "2026-01-01T00:00:00+00:00"
    anchor.anchor_metadata = {}
    return anchor


# ============================================================
# 4.4 Cross-verification tests
# ============================================================


class TestCrossVerifyBatch:

    @pytest.mark.asyncio
    async def test_raises_if_batch_not_found(self):
        """Batch inexistente lanza error."""
        session = AsyncMock()
        service = AnchorService(session)
        service.batch_repo = MagicMock()
        service.batch_repo.get_by_id = AsyncMock(return_value=None)

        with pytest.raises(AnchorServiceError, match="no encontrado"):
            await service.cross_verify_batch(uuid4())

    @pytest.mark.asyncio
    async def test_raises_if_no_merkle_root(self):
        """Batch sin root lanza error."""
        session = AsyncMock()
        service = AnchorService(session)
        batch = _make_mock_batch(merkle_root=None)
        service.batch_repo = MagicMock()
        service.batch_repo.get_by_id = AsyncMock(return_value=batch)

        with pytest.raises(AnchorServiceError, match="Merkle Root"):
            await service.cross_verify_batch(batch.id)

    @pytest.mark.asyncio
    async def test_returns_not_anchored_when_not_on_chain(self):
        """Root no encontrado on-chain retorna integrity=not_anchored."""
        session = AsyncMock()
        service = AnchorService(session)
        batch = _make_mock_batch()

        service.batch_repo = MagicMock()
        service.batch_repo.get_by_id = AsyncMock(return_value=batch)
        service.anchor_repo = MagicMock()
        service.anchor_repo.get_latest_by_batch = AsyncMock(return_value=None)

        # Mock verify_on_chain
        service.verify_on_chain = MagicMock(return_value={
            "found": False,
            "anchor_id": None,
            "timestamp": None,
            "block_timestamp_utc": None,
        })

        result = await service.cross_verify_batch(batch.id)

        assert result["integrity"] == "not_anchored"
        assert result["roots_match"] is False

    @pytest.mark.asyncio
    async def test_returns_verified_when_roots_match(self):
        """Roots que coinciden retornan integrity=verified."""
        session = AsyncMock()
        service = AnchorService(session)
        root = "abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890"
        batch = _make_mock_batch(merkle_root=root)
        anchor = _make_mock_anchor(batch.id)

        service.batch_repo = MagicMock()
        service.batch_repo.get_by_id = AsyncMock(return_value=batch)
        service.anchor_repo = MagicMock()
        service.anchor_repo.get_latest_by_batch = AsyncMock(return_value=anchor)
        service.anchor_repo.get_by_batch = AsyncMock(return_value=[anchor])

        service.verify_on_chain = MagicMock(return_value={
            "found": True,
            "anchor_id": 0,
            "timestamp": 1700000000,
            "block_timestamp_utc": "2023-11-14T22:13:20+00:00",
        })
        service.get_anchor_from_chain = MagicMock(return_value={
            "merkle_root": root,
            "timestamp": 1700000000,
            "batch_id": str(batch.id),
        })

        # Mock web3 para tx receipt
        mock_w3 = MagicMock()
        mock_w3.eth.get_transaction_receipt.return_value = {
            "blockNumber": 5,
            "status": 1,
            "gasUsed": 50000,
        }
        service._w3 = mock_w3

        result = await service.cross_verify_batch(batch.id)

        assert result["integrity"] == "verified"
        assert result["roots_match"] is True
        assert result["local_merkle_root"] == root
        assert result["onchain_merkle_root"] == root

    @pytest.mark.asyncio
    async def test_returns_mismatch_when_roots_differ(self):
        """Roots diferentes retornan integrity=mismatch."""
        session = AsyncMock()
        service = AnchorService(session)
        local_root = "abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890"
        onchain_root = "1111111111111111111111111111111111111111111111111111111111111111"
        batch = _make_mock_batch(merkle_root=local_root)
        anchor = _make_mock_anchor(batch.id)

        service.batch_repo = MagicMock()
        service.batch_repo.get_by_id = AsyncMock(return_value=batch)
        service.anchor_repo = MagicMock()
        service.anchor_repo.get_latest_by_batch = AsyncMock(return_value=anchor)
        service.anchor_repo.get_by_batch = AsyncMock(return_value=[anchor])

        service.verify_on_chain = MagicMock(return_value={
            "found": True,
            "anchor_id": 0,
            "timestamp": 1700000000,
            "block_timestamp_utc": "2023-11-14T22:13:20+00:00",
        })
        service.get_anchor_from_chain = MagicMock(return_value={
            "merkle_root": onchain_root,
            "timestamp": 1700000000,
            "batch_id": str(batch.id),
        })

        mock_w3 = MagicMock()
        mock_w3.eth.get_transaction_receipt.return_value = {
            "blockNumber": 5,
            "status": 1,
            "gasUsed": 50000,
        }
        service._w3 = mock_w3

        result = await service.cross_verify_batch(batch.id)

        assert result["integrity"] == "mismatch"
        assert result["roots_match"] is False


# ============================================================
# 4.5 TSA tests
# ============================================================


class TestTSATimestamp:

    @pytest.mark.asyncio
    async def test_reject_batch_without_root(self):
        """Batch sin root lanza TSAError."""
        session = AsyncMock()
        service = AnchorService(session)
        batch = _make_mock_batch(merkle_root=None)

        with pytest.raises(TSAError, match="merkle_root"):
            await service.timestamp_batch(batch)

    def test_parse_tsr_info_handles_missing_openssl(self):
        """_parse_tsr_info maneja error si openssl no existe."""
        result = AnchorService._parse_tsr_info("/nonexistent/file.tsr")
        # Debería retornar un dict con error, no lanzar excepción
        assert isinstance(result, dict)

    def test_merkle_root_hash_deterministic(self):
        """SHA-256 del merkle_root es determinista para TSA."""
        root = "abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890"
        h1 = hashlib.sha256(root.encode("utf-8")).hexdigest()
        h2 = hashlib.sha256(root.encode("utf-8")).hexdigest()
        assert h1 == h2
        assert len(h1) == 64


class TestTimestampPendingBatches:

    @pytest.mark.asyncio
    async def test_no_candidates_returns_empty(self):
        """Sin batches candidatos retorna lista vacía."""
        session = AsyncMock()
        service = AnchorService(session)
        service.batch_repo = MagicMock()
        service.batch_repo.get_by_status = AsyncMock(return_value=[])

        result = await service.timestamp_pending_batches()
        assert result == []
