"""
Repositorio de MerkleBatch — Operaciones de acceso a datos para batches.
"""

from datetime import datetime, timezone
from typing import Optional, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.merkle_batch import MerkleBatch
from app.repositories import BaseRepository


class MerkleBatchRepository(BaseRepository[MerkleBatch]):
    """
    Repositorio para operaciones sobre MerkleBatch.

    Maneja el ciclo de vida: open → closed → anchored.
    """

    def __init__(self, session: AsyncSession):
        super().__init__(MerkleBatch, session)

    async def get_all(self, offset: int = 0, limit: int = 100) -> List[MerkleBatch]:
        """Obtener todos los batches ordenados por batch_number descendente."""
        result = await self.session.execute(
            select(MerkleBatch)
            .order_by(MerkleBatch.batch_number.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_open_batch(self) -> Optional[MerkleBatch]:
        """Obtener el batch actualmente abierto (debería haber 0 o 1)."""
        result = await self.session.execute(
            select(MerkleBatch)
            .where(MerkleBatch.status == "open")
            .order_by(MerkleBatch.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_by_status(
        self,
        status: str,
        offset: int = 0,
        limit: int = 100,
    ) -> List[MerkleBatch]:
        """Obtener batches por estado."""
        result = await self.session.execute(
            select(MerkleBatch)
            .where(MerkleBatch.status == status)
            .order_by(MerkleBatch.batch_number.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_closed_unanchored(self) -> List[MerkleBatch]:
        """Obtener batches cerrados pero no anclados."""
        result = await self.session.execute(
            select(MerkleBatch)
            .where(MerkleBatch.status == "closed")
            .order_by(MerkleBatch.batch_number)
        )
        return list(result.scalars().all())

    async def get_latest_batch(self) -> Optional[MerkleBatch]:
        """Obtener el batch más reciente (por batch_number)."""
        result = await self.session.execute(
            select(MerkleBatch)
            .order_by(MerkleBatch.batch_number.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_next_batch_number(self) -> int:
        """Calcular el siguiente número de batch."""
        latest = await self.get_latest_batch()
        return (latest.batch_number + 1) if latest else 1

    async def get_with_relations(self, batch_id) -> Optional[MerkleBatch]:
        """Obtener un batch con sus relaciones cargadas (logs, nodos, anchors)."""
        result = await self.session.execute(
            select(MerkleBatch)
            .options(
                selectinload(MerkleBatch.log_entries),
                selectinload(MerkleBatch.merkle_nodes),
                selectinload(MerkleBatch.anchor_records),
            )
            .where(MerkleBatch.id == batch_id)
        )
        return result.scalar_one_or_none()

    async def close_batch(
        self,
        batch: MerkleBatch,
        merkle_root: str,
        leaf_count: int,
    ) -> MerkleBatch:
        """Cerrar un batch: establecer root, count y status."""
        batch.status = "closed"
        batch.merkle_root = merkle_root
        batch.leaf_count = leaf_count
        batch.closed_at = datetime.now(timezone.utc)
        await self.session.flush()
        await self.session.refresh(batch)
        return batch

    async def mark_anchored(self, batch: MerkleBatch) -> MerkleBatch:
        """Marcar un batch como anclado."""
        batch.status = "anchored"
        await self.session.flush()
        await self.session.refresh(batch)
        return batch
