"""
Base declarativa de SQLAlchemy.

Todos los modelos heredan de esta clase Base.
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Clase base para todos los modelos SQLAlchemy."""
    pass
