"""
Entry point de la aplicación FastAPI.

Incluye:
- Registro de routers (logs, verify, batches, audit, auth)
- Lifespan para iniciar/detener BatchScheduler y LogQueue worker
- Endpoint de health check y estado de la cola
"""

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import settings
from app.api.logs import router as logs_router
from app.api.verify import router as verify_router
from app.api.batches import router as batches_router
from app.api.audit import router as audit_router
from app.api.auth import router as auth_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan de la aplicación.

    Startup:
        - Inicia el BatchScheduler si está habilitado
        - Inicia el LogQueue worker si está habilitado
    Shutdown:
        - Detiene el BatchScheduler
        - Detiene el LogQueue worker
    """
    # Startup
    if settings.SCHEDULER_ENABLED:
        from app.services.batch_scheduler import start_scheduler
        start_scheduler()
        logger.info("BatchScheduler iniciado")
    else:
        logger.info("BatchScheduler deshabilitado (SCHEDULER_ENABLED=False)")

    # Iniciar worker de la cola
    queue_task = None
    if settings.QUEUE_ENABLED:
        from app.services.log_queue import get_log_queue
        queue = get_log_queue()
        queue_task = asyncio.create_task(
            queue.start_worker(batch_size=settings.QUEUE_WORKER_BATCH_SIZE)
        )
        logger.info(
            "LogQueue worker iniciado (max=%d, batch_size=%d)",
            settings.QUEUE_MAX_SIZE, settings.QUEUE_WORKER_BATCH_SIZE,
        )
    else:
        logger.info("LogQueue deshabilitada (QUEUE_ENABLED=False)")

    yield

    # Shutdown
    if settings.QUEUE_ENABLED:
        from app.services.log_queue import get_log_queue
        queue = get_log_queue()
        queue.stop_worker()
        if queue_task and not queue_task.done():
            queue_task.cancel()
            try:
                await queue_task
            except asyncio.CancelledError:
                pass
        logger.info("LogQueue worker detenido")

    if settings.SCHEDULER_ENABLED:
        from app.services.batch_scheduler import stop_scheduler
        stop_scheduler()
        logger.info("BatchScheduler detenido")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Sistema de auditoría inmutable basado en Árboles de Merkle",
    lifespan=lifespan,
)

# CORS — Permitir frontend (Fase 5)
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:5174", "http://127.0.0.1:5174"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from app.api.attack import router as attack_router

# Registrar routers
app.include_router(logs_router)
app.include_router(verify_router)
app.include_router(batches_router)
app.include_router(audit_router)
app.include_router(auth_router)
app.include_router(attack_router, prefix="/api/v1/attack", tags=["Forense"])


@app.get("/health", tags=["Sistema"])
async def health_check():
    """Verificar que el sistema está operativo."""
    result = {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "auth_enabled": settings.AUTH_ENABLED,
        "queue_enabled": settings.QUEUE_ENABLED,
    }

    if settings.QUEUE_ENABLED:
        from app.services.log_queue import get_log_queue
        result["queue"] = get_log_queue().get_stats()

    return result


