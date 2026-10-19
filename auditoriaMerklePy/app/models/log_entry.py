"""
Modelo LogEntry — Registro de auditoría.

Representa un log individual recibido de una aplicación externa.
Su content_hash se usa como hoja en el Árbol de Merkle.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    String,
    DateTime,
    Integer,
    ForeignKey,
    Index,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.db.base import Base


class LogEntry(Base):
    """
    Registro de auditoría inmutable.

    Cada log representa un evento generado por una aplicación externa.
    Una vez almacenado y asignado a un batch cerrado, no debe modificarse.
    """

    __tablename__ = "log_entries"

    # Primary Key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Datos del evento
    source_app = Column(String(255), nullable=False, comment="Aplicación que generó el log")
    event_type = Column(String(255), nullable=False, comment="Tipo de evento (login, file_access, etc.)")
    severity = Column(
        String(50),
        nullable=False,
        default="info",
        comment="Nivel de severidad: info, warning, error, critical",
    )
    payload = Column(JSONB, nullable=False, comment="Datos completos del evento en JSON")

    # Hash criptográfico
    content_hash = Column(
        String(64),
        nullable=False,
        unique=True,
        comment="SHA-256 del payload serializado canónicamente",
    )

    # Relación con el batch de Merkle
    batch_id = Column(
        UUID(as_uuid=True),
        ForeignKey("merkle_batches.id"),
        nullable=True,
        comment="Batch al que pertenece (null si aún no asignado)",
    )
    leaf_index = Column(
        Integer,
        nullable=True,
        comment="Posición como hoja en el Merkle Tree del batch",
    )

    # Timestamps
    received_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        comment="Momento de recepción del log",
    )
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        comment="Timestamp de creación en BD",
    )

    # Relaciones ORM
    batch = relationship("MerkleBatch", back_populates="log_entries")

    # Índices para búsquedas eficientes
    __table_args__ = (
        Index("ix_log_entries_source_app", "source_app"),
        Index("ix_log_entries_event_type", "event_type"),
        Index("ix_log_entries_severity", "severity"),
        Index("ix_log_entries_received_at", "received_at"),
        Index("ix_log_entries_content_hash", "content_hash"),
        Index("ix_log_entries_batch_id", "batch_id"),
    )

    def __repr__(self) -> str:
        return (
            f"LogEntry(id={self.id}, source={self.source_app}, "
            f"event={self.event_type}, severity={self.severity})"
        )
