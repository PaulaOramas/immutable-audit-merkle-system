"""
Schemas Pydantic para los endpoints de Auditoría.

Incluye:
- Resultado de verificación masiva de integridad
- Reporte de auditoría
- Listado de anclajes
"""

from datetime import datetime
from typing import Optional, List
from uuid import UUID

from pydantic import BaseModel, Field


# ============================================================
# Integrity Check
# ============================================================

class BatchIntegrityResult(BaseModel):
    """Resultado de la verificación de integridad de un batch."""
    batch_id: UUID
    batch_number: int
    status: str
    leaf_count: int
    merkle_root: Optional[str] = None
    root_matches: Optional[bool] = Field(
        None,
        description="True si el root recalculado coincide con el almacenado",
    )
    error: Optional[str] = Field(
        None,
        description="Mensaje de error si no se pudo verificar",
    )


class IntegrityCheckResponse(BaseModel):
    """Resultado de la verificación masiva de integridad."""
    total_batches: int = Field(..., description="Total de batches verificados")
    valid_batches: int = Field(..., description="Batches con integridad válida")
    invalid_batches: int = Field(..., description="Batches con integridad comprometida")
    skipped_batches: int = Field(
        ...,
        description="Batches omitidos (ej: abiertos, sin nodos)",
    )
    overall_integrity: bool = Field(
        ...,
        description="True si TODOS los batches cerrados son válidos",
    )
    checked_at: datetime = Field(..., description="Timestamp de la verificación")
    details: List[BatchIntegrityResult] = Field(
        ...,
        description="Detalle por batch",
    )


# ============================================================
# Audit Report
# ============================================================

class AuditReportBatchSummary(BaseModel):
    """Resumen de un batch para el reporte."""
    batch_number: int
    status: str
    leaf_count: int
    merkle_root: Optional[str] = None
    created_at: datetime
    closed_at: Optional[datetime] = None
    is_anchored: bool
    anchor_tx: Optional[str] = None
    anchor_network: Optional[str] = None


class AuditReportResponse(BaseModel):
    """Reporte completo de auditoría del sistema."""
    report_generated_at: datetime
    system_summary: dict = Field(
        ...,
        description="Resumen general: total logs, batches, etc.",
    )
    integrity_status: dict = Field(
        ...,
        description="Estado de integridad del sistema",
    )
    batches: List[AuditReportBatchSummary] = Field(
        ...,
        description="Resumen de cada batch",
    )


# ============================================================
# Anchors
# ============================================================

class AnchorResponse(BaseModel):
    """Registro de anclaje individual."""
    id: UUID
    batch_id: UUID
    batch_number: Optional[int] = None
    merkle_root: str
    anchor_type: str
    tx_hash: Optional[str] = None
    block_number: Optional[int] = None
    network: Optional[str] = None
    anchor_metadata: Optional[dict] = None
    anchored_at: datetime

    model_config = {"from_attributes": True}


class AnchorListResponse(BaseModel):
    """Respuesta paginada de anclajes."""
    items: List[AnchorResponse]
    total: int
    offset: int
    limit: int
