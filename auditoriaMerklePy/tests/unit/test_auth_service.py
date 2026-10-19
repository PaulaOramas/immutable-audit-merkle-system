"""
Tests unitarios para AuthService (Fase 3.6).

Cubren:
- API key: generación, hashing, validación
- Usuarios: creación, autenticación, hashing de passwords
- JWT: generación, decodificación, expiración
"""

from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.services.auth_service import AuthService, pwd_context


# ============================================================
# Tests de API Keys
# ============================================================

class TestApiKeyGeneration:

    def test_generate_raw_key_format(self):
        """La raw key generada tiene el formato correcto."""
        key = AuthService._generate_raw_key()
        assert key.startswith("mka_")
        assert len(key) > 20  # 4 bytes prefix + 48 bytes base64

    def test_generate_raw_key_unique(self):
        """Cada key generada es única."""
        keys = {AuthService._generate_raw_key() for _ in range(100)}
        assert len(keys) == 100

    def test_hash_api_key_deterministic(self):
        """El hash de la misma key siempre es igual."""
        key = "mka_test123"
        h1 = AuthService._hash_api_key(key)
        h2 = AuthService._hash_api_key(key)
        assert h1 == h2
        assert len(h1) == 64  # SHA-256 hex

    def test_hash_api_key_different_keys(self):
        """Keys diferentes producen hashes diferentes."""
        h1 = AuthService._hash_api_key("mka_key_a")
        h2 = AuthService._hash_api_key("mka_key_b")
        assert h1 != h2


# ============================================================
# Tests de Password Hashing
# ============================================================

class TestPasswordHashing:

    def test_password_hash_and_verify(self):
        """bcrypt hash y verify funcionan correctamente."""
        password = "mi_password_seguro_123"
        hashed = pwd_context.hash(password)

        assert hashed != password
        assert len(hashed) > 50  # bcrypt hash es largo
        assert pwd_context.verify(password, hashed) is True
        assert pwd_context.verify("wrong_password", hashed) is False

    def test_different_passwords_different_hashes(self):
        """Passwords iguales generan hashes diferentes (salt)."""
        password = "same_password"
        h1 = pwd_context.hash(password)
        h2 = pwd_context.hash(password)
        assert h1 != h2  # bcrypt usa salt aleatorio
        # Ambos verifican correctamente
        assert pwd_context.verify(password, h1) is True
        assert pwd_context.verify(password, h2) is True


# ============================================================
# Tests de JWT
# ============================================================

class TestJWT:

    def _make_mock_user(self, role="auditor"):
        """Crea un mock de AuditUser."""
        user = MagicMock()
        user.id = uuid4()
        user.username = "test_user"
        user.role = role
        return user

    def test_create_and_decode_token(self):
        """Crear y decodificar un JWT."""
        user = self._make_mock_user()

        with patch('app.services.auth_service.settings') as mock_settings:
            mock_settings.JWT_SECRET_KEY = "test_secret_key_12345"
            mock_settings.JWT_ALGORITHM = "HS256"
            mock_settings.JWT_EXPIRATION_MINUTES = 60

            token = AuthService.create_access_token(user)
            assert isinstance(token, str)
            assert len(token) > 50

            payload = AuthService.decode_token(token)
            assert payload is not None
            assert payload["sub"] == str(user.id)
            assert payload["username"] == "test_user"
            assert payload["role"] == "auditor"
            assert payload["type"] == "access"

    def test_expired_token_returns_none(self):
        """Token expirado retorna None."""
        user = self._make_mock_user()

        with patch('app.services.auth_service.settings') as mock_settings:
            mock_settings.JWT_SECRET_KEY = "test_secret_key_12345"
            mock_settings.JWT_ALGORITHM = "HS256"
            mock_settings.JWT_EXPIRATION_MINUTES = 60

            # Token que expira inmediatamente
            token = AuthService.create_access_token(
                user,
                expires_delta=timedelta(seconds=-1),
            )

            payload = AuthService.decode_token(token)
            assert payload is None

    def test_invalid_token_returns_none(self):
        """Token inválido retorna None."""
        with patch('app.services.auth_service.settings') as mock_settings:
            mock_settings.JWT_SECRET_KEY = "test_secret_key_12345"
            mock_settings.JWT_ALGORITHM = "HS256"

            payload = AuthService.decode_token("invalid.token.here")
            assert payload is None

    def test_token_with_wrong_secret_returns_none(self):
        """Token firmado con secret diferente no valida."""
        user = self._make_mock_user()

        with patch('app.services.auth_service.settings') as mock_settings:
            mock_settings.JWT_SECRET_KEY = "secret_A"
            mock_settings.JWT_ALGORITHM = "HS256"
            mock_settings.JWT_EXPIRATION_MINUTES = 60

            token = AuthService.create_access_token(user)

        with patch('app.services.auth_service.settings') as mock_settings:
            mock_settings.JWT_SECRET_KEY = "secret_B"
            mock_settings.JWT_ALGORITHM = "HS256"

            payload = AuthService.decode_token(token)
            assert payload is None

    def test_admin_role_in_token(self):
        """Token de admin incluye role=admin."""
        user = self._make_mock_user(role="admin")

        with patch('app.services.auth_service.settings') as mock_settings:
            mock_settings.JWT_SECRET_KEY = "test_secret_key_12345"
            mock_settings.JWT_ALGORITHM = "HS256"
            mock_settings.JWT_EXPIRATION_MINUTES = 60

            token = AuthService.create_access_token(user)
            payload = AuthService.decode_token(token)
            assert payload["role"] == "admin"
