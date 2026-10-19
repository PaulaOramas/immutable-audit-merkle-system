"""
Schemas para autenticación.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class QueueStatusResponse(BaseModel):
    """Estado de la cola de procesamiento."""
    queue_size: int
    max_size: int
    processed: int
    errors: int
    is_running: bool
    is_full: bool


class EnqueueResponse(BaseModel):
    """Respuesta al encolar un log para procesamiento asíncrono."""
    queue_id: str
    status: str = "enqueued"
    message: str
    queue_size: int
