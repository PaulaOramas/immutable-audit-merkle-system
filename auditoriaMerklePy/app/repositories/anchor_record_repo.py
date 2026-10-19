"""
Repositorio de AnchorRecord — Operaciones de acceso a datos para anclajes.
"""

from typing import Optional, List
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.anchor_record import AnchorRecord
from app.repositories import BaseRepository


class AnchorRecordRepository(BaseRepository[AnchorRecord]):
    """
    Repositorio para operaciones sobre AnchorRecord.

    Permite consultar los registros de anclaje externo (blockchain/TSA).
    """

    def __init__(self, session: AsyncSession):
        super().__init__(AnchorRecord, session)

    async def get_by_batch(self, batch_id: UUID) -> List[AnchorRecord]:
        """Obtener todos los anclajes de un batch."""
        result = await self.session.execute(
            select(AnchorRecord)
            .where(AnchorRecord.batch_id == batch_id)
            .order_by(AnchorRecord.anchored_at.desc())
        )
        return list(result.scalars().all())

    async def get_by_tx_hash(self, tx_hash: str) -> Optional[AnchorRecord]:
        """Buscar un anclaje por su hash de transacción blockchain."""
        result = await self.session.execute(
            select(AnchorRecord)
            .where(AnchorRecord.tx_hash == tx_hash)
        )
        return result.scalar_one_or_none()

    async def get_by_network(
        self,
        network: str,
        offset: int = 0,
        limit: int = 100,
    ) -> List[AnchorRecord]:
        """Obtener anclajes filtrados por red (ganache, sepolia, etc.)."""
        result = await self.session.execute(
            select(AnchorRecord)
            .where(AnchorRecord.network == network)
            .order_by(AnchorRecord.anchored_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_latest_by_batch(self, batch_id: UUID) -> Optional[AnchorRecord]:
        """Obtener el anclaje más reciente de un batch."""
        result = await self.session.execute(
            select(AnchorRecord)
            .where(AnchorRecord.batch_id == batch_id)
            .order_by(AnchorRecord.anchored_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()
