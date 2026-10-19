"""
Router de la API de Autenticación.

Endpoints:
    POST /api/v1/auth/login           — Login de usuario (retorna JWT)
    POST /api/v1/auth/register        — Registrar nuevo usuario (solo admin)
    GET  /api/v1/auth/me              — Perfil del usuario autenticado
    POST /api/v1/auth/api-keys        — Crear API key (solo admin)
    GET  /api/v1/auth/api-keys        — Listar API keys (solo admin)
    DELETE /api/v1/auth/api-keys/{id} — Revocar API key (solo admin)
"""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_async_session
from app.models.api_key import ApiKey
from app.models.audit_user import AuditUser
from app.services.auth_service import AuthService
from app.api.deps import require_jwt, require_admin

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/auth", tags=["Autenticación"])


# ============================================================
# Schemas
# ============================================================

class LoginRequest(BaseModel):
    """Datos para login."""
    username: str = Field(..., min_length=1, max_length=100)
    password: str = Field(..., min_length=6, max_length=128)


class LoginResponse(BaseModel):
    """Respuesta de login exitoso."""
    access_token: str
    token_type: str = "bearer"
    username: str
    role: str
    expires_in_minutes: int


class RegisterRequest(BaseModel):
    """Datos para registrar un usuario."""
    username: str = Field(..., min_length=3, max_length=100)
    password: str = Field(..., min_length=8, max_length=128)
    full_name: str = Field(None, max_length=255)
    role: str = Field(default="auditor", pattern="^(admin|auditor)$")


class UserResponse(BaseModel):
    """Perfil del usuario."""
    id: UUID
    username: str
    full_name: str | None
    role: str
    is_active: bool

    model_config = {"from_attributes": True}


class CreateApiKeyRequest(BaseModel):
    """Datos para crear una API key."""
    app_name: str = Field(..., min_length=1, max_length=255)
    description: str = Field(None, max_length=500)


class ApiKeyCreatedResponse(BaseModel):
    """Respuesta al crear API key (incluye la raw key solo esta vez)."""
    id: UUID
    app_name: str
    key_prefix: str
    raw_key: str = Field(
        ...,
        description="⚠️ Esta es la única vez que se muestra la key completa. Guárdala."
    )
    is_active: bool


class ApiKeyListItem(BaseModel):
    """Ítem de la lista de API keys (sin revelar la key)."""
    id: UUID
    app_name: str
    key_prefix: str
    is_active: bool
    description: str | None
    last_used_at: str | None

    model_config = {"from_attributes": True}


# ============================================================
# Login
# ============================================================

@router.post(
    "/login",
    response_model=LoginResponse,
    summary="Login de usuario",
    description="Autentica un usuario y retorna un JWT.",
)
async def login(
    data: LoginRequest,
    session: AsyncSession = Depends(get_async_session),
):
    auth_service = AuthService(session)
    user = await auth_service.authenticate_user(data.username, data.password)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "credenciales_invalidas",
                "message": "Username o password incorrecto",
            },
        )

    from app.config import settings
    token = auth_service.create_access_token(user)

    return LoginResponse(
        access_token=token,
        username=user.username,
        role=user.role,
        expires_in_minutes=settings.JWT_EXPIRATION_MINUTES,
    )


# ============================================================
# Register (solo admin)
# ============================================================

@router.post(
    "/register",
    response_model=UserResponse,
    status_code=201,
    summary="Registrar nuevo usuario (admin)",
    description="Solo administradores pueden crear nuevos usuarios.",
)
async def register_user(
    data: RegisterRequest,
    admin: AuditUser = Depends(require_admin),
    session: AsyncSession = Depends(get_async_session),
):
    auth_service = AuthService(session)

    try:
        user = await auth_service.create_user(
            username=data.username,
            password=data.password,
            full_name=data.full_name,
            role=data.role,
        )
        return user
    except Exception as e:
        if "unique" in str(e).lower() or "duplicate" in str(e).lower():
            raise HTTPException(
                status_code=409,
                detail={
                    "error": "usuario_duplicado",
                    "message": f"Ya existe un usuario con username '{data.username}'",
                },
            )
        raise


# ============================================================
# GET /me
# ============================================================

@router.get(
    "/me",
    response_model=UserResponse,
    summary="Perfil del usuario autenticado",
)
async def get_my_profile(
    user: AuditUser = Depends(require_jwt),
):
    return user


# ============================================================
# API Keys Management (solo admin)
# ============================================================

@router.post(
    "/api-keys",
    response_model=ApiKeyCreatedResponse,
    status_code=201,
    summary="Crear API key (admin)",
    description=(
        "Crea una nueva API key para una aplicación. "
        "⚠️ La key completa solo se muestra una vez."
    ),
)
async def create_api_key(
    data: CreateApiKeyRequest,
    admin: AuditUser = Depends(require_admin),
    session: AsyncSession = Depends(get_async_session),
):
    auth_service = AuthService(session)

    try:
        api_key, raw_key = await auth_service.create_api_key(
            app_name=data.app_name,
            description=data.description,
        )
        return ApiKeyCreatedResponse(
            id=api_key.id,
            app_name=api_key.app_name,
            key_prefix=api_key.key_prefix,
            raw_key=raw_key,
            is_active=api_key.is_active,
        )
    except Exception as e:
        if "unique" in str(e).lower() or "duplicate" in str(e).lower():
            raise HTTPException(
                status_code=409,
                detail={
                    "error": "app_duplicada",
                    "message": f"Ya existe una API key para '{data.app_name}'",
                },
            )
        raise


@router.get(
    "/api-keys",
    response_model=list[ApiKeyListItem],
    summary="Listar API keys (admin)",
)
async def list_api_keys(
    admin: AuditUser = Depends(require_admin),
    session: AsyncSession = Depends(get_async_session),
):
    auth_service = AuthService(session)
    keys = await auth_service.list_api_keys()
    return [
        ApiKeyListItem(
            id=k.id,
            app_name=k.app_name,
            key_prefix=k.key_prefix,
            is_active=k.is_active,
            description=k.description,
            last_used_at=k.last_used_at.isoformat() if k.last_used_at else None,
        )
        for k in keys
    ]


@router.delete(
    "/api-keys/{key_id}",
    status_code=200,
    summary="Revocar API key (admin)",
)
async def revoke_api_key(
    key_id: UUID,
    admin: AuditUser = Depends(require_admin),
    session: AsyncSession = Depends(get_async_session),
):
    auth_service = AuthService(session)
    revoked = await auth_service.revoke_api_key(key_id)

    if not revoked:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "api_key_no_encontrada",
                "message": f"No existe una API key con ID {key_id}",
            },
        )

    return {"message": "API key revocada exitosamente", "id": str(key_id)}
