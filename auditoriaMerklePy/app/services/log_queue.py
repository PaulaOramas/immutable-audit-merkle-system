"""
LogQueue — Cola interna de procesamiento en tiempo real.

Usa asyncio.Queue para desacoplar la recepción de logs (respuesta rápida)
del procesamiento pesado (asignación a batch, cierre automático, árbol Merkle).

Arquitectura:
    API → LogQueue.enqueue() → respuesta inmediata al cliente
    Worker (background) → LogQueue.process_next() → persistir + batch assign

Esto permite:
- Respuesta inmediata al cliente (< 10ms)
- Procesamiento asíncrono sin bloquear el event loop de FastAPI
- Buffering ante picos de tráfico
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.config import settings
from app.schemas.log_entry import LogEntryCreate

logger = logging.getLogger(__name__)


@dataclass
class QueuedLog:
    """Un log en la cola esperando ser procesado."""
    id: UUID = field(default_factory=uuid4)
    data: LogEntryCreate = field(default=None)
    enqueued_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    source_ip: Optional[str] = None


class LogQueue:
    """
    Cola de procesamiento de logs basada en asyncio.Queue.

    Actúa como buffer entre la recepción HTTP y el procesamiento
    pesado (hashing, deduplicación, persistencia, asignación a batch).

    Atributos:
        max_size: Tamaño máximo de la cola (backpressure).
        _queue: Cola async interna.
        _processed: Contador de logs procesados.
        _errors: Contador de errores.
    """

    def __init__(self, max_size: int = 10000):
        self._queue: asyncio.Queue[QueuedLog] = asyncio.Queue(maxsize=max_size)
        self.max_size = max_size
        self._processed = 0
        self._errors = 0
        self._running = False
        self._worker_task: Optional[asyncio.Task] = None

    @property
    def size(self) -> int:
        """Cantidad de logs pendientes en la cola."""
        return self._queue.qsize()

    @property
    def is_full(self) -> bool:
        """Si la cola está llena."""
        return self._queue.full()

    @property
    def processed_count(self) -> int:
        """Total de logs procesados exitosamente."""
        return self._processed

    @property
    def error_count(self) -> int:
        """Total de errores de procesamiento."""
        return self._errors

    async def enqueue(self, data: LogEntryCreate, source_ip: str = None) -> QueuedLog:
        """
        Encola un log para procesamiento asíncrono.

        Si la cola está llena, lanza QueueFullError (backpressure).

        Args:
            data: Datos del log validados por Pydantic.
            source_ip: IP de origen (para logging).

        Returns:
            QueuedLog con el ID de tracking.

        Raises:
            QueueFullError: Si la cola está llena.
        """
        if self._queue.full():
            raise QueueFullError(
                f"Cola llena ({self.max_size} elementos). "
                "Reintente en unos segundos."
            )

        queued = QueuedLog(data=data, source_ip=source_ip)
        await self._queue.put(queued)

        logger.debug(
            "Log encolado: queue_id=%s, queue_size=%d",
            queued.id, self.size,
        )
        return queued

    async def process_next(self, session: AsyncSession) -> Optional[Dict[str, Any]]:
        """
        Procesa el siguiente log de la cola.

        Saca un log de la cola y lo procesa usando LogService
        (hash, deduplicar, persistir, asignar a batch).

        Args:
            session: Sesión de BD activa.

        Returns:
            Dict con resultado del procesamiento, o None si la cola está vacía.
        """
        try:
            queued = self._queue.get_nowait()
        except asyncio.QueueEmpty:
            return None

        try:
            from app.services.log_service import LogService, DuplicateLogError

            service = LogService(session)
            log = await service.create_log(queued.data)

            self._processed += 1
            self._queue.task_done()

            elapsed = (datetime.now(timezone.utc) - queued.enqueued_at).total_seconds()
            logger.debug(
                "Log procesado: id=%s, queue_time=%.3fs",
                log.id, elapsed,
            )
            return {
                "queue_id": str(queued.id),
                "log_id": str(log.id),
                "content_hash": log.content_hash,
                "batch_id": str(log.batch_id) if log.batch_id else None,
                "processing_time_seconds": elapsed,
                "status": "processed",
            }

        except DuplicateLogError as e:
            self._queue.task_done()
            logger.debug("Log duplicado omitido: %s", e.content_hash)
            return {
                "queue_id": str(queued.id),
                "status": "duplicate",
                "content_hash": e.content_hash,
            }

        except Exception as e:
            self._errors += 1
            self._queue.task_done()
            logger.error("Error procesando log %s: %s", queued.id, str(e))
            return {
                "queue_id": str(queued.id),
                "status": "error",
                "error": str(e),
            }

    async def start_worker(self, batch_size: int = 10) -> None:
        """
        Inicia el worker de procesamiento en background.

        Procesa logs de la cola continuamente. Usa un batch_size
        para procesar varios logs por sesión de BD.

        Args:
            batch_size: Cantidad de logs a procesar por ciclo.
        """
        if self._running:
            logger.warning("Worker ya está corriendo")
            return

        self._running = True
        logger.info(
            "LogQueue worker iniciado (batch_size=%d, max_queue=%d)",
            batch_size, self.max_size,
        )

        engine = create_async_engine(settings.DATABASE_URL, echo=False)
        factory = async_sessionmaker(
            bind=engine, class_=AsyncSession, expire_on_commit=False,
        )

        try:
            while self._running:
                if self._queue.empty():
                    await asyncio.sleep(0.1)  # Polling interval
                    continue

                async with factory() as session:
                    try:
                        processed = 0
                        while processed < batch_size and not self._queue.empty():
                            result = await self.process_next(session)
                            if result:
                                processed += 1

                        if processed > 0:
                            await session.commit()
                            logger.debug(
                                "Ciclo de worker: %d logs procesados, cola=%d",
                                processed, self.size,
                            )
                    except Exception:
                        await session.rollback()
                        logger.exception("Error en ciclo de worker")
        finally:
            await engine.dispose()
            self._running = False
            logger.info("LogQueue worker detenido")

    def stop_worker(self) -> None:
        """Señala al worker que debe detenerse."""
        self._running = False
        if self._worker_task and not self._worker_task.done():
            self._worker_task.cancel()
        logger.info("LogQueue worker señalado para detener")

    def get_stats(self) -> Dict[str, Any]:
        """Retorna estadísticas de la cola."""
        return {
            "queue_size": self.size,
            "max_size": self.max_size,
            "processed": self._processed,
            "errors": self._errors,
            "is_running": self._running,
            "is_full": self.is_full,
        }


class QueueFullError(Exception):
    """Se lanza cuando la cola está llena (backpressure)."""
    pass


# ============================================================
# Instancia global de la cola (Singleton)
# ============================================================

_log_queue: Optional[LogQueue] = None


def get_log_queue() -> LogQueue:
    """Obtiene la instancia global de LogQueue."""
    global _log_queue
    if _log_queue is None:
        _log_queue = LogQueue(max_size=settings.QUEUE_MAX_SIZE)
    return _log_queue


def reset_log_queue() -> None:
    """Resetea la cola (para tests)."""
    global _log_queue
    if _log_queue:
        _log_queue.stop_worker()
    _log_queue = None
