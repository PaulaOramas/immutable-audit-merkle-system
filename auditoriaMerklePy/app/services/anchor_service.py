"""
AnchorService — Servicio de anclaje de Merkle Roots en blockchain y TSA.

Conecta con un nodo Ethereum (Ganache/Infura) usando Web3.py para:
1. Anclar Merkle Roots invocando anchorRoot() en MerkleAnchor.sol
2. Esperar confirmación de la transacción
3. Guardar tx_hash, block_number, network en AnchorRecord
4. Verificación cruzada: comparar root local vs on-chain (Fase 4.4)
5. Sellado RFC 3161 con FreeTSA.org (Fase 4.5)

Configuración requerida en .env:
    GANACHE_URL=http://127.0.0.1:8545
    CONTRACT_ADDRESS=0x...
    DEPLOYER_PRIVATE_KEY=0x...
"""

import base64
import hashlib
import json
import logging
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.anchor_record import AnchorRecord
from app.models.merkle_batch import MerkleBatch
from app.repositories.anchor_record_repo import AnchorRecordRepository
from app.repositories.merkle_batch_repo import MerkleBatchRepository

logger = logging.getLogger(__name__)

# Ruta al ABI del contrato
ABI_PATH = Path(__file__).parent.parent / "core" / "MerkleAnchor_abi.json"

# FreeTSA.org endpoint
TSA_URL = "https://freetsa.org/tsr"


class AnchorServiceError(Exception):
    """Error base del servicio de anclaje."""
    pass


class BlockchainConnectionError(AnchorServiceError):
    """No se pudo conectar al nodo blockchain."""
    pass


class ContractCallError(AnchorServiceError):
    """Error al llamar al smart contract."""
    pass


class TSAError(AnchorServiceError):
    """Error al comunicarse con la autoridad de sellado de tiempo."""
    pass


