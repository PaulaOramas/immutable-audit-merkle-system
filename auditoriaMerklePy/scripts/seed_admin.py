"""
Seed script — Crea el usuario administrador por defecto.

Credenciales:
    username: admin
    password: admin123!

Uso:
    python -m scripts.seed_admin
"""

import sys
import os

# Asegurar que el directorio raíz del proyecto esté en el path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from passlib.context import CryptContext

from app.config import settings
from app.db.base import Base
from app.models.audit_user import AuditUser

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

SEED_USERS = [
    {
        "username": "admin",
        "password": "admin123!",
        "full_name": "Administrador del Sistema",
        "role": "admin",
    },
    {
        "username": "auditor",
        "password": "auditor123!",
        "full_name": "Auditor Principal",
        "role": "auditor",
    },
]


def main():
    engine = create_engine(settings.DATABASE_URL_SYNC, echo=False)

    with Session(engine) as session:
        for user_data in SEED_USERS:
            existing = session.execute(
                select(AuditUser).where(AuditUser.username == user_data["username"])
            ).scalar_one_or_none()

            if existing:
                print(f"  ⏭  Usuario '{user_data['username']}' ya existe — omitido.")
                continue

            user = AuditUser(
                username=user_data["username"],
                password_hash=pwd_context.hash(user_data["password"]),
                full_name=user_data["full_name"],
                role=user_data["role"],
                is_active=True,
            )
            session.add(user)
            print(f"  ✅ Usuario '{user_data['username']}' creado (role={user_data['role']})")

        session.commit()

        # Seed API Key for the simulator
        from app.models.api_key import ApiKey
        import hashlib
        
        sim_app_name = "SecureBank Simulator"
        existing_key = session.execute(
            select(ApiKey).where(ApiKey.app_name == sim_app_name)
        ).scalar_one_or_none()

        if existing_key:
            print(f"  ⏭  API Key para '{sim_app_name}' ya existe — omitida.")
        else:
            raw_key = "mka_vlbodydfBaxATO_vIW175caYHxMw9vOGJ7MR86nW62igHPFL8_abQbhXjDwFwE0-"
            key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
            key_prefix = raw_key[:8]
            
            api_key = ApiKey(
                key_hash=key_hash,
                key_prefix=key_prefix,
                app_name=sim_app_name,
                description="API Key estática para el simulador de eventos",
                is_active=True
            )
            session.add(api_key)
            session.commit()
            print(f"  ✅ API Key para '{sim_app_name}' creada exitosamente.")

    print("\n🎉 Seed completado.")
    print("   Credenciales de acceso:")
    print("   ─────────────────────────────────")
    print("   Admin:   admin / admin123!")
    print("   Auditor: auditor / auditor123!")
    print("   ─────────────────────────────────")


if __name__ == "__main__":
    main()
