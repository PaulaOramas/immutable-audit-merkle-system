"""
Tests unitarios para LogQueue (Fase 3.5).

Cubren:
- Enqueue/dequeue básico
- Backpressure (cola llena)
- Estadísticas
- Queue singleton
"""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from app.schemas.log_entry import LogEntryCreate
from app.services.log_queue import LogQueue, QueueFullError, get_log_queue, reset_log_queue


def _make_log_data(index: int = 1) -> LogEntryCreate:
    """Helper para crear datos de log de prueba."""
    return LogEntryCreate(
        source_app="test_app",
        event_type="test_event",
        severity="info",
        payload={"test": f"data_{index}", "index": index},
    )


# ============================================================
# Tests de LogQueue
# ============================================================

class TestLogQueue:

    @pytest.mark.asyncio
    async def test_enqueue_adds_to_queue(self):
        """Encolar un log incrementa el tamaño de la cola."""
        queue = LogQueue(max_size=100)
        data = _make_log_data(1)

        queued = await queue.enqueue(data)

        assert queue.size == 1
        assert queued.id is not None
        assert queued.data == data

    @pytest.mark.asyncio
    async def test_enqueue_multiple(self):
        """Encolar múltiples logs."""
        queue = LogQueue(max_size=100)

        for i in range(5):
            await queue.enqueue(_make_log_data(i))

        assert queue.size == 5

    @pytest.mark.asyncio
    async def test_queue_full_raises_error(self):
        """Cola llena lanza QueueFullError."""
        queue = LogQueue(max_size=2)

        await queue.enqueue(_make_log_data(1))
        await queue.enqueue(_make_log_data(2))

        assert queue.is_full is True

        with pytest.raises(QueueFullError, match="Cola llena"):
            await queue.enqueue(_make_log_data(3))

    @pytest.mark.asyncio
    async def test_process_next_empty_returns_none(self):
        """Procesar cola vacía retorna None."""
        queue = LogQueue(max_size=100)
        mock_session = AsyncMock()

        result = await queue.process_next(mock_session)
        assert result is None

    @pytest.mark.asyncio
    async def test_stats(self):
        """Estadísticas de la cola son correctas."""
        queue = LogQueue(max_size=50)

        stats = queue.get_stats()
        assert stats["queue_size"] == 0
        assert stats["max_size"] == 50
        assert stats["processed"] == 0
        assert stats["errors"] == 0
        assert stats["is_running"] is False
        assert stats["is_full"] is False

    @pytest.mark.asyncio
    async def test_enqueue_with_source_ip(self):
        """Se puede encolar con IP de origen."""
        queue = LogQueue(max_size=100)
        data = _make_log_data(1)

        queued = await queue.enqueue(data, source_ip="192.168.1.1")

        assert queued.source_ip == "192.168.1.1"


# ============================================================
# Tests de singleton
# ============================================================

class TestLogQueueSingleton:

    def test_get_log_queue_returns_same_instance(self):
        """get_log_queue retorna la misma instancia."""
        reset_log_queue()
        q1 = get_log_queue()
        q2 = get_log_queue()
        assert q1 is q2
        reset_log_queue()

    def test_reset_creates_new_instance(self):
        """reset_log_queue crea una nueva instancia."""
        reset_log_queue()
        q1 = get_log_queue()
        reset_log_queue()
        q2 = get_log_queue()
        assert q1 is not q2
        reset_log_queue()