class AnchorService:
    """
    Servicio de anclaje en blockchain y TSA.

    Se encarga de enviar transacciones al smart contract MerkleAnchor,
    verificar la integridad cruzada, y opcionalmente sellar con TSA RFC 3161.
    """

    def __init__(self, session: AsyncSession):
        self.session = session
        self.batch_repo = MerkleBatchRepository(session)
        self.anchor_repo = AnchorRecordRepository(session)
        self._w3 = None
        self._contract = None
        self._account = None

    # ============================================================
    # Conexión a blockchain
    # ============================================================

    def _get_web3(self):
        """Inicializa y retorna la conexión Web3 (lazy)."""
        if self._w3 is not None:
            return self._w3

        from web3 import Web3

        self._w3 = Web3(Web3.HTTPProvider(settings.GANACHE_URL))

        if not self._w3.is_connected():
            raise BlockchainConnectionError(
                f"No se pudo conectar al nodo en {settings.GANACHE_URL}. "
                "Verifica que Ganache esté corriendo."
            )

        logger.info(
            "Conectado a blockchain: %s (chain_id=%d)",
            settings.GANACHE_URL, self._w3.eth.chain_id,
        )
        return self._w3

    def _get_contract(self):
        """Inicializa y retorna la instancia del contrato."""
        if self._contract is not None:
            return self._contract

        w3 = self._get_web3()

        if not settings.CONTRACT_ADDRESS:
            raise AnchorServiceError(
                "CONTRACT_ADDRESS no está configurado. "
                "Despliega el contrato con 'npx hardhat run scripts/deploy.js --network ganache'"
            )

        with open(ABI_PATH, "r") as f:
            abi = json.load(f)

        self._contract = w3.eth.contract(
            address=w3.to_checksum_address(settings.CONTRACT_ADDRESS),
            abi=abi,
        )
        logger.debug("Contrato cargado: %s", settings.CONTRACT_ADDRESS)
        return self._contract

    def _get_account(self):
        """Inicializa la cuenta de firma desde la private key."""
        if self._account is not None:
            return self._account

        if not settings.DEPLOYER_PRIVATE_KEY:
            raise AnchorServiceError(
                "DEPLOYER_PRIVATE_KEY no está configurado."
            )

        w3 = self._get_web3()
        self._account = w3.eth.account.from_key(settings.DEPLOYER_PRIVATE_KEY)
        logger.debug("Cuenta de anclaje: %s", self._account.address)
        return self._account

    # ============================================================
    # Anclaje de un batch (Fase 4.3)
    # ============================================================

    async def anchor_batch(self, batch: MerkleBatch) -> AnchorRecord:
        """
        Ancla un batch cerrado en la blockchain.

        Proceso:
        1. Verifica que el batch esté cerrado y tenga merkle_root
        2. Convierte el merkle_root a bytes32
        3. Llama anchorRoot() en el smart contract
        4. Espera confirmación
        5. Crea AnchorRecord
        6. Marca batch como 'anchored'
        """
        if batch.status != "closed":
            raise AnchorServiceError(
                f"Solo se pueden anclar batches cerrados. "
                f"Batch #{batch.batch_number} tiene status='{batch.status}'"
            )

        if not batch.merkle_root:
            raise AnchorServiceError(
                f"Batch #{batch.batch_number} no tiene merkle_root"
            )

        w3 = self._get_web3()
        contract = self._get_contract()
        account = self._get_account()

        merkle_root_bytes = bytes.fromhex(batch.merkle_root)
        batch_id_str = str(batch.id)

        logger.info(
            "Anclando batch #%d (root=%s...)",
            batch.batch_number, batch.merkle_root[:16],
        )

        try:
            nonce = w3.eth.get_transaction_count(account.address)

            tx = contract.functions.anchorRoot(
                merkle_root_bytes, batch_id_str,
            ).build_transaction({
                "from": account.address,
                "nonce": nonce,
                "gas": 200000,
                "gasPrice": w3.eth.gas_price,
                "chainId": settings.CHAIN_ID,
            })

            signed_tx = w3.eth.account.sign_transaction(tx, account.key)
            tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
            tx_hash_hex = tx_hash.hex()

            logger.info("Tx enviada: %s", tx_hash_hex)

            receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)

            if receipt["status"] != 1:
                raise ContractCallError(f"Transacción fallida: {tx_hash_hex}")

            block_number = receipt["blockNumber"]
            gas_used = receipt["gasUsed"]

            logger.info(
                "✅ Batch #%d anclado. tx=%s, bloque=%d, gas=%d",
                batch.batch_number, tx_hash_hex, block_number, gas_used,
            )

        except (BlockchainConnectionError, ContractCallError):
            raise
        except Exception as e:
            raise ContractCallError(
                f"Error al anclar batch #{batch.batch_number}: {str(e)}"
            ) from e

        anchor = AnchorRecord(
            batch_id=batch.id,
            merkle_root=batch.merkle_root,
            anchor_type="blockchain",
            tx_hash=tx_hash_hex,
            block_number=block_number,
            network="ganache",
            anchor_metadata={
                "gas_used": gas_used,
                "contract_address": settings.CONTRACT_ADDRESS,
                "chain_id": settings.CHAIN_ID,
                "deployer": account.address,
            },
        )
        self.session.add(anchor)
        await self.batch_repo.mark_anchored(batch)
        await self.session.flush()

        logger.info(
            "AnchorRecord creado para batch #%d: tx=%s",
            batch.batch_number, tx_hash_hex[:16] + "...",
        )
        return anchor

    # ============================================================
    # Anclaje de batches pendientes
    # ============================================================

    async def anchor_pending_batches(self) -> List[AnchorRecord]:
        """Ancla todos los batches cerrados que aún no están anclados."""
        closed_batches = await self.batch_repo.get_closed_unanchored()

        if not closed_batches:
            logger.debug("Sin batches pendientes de anclaje")
            return []

        logger.info("%d batches pendientes de anclaje", len(closed_batches))

        anchored = []
        for batch in closed_batches:
            try:
                anchor = await self.anchor_batch(batch)
                anchored.append(anchor)
            except AnchorServiceError as e:
                logger.error(
                    "Error anclando batch #%d: %s",
                    batch.batch_number, str(e),
                )
                continue

        return anchored

    # ============================================================
    # Verificación on-chain simple
    # ============================================================

    def verify_on_chain(self, merkle_root: str) -> dict:
        """Verifica si un Merkle Root fue anclado en el smart contract."""
        contract = self._get_contract()

        merkle_root_bytes = bytes.fromhex(merkle_root)
        found, anchor_id, timestamp = contract.functions.verifyRoot(
            merkle_root_bytes
        ).call()

        result = {
            "found": found,
            "anchor_id": int(anchor_id) if found else None,
            "timestamp": int(timestamp) if found else None,
            "block_timestamp_utc": (
                datetime.fromtimestamp(int(timestamp), tz=timezone.utc).isoformat()
                if found else None
            ),
        }

        if found:
            logger.debug("Root %s... encontrado on-chain", merkle_root[:16])
        else:
            logger.debug("Root %s... NO encontrado on-chain", merkle_root[:16])

        return result

    def get_anchor_from_chain(self, anchor_id: int) -> dict:
        """Obtiene un anclaje directamente del smart contract."""
        contract = self._get_contract()

        root_bytes, timestamp, batch_id = contract.functions.getAnchor(
            anchor_id
        ).call()

        return {
            "merkle_root": root_bytes.hex(),
            "timestamp": int(timestamp),
            "timestamp_utc": datetime.fromtimestamp(
                int(timestamp), tz=timezone.utc
            ).isoformat(),
            "batch_id": batch_id,
        }

    # ============================================================
    # 4.4 Verificación cruzada (local vs on-chain)
    # ============================================================

    async def cross_verify_batch(self, batch_id: UUID) -> dict:
        """
        Verificación cruzada completa de un batch:

        1. Recupera el batch y su AnchorRecord local (tx_hash)
        2. Consulta el smart contract para obtener el root on-chain
        3. Compara root local vs root on-chain
        4. Si coinciden → integridad confirmada externamente

        Args:
            batch_id: UUID del batch a verificar.

        Returns:
            Dict completo con el resultado de la verificación cruzada.
        """
        # 1. Obtener batch
        batch = await self.batch_repo.get_by_id(batch_id)
        if not batch:
            raise AnchorServiceError(f"Batch {batch_id} no encontrado")

        if not batch.merkle_root:
            raise AnchorServiceError(
                f"Batch #{batch.batch_number} no tiene Merkle Root"
            )

        # 2. Obtener anchor record local
        anchor = await self.anchor_repo.get_latest_by_batch(batch_id)

        # 3. Consultar on-chain
        onchain_result = self.verify_on_chain(batch.merkle_root)

        # 4. Si hay anchor local con tx_hash, verificar la tx específica
        tx_verification = None
        if anchor and anchor.tx_hash:
            try:
                w3 = self._get_web3()
                receipt = w3.eth.get_transaction_receipt(anchor.tx_hash)
                tx_verification = {
                    "tx_hash": anchor.tx_hash,
                    "tx_found": True,
                    "block_number": receipt["blockNumber"],
                    "status": "success" if receipt["status"] == 1 else "failed",
                    "gas_used": receipt["gasUsed"],
                }
            except Exception as e:
                tx_verification = {
                    "tx_hash": anchor.tx_hash,
                    "tx_found": False,
                    "error": str(e),
                }

        # 5. Si se encontró on-chain, obtener los datos almacenados
        onchain_data = None
        if onchain_result["found"]:
            onchain_data = self.get_anchor_from_chain(onchain_result["anchor_id"])

        # 6. Recalcular el Merkle Root en tiempo real desde la BD (para detectar inyecciones)
        from app.repositories.log_entry_repo import LogEntryRepository
        from app.core.hashing import hash_log_entry
        from app.core.merkle_tree import MerkleTree
        
        log_repo = LogEntryRepository(self.session)
        logs = await log_repo.get_by_batch(batch_id, limit=1000)
        
        calculated_leaf_hashes = []
        for log in logs:
            hasheable_data = {
                "source_app": log.source_app,
                "event_type": log.event_type,
                "severity": log.severity,
                "payload": log.payload,
            }
            calculated_leaf_hashes.append(hash_log_entry(hasheable_data))
            
        tree = MerkleTree(calculated_leaf_hashes)
        real_time_root = tree.root

        # 7. Comparar roots
        roots_match = False
        if onchain_data:
            roots_match = onchain_data["merkle_root"] == real_time_root

        # 7. Veredicto
        if not onchain_result["found"]:
            integrity = "not_anchored"
            message = "El Merkle Root NO fue encontrado en la blockchain"
        elif roots_match:
            integrity = "verified"
            message = "Integridad confirmada: root local coincide con root on-chain"
        else:
            integrity = "mismatch"
            message = (
                "DISCREPANCIA: root local y root on-chain NO coinciden. "
                "Posible manipulación de datos."
            )

        # 8. Info de TSA si existe
        tsa_anchor = None
        if anchor:
            all_anchors = await self.anchor_repo.get_by_batch(batch_id)
            tsa_records = [a for a in all_anchors if a.anchor_type == "timestamp_authority"]
            if tsa_records:
                tsa = tsa_records[0]
                tsa_anchor = {
                    "anchor_type": tsa.anchor_type,
                    "anchored_at": tsa.anchored_at.isoformat() if tsa.anchored_at else None,
                    "tsa_url": tsa.anchor_metadata.get("tsa_url") if tsa.anchor_metadata else None,
                }

        return {
            "batch_id": str(batch.id),
            "batch_number": batch.batch_number,
            "batch_status": batch.status,
            "local_merkle_root": real_time_root,  # Modificado para devolver el root real calculado
            "onchain_found": onchain_result["found"],
            "onchain_merkle_root": onchain_data["merkle_root"] if onchain_data else None,
            "onchain_anchor_id": onchain_result["anchor_id"],
            "onchain_timestamp": onchain_result["timestamp"],
            "onchain_timestamp_utc": onchain_result["block_timestamp_utc"],
            "tx_verification": tx_verification,
            "local_anchor": {
                "anchor_type": anchor.anchor_type,
                "tx_hash": anchor.tx_hash,
                "block_number": anchor.block_number,
                "network": anchor.network,
                "anchored_at": anchor.anchored_at.isoformat() if anchor.anchored_at else None,
            } if anchor else None,
            "tsa_anchor": tsa_anchor,
            "roots_match": roots_match,
            "integrity": integrity,
            "message": message,
        }

    # ============================================================
    # 4.5 Sellado de tiempo RFC 3161 (FreeTSA.org)
    # ============================================================

    async def timestamp_batch(self, batch: MerkleBatch) -> AnchorRecord:
        """
        Sella un batch con una autoridad de sellado de tiempo RFC 3161.

        Proceso:
        1. Calcula SHA-256 del merkle_root
        2. Crea un Timestamp Request (tsq) con openssl
        3. Envía al servidor TSA (FreeTSA.org)
        4. Recibe el Timestamp Response (tsr)
        5. Almacena el token como AnchorRecord tipo 'timestamp_authority'

        Args:
            batch: MerkleBatch con merkle_root.

        Returns:
            AnchorRecord con la evidencia del sellado.
        """
        if not batch.merkle_root:
            raise TSAError(f"Batch #{batch.batch_number} no tiene merkle_root")

        logger.info(
            "Solicitando sellado TSA para batch #%d (root=%s...)",
            batch.batch_number, batch.merkle_root[:16],
        )

        data_to_stamp = batch.merkle_root.encode("utf-8")
        data_hash = hashlib.sha256(data_to_stamp).hexdigest()

        with tempfile.TemporaryDirectory() as tmpdir:
            tsq_path = Path(tmpdir) / "request.tsq"
            tsr_path = Path(tmpdir) / "response.tsr"
            data_path = Path(tmpdir) / "data.bin"

            data_path.write_bytes(data_to_stamp)

            # Crear Timestamp Request con openssl
            try:
                result = subprocess.run(
                    [
                        "openssl", "ts", "-query",
                        "-data", str(data_path),
                        "-no_nonce", "-sha256",
                        "-out", str(tsq_path),
                    ],
                    capture_output=True, text=True, timeout=10,
                )
                if result.returncode != 0:
                    raise TSAError(f"Error creando TSQ: {result.stderr}")
            except FileNotFoundError:
                raise TSAError("openssl no está instalado.")

            # Enviar al servidor TSA
            try:
                import urllib.request
                import urllib.error

                tsq_data = tsq_path.read_bytes()

                req = urllib.request.Request(
                    TSA_URL,
                    data=tsq_data,
                    headers={"Content-Type": "application/timestamp-query"},
                )
                with urllib.request.urlopen(req, timeout=30) as resp:
                    tsr_data = resp.read()

                if not tsr_data:
                    raise TSAError("Respuesta TSA vacía")

                tsr_path.write_bytes(tsr_data)

            except urllib.error.URLError as e:
                raise TSAError(f"Error conectando con TSA: {str(e)}")

            # Parsear info del TSR
            tsr_info = self._parse_tsr_info(str(tsr_path))

            # Codificar token en base64
            tsr_b64 = base64.b64encode(tsr_data).decode("ascii")

        # Crear AnchorRecord
        anchor = AnchorRecord(
            batch_id=batch.id,
            merkle_root=batch.merkle_root,
            anchor_type="timestamp_authority",
            tx_hash=None,
            block_number=None,
            network=None,
            anchor_metadata={
                "tsa_url": TSA_URL,
                "tsa_protocol": "RFC 3161",
                "data_hash_sha256": data_hash,
                "tsr_token_b64": tsr_b64,
                "tsr_info": tsr_info,
            },
        )
        self.session.add(anchor)
        await self.session.flush()

        logger.info(
            "✅ Batch #%d sellado con TSA. Hash: %s...",
            batch.batch_number, data_hash[:16],
        )
        return anchor

    @staticmethod
    def _parse_tsr_info(tsr_path: str) -> dict:
        """Extrae información legible del Timestamp Response con openssl."""
        try:
            result = subprocess.run(
                ["openssl", "ts", "-reply", "-in", tsr_path, "-text"],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode != 0:
                return {"raw_error": result.stderr}

            info = {}
            for line in result.stdout.split("\n"):
                line = line.strip()
                if line.startswith("Status:"):
                    info["status"] = line.split(":", 1)[1].strip()
                elif line.startswith("Time stamp:"):
                    info["timestamp"] = line.split(":", 1)[1].strip()
                elif line.startswith("Serial number:"):
                    info["serial_number"] = line.split(":", 1)[1].strip()
                elif line.startswith("Hash Algorithm:"):
                    info["hash_algorithm"] = line.split(":", 1)[1].strip()
                elif "TSA:" in line:
                    info["tsa_name"] = line.split("TSA:", 1)[1].strip()

            return info

        except Exception as e:
            return {"parse_error": str(e)}

    async def timestamp_pending_batches(self) -> List[AnchorRecord]:
        """Sella con TSA batches que no tienen sellado TSA aún."""
        closed = await self.batch_repo.get_by_status("closed")
        anchored = await self.batch_repo.get_by_status("anchored")
        candidates = closed + anchored

        if not candidates:
            return []

        stamped = []
        for batch in candidates:
            anchors = await self.anchor_repo.get_by_batch(batch.id)
            has_tsa = any(a.anchor_type == "timestamp_authority" for a in anchors)

            if has_tsa:
                continue

            try:
                anchor = await self.timestamp_batch(batch)
                stamped.append(anchor)
            except TSAError as e:
                logger.error(
                    "Error sellando batch #%d: %s",
                    batch.batch_number, str(e),
                )
                continue

        return stamped
