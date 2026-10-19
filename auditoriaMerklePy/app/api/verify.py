"""
Router de la API de Verificación — Verificar integridad de logs.

Endpoints:
    GET  /api/v1/logs/{id}/proof  — Obtener prueba Merkle de un log
    POST /api/v1/verify           — Verificar una prueba Merkle
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_async_session
from app.schemas.batch import (
    MerkleProofResponse,
    VerifyRequest,
    VerifyResponse,
)
from app.services.batch_service import (
    BatchService,
    LogNotInBatchError,
    BatchNotClosedError,
)

router = APIRouter(prefix="/api/v1", tags=["Verificación"])


def get_batch_service(
    session: AsyncSession = Depends(get_async_session),
) -> BatchService:
    return BatchService(session)


# ============================================================
# GET /api/v1/logs/{id}/proof
# ============================================================

@router.get(
    "/logs/{log_id}/proof",
    response_model=MerkleProofResponse,
    summary="Obtener prueba Merkle de un log",
    description=(
        "Genera la prueba de Merkle para un log específico. "
        "La prueba permite a un tercero verificar criptográficamente "
        "que el log fue incluido en el Merkle Tree del batch."
    ),
)
async def get_log_proof(
    log_id: UUID,
    service: BatchService = Depends(get_batch_service),
):
    try:
        result = await service.generate_proof_for_log(log_id)
    except LogNotInBatchError as e:
        raise HTTPException(
            status_code=409,
            detail={
                "error": "log_sin_batch",
                "message": str(e),
            },
        )
    except BatchNotClosedError as e:
        raise HTTPException(
            status_code=409,
            detail={
                "error": "batch_no_cerrado",
                "message": str(e),
            },
        )

    if result is None:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "log_no_encontrado",
                "message": f"No existe un log con ID {log_id}",
            },
        )

    return result


# ============================================================
# POST /api/v1/verify
# ============================================================

@router.post(
    "/verify",
    response_model=VerifyResponse,
    summary="Verificar una prueba Merkle",
    description=(
        "Recibe un content_hash, un merkle_root y los pasos de la prueba. "
        "Recalcula el root criptográficamente y verifica si coincide. "
        "Esta operación es completamente stateless (no consulta la BD)."
    ),
)
async def verify_merkle_proof(
    data: VerifyRequest,
    service: BatchService = Depends(get_batch_service),
):
    proof_dicts = [step.model_dump() for step in data.proof]
    is_valid = service.verify_proof(
        content_hash=data.content_hash,
        merkle_root=data.merkle_root,
        proof_steps=proof_dicts,
    )

    if is_valid:
        message = "✅ Prueba válida: el log fue incluido en el Merkle Tree"
    else:
        message = "❌ Prueba inválida: el hash recalculado no coincide con el Merkle Root"

    return VerifyResponse(
        is_valid=is_valid,
        content_hash=data.content_hash,
        merkle_root=data.merkle_root,
        message=message,
    )
