"""
Repositorio de MerkleNode — Operaciones de acceso a datos para nodos del árbol.
"""

from typing import Optional, List
from uuid import UUID

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.merkle_node import MerkleNode
from app.repositories import BaseRepository


class MerkleNodeRepository(BaseRepository[MerkleNode]):
    """
    Repositorio para operaciones sobre MerkleNode.

    Permite consultar la estructura del árbol persistido:
    hojas, niveles, raíz, y hermanos para reconstruir proofs.
    """

    def __init__(self, session: AsyncSession):
        super().__init__(MerkleNode, session)

    async def get_by_batch_and_level(
        self,
        batch_id: UUID,
        level: int,
    ) -> List[MerkleNode]:
        """Obtener todos los nodos de un nivel específico de un batch."""
        result = await self.session.execute(
            select(MerkleNode)
            .where(
                and_(
                    MerkleNode.batch_id == batch_id,
                    MerkleNode.level == level,
                )
            )
            .order_by(MerkleNode.position)
        )
        return list(result.scalars().all())

    async def get_leaves(self, batch_id: UUID) -> List[MerkleNode]:
        """Obtener todas las hojas (level=0) de un batch, ordenadas por posición."""
        return await self.get_by_batch_and_level(batch_id, level=0)

    async def get_root(self, batch_id: UUID) -> Optional[MerkleNode]:
        """Obtener el nodo raíz de un batch (el de mayor nivel)."""
        from sqlalchemy import func
        # Encontrar el nivel máximo
        max_level_result = await self.session.execute(
            select(func.max(MerkleNode.level))
            .where(MerkleNode.batch_id == batch_id)
        )
        max_level = max_level_result.scalar_one_or_none()

        if max_level is None:
            return None

        result = await self.session.execute(
            select(MerkleNode)
            .where(
                and_(
                    MerkleNode.batch_id == batch_id,
                    MerkleNode.level == max_level,
                    MerkleNode.position == 0,
                )
            )
        )
        return result.scalar_one_or_none()

    async def get_node_at(
        self,
        batch_id: UUID,
        level: int,
        position: int,
    ) -> Optional[MerkleNode]:
        """Obtener un nodo específico por su posición en el árbol."""
        result = await self.session.execute(
            select(MerkleNode)
            .where(
                and_(
                    MerkleNode.batch_id == batch_id,
                    MerkleNode.level == level,
                    MerkleNode.position == position,
                )
            )
        )
        return result.scalar_one_or_none()

    async def get_all_by_batch(self, batch_id: UUID) -> List[MerkleNode]:
        """Obtener todos los nodos de un batch, ordenados por nivel y posición."""
        result = await self.session.execute(
            select(MerkleNode)
            .where(MerkleNode.batch_id == batch_id)
            .order_by(MerkleNode.level, MerkleNode.position)
        )
        return list(result.scalars().all())

    async def bulk_create(self, nodes: List[MerkleNode]) -> List[MerkleNode]:
        """Crear múltiples nodos de una vez (eficiente para persistir un árbol completo)."""
        self.session.add_all(nodes)
        await self.session.flush()
        return nodes
