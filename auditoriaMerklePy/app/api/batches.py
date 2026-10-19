"""
Router de la API de Batches — Consultar batches y su estado.

Endpoints:
    GET  /api/v1/batches                    — Listar batches con paginación
    GET  /api/v1/batches/{id}               — Detalle de un batch
    GET  /api/v1/batches/{id}/tree          — Estructura del árbol Merkle
    POST /api/v1/batches/{id}/anchor        — Anclar un batch en blockchain
    GET  /api/v1/batches/{id}/verify-onchain — Verificar anclaje on-chain
    GET  /api/v1/batches/{id}/cross-verify  — Verificación cruzada completa
    POST /api/v1/batches/{id}/timestamp     — Sellado RFC 3161 (TSA)
"""

from typing import Optional, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.config import settings
from app.db.session import get_async_session
from app.schemas.batch import (
    BatchSummaryResponse,
    BatchListResponse,
    BatchDetailResponse,
)
from app.services.batch_service import BatchService

router = APIRouter(prefix="/api/v1/batches", tags=["Batches"])


def get_batch_service(
    session: AsyncSession = Depends(get_async_session),
) -> BatchService:
    return BatchService(session)


# ============================================================
# Schemas de respuesta para anclaje
# ============================================================

class AnchorResponse(BaseModel):
    """Respuesta al anclar un batch."""
    batch_id: str
    batch_number: int
    merkle_root: str
    tx_hash: str
    block_number: int
    network: str
    status: str = "anchored"


class OnChainVerifyResponse(BaseModel):
    """Respuesta de verificación on-chain."""
    batch_id: str
    merkle_root: str
    found_onchain: bool
    anchor_id: int | None = None
    block_timestamp: int | None = None
    block_timestamp_utc: str | None = None
    db_anchor_tx: str | None = None


class CrossVerifyResponse(BaseModel):
    """Respuesta de verificación cruzada local vs on-chain."""
    batch_id: str
    batch_number: int
    batch_status: str
    local_merkle_root: str
    onchain_found: bool
    onchain_merkle_root: str | None = None
    onchain_anchor_id: int | None = None
    onchain_timestamp: int | None = None
    onchain_timestamp_utc: str | None = None
    tx_verification: dict | None = None
    local_anchor: dict | None = None
    tsa_anchor: dict | None = None
    roots_match: bool
    integrity: str  # verified, not_anchored, mismatch
    message: str


class TSAResponse(BaseModel):
    """Respuesta del sellado RFC 3161."""
    batch_id: str
    batch_number: int
    merkle_root: str
    tsa_url: str
    data_hash: str
    timestamp_info: dict | None = None
    status: str = "stamped"


# ============================================================
# GET /api/v1/batches
# ============================================================

@router.get(
    "",
    response_model=BatchListResponse,
    summary="Listar batches de auditoría",
    description=(
        "Retorna batches con su estado de anclaje. "
        "Filtrar opcionalmente por estado: open, closed, anchored."
    ),
)
async def list_batches(
    status: Optional[str] = Query(
        None,
        description="Filtrar por estado: open, closed, anchored",
    ),
    offset: int = Query(0, ge=0, description="Offset para paginación"),
    limit: int = Query(50, ge=1, le=200, description="Límite de resultados"),
    service: BatchService = Depends(get_batch_service),
):
    batches, total = await service.list_batches(
        status=status,
        offset=offset,
        limit=limit,
    )
    return BatchListResponse(
        items=batches,
        total=total,
        offset=offset,
        limit=limit,
    )


@router.post(
    "/{batch_id}/close",
    response_model=BatchDetailResponse,
    summary="Cerrar lote forzosamente",
    description="Fuerza el cierre del batch y genera el árbol de Merkle."
)
async def force_close_batch(
    batch_id: UUID,
    service: BatchService = Depends(get_batch_service),
    db: AsyncSession = Depends(get_async_session)
):
    from app.services.merkle_service import MerkleService
    merkle_service = MerkleService(db)
    
    batch = await service.batch_repo.get_by_id(batch_id)
    if not batch:
        raise HTTPException(404, "Batch not found")
    if batch.status != "open":
        raise HTTPException(400, "Batch is already closed or anchored")
        
    await merkle_service.close_batch(batch)
    
    # Reload to get relations
    reloaded_batch = await service.get_batch_detail(batch_id)
    
    return BatchDetailResponse(
        id=reloaded_batch.id,
        batch_number=reloaded_batch.batch_number,
        status=reloaded_batch.status,
        leaf_count=reloaded_batch.leaf_count,
        merkle_root=reloaded_batch.merkle_root,
        prev_batch_root=reloaded_batch.prev_batch_root,
        created_at=reloaded_batch.created_at,
        closed_at=reloaded_batch.closed_at,
        log_count=len(reloaded_batch.log_entries) if reloaded_batch.log_entries else 0,
        node_count=len(reloaded_batch.merkle_nodes) if reloaded_batch.merkle_nodes else 0,
        anchors=[
            AnchorRecordSchema.model_validate(anchor)
            for anchor in (reloaded_batch.anchor_records or [])
        ],
    )

