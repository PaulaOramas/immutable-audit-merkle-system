"""
Repositorio de LogEntry — Operaciones de acceso a datos para logs de auditoría.
"""

from datetime import datetime
from typing import Optional, List
from uuid import UUID

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.log_entry import LogEntry
from app.repositories import BaseRepository


class LogEntryRepository(BaseRepository[LogEntry]):
    """
    Repositorio para operaciones sobre LogEntry.

    Extiende BaseRepository con queries específicas para logs:
    filtrado por app, tipo, severidad, rango de fechas, y batch.
    """

    def __init__(self, session: AsyncSession):
        super().__init__(LogEntry, session)

    async def get_by_content_hash(self, content_hash: str) -> Optional[LogEntry]:
        """Buscar un log por su hash de contenido."""
        result = await self.session.execute(
            select(LogEntry).where(LogEntry.content_hash == content_hash)
        )
        return result.scalar_one_or_none()

    async def get_by_batch(
        self,
        batch_id: UUID,
        offset: int = 0,
        limit: int = 100,
    ) -> List[LogEntry]:
        """Obtener todos los logs de un batch específico, ordenados por leaf_index."""
        result = await self.session.execute(
            select(LogEntry)
            .where(LogEntry.batch_id == batch_id)
            .order_by(LogEntry.leaf_index)
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_unassigned(self, limit: int = 100) -> List[LogEntry]:
        """Obtener logs que aún no han sido asignados a un batch."""
        result = await self.session.execute(
            select(LogEntry)
            .where(LogEntry.batch_id.is_(None))
            .order_by(LogEntry.received_at)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def count_unassigned(self) -> int:
        """Contar logs sin asignar a un batch."""
        from sqlalchemy import func
        result = await self.session.execute(
            select(func.count())
            .select_from(LogEntry)
            .where(LogEntry.batch_id.is_(None))
        )
        return result.scalar_one()

    async def search(
        self,
        source_app: Optional[str] = None,
        event_type: Optional[str] = None,
        severity: Optional[str] = None,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
        offset: int = 0,
        limit: int = 100,
    ) -> List[LogEntry]:
        """
        Buscar logs con filtros opcionales.

        Todos los filtros son AND. Si no se especifica un filtro, no se aplica.
        """
        query = select(LogEntry)
        conditions = []

        if source_app:
            conditions.append(LogEntry.source_app == source_app)
        if event_type:
            conditions.append(LogEntry.event_type == event_type)
        if severity:
            conditions.append(LogEntry.severity == severity)
        if from_date:
            conditions.append(LogEntry.received_at >= from_date)
        if to_date:
            conditions.append(LogEntry.received_at <= to_date)

        if conditions:
            query = query.where(and_(*conditions))

        query = query.order_by(LogEntry.received_at.desc()).offset(offset).limit(limit)

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def assign_to_batch(
        self,
        log_ids: List[UUID],
        batch_id: UUID,
    ) -> None:
        """Asignar una lista de logs a un batch, estableciendo sus leaf_index."""
        for index, log_id in enumerate(log_ids):
            log = await self.get_by_id(log_id)
            if log:
                log.batch_id = batch_id
                log.leaf_index = index
        await self.session.flush()
