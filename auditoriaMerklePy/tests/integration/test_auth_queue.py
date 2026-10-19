"""
Tests de integración para Autenticación y Cola (Fase 3.5 + 3.6).

Prueba el flujo completo:
- Crear usuario admin → login → obtener JWT
- Crear API key → usar para ingestar logs
- Validar que endpoints protegidos requieren autenticación
- Encolar logs para procesamiento asíncrono

Requiere: PostgreSQL corriendo (docker compose up -d)
"""

import os
import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.config import settings
from app.db.session import get_async_session


# ============================================================
# Helpers
# ============================================================

def _unique_payload(prefix: str = "auth_test") -> dict:
    return {
        "user": f"user_{uuid.uuid4().hex[:8]}",
        "action": f"{prefix}_{uuid.uuid4().hex[:6]}",
        "unique": uuid.uuid4().hex,
    }


# ============================================================
# Fixtures
# ============================================================

@pytest_asyncio.fixture(scope="function")
async def auth_app():
    """
    App con AUTH_ENABLED=True para probar autenticación.

    Crea un engine propio, importa la app fresh con auth habilitado.
    """
    # Reimportar con auth habilitado
    settings.AUTH_ENABLED = True

    from app.main import app

    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    factory = async_sessionmaker(
        bind=engine, class_=AsyncSession, expire_on_commit=False,
    )

    async def override_session():
        async with factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_async_session] = override_session
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

    app.dependency_overrides.clear()
    await engine.dispose()

    # Restaurar
    settings.AUTH_ENABLED = False


@pytest_asyncio.fixture(scope="function")
async def admin_setup(auth_app: AsyncClient):
    """
    Crea un usuario admin y retorna su token JWT.

    Usa acceso directo a la BD para crear el primer admin
    (ya que no hay admin previo para autorizarse).
    """
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    factory = async_sessionmaker(
        bind=engine, class_=AsyncSession, expire_on_commit=False,
    )

    admin_username = f"admin_{uuid.uuid4().hex[:8]}"
    admin_password = "admin_pass_12345"

    async with factory() as session:
        from app.services.auth_service import AuthService

        auth_service = AuthService(session)
        admin = await auth_service.create_user(
            username=admin_username,
            password=admin_password,
            full_name="Test Admin",
            role="admin",
        )
        await session.commit()

    # Login para obtener JWT
    login_resp = await auth_app.post("/api/v1/auth/login", json={
        "username": admin_username,
        "password": admin_password,
    })
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]

    await engine.dispose()

    return {
        "token": token,
        "username": admin_username,
        "client": auth_app,
    }


# ============================================================
# Tests: Login y JWT
# ============================================================

class TestAuthLogin:

    async def test_login_success(self, auth_app: AsyncClient, admin_setup):
        """Login exitoso retorna JWT."""
        data = admin_setup
        assert "token" in data
        assert len(data["token"]) > 50

    async def test_login_wrong_password(self, auth_app: AsyncClient, admin_setup):
        """Password incorrecto retorna 401."""
        resp = await auth_app.post("/api/v1/auth/login", json={
            "username": admin_setup["username"],
            "password": "wrong_password",
        })
        assert resp.status_code == 401
        assert resp.json()["detail"]["error"] == "credenciales_invalidas"

    async def test_login_unknown_user(self, auth_app: AsyncClient):
        """Usuario inexistente retorna 401."""
        resp = await auth_app.post("/api/v1/auth/login", json={
            "username": "no_existe",
            "password": "any_password",
        })
        assert resp.status_code == 401

    async def test_get_my_profile(self, auth_app: AsyncClient, admin_setup):
        """GET /me retorna perfil del usuario autenticado."""
        resp = await auth_app.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {admin_setup['token']}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["username"] == admin_setup["username"]
        assert data["role"] == "admin"

    async def test_get_me_without_token(self, auth_app: AsyncClient):
        """GET /me sin token retorna 401."""
        resp = await auth_app.get("/api/v1/auth/me")
        assert resp.status_code == 401


# ============================================================
# Tests: API Key Management
# ============================================================

