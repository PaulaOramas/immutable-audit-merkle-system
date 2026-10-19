from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import update, select
from typing import Dict, Any, List

from app.db.session import get_async_session
from app.models.log_entry import LogEntry
from app.core.hashing import hash_log_entry

router = APIRouter()

@router.post("/tamper-database")
async def tamper_database_payload(
    log_id: str,
    new_payload: Dict[str, Any],
    hacker_username: str = "sys_admin_escalated",
    db: AsyncSession = Depends(get_async_session)
):
    """
    Simula un ataque directo a la base de datos (Inyección/DBA Malicioso).
    Modifica el payload de un log específico SIN actualizar su content_hash,
    esquivando la lógica de la API para generar una discrepancia en la integridad.
    """
    result = await db.execute(select(LogEntry).where(LogEntry.id == log_id))
    log_entry = result.scalar_one_or_none()
    
    if not log_entry:
        raise HTTPException(status_code=404, detail="Log entry not found")
        
    # Hacemos el update con SQLAlchemy a bajo nivel para esquivar 
    # la generación de un nuevo content_hash (como si fuera un UPDATE en raw SQL)
    stmt = (
        update(LogEntry)
        .where(LogEntry.id == log_id)
        .values(
            payload=new_payload,
            severity="critical"  # También alteramos la severidad como daño adicional
        )
    )
    await db.execute(stmt)
    await db.commit()
    
    return {
        "success": True,
        "message": f"Base de datos alterada por {hacker_username}. Payload modificado sin actualizar hashes.",
        "log_id": log_id
    }

@router.get("/scan-integrity")
async def scan_database_integrity(db: AsyncSession = Depends(get_async_session)):
    """
    Escáner forense (El SOC del Dashboard).
    Lee los últimos 100 logs y verifica matemáticamente si la información de
    la base de datos cuadra con su huella digital original.
    """
    result = await db.execute(
        select(LogEntry).order_by(LogEntry.created_at.desc()).limit(100)
    )
    logs = result.scalars().all()
    
    compromised_records = []
    
    for log in logs:
        # Reconstruimos la misma estructura que usó log_service al crearlo
        hasheable_data = {
            "source_app": log.source_app,
            "event_type": log.event_type,
            "severity": log.severity,
            "payload": log.payload,
        }
        calculated_hash = hash_log_entry(hasheable_data)
        
        # Si el hash recalculado no coincide con el guardado en la base de datos,
        # significa que alguien modificó los datos subyacentes.
        if calculated_hash != log.content_hash:
            compromised_records.append({
                "log_id": str(log.id),
                "event_type": log.event_type,
                "timestamp": log.created_at.isoformat(),
                "stored_hash": log.content_hash,
                "calculated_hash": calculated_hash,
                "suspicious_payload": log.payload
            })
            
    return {
        "scanned_count": len(logs),
        "compromised_count": len(compromised_records),
        "compromised_records": compromised_records
    }
