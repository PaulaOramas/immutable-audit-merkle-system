"""
Servicio de negocio para LogEntry.

Encapsula la lógica de:
- Recepción de logs
- Cálculo del hash canónico (content_hash)
- Deduplicación
- Persistencia
- Asignación automática a batch activo (integración con MerkleService)
"""

import logging
from typing import Optional, List, Tuple
from uuid import UUID
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.hashing import hash_log_entry
from app.models.log_entry import LogEntry
from app.repositories.log_entry_repo import LogEntryRepository
from app.schemas.log_entry import LogEntryCreate

logger = logging.getLogger(__name__)


class DuplicateLogError(Exception):
    """Se lanza cuando se intenta ingestar un log con hash duplicado."""

    def __init__(self, content_hash: str):
        self.content_hash = content_hash
        super().__init__(f"Log duplicado: ya existe un log con hash {content_hash}")


class LogService:
    """
    Servicio de negocio para la ingesta y consulta de logs.

    Flujo de ingesta:
        Recibe log → calcula hash → persiste → asigna a batch activo.

    Si el batch activo alcanza BATCH_MAX_LEAVES, MerkleService lo cierra
    automáticamente (construye árbol, calcula root, persiste nodos).
    """

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = LogEntryRepository(session)
        # Import diferido para evitar circular imports
        from app.services.merkle_service import MerkleService
        self.merkle_service = MerkleService(session)

    async def create_log(self, data: LogEntryCreate) -> LogEntry:
        """
        Crear un nuevo log de auditoría y asignarlo al batch activo.

        1. Construye el dict hasheables (source_app + event_type + severity + payload)
        2. Calcula el content_hash con serialización canónica
        3. Verifica que no exista un log con el mismo hash (deduplicación)
        4. Persiste el LogEntry
        5. Asigna el log al batch activo (crea uno si no existe)
        6. Si el batch alcanza BATCH_MAX_LEAVES, se cierra automáticamente

        Args:
            data: Datos del log (validados por Pydantic).

        Returns:
            LogEntry creado con su content_hash calculado y batch_id asignado.

        Raises:
            DuplicateLogError: Si ya existe un log con el mismo hash.
        """
        # Construir el diccionario hasheable
        hasheable_data = {
            "source_app": data.source_app,
            "event_type": data.event_type,
            "severity": data.severity,
            "payload": data.payload,
        }

        # Calcular hash canónico
        content_hash = hash_log_entry(hasheable_data)

        # Verificar duplicados
        existing = await self.repo.get_by_content_hash(content_hash)
        if existing:
            raise DuplicateLogError(content_hash)

        # Crear el LogEntry
        log_entry = LogEntry(
            source_app=data.source_app,
            event_type=data.event_type,
            severity=data.severity,
            payload=data.payload,
            content_hash=content_hash,
        )

        created = await self.repo.create(log_entry)

        # Asignar al batch activo (auto-cierra si alcanza N hojas)
        await self.merkle_service.assign_log_to_batch(created)

        logger.info(
            "Log ingestado: id=%s, hash=%s, batch=%s, leaf=%s",
            created.id, content_hash[:16] + "...",
            created.batch_id, created.leaf_index,
        )
        return created

    async def create_logs_batch(
        self, logs_data: List[LogEntryCreate]
    ) -> List[LogEntry]:
        """
        Crear múltiples logs en una sola transacción.

        Los logs duplicados se omiten (no lanzan error en modo batch),
        pero se retorna una lista solo con los logs creados exitosamente.
        Cada log creado se asigna automáticamente al batch activo.

        Args:
            logs_data: Lista de datos de logs.

        Returns:
            Lista de LogEntry creados (sin los duplicados).
        """
        created_logs: List[LogEntry] = []

        for data in logs_data:
            hasheable_data = {
                "source_app": data.source_app,
                "event_type": data.event_type,
                "severity": data.severity,
                "payload": data.payload,
            }
            content_hash = hash_log_entry(hasheable_data)

            # Omitir duplicados en batch
            existing = await self.repo.get_by_content_hash(content_hash)
            if existing:
                continue

            log_entry = LogEntry(
                source_app=data.source_app,
                event_type=data.event_type,
                severity=data.severity,
                payload=data.payload,
                content_hash=content_hash,
            )
            created = await self.repo.create(log_entry)

            # Asignar al batch activo
            await self.merkle_service.assign_log_to_batch(created)
            created_logs.append(created)

        logger.info(
            "Batch de ingesta: %d/%d logs creados y asignados",
            len(created_logs), len(logs_data),
        )
        return created_logs

    async def get_log(self, log_id: UUID) -> Optional[LogEntry]:
        """Obtener un log por su ID."""
        return await self.repo.get_by_id(log_id)

    async def list_logs(
        self,
        source_app: Optional[str] = None,
        event_type: Optional[str] = None,
        severity: Optional[str] = None,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
        offset: int = 0,
        limit: int = 50,
    ) -> Tuple[List[LogEntry], int]:
        """
        Listar logs con filtros opcionales y paginación.

        Returns:
            Tupla (lista_de_logs, total_count).
        """
        logs = await self.repo.search(
            source_app=source_app,
            event_type=event_type,
            severity=severity,
            from_date=from_date,
            to_date=to_date,
            offset=offset,
            limit=limit,
        )
        total = await self.repo.count()
        return logs, total
