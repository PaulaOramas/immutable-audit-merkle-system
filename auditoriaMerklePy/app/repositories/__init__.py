"""
Repositorio base con operaciones CRUD genéricas.

Todos los demás repositorios heredan de este para evitar
duplicar lógica común.
"""

from typing import Generic, TypeVar, Type, Optional, List
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import Base

ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    """
    Repositorio genérico con operaciones CRUD básicas.

    Todas las operaciones son async para compatibilidad con FastAPI.
    """

    def __init__(self, model: Type[ModelType], session: AsyncSession):
        self.model = model
        self.session = session

    async def get_by_id(self, id: UUID) -> Optional[ModelType]:
        """Obtener una entidad por su ID."""
        result = await self.session.execute(
            select(self.model).where(self.model.id == id)
        )
        return result.scalar_one_or_none()

    async def get_all(
        self,
        offset: int = 0,
        limit: int = 100,
    ) -> List[ModelType]:
        """Obtener todas las entidades con paginación."""
        result = await self.session.execute(
            select(self.model).offset(offset).limit(limit)
        )
        return list(result.scalars().all())

    async def count(self) -> int:
        """Contar el total de entidades."""
        result = await self.session.execute(
            select(func.count()).select_from(self.model)
        )
        return result.scalar_one()

    async def create(self, entity: ModelType) -> ModelType:
        """Crear una nueva entidad."""
        self.session.add(entity)
        await self.session.flush()
        await self.session.refresh(entity)
        return entity

    async def create_many(self, entities: List[ModelType]) -> List[ModelType]:
        """Crear múltiples entidades."""
        self.session.add_all(entities)
        await self.session.flush()
        for entity in entities:
            await self.session.refresh(entity)
        return entities

    async def update(self, entity: ModelType) -> ModelType:
        """Actualizar una entidad existente."""
        await self.session.merge(entity)
        await self.session.flush()
        await self.session.refresh(entity)
        return entity

    async def delete(self, entity: ModelType) -> None:
        """Eliminar una entidad."""
        await self.session.delete(entity)
        await self.session.flush()
