import asyncio
from sqlalchemy import select
from app.db.session import async_session_maker
from app.models.log_entry import LogEntry
from app.core.hashing import hash_log_entry

async def main():
    async with async_session_maker() as session:
        result = await session.execute(select(LogEntry).limit(1))
        log = result.scalar_one_or_none()
        if not log:
            print("No logs")
            return
            
        print("Original hash:", log.content_hash)
        
        hasheable_data = {
            "source_app": log.source_app,
            "event_type": log.event_type,
            "severity": log.severity,
            "payload": log.payload,
        }
        calc_hash = hash_log_entry(hasheable_data)
        print("Calculated hash:", calc_hash)
        print("Match?", calc_hash == log.content_hash)

asyncio.run(main())
