"""
MerkleService — Motor de procesamiento de árboles Merkle.

Responsabilidades:
- Obtener o crear el batch activo (open)
- Asignar logs a batches
- Cerrar batches: construir el Merkle Tree → calcular root → persistir nodos
- Decidir cuándo cerrar un batch (por cantidad o por tiempo)

Ciclo de vida del batch:
    open  → (N logs alcanzados o timeout) → closed → (anchoring) → anchored
"""

import logging
from datetime import datetime, timezone
from typing import Optional, List
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.hashing import hash_log_entry
from app.core.merkle_tree import MerkleTree
from app.models.log_entry import LogEntry
from app.models.merkle_batch import MerkleBatch
from app.models.merkle_node import MerkleNode
from app.repositories.log_entry_repo import LogEntryRepository
from app.repositories.merkle_batch_repo import MerkleBatchRepository
from app.repositories.merkle_node_repo import MerkleNodeRepository

logger = logging.getLogger(__name__)


class MerkleService:
    """
    Servicio de procesamiento Merkle.

    Gestiona la asignación de logs a batches, el cierre de batches
    cuando alcanzan el límite de hojas, y la construcción del árbol
    Merkle con persistencia de nodos.
    """

    def __init__(self, session: AsyncSession):
        self.session = session
        self.log_repo = LogEntryRepository(session)
        self.batch_repo = MerkleBatchRepository(session)
        self.node_repo = MerkleNodeRepository(session)

    # ============================================================
    # Batch Activo
    # ============================================================

    async def get_or_create_active_batch(self) -> MerkleBatch:
        """
        Obtiene el batch activo (open), o crea uno nuevo si no existe.

        Solo debe existir un batch open a la vez. El batch nuevo
        encadena con el anterior mediante prev_batch_root.

        Returns:
            MerkleBatch con status='open'.
        """
        batch = await self.batch_repo.get_open_batch()
        if batch:
            return batch

        # Crear nuevo batch
        next_number = await self.batch_repo.get_next_batch_number()

        # Encadenar con el batch anterior
        latest = await self.batch_repo.get_latest_batch()
        prev_root = latest.merkle_root if latest else None

        new_batch = MerkleBatch(
            batch_number=next_number,
            status="open",
            leaf_count=0,
            prev_batch_root=prev_root,
        )
        created = await self.batch_repo.create(new_batch)
        logger.info(
            "Nuevo batch creado: #%d (prev_root=%s)",
            created.batch_number,
            prev_root[:16] + "..." if prev_root else "None",
        )
        return created

    # ============================================================
    # Asignación de Log a Batch
    # ============================================================

    async def assign_log_to_batch(self, log: LogEntry) -> MerkleBatch:
        """
        Asigna un log al batch activo y verifica si debe cerrarse.

        1. Obtiene el batch activo (o lo crea)
        2. Asigna el log con su leaf_index
        3. Incrementa leaf_count
        4. Si leaf_count >= BATCH_MAX_LEAVES, cierra el batch

        Args:
            log: LogEntry ya persistido (con content_hash).

        Returns:
            El MerkleBatch al que se asignó el log.
        """
        batch = await self.get_or_create_active_batch()

        # Asignar el log al batch
        log.batch_id = batch.id
        log.leaf_index = batch.leaf_count
        batch.leaf_count += 1
        await self.session.flush()

        logger.debug(
            "Log %s asignado a batch #%d (leaf_index=%d, total=%d)",
            log.id, batch.batch_number, log.leaf_index, batch.leaf_count,
        )

        # Verificar si el batch alcanzó el máximo de hojas
        if batch.leaf_count >= settings.BATCH_MAX_LEAVES:
            logger.info(
                "Batch #%d alcanzó %d hojas, cerrando automáticamente",
                batch.batch_number, batch.leaf_count,
            )
            await self.close_batch(batch)

        return batch

    # ============================================================
    # Cierre de Batch
    # ============================================================

    async def close_batch(self, batch: MerkleBatch) -> MerkleBatch:
        """
        Cierra un batch: construye el Merkle Tree y persiste los nodos.

        Proceso:
        1. Obtiene los logs del batch (ordenados por leaf_index)
        2. Extrae los content_hash como hojas
        3. Construye el MerkleTree
        4. Persiste todos los nodos del árbol
        5. Actualiza el batch con el merkle_root y status='closed'

        Args:
            batch: MerkleBatch con status='open'.

        Returns:
            MerkleBatch actualizado con status='closed' y merkle_root.

        Raises:
            ValueError: Si el batch no está open o no tiene logs.
        """
        if batch.status != "open":
            raise ValueError(
                f"Solo se pueden cerrar batches abiertos. "
                f"Batch #{batch.batch_number} tiene status='{batch.status}'"
            )

        # Obtener los logs del batch ordenados por leaf_index
        logs = await self.log_repo.get_by_batch(
            batch.id, offset=0, limit=settings.BATCH_MAX_LEAVES + 1
        )

        if not logs:
            raise ValueError(
                f"El batch #{batch.batch_number} no tiene logs asignados"
            )

        # Extraer los hashes de las hojas
        leaf_hashes = [log.content_hash for log in logs]

        # Construir el Merkle Tree
        tree = MerkleTree(leaf_hashes)

        logger.info(
            "Merkle Tree construido para batch #%d: %d hojas, root=%s",
            batch.batch_number, tree.leaf_count, tree.root[:16] + "...",
        )

        # Persistir todos los nodos del árbol
        await self._persist_tree_nodes(batch.id, tree)

        # Actualizar el batch
        batch = await self.batch_repo.close_batch(
            batch=batch,
            merkle_root=tree.root,
            leaf_count=tree.leaf_count,
        )

        logger.info(
            "Batch #%d cerrado exitosamente. Root: %s",
            batch.batch_number, batch.merkle_root,
        )
        return batch

    async def _persist_tree_nodes(
        self, batch_id: UUID, tree: MerkleTree
    ) -> List[MerkleNode]:
        """
        Persiste todos los nodos del Merkle Tree en la base de datos.

        Recorre cada nivel del árbol (levels[0]=hojas, levels[-1]=raíz)
        y crea un MerkleNode por cada hash.

        Args:
            batch_id: ID del batch al que pertenecen los nodos.
            tree: MerkleTree ya construido.

        Returns:
            Lista de MerkleNode creados.
        """
        all_nodes = []

        for level_idx, level_hashes in enumerate(tree.levels):
            for position, hash_value in enumerate(level_hashes):
                node = MerkleNode(
                    batch_id=batch_id,
                    level=level_idx,
                    position=position,
                    hash_value=hash_value,
                )
                all_nodes.append(node)

        created = await self.node_repo.bulk_create(all_nodes)
        logger.debug(
            "Persistidos %d nodos para batch %s",
            len(created), batch_id,
        )
        return created

    # ============================================================
    # Cierre por Timeout (para BatchScheduler)
    # ============================================================

    async def close_expired_batches(self) -> List[MerkleBatch]:
        """
        Cierra batches que han excedido el tiempo máximo de vida.

        Busca el batch open actual. Si su created_at + BATCH_TIMEOUT_SECONDS
        ha sido excedido y tiene al menos 1 log, lo cierra.

        Returns:
            Lista de batches cerrados (0 o 1 normalmente).
        """
        batch = await self.batch_repo.get_open_batch()

        if not batch:
            return []

        # Calcular si expiró
        now = datetime.now(timezone.utc)
        elapsed = (now - batch.created_at).total_seconds()

        if elapsed < settings.BATCH_TIMEOUT_SECONDS:
            return []

        # Verificar que tenga logs
        if batch.leaf_count == 0:
            logger.debug(
                "Batch #%d expiró pero no tiene logs, omitiendo",
                batch.batch_number,
            )
            return []

        logger.info(
            "Batch #%d expiró (%.0fs > %ds) con %d logs, cerrando",
            batch.batch_number, elapsed,
            settings.BATCH_TIMEOUT_SECONDS, batch.leaf_count,
        )
        closed = await self.close_batch(batch)
        return [closed]
