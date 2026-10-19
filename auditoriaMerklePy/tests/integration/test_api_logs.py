"""
Tests de integración para los endpoints de la API de Logs.

Usa httpx.AsyncClient contra la app FastAPI con PostgreSQL.
Cada test crea su propio engine para evitar issues de event loop.
"""

import uuid
import os

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    create_async_engine,
    async_sessionmaker,
)

from app.config import settings
from app.db.session import get_async_session
from app.main import app


# ============================================================
# Fixtures
# ============================================================

@pytest_asyncio.fixture(scope="function")
async def client():
    """
    Cliente HTTP para tests de API.

    Crea un engine propio por test para evitar issues de event loop.
    Override get_async_session para inyectar nuestra sesión.
    """
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    factory = async_sessionmaker(
        bind=engine, class_=AsyncSession, expire_on_commit=False
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


# ============================================================
# Helpers
# ============================================================

def make_log_payload(
    source_app: str = "test_app",
    event_type: str = "test_event",
    severity: str = "info",
    payload: dict = None,
) -> dict:
    """Construir body para POST /api/v1/logs."""
    return {
        "source_app": source_app,
        "event_type": event_type,
        "severity": severity,
        "payload": payload or {"action": "test", "detail": str(uuid.uuid4())},
    }


# ============================================================
# Tests POST /api/v1/logs
# ============================================================

class TestCreateLog:
    """Tests del endpoint POST /api/v1/logs."""

    async def test_create_log_success(self, client: AsyncClient):
        """Crear un log retorna 201 con content_hash calculado."""
        body = make_log_payload(source_app="app_web", event_type="login")
        resp = await client.post("/api/v1/logs", json=body)

        assert resp.status_code == 201
        data = resp.json()
        assert data["source_app"] == "app_web"
        assert data["event_type"] == "login"
        assert data["severity"] == "info"
        assert len(data["content_hash"]) == 64
        assert data["batch_id"] is not None  # Ahora se asigna automáticamente al batch activo
        assert data["id"] is not None

    async def test_create_log_with_severity(self, client: AsyncClient):
        """Crear un log con severidad warning."""
        body = make_log_payload(severity="warning")
        resp = await client.post("/api/v1/logs", json=body)

        assert resp.status_code == 201
        assert resp.json()["severity"] == "warning"

    async def test_create_log_duplicate_returns_409(self, client: AsyncClient):
        """Ingestar el mismo log dos veces retorna 409 Conflict."""
        unique = {"dup_test": str(uuid.uuid4())}
        body = make_log_payload(payload=unique)

        resp1 = await client.post("/api/v1/logs", json=body)
        assert resp1.status_code == 201

        resp2 = await client.post("/api/v1/logs", json=body)
        assert resp2.status_code == 409
        assert resp2.json()["detail"]["error"] == "log_duplicado"

    async def test_create_log_invalid_severity_returns_422(self, client: AsyncClient):
        """Severidad no válida retorna 422."""
        body = make_log_payload(severity="debug")
        resp = await client.post("/api/v1/logs", json=body)
        assert resp.status_code == 422

    async def test_create_log_empty_payload_returns_422(self, client: AsyncClient):
        """Payload vacío retorna 422."""
        body = {
            "source_app": "app",
            "event_type": "test",
            "severity": "info",
            "payload": {},
        }
        resp = await client.post("/api/v1/logs", json=body)
        assert resp.status_code == 422

    async def test_create_log_missing_fields_returns_422(self, client: AsyncClient):
        """Campos requeridos faltantes retorna 422."""
        body = {"source_app": "app"}
        resp = await client.post("/api/v1/logs", json=body)
        assert resp.status_code == 422

    async def test_content_hash_is_deterministic(self, client: AsyncClient):
        """Mismo payload con claves reordenadas genera el mismo hash."""
        det_val = str(uuid.uuid4())
        body = make_log_payload(payload={"determinism": det_val, "order": "test"})
        resp = await client.post("/api/v1/logs", json=body)
        assert resp.status_code == 201

        body2 = make_log_payload(payload={"order": "test", "determinism": det_val})
        resp2 = await client.post("/api/v1/logs", json=body2)
        assert resp2.status_code == 409


# ============================================================
# Tests POST /api/v1/logs/batch
# ============================================================

class TestCreateLogsBatch:
    """Tests del endpoint POST /api/v1/logs/batch."""

    async def test_batch_create_success(self, client: AsyncClient):
        """Crear batch de 3 logs retorna 201."""
        logs = [
            make_log_payload(event_type="event_a"),
            make_log_payload(event_type="event_b"),
            make_log_payload(event_type="event_c"),
        ]
        resp = await client.post("/api/v1/logs/batch", json={"logs": logs})

        assert resp.status_code == 201
        assert len(resp.json()) == 3

    async def test_batch_skips_duplicates(self, client: AsyncClient):
        """En batch, los duplicados se omiten sin error."""
        unique_payload = {"batch_dup": str(uuid.uuid4())}
        logs = [
            make_log_payload(payload=unique_payload),
            make_log_payload(payload=unique_payload),
            make_log_payload(event_type="otro"),
        ]
        resp = await client.post("/api/v1/logs/batch", json={"logs": logs})

        assert resp.status_code == 201
        assert len(resp.json()) == 2

    async def test_batch_empty_returns_422(self, client: AsyncClient):
        """Batch vacío retorna 422."""
        resp = await client.post("/api/v1/logs/batch", json={"logs": []})
        assert resp.status_code == 422


# ============================================================
# Tests GET /api/v1/logs/{id}
# ============================================================

class TestGetLog:
    """Tests del endpoint GET /api/v1/logs/{id}."""

    async def test_get_log_success(self, client: AsyncClient):
        """Obtener un log por su ID."""
        create_resp = await client.post("/api/v1/logs", json=make_log_payload())
        log_id = create_resp.json()["id"]

        resp = await client.get(f"/api/v1/logs/{log_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == log_id

    async def test_get_log_not_found(self, client: AsyncClient):
        """ID inexistente retorna 404."""
        fake_id = str(uuid.uuid4())
        resp = await client.get(f"/api/v1/logs/{fake_id}")

        assert resp.status_code == 404
        assert resp.json()["detail"]["error"] == "log_no_encontrado"

    async def test_get_log_invalid_uuid(self, client: AsyncClient):
        """UUID inválido retorna 422."""
        resp = await client.get("/api/v1/logs/not-a-uuid")
        assert resp.status_code == 422


# ============================================================
# Tests GET /api/v1/logs
# ============================================================

class TestListLogs:
    """Tests del endpoint GET /api/v1/logs."""

    async def test_list_logs_returns_200(self, client: AsyncClient):
        """Listar logs retorna 200 con estructura correcta."""
        resp = await client.get("/api/v1/logs")

        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data
        assert "offset" in data
        assert "limit" in data

    async def test_list_logs_pagination_params(self, client: AsyncClient):
        """Los parámetros de paginación se reflejan en la respuesta."""
        resp = await client.get("/api/v1/logs", params={"limit": 10, "offset": 5})
        data = resp.json()

        assert data["limit"] == 10
        assert data["offset"] == 5
