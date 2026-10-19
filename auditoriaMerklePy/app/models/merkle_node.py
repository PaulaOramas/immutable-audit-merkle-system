"""
Modelo MerkleNode — Nodo del Árbol de Merkle.

Representa un nodo en el árbol: puede ser una hoja (level=0),
un nodo intermedio, o la raíz (level más alto).
Almacena la estructura completa del árbol para poder regenerar
proofs sin recalcular.
"""

import uuid

from sqlalchemy import (
    Column,
    String,
    Integer,
    ForeignKey,
    DateTime,
    Index,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime, timezone

from app.db.base import Base


class MerkleNode(Base):
    """
    Nodo del Árbol de Merkle persistido en base de datos.

    Niveles:
    - level=0: hojas (corresponden a content_hash de un LogEntry)
    - level=N: nodos intermedios o raíz
    """

    __tablename__ = "merkle_nodes"

    # Primary Key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Relación con el batch
    batch_id = Column(
        UUID(as_uuid=True),
        ForeignKey("merkle_batches.id"),
        nullable=False,
        comment="Batch al que pertenece este nodo",
    )

    # Posición en el árbol
    level = Column(
        Integer,
        nullable=False,
        comment="Nivel del nodo: 0=hoja, N=raíz",
    )
    position = Column(
        Integer,
        nullable=False,
        comment="Posición dentro del nivel (0-based, izquierda a derecha)",
    )

    # Hash del nodo
    hash_value = Column(
        String(64),
        nullable=False,
        comment="SHA-256 del nodo (hoja: hash del log, interno: combine de hijos)",
    )

    # Referencias a hijos (null en hojas)
    left_child_id = Column(
        UUID(as_uuid=True),
        ForeignKey("merkle_nodes.id"),
        nullable=True,
        comment="Hijo izquierdo (null en hojas)",
    )
    right_child_id = Column(
        UUID(as_uuid=True),
        ForeignKey("merkle_nodes.id"),
        nullable=True,
        comment="Hijo derecho (null en hojas)",
    )

    # Timestamps
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    # Relaciones ORM
    batch = relationship("MerkleBatch", back_populates="merkle_nodes")
    left_child = relationship(
        "MerkleNode",
        foreign_keys=[left_child_id],
        remote_side=[id],
        uselist=False,
    )
    right_child = relationship(
        "MerkleNode",
        foreign_keys=[right_child_id],
        remote_side=[id],
        uselist=False,
    )

    # Índices
    __table_args__ = (
        Index("ix_merkle_nodes_batch_level", "batch_id", "level"),
        Index("ix_merkle_nodes_batch_level_pos", "batch_id", "level", "position"),
    )

    def __repr__(self) -> str:
        return (
            f"MerkleNode(level={self.level}, pos={self.position}, "
            f"hash={self.hash_value[:16]}...)"
        )