class TestApiKeyManagement:

    async def test_create_api_key(self, auth_app: AsyncClient, admin_setup):
        """Admin puede crear API keys."""
        resp = await auth_app.post(
            "/api/v1/auth/api-keys",
            headers={"Authorization": f"Bearer {admin_setup['token']}"},
            json={
                "app_name": f"test_app_{uuid.uuid4().hex[:8]}",
                "description": "Test application",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["raw_key"].startswith("mka_")
        assert data["is_active"] is True

    async def test_list_api_keys(self, auth_app: AsyncClient, admin_setup):
        """Admin puede listar API keys."""
        # Crear una key primero
        app_name = f"list_test_{uuid.uuid4().hex[:8]}"
        await auth_app.post(
            "/api/v1/auth/api-keys",
            headers={"Authorization": f"Bearer {admin_setup['token']}"},
            json={"app_name": app_name},
        )

        resp = await auth_app.get(
            "/api/v1/auth/api-keys",
            headers={"Authorization": f"Bearer {admin_setup['token']}"},
        )
        assert resp.status_code == 200
        keys = resp.json()
        assert len(keys) >= 1

    async def test_revoke_api_key(self, auth_app: AsyncClient, admin_setup):
        """Admin puede revocar API keys."""
        # Crear key
        create_resp = await auth_app.post(
            "/api/v1/auth/api-keys",
            headers={"Authorization": f"Bearer {admin_setup['token']}"},
            json={"app_name": f"revoke_test_{uuid.uuid4().hex[:8]}"},
        )
        key_id = create_resp.json()["id"]

        # Revocar
        resp = await auth_app.delete(
            f"/api/v1/auth/api-keys/{key_id}",
            headers={"Authorization": f"Bearer {admin_setup['token']}"},
        )
        assert resp.status_code == 200


# ============================================================
# Tests: Endpoints protegidos
# ============================================================

class TestProtectedEndpoints:

    async def test_post_log_without_api_key_returns_401(
        self, auth_app: AsyncClient,
    ):
        """POST /logs sin API key retorna 401."""
        resp = await auth_app.post("/api/v1/logs", json={
            "source_app": "test",
            "event_type": "test",
            "severity": "info",
            "payload": _unique_payload(),
        })
        assert resp.status_code == 401

    async def test_post_log_with_invalid_api_key_returns_403(
        self, auth_app: AsyncClient,
    ):
        """POST /logs con API key inválida retorna 403."""
        resp = await auth_app.post(
            "/api/v1/logs",
            headers={"X-API-Key": "invalid_key"},
            json={
                "source_app": "test",
                "event_type": "test",
                "severity": "info",
                "payload": _unique_payload(),
            },
        )
        assert resp.status_code == 403

    async def test_post_log_with_valid_api_key(
        self, auth_app: AsyncClient, admin_setup,
    ):
        """POST /logs con API key válida funciona."""
        # Crear API key
        create_resp = await auth_app.post(
            "/api/v1/auth/api-keys",
            headers={"Authorization": f"Bearer {admin_setup['token']}"},
            json={"app_name": f"ingest_test_{uuid.uuid4().hex[:8]}"},
        )
        raw_key = create_resp.json()["raw_key"]

        # Ingestar log con la key
        resp = await auth_app.post(
            "/api/v1/logs",
            headers={"X-API-Key": raw_key},
            json={
                "source_app": "test",
                "event_type": "test",
                "severity": "info",
                "payload": _unique_payload(),
            },
        )
        assert resp.status_code == 201
        assert resp.json()["content_hash"] is not None

    async def test_get_logs_without_jwt_returns_401(
        self, auth_app: AsyncClient,
    ):
        """GET /logs sin JWT retorna 401."""
        resp = await auth_app.get("/api/v1/logs")
        assert resp.status_code == 401

    async def test_get_logs_with_valid_jwt(
        self, auth_app: AsyncClient, admin_setup,
    ):
        """GET /logs con JWT válido funciona."""
        resp = await auth_app.get(
            "/api/v1/logs",
            headers={"Authorization": f"Bearer {admin_setup['token']}"},
        )
        assert resp.status_code == 200


# ============================================================
# Tests: Cola Asíncrona (sin auth, usa app normal)
# ============================================================

class TestAsyncQueue:

    @pytest_asyncio.fixture(scope="function")
    async def queue_client(self):
        """Cliente con cola habilitada."""
        settings.QUEUE_ENABLED = True
        settings.AUTH_ENABLED = False

        from app.main import app

        engine = create_async_engine(settings.DATABASE_URL, echo=False)
        factory = async_sessionmaker(
            bind=engine, class_=AsyncSession, expire_on_commit=False,
        )

        async def override_session():
            async with factory() as session:
                try:
                    yield session
                    await session.commit()
                except Exception:
                    await session.rollback()
                    raise

        app.dependency_overrides[get_async_session] = override_session
        transport = ASGITransport(app=app)

        async with AsyncClient(transport=transport, base_url="http://test") as c:
            yield c

        app.dependency_overrides.clear()
        await engine.dispose()
        settings.QUEUE_ENABLED = False

    async def test_enqueue_log_returns_202(self, queue_client: AsyncClient):
        """Encolar un log retorna 202 Accepted."""
        resp = await queue_client.post("/api/v1/logs/async", json={
            "source_app": "test_queue",
            "event_type": "async_test",
            "severity": "info",
            "payload": _unique_payload("queue"),
        })
        assert resp.status_code == 202
        data = resp.json()
        assert data["status"] == "enqueued"
        assert data["queue_id"] is not None

    async def test_enqueue_when_disabled_returns_503(self):
        """Encolar cuando la cola está deshabilitada retorna 503."""
        settings.QUEUE_ENABLED = False
        settings.AUTH_ENABLED = False

        from app.main import app

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            resp = await c.post("/api/v1/logs/async", json={
                "source_app": "test",
                "event_type": "test",
                "severity": "info",
                "payload": _unique_payload(),
            })
            assert resp.status_code == 503
