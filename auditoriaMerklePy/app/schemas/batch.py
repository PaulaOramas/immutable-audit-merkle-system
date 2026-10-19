"""
Schemas Pydantic para Batches, Verificación y Merkle Proofs.
"""

from datetime import datetime
from typing import Optional, List
from uuid import UUID

from pydantic import BaseModel, Field


# ============================================================
# Merkle Proof schemas
# ============================================================

class ProofStepSchema(BaseModel):
    """Un paso en la prueba de Merkle."""
    hash: str = Field(..., description="Hash del nodo hermano")
    position: str = Field(..., description="Posición del hermano: 'left' o 'right'")


class MerkleProofResponse(BaseModel):
    """Respuesta con la prueba de Merkle de un log."""
    log_id: UUID
    content_hash: str = Field(..., description="Hash del log (hoja del árbol)")
    leaf_index: int = Field(..., description="Índice de la hoja en el batch")
    batch_id: UUID
    batch_number: int
    merkle_root: str = Field(..., description="Raíz del Merkle Tree del batch")
    proof: List[ProofStepSchema] = Field(..., description="Pasos de la prueba Merkle")
    is_anchored: bool = Field(..., description="Si el batch fue anclado externamente")


# ============================================================
# Verify schemas
# ============================================================

class VerifyRequest(BaseModel):
    """Request para verificar un log con su prueba."""
    content_hash: str = Field(
        ...,
        min_length=64,
        max_length=64,
        description="Hash SHA-256 del log a verificar",
    )
    merkle_root: str = Field(
        ...,
        min_length=64,
        max_length=64,
        description="Merkle Root esperado",
    )
    proof: List[ProofStepSchema] = Field(
        ...,
        description="Pasos de la prueba Merkle",
    )


class VerifyResponse(BaseModel):
    """Resultado de la verificación."""
    is_valid: bool = Field(..., description="Si la prueba es válida")
    content_hash: str
    merkle_root: str
    message: str = Field(..., description="Mensaje descriptivo del resultado")


# ============================================================
# Batch schemas
# ============================================================

class AnchorRecordSchema(BaseModel):
    """Datos del anclaje externo de un batch."""
    id: UUID
    anchor_type: str
    tx_hash: Optional[str] = None
    block_number: Optional[int] = None
    network: Optional[str] = None
    raw_proof: Optional[dict] = None
    anchored_at: datetime

    model_config = {"from_attributes": True}


class BatchSummaryResponse(BaseModel):
    """Resumen de un batch para listados."""
    id: UUID
    batch_number: int
    status: str
    leaf_count: int
    merkle_root: Optional[str] = None
    prev_batch_root: Optional[str] = None
    created_at: datetime
    closed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class BatchListResponse(BaseModel):
    """Respuesta paginada de batches."""
    items: List[BatchSummaryResponse]
    total: int
    offset: int
    limit: int


class BatchDetailResponse(BaseModel):
    """Detalle completo de un batch."""
    id: UUID
    batch_number: int
    status: str
    leaf_count: int
    merkle_root: Optional[str] = None
    prev_batch_root: Optional[str] = None
    created_at: datetime
    closed_at: Optional[datetime] = None
    log_count: int = Field(..., description="Cantidad de logs en el batch")
    node_count: int = Field(..., description="Cantidad de nodos del árbol")
    anchors: List[AnchorRecordSchema] = Field(
        default_factory=list,
        description="Registros de anclaje externo",
    )
