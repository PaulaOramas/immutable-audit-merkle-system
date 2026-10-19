"""
Dependencias de autenticación para FastAPI.

Provee dos mecanismos de autenticación como dependencies inyectables:

1. require_api_key: Valida X-API-Key header (para ingesta de logs)
2. require_jwt: Valida Bearer token (para interfaz de auditoría)
3. require_admin: Requiere JWT con role=admin
"""

import logging
from typing import Optional
from uuid import UUID

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader, HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_async_session
from app.models.api_key import ApiKey
from app.models.audit_user import AuditUser
from app.services.auth_service import AuthService

logger = logging.getLogger(__name__)

# Security schemes
api_key_header = APIKeyHeader(
    name="X-API-Key",
    auto_error=False,
    description="API key para aplicaciones que envían logs",
)

bearer_scheme = HTTPBearer(
    auto_error=False,
    description="Token JWT para usuarios de auditoría",
)


# ============================================================
# API Key Authentication (para ingesta)
# ============================================================

async def require_api_key(
    api_key: Optional[str] = Security(api_key_header),
    session: AsyncSession = Depends(get_async_session),
) -> ApiKey:
    """
    Dependencia que requiere una API key válida.

    Usar en endpoints de ingesta de logs (POST /api/v1/logs).

    Raises:
        HTTPException 401: Si no se proporciona API key.
        HTTPException 403: Si la API key es inválida, inactiva o expirada.
    """
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "api_key_requerida",
                "message": "Se requiere el header X-API-Key",
            },
        )

    auth_service = AuthService(session)
    validated = await auth_service.validate_api_key(api_key)

    if not validated:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "api_key_invalida",
                "message": "API key inválida, inactiva o expirada",
            },
        )

    return validated


async def optional_api_key(
    api_key: Optional[str] = Security(api_key_header),
    session: AsyncSession = Depends(get_async_session),
) -> Optional[ApiKey]:
    """
    Dependencia que acepta opcionalmente una API key.

    Útil para endpoints que pueden funcionar con o sin autenticación.
    """
    if not api_key:
        return None

    auth_service = AuthService(session)
    return await auth_service.validate_api_key(api_key)


# ============================================================
# JWT Authentication (para interfaz de auditoría)
# ============================================================

async def require_jwt(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(bearer_scheme),
    session: AsyncSession = Depends(get_async_session),
) -> AuditUser:
    """
    Dependencia que requiere un JWT válido.

    Usar en endpoints de consulta, verificación y reportes.

    Raises:
        HTTPException 401: Si no se proporciona token o es inválido.
        HTTPException 403: Si el usuario no existe o está inactivo.
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "token_requerido",
                "message": "Se requiere un Bearer token en el header Authorization",
            },
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = AuthService.decode_token(credentials.credentials)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "token_invalido",
                "message": "Token inválido o expirado",
            },
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Verificar que el usuario existe y está activo
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


async def require_admin(
    user: AuditUser = Depends(require_jwt),
) -> AuditUser:
    """
    Dependencia que requiere JWT con role=admin.

    Usar en endpoints administrativos (crear API keys, gestionar usuarios).

    Raises:
        HTTPException 403: Si el usuario no es admin.
    """
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "permisos_insuficientes",
                "message": "Se requiere rol de administrador",
            },
        )
    return user
