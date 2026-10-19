"""
Servicio de negocio para Batches y Verificación.

Encapsula la lógica de:
- Consulta de batches con sus relaciones
- Generación de Merkle Proofs desde la BD
- Verificación criptográfica de proofs
"""

from typing import Optional, List, Tuple
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.hashing import hash_log_entry
from app.core.merkle_tree import MerkleTree
from app.core.proof import generate_proof, verify_proof, ProofStep
from app.models.log_entry import LogEntry
from app.models.merkle_batch import MerkleBatch
from app.repositories.log_entry_repo import LogEntryRepository
from app.repositories.merkle_batch_repo import MerkleBatchRepository
from app.repositories.merkle_node_repo import MerkleNodeRepository
from app.repositories.anchor_record_repo import AnchorRecordRepository


class LogNotInBatchError(Exception):
    """El log no ha sido asignado a un batch aún."""
    pass


class BatchNotClosedError(Exception):
    """El batch no ha sido cerrado (aún no tiene Merkle Tree)."""
    pass


class BatchService:
    """Servicio de negocio para batches y verificación de integridad."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.log_repo = LogEntryRepository(session)
        self.batch_repo = MerkleBatchRepository(session)
        self.node_repo = MerkleNodeRepository(session)
        self.anchor_repo = AnchorRecordRepository(session)

    # ============================================================
    # Batches
    # ============================================================

    async def list_batches(
        self,
        status: Optional[str] = None,
        offset: int = 0,
        limit: int = 50,
    ) -> Tuple[List[MerkleBatch], int]:
        """Listar batches con filtro opcional por estado."""
        if status:
            batches = await self.batch_repo.get_by_status(status, offset, limit)
        else:
            batches = await self.batch_repo.get_all(offset, limit)
        total = await self.batch_repo.count()
        return batches, total

    async def get_batch_detail(self, batch_id: UUID) -> Optional[MerkleBatch]:
        """Obtener un batch con sus relaciones (logs, nodos, anchors)."""
        return await self.batch_repo.get_with_relations(batch_id)

    # ============================================================
    # Merkle Proof Generation
    # ============================================================

    async def generate_proof_for_log(self, log_id: UUID) -> dict:
        """
        Genera una prueba de Merkle para un log específico.

        Reconstruye el árbol en memoria a partir de los hashes de las hojas
        almacenados en la BD, y genera la prueba para la posición del log.

        Args:
            log_id: ID del log.

        Returns:
            dict con los datos de la prueba (compatible con MerkleProofResponse).

        Raises:
            LogNotInBatchError: Si el log no tiene batch asignado.
            BatchNotClosedError: Si el batch no está cerrado (no tiene root).
        """
        # 1. Obtener el log
        log = await self.log_repo.get_by_id(log_id)
        if not log:
            return None

        # 2. Verificar que tenga batch asignado
        if not log.batch_id or log.leaf_index is None:
            raise LogNotInBatchError(
                f"El log {log_id} aún no ha sido asignado a un batch"
            )

        # 3. Obtener el batch
        batch = await self.batch_repo.get_by_id(log.batch_id)
        if not batch or not batch.merkle_root:
            raise BatchNotClosedError(
                f"El batch del log {log_id} no está cerrado"
            )

        # 4. Obtener hojas del batch (ordenadas por posición)
        leaf_nodes = await self.node_repo.get_leaves(log.batch_id)
        leaf_hashes = [node.hash_value for node in leaf_nodes]

        # 5. Reconstruir el árbol y generar la prueba
        tree = MerkleTree(leaf_hashes)
        proof_steps = generate_proof(tree, log.leaf_index)

        # 6. Verificar que el root recalculado coincida con el almacenado
        assert tree.root == batch.merkle_root, (
            f"Integridad comprometida: root recalculado ({tree.root}) "
            f"!= root almacenado ({batch.merkle_root})"
        )

        # 7. Verificar si el batch está anclado
        anchors = await self.anchor_repo.get_by_batch(log.batch_id)

        # Calculate real-time hash to expose tampering if it occurred
        hasheable_data = {
            "source_app": log.source_app,
            "event_type": log.event_type,
            "severity": log.severity,
            "payload": log.payload,
        }
        calculated_hash = hash_log_entry(hasheable_data)

        return {
            "log_id": log.id,
            "content_hash": calculated_hash,  # Usamos el hash real actual
            "leaf_index": log.leaf_index,
            "batch_id": batch.id,
            "batch_number": batch.batch_number,
            "merkle_root": batch.merkle_root,
            "proof": [{"hash": s.hash, "position": s.position} for s in proof_steps],
            "is_anchored": len(anchors) > 0,
            "original_hash": log.content_hash, # Para propósitos de depuración frontend
        }

    # ============================================================
    # Verification
    # ============================================================

    def verify_proof(
        self,
        content_hash: str,
        merkle_root: str,
        proof_steps: List[dict],
    ) -> bool:
        """
        Verifica una prueba de Merkle.

        Esta operación es puramente criptográfica (sin BD).
        Recalcula el root a partir de la hoja y los pasos de la prueba.

        Args:
            content_hash: Hash de la hoja.
            merkle_root: Root esperado.
            proof_steps: Lista de dicts con {hash, position}.

        Returns:
            True si la prueba es válida.
        """
        steps = [
            ProofStep(hash=step["hash"], position=step["position"])
            for step in proof_steps
        ]
        return verify_proof(content_hash, steps, merkle_root)
