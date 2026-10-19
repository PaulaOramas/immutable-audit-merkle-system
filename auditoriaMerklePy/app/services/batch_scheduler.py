"""
BatchScheduler — Tareas periódicas automáticas.

Gestiona dos tareas con APScheduler (AsyncIOScheduler):

1. Cierre de batches por timeout:
   Verifica si el batch activo ha excedido BATCH_TIMEOUT_SECONDS
   y lo cierra automáticamente, incluso si no alcanzó BATCH_MAX_LEAVES.

2. Anclaje de batches cerrados en blockchain:
   Busca batches con status='closed' y los ancla en el smart contract
   MerkleAnchor usando Web3.py.

Configuración:
    SCHEDULER_INTERVAL_SECONDS: Intervalo de verificación de timeout.
    ANCHOR_INTERVAL_SECONDS: Intervalo de verificación de anclaje.
    ANCHOR_ENABLED: Habilitar/deshabilitar anclaje automático.
"""

import logging
from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.config import settings

logger = logging.getLogger(__name__)

# Instancia global del scheduler
_scheduler: AsyncIOScheduler | None = None


async def _check_and_close_expired_batches() -> None:
    """
    Job periódico: verifica si hay batches expirados y los cierra.

    Crea su propia sesión de BD para operar de forma independiente
    del ciclo request/response de FastAPI.
    """
    # Import diferido para evitar circular imports al iniciar
    from app.services.merkle_service import MerkleService

    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    factory = async_sessionmaker(
        bind=engine, class_=AsyncSession, expire_on_commit=False,
    )

    try:
        async with factory() as session:
            try:
                service = MerkleService(session)
                closed = await service.close_expired_batches()

                if closed:
                    for batch in closed:
                        logger.info(
                            "[Scheduler] Batch #%d cerrado por timeout. "
                            "Hojas: %d, Root: %s",
                            batch.batch_number,
                            batch.leaf_count,
                            batch.merkle_root[:16] + "..." if batch.merkle_root else "N/A",
                        )
                    await session.commit()
                else:
                    logger.debug("[Scheduler] Sin batches expirados")
            except Exception:
                await session.rollback()
                logger.exception("[Scheduler] Error al procesar batches expirados")
    finally:
        await engine.dispose()


async def _anchor_pending_batches() -> None:
    """
    Job periódico: ancla batches cerrados en blockchain.

    Busca batches con status='closed' y los ancla uno por uno
    usando AnchorService → MerkleAnchor.anchorRoot().
    """
    from app.services.anchor_service import AnchorService, AnchorServiceError

    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    factory = async_sessionmaker(
        bind=engine, class_=AsyncSession, expire_on_commit=False,
    )

    try:
        async with factory() as session:
            try:
                service = AnchorService(session)
                anchored = await service.anchor_pending_batches()

                if anchored:
                    for anchor in anchored:
                        logger.info(
                            "[Scheduler] Batch anclado en blockchain. "
                            "tx=%s, bloque=%d",
                            anchor.tx_hash[:16] + "...",
                            anchor.block_number,
                        )
                    await session.commit()
                else:
                    logger.debug("[Scheduler] Sin batches pendientes de anclaje")
            except AnchorServiceError as e:
                await session.rollback()
                logger.error("[Scheduler] Error de anclaje: %s", str(e))
            except Exception:
                await session.rollback()
                logger.exception("[Scheduler] Error inesperado en anclaje")
    finally:
        await engine.dispose()


def start_scheduler() -> AsyncIOScheduler:
    """
    Inicia el scheduler con las tareas periódicas.

    Jobs:
        1. batch_timeout_check — cada SCHEDULER_INTERVAL_SECONDS
        2. anchor_pending — cada ANCHOR_INTERVAL_SECONDS (si ANCHOR_ENABLED)

    Returns:
        AsyncIOScheduler configurado y en ejecución.
    """
    global _scheduler

    if _scheduler is not None and _scheduler.running:
        logger.warning("[Scheduler] Ya está en ejecución, omitiendo inicio")
        return _scheduler

    _scheduler = AsyncIOScheduler()

    # Job 1: Cierre de batches por timeout
    _scheduler.add_job(
        _check_and_close_expired_batches,
        trigger="interval",
        seconds=settings.SCHEDULER_INTERVAL_SECONDS,
        id="batch_timeout_check",
        name="Verificar y cerrar batches expirados",
        replace_existing=True,
    )

    # Job 2: Anclaje de batches cerrados en blockchain
    if settings.ANCHOR_ENABLED and settings.CONTRACT_ADDRESS:
        _scheduler.add_job(
            _anchor_pending_batches,
            trigger="interval",
            seconds=settings.ANCHOR_INTERVAL_SECONDS,
            id="anchor_pending",
            name="Anclar batches cerrados en blockchain",
            replace_existing=True,
        )
        logger.info(
            "[Scheduler] Job de anclaje habilitado — cada %ds",
            settings.ANCHOR_INTERVAL_SECONDS,
        )
    else:
        logger.info(
            "[Scheduler] Anclaje deshabilitado (ANCHOR_ENABLED=%s, CONTRACT=%s)",
            settings.ANCHOR_ENABLED,
            "configurado" if settings.CONTRACT_ADDRESS else "vacío",
        )

    _scheduler.start()

    logger.info(
        "[Scheduler] Iniciado — timeout check cada %ds, batch timeout: %ds",
        settings.SCHEDULER_INTERVAL_SECONDS,
        settings.BATCH_TIMEOUT_SECONDS,
    )
    return _scheduler


def stop_scheduler() -> None:
    """Detiene el scheduler de forma segura."""
    global _scheduler

    if _scheduler is not None and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("[Scheduler] Detenido")

    _scheduler = None


def get_scheduler() -> AsyncIOScheduler | None:
    """Retorna la instancia actual del scheduler (para monitoreo)."""
    return _scheduler

