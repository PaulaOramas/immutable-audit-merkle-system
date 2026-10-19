"""
Modelo MerkleBatch — Agrupación de logs con su Árbol de Merkle.

Un batch agrupa N logs, construye su Árbol de Merkle y produce
un Merkle Root que luego puede anclarse externamente.

Ciclo de vida: open → closed → anchored
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    String,
    DateTime,
    Integer,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.base import Base


class MerkleBatch(Base):
    """
    Agrupación de logs con su Árbol de Merkle.

    Estados:
    - open: Recibiendo logs, el árbol aún no se construye.
    - closed: No se aceptan más logs, el árbol está construido.
    - anchored: El Merkle Root fue anclado externamente (blockchain/TSA).
    """

    __tablename__ = "merkle_batches"

    # Primary Key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Identificación secuencial
    batch_number = Column(
        Integer,
        nullable=False,
        unique=True,
        autoincrement=True,
        comment="Número secuencial del batch",
    )

    # Datos del árbol
    leaf_count = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Número de hojas (logs) en este batch",
    )
    merkle_root = Column(
        String(64),
        nullable=True,
        comment="Hash raíz del Merkle Tree (null mientras está open)",
    )
    prev_batch_root = Column(
        String(64),
        nullable=True,
        comment="Merkle Root del batch anterior (encadenamiento)",
    )

    # Estado del batch
    status = Column(
        String(20),
        nullable=False,
        default="open",
        comment="Estado: open, closed, anchored",
    )

    # Timestamps
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        comment="Momento de creación del batch",
    )
    closed_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Momento en que se cerró el batch",
    )

    # Relaciones ORM
    log_entries = relationship("LogEntry", back_populates="batch", order_by="LogEntry.leaf_index")
    merkle_nodes = relationship("MerkleNode", back_populates="batch", cascade="all, delete-orphan")
    anchor_records = relationship("AnchorRecord", back_populates="batch", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return (
            f"MerkleBatch(id={self.id}, number={self.batch_number}, "
            f"leaves={self.leaf_count}, status={self.status})"
        )
