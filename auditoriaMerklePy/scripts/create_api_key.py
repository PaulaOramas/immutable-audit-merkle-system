import asyncio
from app.db.session import get_async_session_factory
from app.services.auth_service import AuthService

async def main():
    factory = get_async_session_factory()
    async with factory() as session:
        service = AuthService(session)
        api_key, raw_key = await service.create_api_key(
            app_name="SecureBank Simulator",
            description="API Key para el simulador de eventos"
        )
        await session.commit()
        print(f"API_KEY={raw_key}")

if __name__ == "__main__":
    asyncio.run(main())
