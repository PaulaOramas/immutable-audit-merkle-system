"""
Schemas Pydantic para LogEntry.

Define las estructuras de request/response para la API REST.
Pydantic valida automáticamente los tipos y restricciones.
"""

from datetime import datetime
from typing import Optional, List
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


# ============================================================
# Request schemas
# ============================================================

class LogEntryCreate(BaseModel):
    """Schema para crear un log individual."""

    source_app: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Nombre de la aplicación que genera el log",
        examples=["app_web", "file_server", "api_gateway"],
    )
    event_type: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Tipo de evento registrado",
        examples=["login", "file_access", "db_query"],
    )
    severity: str = Field(
        default="info",
        description="Nivel de severidad del evento",
        examples=["info", "warning", "error", "critical"],
    )
    payload: dict = Field(
        ...,
        description="Datos completos del evento en formato JSON",
        examples=[{"user": "admin", "action": "login", "ip": "192.168.1.1"}],
    )

    @field_validator("severity")
    @classmethod
    def validate_severity(cls, v: str) -> str:
        allowed = {"info", "warning", "error", "critical"}
        if v.lower() not in allowed:
            raise ValueError(
                f"Severidad '{v}' no válida. Valores permitidos: {', '.join(sorted(allowed))}"
            )
        return v.lower()

    @field_validator("payload")
    @classmethod
    def validate_payload_not_empty(cls, v: dict) -> dict:
        if not v:
            raise ValueError("El payload no puede estar vacío")
        return v


class LogEntryBatchCreate(BaseModel):
    """Schema para crear múltiples logs de una vez."""

    logs: List[LogEntryCreate] = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Lista de logs a ingestar (1 a 500)",
    )


# ============================================================
# Response schemas
# ============================================================

class LogEntryResponse(BaseModel):
    """Schema de respuesta para un log individual."""

    id: UUID
    source_app: str
    event_type: str
    severity: str
    payload: dict
    content_hash: str
    batch_id: Optional[UUID] = None
    leaf_index: Optional[int] = None
    received_at: datetime
    created_at: datetime

    model_config = {"from_attributes": True}


class LogEntryListResponse(BaseModel):
    """Schema de respuesta para listado paginado de logs."""

    items: List[LogEntryResponse]
    total: int
    offset: int
    limit: int
