"""
Modelo AuditUser — Usuarios de la interfaz de auditoría.

Los usuarios se autentican con username/password y reciben un JWT.
Solo los usuarios autenticados pueden acceder a endpoints de
consulta, verificación, reportes y auditoría.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    String,
    Boolean,
    DateTime,
)
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base


class AuditUser(Base):
    """
    Usuario de la interfaz de auditoría.

    Los usuarios pueden consultar logs, generar reportes y verificar
    pruebas Merkle. No pueden ingestar logs (eso es para API keys).
    """

    __tablename__ = "audit_users"

    # Primary Key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Credenciales
    username = Column(
        String(100),
        nullable=False,
        unique=True,
        index=True,
        comment="Nombre de usuario único",
    )
    password_hash = Column(
        String(128),
        nullable=False,
        comment="Hash bcrypt del password",
    )

    # Perfil
    full_name = Column(
        String(255),
        nullable=True,
        comment="Nombre completo del usuario",
    )
    role = Column(
        String(50),
        nullable=False,
        default="auditor",
        comment="Rol: admin, auditor",
    )

    # Estado
    is_active = Column(
        Boolean,
        nullable=False,
        default=True,
    )

    # Timestamps
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    last_login_at = Column(
        DateTime(timezone=True),
        nullable=True,
    )

    def __repr__(self) -> str:
        return f"AuditUser(username={self.username}, role={self.role})"
