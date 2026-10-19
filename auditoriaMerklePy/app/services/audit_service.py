"""
Servicio de Auditoría — Verificación masiva, reportes y anclajes.

Encapsula la lógica de:
- Verificación masiva de integridad de todos los batches cerrados
- Generación de reportes de auditoría
- Consulta de registros de anclaje
"""

from datetime import datetime, timezone
from typing import Optional, List, Tuple
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.merkle_tree import MerkleTree
from app.models.anchor_record import AnchorRecord
from app.models.log_entry import LogEntry
from app.models.merkle_batch import MerkleBatch
from app.models.merkle_node import MerkleNode
from app.repositories.anchor_record_repo import AnchorRecordRepository
from app.repositories.log_entry_repo import LogEntryRepository
from app.repositories.merkle_batch_repo import MerkleBatchRepository
from app.repositories.merkle_node_repo import MerkleNodeRepository


class AuditService:
    """Servicio de auditoría e integridad del sistema."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.batch_repo = MerkleBatchRepository(session)
        self.node_repo = MerkleNodeRepository(session)
        self.log_repo = LogEntryRepository(session)
        self.anchor_repo = AnchorRecordRepository(session)

    # ============================================================
    # Verificación Masiva de Integridad
    # ============================================================

    async def check_integrity(self) -> dict:
        """
        Verifica la integridad de TODOS los batches cerrados/anclados.

        Para cada batch cerrado:
        1. Obtiene las hojas persistidas
        2. Reconstruye el Merkle Tree en memoria
        3. Compara el root recalculado con el almacenado

        Returns:
            dict compatible con IntegrityCheckResponse.
        """
        # Obtener todos los batches
        all_batches = await self.batch_repo.get_all(offset=0, limit=10000)

        details = []
        valid_count = 0
        invalid_count = 0
        skipped_count = 0

        for batch in all_batches:
            result = {
                "batch_id": batch.id,
                "batch_number": batch.batch_number,
                "status": batch.status,
                "leaf_count": batch.leaf_count,
                "merkle_root": batch.merkle_root,
            }

            # Solo verificar batches cerrados o anclados
            if batch.status == "open":
                result["root_matches"] = None
                result["error"] = "Batch abierto, omitido"
                skipped_count += 1
                details.append(result)
                continue

            if not batch.merkle_root:
                result["root_matches"] = None
                result["error"] = "Sin Merkle Root"
                skipped_count += 1
                details.append(result)
                continue

            try:
                # Obtener hojas del batch
                leaf_nodes = await self.node_repo.get_leaves(batch.id)

                if not leaf_nodes:
                    result["root_matches"] = None
                    result["error"] = "Sin nodos de hoja persistidos"
                    skipped_count += 1
                    details.append(result)
                    continue

                # Reconstruir el árbol
                leaf_hashes = [node.hash_value for node in leaf_nodes]
                tree = MerkleTree(leaf_hashes)

                # Comparar roots
                matches = tree.root == batch.merkle_root
                result["root_matches"] = matches

                if matches:
                    valid_count += 1
                else:
                    invalid_count += 1
                    result["error"] = (
                        f"Root mismatch: recalculado={tree.root}, "
                        f"almacenado={batch.merkle_root}"
                    )
            except Exception as e:
                result["root_matches"] = False
                result["error"] = f"Error al verificar: {str(e)}"
                invalid_count += 1

            details.append(result)

        total = len(all_batches)
        return {
            "total_batches": total,
            "valid_batches": valid_count,
            "invalid_batches": invalid_count,
            "skipped_batches": skipped_count,
            "overall_integrity": invalid_count == 0 and valid_count > 0,
            "checked_at": datetime.now(timezone.utc),
            "details": details,
        }

    # ============================================================
    # Reporte de Auditoría
    # ============================================================

    async def generate_report(self) -> dict:
        """
        Genera un reporte completo de auditoría del sistema.

        Incluye:
        - Resumen general (total logs, batches, etc.)
        - Estado de integridad
        - Detalle de cada batch con info de anclaje
        """
        # Conteos generales
        total_logs = await self.log_repo.count()
        total_batches = await self.batch_repo.count()

        # Contar por estado
        open_batches = await self.batch_repo.get_by_status("open")
        closed_batches = await self.batch_repo.get_by_status("closed")
        anchored_batches = await self.batch_repo.get_by_status("anchored")

        # Logs sin asignar
        unassigned_logs = await self.log_repo.count_unassigned()

        # Total anclajes
        anchor_count_result = await self.session.execute(
            select(func.count()).select_from(AnchorRecord)
        )
        total_anchors = anchor_count_result.scalar_one()

        # Detalle de batches con anclajes
        all_batches = await self.session.execute(
            select(MerkleBatch)
            .options(selectinload(MerkleBatch.anchor_records))
            .order_by(MerkleBatch.batch_number)
        )
        batches = list(all_batches.scalars().all())

        batch_summaries = []
        for b in batches:
            anchors = b.anchor_records or []
            latest_anchor = anchors[0] if anchors else None
            batch_summaries.append({
                "batch_number": b.batch_number,
                "status": b.status,
                "leaf_count": b.leaf_count,
                "merkle_root": b.merkle_root,
                "created_at": b.created_at,
                "closed_at": b.closed_at,
                "is_anchored": b.status == "anchored" or len(anchors) > 0,
                "anchor_tx": latest_anchor.tx_hash if latest_anchor else None,
                "anchor_network": latest_anchor.network if latest_anchor else None,
            })

        # Verificación rápida de integridad
        integrity = await self.check_integrity()

        return {
            "report_generated_at": datetime.now(timezone.utc),
            "system_summary": {
                "total_logs": total_logs,
                "total_batches": total_batches,
                "open_batches": len(open_batches),
                "closed_batches": len(closed_batches),
                "anchored_batches": len(anchored_batches),
                "unassigned_logs": unassigned_logs,
                "total_anchors": total_anchors,
            },
            "integrity_status": {
                "overall_integrity": integrity["overall_integrity"],
                "valid_batches": integrity["valid_batches"],
                "invalid_batches": integrity["invalid_batches"],
                "skipped_batches": integrity["skipped_batches"],
                "checked_at": integrity["checked_at"].isoformat(),
            },
            "batches": batch_summaries,
        }

    # ============================================================
    # Anclajes
    # ============================================================

    async def list_anchors(
        self,
        network: Optional[str] = None,
        offset: int = 0,
        limit: int = 50,
    ) -> Tuple[List[dict], int]:
        """
        Listar registros de anclaje con filtro opcional por red.

        Incluye batch_number para facilitar la referencia cruzada.
        """
        # Query base con join para obtener batch_number
        query = (
            select(AnchorRecord, MerkleBatch.batch_number)
            .join(MerkleBatch, AnchorRecord.batch_id == MerkleBatch.id)
            .order_by(AnchorRecord.anchored_at.desc())
        )

        if network:
            query = query.where(AnchorRecord.network == network)

        # Contar total
        from sqlalchemy import func as sqla_func
        count_query = select(sqla_func.count()).select_from(AnchorRecord)
        if network:
            count_query = count_query.where(AnchorRecord.network == network)
        count_result = await self.session.execute(count_query)
        total = count_result.scalar_one()

        # Paginación
        query = query.offset(offset).limit(limit)
        result = await self.session.execute(query)

        items = []
        for anchor, batch_number in result.all():
            items.append({
                "id": anchor.id,
                "batch_id": anchor.batch_id,
                "batch_number": batch_number,
                "merkle_root": anchor.merkle_root,
                "anchor_type": anchor.anchor_type,
                "tx_hash": anchor.tx_hash,
                "block_number": anchor.block_number,
                "network": anchor.network,
                "anchor_metadata": anchor.anchor_metadata,
                "anchored_at": anchor.anchored_at,
            })

        return items, total
