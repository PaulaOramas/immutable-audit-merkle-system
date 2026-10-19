"""
Configuración central de la aplicación.
Usa Pydantic Settings para manejar variables de entorno con validación de tipos.
"""

import secrets

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Configuración de la aplicación cargada desde variables de entorno."""

    # General
    APP_NAME: str = "Merkle Audit System"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = True

    # Base de datos
    DATABASE_URL: str = "postgresql+asyncpg://audit_user:audit_pass@localhost:5432/merkle_audit"
    DATABASE_URL_SYNC: str = "postgresql+psycopg2://audit_user:audit_pass@localhost:5432/merkle_audit"

    # Criptografía
    HASH_ALGORITHM: str = "sha256"

    # Merkle Tree
    BATCH_MAX_LEAVES: int = 1024  # Máximo de hojas por batch antes de cerrar
    BATCH_TIMEOUT_SECONDS: int = 300  # Tiempo máximo antes de cerrar un batch (5 min)

    # Scheduler
    SCHEDULER_ENABLED: bool = True  # Habilitar el scheduler de cierre por timeout
    SCHEDULER_INTERVAL_SECONDS: int = 30  # Intervalo de verificación del scheduler

    # Cola de procesamiento (Fase 3.5)
    QUEUE_ENABLED: bool = True  # Habilitar cola de procesamiento en background
    QUEUE_MAX_SIZE: int = 10000  # Tamaño máximo de la cola
    QUEUE_WORKER_BATCH_SIZE: int = 10  # Logs a procesar por ciclo del worker

    # Autenticación (Fase 3.6)
    AUTH_ENABLED: bool = True  # Habilitar autenticación (False para dev/tests)
    JWT_SECRET_KEY: str = secrets.token_urlsafe(32)  # Generar automáticamente si no se configura
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_MINUTES: int = 60  # Duración del token JWT (1 hora)

    # Blockchain / Anclaje (Fase 4.1)
    ANCHOR_ENABLED: bool = True  # Habilitar anclaje en blockchain
    GANACHE_URL: str = "http://127.0.0.1:8545"  # URL del nodo Ethereum
    CONTRACT_ADDRESS: str = ""  # Dirección del contrato MerkleAnchor (post-deploy)
    DEPLOYER_PRIVATE_KEY: str = ""  # Private key para firmar transacciones
    CHAIN_ID: int = 1337  # Chain ID (1337 = Ganache)
    ANCHOR_INTERVAL_SECONDS: int = 60  # Intervalo del job periódico de anclaje

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