# ============================================================
# GET /api/v1/batches/{id}
# ============================================================

@router.get(
    "/{batch_id}",
    response_model=BatchDetailResponse,
    summary="Detalle de un batch",
    description=(
        "Retorna los datos completos de un batch incluyendo: "
        "Merkle Root, cantidad de logs y nodos, y registros de anclaje."
    ),
)
async def get_batch_detail(
    batch_id: UUID,
    service: BatchService = Depends(get_batch_service),
):
    batch = await service.get_batch_detail(batch_id)
    if not batch:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "batch_no_encontrado",
                "message": f"No existe un batch con ID {batch_id}",
            },
        )

    return BatchDetailResponse(
        id=batch.id,
        batch_number=batch.batch_number,
        status=batch.status,
        leaf_count=batch.leaf_count,
        merkle_root=batch.merkle_root,
        prev_batch_root=batch.prev_batch_root,
        created_at=batch.created_at,
        closed_at=batch.closed_at,
        log_count=len(batch.log_entries) if batch.log_entries else 0,
        node_count=len(batch.merkle_nodes) if batch.merkle_nodes else 0,
        anchors=batch.anchor_records or [],
    )


# ============================================================
# POST /api/v1/batches/{id}/anchor — Anclar en blockchain
# ============================================================

@router.post(
    "/{batch_id}/anchor",
    response_model=AnchorResponse,
    summary="Anclar un batch en blockchain",
    description=(
        "Envía el Merkle Root del batch al smart contract MerkleAnchor. "
        "Requiere que el batch esté cerrado (status='closed'). "
        "Espera la confirmación de la transacción y guarda la evidencia."
    ),
)
async def anchor_batch(
    batch_id: UUID,
    session: AsyncSession = Depends(get_async_session),
):
    if not settings.ANCHOR_ENABLED:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "anclaje_deshabilitado",
                "message": "El anclaje en blockchain no está habilitado",
            },
        )

    from app.services.anchor_service import (
        AnchorService,
        AnchorServiceError,
        BlockchainConnectionError,
        ContractCallError,
    )
    from app.repositories.merkle_batch_repo import MerkleBatchRepository

    # Obtener el batch
    batch_repo = MerkleBatchRepository(session)
    batch = await batch_repo.get_by_id(batch_id)

    if not batch:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "batch_no_encontrado",
                "message": f"No existe un batch con ID {batch_id}",
            },
        )

    if batch.status == "anchored":
        raise HTTPException(
            status_code=409,
            detail={
                "error": "batch_ya_anclado",
                "message": f"El batch #{batch.batch_number} ya está anclado",
            },
        )

    if batch.status != "closed":
        raise HTTPException(
            status_code=409,
            detail={
                "error": "batch_no_cerrado",
                "message": (
                    f"El batch #{batch.batch_number} tiene status='{batch.status}'. "
                    "Solo se pueden anclar batches cerrados."
                ),
            },
        )

    try:
        service = AnchorService(session)
        anchor = await service.anchor_batch(batch)

        return AnchorResponse(
            batch_id=str(batch.id),
            batch_number=batch.batch_number,
            merkle_root=batch.merkle_root,
            tx_hash=anchor.tx_hash,
            block_number=anchor.block_number,
            network=anchor.network,
        )

    except BlockchainConnectionError as e:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "blockchain_desconectada",
                "message": str(e),
            },
        )
    except ContractCallError as e:
        raise HTTPException(
            status_code=502,
            detail={
                "error": "error_contrato",
                "message": str(e),
            },
        )
    except AnchorServiceError as e:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "error_anclaje",
                "message": str(e),
            },
        )


