"""
AuthService — Servicio de autenticación y autorización.

Implementa dos mecanismos de autenticación:

1. API Keys (X-API-Key header):
   - Para aplicaciones que envían logs (ingesta)
   - Las keys se hashean con SHA-256 antes de almacenarse
   - Se generan con token seguro de 48 bytes

2. JWT (Bearer token):
   - Para usuarios de la interfaz de auditoría
   - Tokens con expiración configurable
   - Passwords hasheados con bcrypt

Flujo:
    Aplicación → X-API-Key → ingesta de logs
    Usuario    → /auth/login → JWT → consulta/verificación/reportes
"""

import hashlib
import logging
import secrets
from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple
from uuid import UUID

import jwt
from passlib.context import CryptContext
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.api_key import ApiKey
from app.models.audit_user import AuditUser

logger = logging.getLogger(__name__)

# Contexto de password hashing (bcrypt)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class AuthService:
    """
    Servicio de autenticación para API keys y usuarios JWT.
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    # ============================================================
    # API Keys
    # ============================================================

    @staticmethod
    def _hash_api_key(raw_key: str) -> str:
        """Hashea una API key con SHA-256."""
        return hashlib.sha256(raw_key.encode()).hexdigest()

    @staticmethod
    def _generate_raw_key() -> str:
        """Genera una API key segura de 48 bytes (base64url)."""
        return "mka_" + secrets.token_urlsafe(48)

    async def create_api_key(
        self,
        app_name: str,
        description: str = None,
        expires_at: datetime = None,
    ) -> Tuple[ApiKey, str]:
        """
        Crea una nueva API key para una aplicación.

        IMPORTANTE: La raw_key solo se retorna una vez. Después solo
        se almacena el hash.

        Args:
            app_name: Nombre de la aplicación.
            description: Descripción opcional.
            expires_at: Fecha de expiración (null = no expira).

        Returns:
            Tupla (ApiKey modelo, raw_key en texto plano).
        """
        raw_key = self._generate_raw_key()
        key_hash = self._hash_api_key(raw_key)
        key_prefix = raw_key[:8]

        api_key = ApiKey(
            key_hash=key_hash,
            key_prefix=key_prefix,
            app_name=app_name,
            description=description,
            is_active=True,
            expires_at=expires_at,
        )
        self.session.add(api_key)
        await self.session.flush()

        logger.info(
            "API key creada para app '%s' (prefix=%s)",
            app_name, key_prefix,
        )
        return api_key, raw_key

    async def validate_api_key(self, raw_key: str) -> Optional[ApiKey]:
        """
        Valida una API key y retorna el registro si es válida.

        Verifica:
        1. Que el hash exista en la BD
        2. Que la key esté activa
        3. Que no haya expirado

        También actualiza last_used_at.

        Args:
            raw_key: API key en texto plano.

        Returns:
            ApiKey si es válida, None si no.
        """
        key_hash = self._hash_api_key(raw_key)

        result = await self.session.execute(
            select(ApiKey).where(ApiKey.key_hash == key_hash)
        )
        api_key = result.scalar_one_or_none()

        if not api_key:
            return None

        if not api_key.is_active:
            logger.warning("API key inactiva: %s", api_key.key_prefix)
            return None

        if api_key.expires_at and api_key.expires_at < datetime.now(timezone.utc):
            logger.warning("API key expirada: %s", api_key.key_prefix)
            return None

        # Actualizar último uso
        api_key.last_used_at = datetime.now(timezone.utc)
        await self.session.flush()

        return api_key

    async def revoke_api_key(self, key_id: UUID) -> bool:
        """Revoca (desactiva) una API key."""
        result = await self.session.execute(
            select(ApiKey).where(ApiKey.id == key_id)
        )
        api_key = result.scalar_one_or_none()
        if not api_key:
            return False

        api_key.is_active = False
        await self.session.flush()
        logger.info("API key revocada: %s (%s)", api_key.key_prefix, api_key.app_name)
        return True

    async def list_api_keys(self) -> list[ApiKey]:
        """Lista todas las API keys (sin revelar los hashes)."""
        result = await self.session.execute(
            select(ApiKey).order_by(ApiKey.created_at.desc())
        )
        return list(result.scalars().all())

    # ============================================================
    # Usuarios JWT
    # ============================================================

    async def create_user(
        self,
        username: str,
        password: str,
        full_name: str = None,
        role: str = "auditor",
    ) -> AuditUser:
        """
        Crea un nuevo usuario de auditoría.

        Args:
            username: Nombre de usuario único.
            password: Password en texto plano (se hashea con bcrypt).
            full_name: Nombre completo.
            role: Rol del usuario (admin, auditor).

        Returns:
            AuditUser creado.
        """
        password_hash = pwd_context.hash(password)

        user = AuditUser(
            username=username,
            password_hash=password_hash,
            full_name=full_name,
            role=role,
        )
        self.session.add(user)
        await self.session.flush()

        logger.info("Usuario creado: %s (role=%s)", username, role)
        return user

    async def authenticate_user(
        self, username: str, password: str
    ) -> Optional[AuditUser]:
        """
        Autentica un usuario con username y password.

        Args:
            username: Nombre de usuario.
            password: Password en texto plano.

        Returns:
            AuditUser si la autenticación es exitosa, None si no.
        """
        result = await self.session.execute(
            select(AuditUser).where(AuditUser.username == username)
        )
        user = result.scalar_one_or_none()

        if not user:
            return None

        if not user.is_active:
            logger.warning("Intento de login de usuario inactivo: %s", username)
            return None

        if not pwd_context.verify(password, user.password_hash):
            logger.warning("Password incorrecto para usuario: %s", username)
            return None

        # Actualizar último login
        user.last_login_at = datetime.now(timezone.utc)
        await self.session.flush()

        logger.info("Login exitoso: %s", username)
        return user

    @staticmethod
    def create_access_token(
        user: AuditUser,
        expires_delta: timedelta = None,
    ) -> str:
        """
        Genera un JWT para un usuario autenticado.

        Args:
            user: Usuario autenticado.
            expires_delta: Tiempo de expiración. Default: JWT_EXPIRATION_MINUTES.

        Returns:
            Token JWT firmado.
        """
        if expires_delta is None:
            expires_delta = timedelta(minutes=settings.JWT_EXPIRATION_MINUTES)

        expire = datetime.now(timezone.utc) + expires_delta

        payload = {
            "sub": str(user.id),
            "username": user.username,
            "role": user.role,
            "exp": expire,
            "iat": datetime.now(timezone.utc),
            "type": "access",
        }

        token = jwt.encode(
            payload,
            settings.JWT_SECRET_KEY,
            algorithm=settings.JWT_ALGORITHM,
        )
        return token

    @staticmethod
    def decode_token(token: str) -> Optional[dict]:
        """
        Decodifica y valida un JWT.

        Args:
            token: Token JWT.

        Returns:
            Payload decodificado, o None si es inválido/expirado.
        """
        try:
            payload = jwt.decode(
                token,
                settings.JWT_SECRET_KEY,
                algorithms=[settings.JWT_ALGORITHM],
            )
            return payload
        except jwt.ExpiredSignatureError:
            logger.debug("Token expirado")
            return None
        except jwt.InvalidTokenError as e:
            logger.debug("Token inválido: %s", str(e))
            return None

    async def get_user_by_id(self, user_id: UUID) -> Optional[AuditUser]:
        """Obtiene un usuario por su ID."""
        result = await self.session.execute(
            select(AuditUser).where(AuditUser.id == user_id)
        )
        return result.scalar_one_or_none()
