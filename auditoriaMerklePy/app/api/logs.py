"""
Router de la API de Logs — Endpoints de ingesta y consulta.

Endpoints:
    POST /api/v1/logs          — Ingestar un log individual
    POST /api/v1/logs/batch    — Ingestar múltiples logs
    POST /api/v1/logs/async    — Encolar un log para procesamiento asíncrono
    GET  /api/v1/logs          — Listar logs con filtros y paginación
    GET  /api/v1/logs/{id}     — Obtener detalle de un log

Autenticación (evaluada en runtime, no en import time):
    - POST endpoints: requieren API key (X-API-Key) si AUTH_ENABLED=True
    - GET endpoints: requieren JWT si AUTH_ENABLED=True
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Header, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.session import get_async_session
from app.schemas.log_entry import (
    LogEntryCreate,
    LogEntryBatchCreate,
    LogEntryResponse,
    LogEntryListResponse,
)
from app.schemas.queue import EnqueueResponse
from app.services.log_service import LogService, DuplicateLogError

router = APIRouter(prefix="/api/v1/logs", tags=["Logs"])


def get_log_service(session: AsyncSession = Depends(get_async_session)) -> LogService:
    """Dependency injection para LogService."""
    return LogService(session)


# ============================================================
# Dependencias de autenticación (runtime)
# ============================================================

async def check_api_key(
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    session: AsyncSession = Depends(get_async_session),
):
    """
    Valida API key en runtime. Si AUTH_ENABLED=False, permite todo.
    """
    if not settings.AUTH_ENABLED:
        return None

    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "api_key_requerida",
                "message": "Se requiere el header X-API-Key",
            },
        )

    from app.services.auth_service import AuthService
    auth_service = AuthService(session)
    validated = await auth_service.validate_api_key(x_api_key)

    if not validated:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "api_key_invalida",
                "message": "API key inválida, inactiva o expirada",
            },
        )
    return validated


async def check_jwt(
    authorization: Optional[str] = Header(None),
    session: AsyncSession = Depends(get_async_session),
):
    """
    Valida JWT en runtime. Si AUTH_ENABLED=False, permite todo.
    """
    if not settings.AUTH_ENABLED:
        return None

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "token_requerido",
                "message": "Se requiere un Bearer token en el header Authorization",
            },
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = authorization.split(" ", 1)[1]

    from app.services.auth_service import AuthService
    payload = AuthService.decode_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "token_invalido",
                "message": "Token inválido o expirado",
            },
            headers={"WWW-Authenticate": "Bearer"},
        )

    auth_service = AuthService(session)
    user = await auth_service.get_user_by_id(UUID(payload["sub"]))
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "usuario_inactivo",
                "message": "El usuario no existe o está inactivo",
            },
        )
    return user


# ============================================================
# POST /api/v1/logs — Ingestar un log individual
# ============================================================

@router.post(
    "",
    response_model=LogEntryResponse,
    status_code=201,
    summary="Ingestar un log de auditoría",
    description=(
        "Recibe un log de auditoría, calcula su hash criptográfico SHA-256 "
        "con serialización canónica, y lo almacena. Rechaza duplicados."
    ),
)
async def create_log(
    data: LogEntryCreate,
    service: LogService = Depends(get_log_service),
    _auth=Depends(check_api_key),
):
    try:
        log = await service.create_log(data)
        return log
    except DuplicateLogError as e:
        raise HTTPException(
            status_code=409,
            detail={
                "error": "log_duplicado",
                "message": str(e),
                "content_hash": e.content_hash,
            },
        )


# ============================================================
# POST /api/v1/logs/batch — Ingestar múltiples logs
# ============================================================

@router.post(
    "/batch",
    response_model=list[LogEntryResponse],
    status_code=201,
    summary="Ingestar múltiples logs de auditoría",
    description=(
        "Recibe una lista de 1 a 500 logs, calcula el hash de cada uno, "
        "y almacena los que no sean duplicados. Los duplicados se omiten."
    ),
)
async def create_logs_batch(
    data: LogEntryBatchCreate,
    service: LogService = Depends(get_log_service),
    _auth=Depends(check_api_key),
):
    logs = await service.create_logs_batch(data.logs)
    return logs


# ============================================================
# POST /api/v1/logs/async — Encolar log para procesamiento asíncrono
# ============================================================

@router.post(
    "/async",
    response_model=EnqueueResponse,
    status_code=202,
    summary="Encolar un log para procesamiento asíncrono",
    description=(
        "Acepta el log inmediatamente y lo encola para procesamiento en background. "
        "El log será hasheado, persistido y asignado a un batch de forma asíncrona. "
        "Ideal para alto throughput donde la respuesta inmediata es prioritaria."
    ),
)
async def enqueue_log(
    data: LogEntryCreate,
    request: Request,
    _auth=Depends(check_api_key),
):
    if not settings.QUEUE_ENABLED:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "cola_deshabilitada",
                "message": "La cola de procesamiento no está habilitada",
            },
        )

    from app.services.log_queue import get_log_queue, QueueFullError

    queue = get_log_queue()
    try:
        queued = await queue.enqueue(
            data=data,
            source_ip=request.client.host if request.client else None,
        )
        return EnqueueResponse(
            queue_id=str(queued.id),
            status="enqueued",
            message="Log aceptado para procesamiento asíncrono",
            queue_size=queue.size,
        )
    except QueueFullError as e:
        raise HTTPException(
            status_code=429,
            detail={
                "error": "cola_llena",
                "message": str(e),
            },
        )


# ============================================================
# GET /api/v1/logs — Listar logs con filtros y paginación
# ============================================================

@router.get(
    "",
    response_model=LogEntryListResponse,
    summary="Listar logs de auditoría",
    description=(
        "Retorna logs de auditoría con filtros opcionales y paginación. "
        "Los filtros se aplican con AND."
    ),
)
async def list_logs(
    source_app: Optional[str] = Query(None, description="Filtrar por aplicación"),
    event_type: Optional[str] = Query(None, description="Filtrar por tipo de evento"),
    severity: Optional[str] = Query(None, description="Filtrar por severidad"),
    from_date: Optional[datetime] = Query(None, description="Fecha inicio (ISO 8601)"),
    to_date: Optional[datetime] = Query(None, description="Fecha fin (ISO 8601)"),
    offset: int = Query(0, ge=0, description="Offset para paginación"),
    limit: int = Query(50, ge=1, le=200, description="Límite de resultados"),
    service: LogService = Depends(get_log_service),
    _auth=Depends(check_jwt),
):
    logs, total = await service.list_logs(
        source_app=source_app,
        event_type=event_type,
        severity=severity,
        from_date=from_date,
        to_date=to_date,
        offset=offset,
        limit=limit,
    )
    return LogEntryListResponse(
        items=logs,
        total=total,
        offset=offset,
        limit=limit,
    )


# ============================================================
# GET /api/v1/logs/{id} — Obtener detalle de un log
# ============================================================

@router.get(
    "/{log_id}",
    response_model=LogEntryResponse,
    summary="Obtener detalle de un log",
    description="Retorna los datos completos de un log por su ID.",
)
async def get_log(
    log_id: UUID,
    service: LogService = Depends(get_log_service),
    _auth=Depends(check_jwt),
):
    log = await service.get_log(log_id)
    if not log:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "log_no_encontrado",
                "message": f"No existe un log con ID {log_id}",
            },
        )
    return log