# ============================================================
# GET /api/v1/batches/{id}/verify-onchain — Verificación on-chain
# ============================================================

@router.get(
    "/{batch_id}/verify-onchain",
    response_model=OnChainVerifyResponse,
    summary="Verificar anclaje on-chain",
    description=(
        "Consulta directamente el smart contract para verificar si "
        "el Merkle Root de este batch fue anclado en la blockchain. "
        "Compara con el registro local (AnchorRecord)."
    ),
)
async def verify_batch_onchain(
    batch_id: UUID,
    session: AsyncSession = Depends(get_async_session),
):
    if not settings.ANCHOR_ENABLED:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "anclaje_deshabilitado",
                "message": "El anclaje en blockchain no está habilitado",
            },
        )

    from app.services.anchor_service import (
        AnchorService,
        AnchorServiceError,
    )
    from app.repositories.merkle_batch_repo import MerkleBatchRepository
    from app.repositories.anchor_record_repo import AnchorRecordRepository

    batch_repo = MerkleBatchRepository(session)
    batch = await batch_repo.get_by_id(batch_id)

    if not batch:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "batch_no_encontrado",
                "message": f"No existe un batch con ID {batch_id}",
            },
        )

    if not batch.merkle_root:
        raise HTTPException(
            status_code=409,
            detail={
                "error": "batch_sin_root",
                "message": f"El batch #{batch.batch_number} no tiene Merkle Root",
            },
        )

    try:
        service = AnchorService(session)
        result = service.verify_on_chain(batch.merkle_root)
    except AnchorServiceError as e:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "blockchain_error",
                "message": str(e),
            },
        )

    # Obtener el anchor local para comparar
    anchor_repo = AnchorRecordRepository(session)
    local_anchor = await anchor_repo.get_latest_by_batch(batch_id)

    return OnChainVerifyResponse(
        batch_id=str(batch.id),
        merkle_root=batch.merkle_root,
        found_onchain=result["found"],
        anchor_id=result["anchor_id"],
        block_timestamp=result["timestamp"],
        block_timestamp_utc=result["block_timestamp_utc"],
        db_anchor_tx=local_anchor.tx_hash if local_anchor else None,
    )


# ============================================================
# GET /api/v1/batches/{id}/cross-verify — Verificación cruzada (4.4)
# ============================================================

@router.get(
    "/{batch_id}/cross-verify",
    response_model=CrossVerifyResponse,
    summary="Verificación cruzada completa",
    description=(
        "Recupera el tx_hash del anclaje, consulta el smart contract "
        "para obtener el Merkle Root almacenado on-chain, y lo compara "
        "con el root local. Si coinciden → integridad confirmada externamente."
    ),
)
async def cross_verify_batch(
    batch_id: UUID,
    session: AsyncSession = Depends(get_async_session),
):
    if not settings.ANCHOR_ENABLED:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "anclaje_deshabilitado",
                "message": "El anclaje en blockchain no está habilitado",
            },
        )

    from app.services.anchor_service import (
        AnchorService,
        AnchorServiceError,
    )

    try:
        service = AnchorService(session)
        result = await service.cross_verify_batch(batch_id)
        return CrossVerifyResponse(**result)

    except AnchorServiceError as e:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "error_verificacion",
                "message": str(e),
            },
        )


# ============================================================
# POST /api/v1/batches/{id}/timestamp — Sellado RFC 3161 (4.5)
# ============================================================

@router.post(
    "/{batch_id}/timestamp",
    response_model=TSAResponse,
    summary="Sellar batch con TSA RFC 3161",
    description=(
        "Envía el Merkle Root del batch a FreeTSA.org para obtener "
        "un token de sellado de tiempo RFC 3161. Proporciona evidencia "
        "adicional e independiente de la existencia de los datos."
    ),
)
async def timestamp_batch(
    batch_id: UUID,
    session: AsyncSession = Depends(get_async_session),
):
    from app.services.anchor_service import (
        AnchorService,
        AnchorServiceError,
        TSAError,
    )
    from app.repositories.merkle_batch_repo import MerkleBatchRepository

    batch_repo = MerkleBatchRepository(session)
    batch = await batch_repo.get_by_id(batch_id)

    if not batch:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "batch_no_encontrado",
                "message": f"No existe un batch con ID {batch_id}",
            },
        )

    if not batch.merkle_root:
        raise HTTPException(
            status_code=409,
            detail={
                "error": "batch_sin_root",
                "message": f"El batch #{batch.batch_number} no tiene Merkle Root",
            },
        )

    try:
        service = AnchorService(session)
        anchor = await service.timestamp_batch(batch)

        return TSAResponse(
            batch_id=str(batch.id),
            batch_number=batch.batch_number,
            merkle_root=batch.merkle_root,
            tsa_url=anchor.anchor_metadata.get("tsa_url", ""),
            data_hash=anchor.anchor_metadata.get("data_hash_sha256", ""),
            timestamp_info=anchor.anchor_metadata.get("tsr_info"),
        )

    except TSAError as e:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "error_tsa",
                "message": str(e),
            },
        )
    except AnchorServiceError as e:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "error_anclaje",
                "message": str(e),
            },
        )


