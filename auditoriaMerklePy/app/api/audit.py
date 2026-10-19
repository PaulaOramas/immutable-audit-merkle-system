"""
Router de la API de Auditoría — Integridad, reportes y anclajes.

Endpoints:
    GET /api/v1/audit/integrity-check  — Verificación masiva de integridad
    GET /api/v1/audit/report           — Reporte de auditoría (JSON)
    GET /api/v1/anchors                — Listar anclajes realizados
"""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_async_session
from app.schemas.audit import (
    IntegrityCheckResponse,
    AuditReportResponse,
    AnchorListResponse,
)
from app.services.audit_service import AuditService

router = APIRouter(tags=["Auditoría"])


def get_audit_service(
    session: AsyncSession = Depends(get_async_session),
) -> AuditService:
    return AuditService(session)


# ============================================================
# GET /api/v1/audit/integrity-check
# ============================================================

@router.get(
    "/api/v1/audit/integrity-check",
    response_model=IntegrityCheckResponse,
    summary="Verificación masiva de integridad",
    description=(
        "Reconstruye el Merkle Tree de cada batch cerrado a partir de las "
        "hojas persistidas y compara el root recalculado con el almacenado. "
        "Permite detectar cualquier alteración de datos post-cierre."
    ),
)
async def integrity_check(
    service: AuditService = Depends(get_audit_service),
):
    return await service.check_integrity()


# ============================================================
# GET /api/v1/audit/report
# ============================================================

@router.get(
    "/api/v1/audit/report",
    response_model=AuditReportResponse,
    summary="Reporte de auditoría del sistema",
    description=(
        "Genera un reporte completo del estado del sistema incluyendo: "
        "conteos de logs y batches, estado de integridad de cada batch, "
        "y registros de anclaje externo."
    ),
)
async def audit_report(
    service: AuditService = Depends(get_audit_service),
):
    return await service.generate_report()


# ============================================================
# GET /api/v1/anchors
# ============================================================

@router.get(
    "/api/v1/anchors",
    response_model=AnchorListResponse,
    summary="Listar anclajes realizados",
    description=(
        "Retorna los registros de anclaje externo (blockchain/TSA) "
        "con paginación y filtro opcional por red."
    ),
)
async def list_anchors(
    network: Optional[str] = Query(
        None,
        description="Filtrar por red: ganache, sepolia, mainnet, etc.",
    ),
    offset: int = Query(0, ge=0, description="Offset para paginación"),
    limit: int = Query(50, ge=1, le=200, description="Límite de resultados"),
    service: AuditService = Depends(get_audit_service),
):
    items, total = await service.list_anchors(
        network=network,
        offset=offset,
        limit=limit,
    )
    return AnchorListResponse(
        items=items,
        total=total,
        offset=offset,
        limit=limit,
    )
