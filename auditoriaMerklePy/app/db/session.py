"""
Configuración de la base de datos y gestión de sesiones.

Usa SQLAlchemy 2.0 con soporte async (asyncpg).
La URL de conexión se lee desde las variables de entorno.

NOTA: Los engines se crean de forma lazy (bajo demanda) para evitar
intentos de conexión al importar el módulo.
"""

from typing import AsyncGenerator, Generator

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import Session
from sqlalchemy import create_engine

from app.config import settings


# ============================================================
# Motor async (para la aplicación FastAPI)
# ============================================================

_async_engine = None
_async_session_factory = None


def get_async_engine():
    """Obtener el motor async (creación lazy)."""
    global _async_engine
    if _async_engine is None:
        _async_engine = create_async_engine(
            settings.DATABASE_URL,
            echo=settings.DEBUG,
            pool_size=5,
            max_overflow=10,
        )
    return _async_engine


def get_async_session_factory():
    """Obtener la factory de sesiones async (creación lazy)."""
    global _async_session_factory
    if _async_session_factory is None:
        _async_session_factory = async_sessionmaker(
            bind=get_async_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _async_session_factory


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency de FastAPI para obtener una sesión async."""
    factory = get_async_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# ============================================================
# Motor sync (para Alembic y scripts)
# ============================================================

_sync_engine = None


def get_sync_engine():
    """Obtener el motor síncrono (creación lazy)."""
    global _sync_engine
    if _sync_engine is None:
        _sync_engine = create_engine(
            settings.DATABASE_URL_SYNC,
            echo=settings.DEBUG,
        )
    return _sync_engine


def get_sync_session() -> Generator[Session, None, None]:
    """Obtener una sesión síncrona (para Alembic y scripts)."""
    engine = get_sync_engine()
    with Session(engine) as session:
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
