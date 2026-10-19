"""
Modelo AnchorRecord — Registro de anclaje externo.

Almacena la evidencia de que un Merkle Root fue anclado en una
fuente de confianza externa (blockchain o autoridad de sellado de tiempo).
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    String,
    Integer,
    ForeignKey,
    DateTime,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.db.base import Base


class AnchorRecord(Base):
    """
    Registro de anclaje externo de un Merkle Root.

    Cada vez que un batch se ancla en una fuente externa (ej: blockchain),
    se crea un registro con la evidencia de la transacción.
    """

    __tablename__ = "anchor_records"

    # Primary Key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Relación con el batch
    batch_id = Column(
        UUID(as_uuid=True),
        ForeignKey("merkle_batches.id"),
        nullable=False,
        comment="Batch cuyo Merkle Root se ancló",
    )

    # Datos del anclaje
    merkle_root = Column(
        String(64),
        nullable=False,
        comment="Copia del Merkle Root que se ancló",
    )
    anchor_type = Column(
        String(50),
        nullable=False,
        comment="Tipo de anclaje: blockchain, timestamp_authority",
    )

    # Datos de blockchain (nullable, solo aplican para anchor_type=blockchain)
    tx_hash = Column(
        String(128),
        nullable=True,
        comment="Hash de la transacción en blockchain",
    )
    block_number = Column(
        Integer,
        nullable=True,
        comment="Número de bloque en la blockchain",
    )
    network = Column(
        String(50),
        nullable=True,
        comment="Red utilizada: ganache, sepolia, etc.",
    )

    # Metadatos adicionales (flexible para diferentes tipos de anclaje)
    anchor_metadata = Column(
        JSONB,
        nullable=True,
        comment="Datos adicionales del anclaje (respuesta TSA, gas usado, etc.)",
    )

    # Timestamps
    anchored_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        comment="Momento del anclaje externo",
    )

    # Relaciones ORM
    batch = relationship("MerkleBatch", back_populates="anchor_records")

    def __repr__(self) -> str:
        return (
            f"AnchorRecord(type={self.anchor_type}, network={self.network}, "
            f"tx={self.tx_hash[:16] + '...' if self.tx_hash else 'N/A'})"
        )
