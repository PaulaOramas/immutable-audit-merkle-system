"""
Modelo ApiKey — Claves API para aplicaciones que envían logs.

Cada aplicación registrada tiene una API key que debe incluir
en el header X-API-Key para autenticarse.
"""

import uuid
import secrets
from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    String,
    Boolean,
    DateTime,
)
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base


class ApiKey(Base):
    """
    Clave API para autenticación de aplicaciones.

    Cada aplicación source_app tiene una API key única.
    La key se genera automáticamente al crear el registro.
    """

    __tablename__ = "api_keys"

    # Primary Key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Datos de la API key
    key_hash = Column(
        String(128),
        nullable=False,
        unique=True,
        index=True,
        comment="Hash SHA-256 de la API key (nunca se almacena en texto plano)",
    )
    key_prefix = Column(
        String(8),
        nullable=False,
        comment="Prefijo de la key para identificación (ej: 'mka_ab12')",
    )
    app_name = Column(
        String(255),
        nullable=False,
        unique=True,
        comment="Nombre de la aplicación asociada",
    )
    description = Column(
        String(500),
        nullable=True,
        comment="Descripción de la aplicación",
    )

    # Estado
    is_active = Column(
        Boolean,
        nullable=False,
        default=True,
        comment="Si la key está activa",
    )

    # Timestamps
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    last_used_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Última vez que se usó la key",
    )
    expires_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Fecha de expiración (null = no expira)",
    )

    def __repr__(self) -> str:
        return (
            f"ApiKey(app={self.app_name}, prefix={self.key_prefix}, "
            f"active={self.is_active})"
        )