# ============================================================
# GET /api/v1/batches/{id}/tree — Estructura del árbol Merkle
# ============================================================

class TreeNodeResponse(BaseModel):
    """Nodo individual del árbol Merkle."""
    level: int
    position: int
    hash_value: str
    log_id: str | None = None
    log_label: str | None = None


class MerkleTreeResponse(BaseModel):
    """Estructura completa del árbol Merkle de un batch."""
    batch_id: str
    batch_number: int
    status: str
    merkle_root: str | None
    total_levels: int
    total_nodes: int
    levels: dict[int, list[TreeNodeResponse]]


@router.get(
    "/{batch_id}/tree",
    response_model=MerkleTreeResponse,
    summary="Estructura del árbol Merkle",
    description=(
        "Retorna todos los nodos del árbol Merkle de un batch, "
        "organizados por niveles. Level 0 = hojas, nivel máximo = raíz. "
        "Las hojas incluyen el ID del log asociado para referencia."
    ),
)
async def get_batch_tree(
    batch_id: UUID,
    session: AsyncSession = Depends(get_async_session),
):
    from app.repositories.merkle_batch_repo import MerkleBatchRepository
    from app.repositories.merkle_node_repo import MerkleNodeRepository
    from app.models.log_entry import LogEntry

    batch_repo = MerkleBatchRepository(session)
    batch = await batch_repo.get_by_id(batch_id)

    if not batch:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "batch_no_encontrado",
                "message": f"No existe un batch con ID {batch_id}",
            },
        )

    node_repo = MerkleNodeRepository(session)
    all_nodes = await node_repo.get_all_by_batch(batch_id)

    if not all_nodes:
        return MerkleTreeResponse(
            batch_id=str(batch.id),
            batch_number=batch.batch_number,
            status=batch.status,
            merkle_root=batch.merkle_root,
            total_levels=0,
            total_nodes=0,
            levels={},
        )

    # Get leaf hashes and map them to log entries
    leaf_nodes = [n for n in all_nodes if n.level == 0]
    leaf_hashes = [n.hash_value for n in leaf_nodes]

    # Query log entries that belong to this batch, ordered by leaf_index
    log_result = await session.execute(
        select(LogEntry)
        .where(
            and_(
                LogEntry.batch_id == batch_id,
                LogEntry.leaf_index.isnot(None),
            )
        )
        .order_by(LogEntry.leaf_index)
    )
    logs = list(log_result.scalars().all())

    # Map leaf position -> log info
    leaf_log_map = {}
    for log_entry in logs:
        if log_entry.leaf_index is not None:
            leaf_log_map[log_entry.leaf_index] = {
                "log_id": str(log_entry.id),
                "log_label": f"LOG-{log_entry.leaf_index}",
            }

    # Organize nodes by level
    max_level = max(n.level for n in all_nodes)
    levels = {}
    for level in range(max_level + 1):
        level_nodes = sorted(
            [n for n in all_nodes if n.level == level],
            key=lambda n: n.position,
        )
        levels[level] = [
            TreeNodeResponse(
                level=n.level,
                position=n.position,
                hash_value=n.hash_value,
                log_id=leaf_log_map.get(n.position, {}).get("log_id") if n.level == 0 else None,
                log_label=leaf_log_map.get(n.position, {}).get("log_label") if n.level == 0 else None,
            )
            for n in level_nodes
        ]

    return MerkleTreeResponse(
        batch_id=str(batch.id),
        batch_number=batch.batch_number,
        status=batch.status,
        merkle_root=batch.merkle_root,
        total_levels=max_level + 1,
        total_nodes=len(all_nodes),
        levels=levels,
    )
