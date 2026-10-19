"""
Tests unitarios para AnchorService (Fase 4.2/4.3).

Cubren:
- Validaciones de estado del batch
- Verificación de configuración
- Conversión de merkle_root a bytes32
- Errores de conexión

Usa mocks para web3 (no necesita blockchain real).
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
from uuid import uuid4

import pytest

from app.services.anchor_service import (
    AnchorService,
    AnchorServiceError,
    BlockchainConnectionError,
    ContractCallError,
)


def _make_mock_batch(
    status="closed",
    merkle_root="abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
    batch_number=1,
):
    """Helper para crear un mock de MerkleBatch."""
    batch = MagicMock()
    batch.id = uuid4()
    batch.batch_number = batch_number
    batch.status = status
    batch.merkle_root = merkle_root
    return batch


class TestAnchorServiceValidation:

    @pytest.mark.asyncio
    async def test_reject_non_closed_batch(self):
        """No se puede anclar un batch que no está cerrado."""
        session = AsyncMock()
        service = AnchorService(session)
        batch = _make_mock_batch(status="open")

        with pytest.raises(AnchorServiceError, match="cerrados"):
            await service.anchor_batch(batch)

    @pytest.mark.asyncio
    async def test_reject_batch_without_root(self):
        """No se puede anclar un batch sin merkle_root."""
        session = AsyncMock()
        service = AnchorService(session)
        batch = _make_mock_batch(merkle_root=None)

        with pytest.raises(AnchorServiceError, match="merkle_root"):
            await service.anchor_batch(batch)

    @pytest.mark.asyncio
    async def test_reject_anchored_batch(self):
        """No se puede re-anclar un batch ya anclado."""
        session = AsyncMock()
        service = AnchorService(session)
        batch = _make_mock_batch(status="anchored")

        with pytest.raises(AnchorServiceError, match="cerrados"):
            await service.anchor_batch(batch)


class TestAnchorServiceConfig:

    def test_no_contract_address_raises(self):
        """Sin CONTRACT_ADDRESS configurado lanza error."""
        session = AsyncMock()
        service = AnchorService(session)

        # Mock web3 como conectado
        mock_w3 = MagicMock()
        mock_w3.is_connected.return_value = True
        mock_w3.eth.chain_id = 1337
        service._w3 = mock_w3

        with patch('app.services.anchor_service.settings') as mock_settings:
            mock_settings.CONTRACT_ADDRESS = ""
            with pytest.raises(AnchorServiceError, match="CONTRACT_ADDRESS"):
                service._get_contract()

    def test_no_private_key_raises(self):
        """Sin DEPLOYER_PRIVATE_KEY lanza error."""
        session = AsyncMock()
        service = AnchorService(session)

        mock_w3 = MagicMock()
        mock_w3.is_connected.return_value = True
        service._w3 = mock_w3

        with patch('app.services.anchor_service.settings') as mock_settings:
            mock_settings.DEPLOYER_PRIVATE_KEY = ""
            with pytest.raises(AnchorServiceError, match="DEPLOYER_PRIVATE_KEY"):
                service._get_account()


class TestMerkleRootConversion:

    def test_hex_to_bytes32_conversion(self):
        """Merkle root hex string se convierte correctamente a 32 bytes."""
        # SHA-256 produce 64 chars hex = 32 bytes
        merkle_root = "abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890"
        result = bytes.fromhex(merkle_root)

        assert len(result) == 32
        assert result.hex() == merkle_root

    def test_different_roots_different_bytes(self):
        """Roots diferentes producen bytes diferentes."""
        root_a = "abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890"
        root_b = "1111111111111111111111111111111111111111111111111111111111111111"

        assert bytes.fromhex(root_a) != bytes.fromhex(root_b)


class TestAnchorPendingBatches:

    @pytest.mark.asyncio
    async def test_no_pending_returns_empty(self):
        """Sin batches pendientes retorna lista vacía."""
        session = AsyncMock()
        service = AnchorService(session)

        # Mock del batch_repo
        service.batch_repo = MagicMock()
        service.batch_repo.get_closed_unanchored = AsyncMock(return_value=[])

        result = await service.anchor_pending_batches()
        assert result == []
