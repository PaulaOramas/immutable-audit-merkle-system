# 🛡️ Immutable Audit System with Merkle Trees & Blockchain Anchoring

Sistema integral de auditoría continua, integridad criptográfica y no-repudio diseñado para mitigar la mutabilidad de registros de auditoría y prevenir amenazas internas (*insider threats*) y manipulaciones no autorizadas en bases de datos tradicionales.

El sistema agrupa eventos de auditoría en lotes (*batching*), construye **árboles de Merkle** para verificar pruebas de inclusión en tiempo logarítmico $\mathcal{O}(\log n)$, y ancla periódicamente el *Root Hash* en una red blockchain local/EVM mediante contratos inteligentes.

---

## 🏗️ Arquitectura del Sistema

El proyecto opera como una arquitectura desacoplada en tres capas principales:

              ┌────────────────────────────────────────┐
              │      auditoriaMerkleLogs (React)       │
              │   (Simulador de Eventos & Incidentes)  │
              └───────────────────┬────────────────────┘
                                  │ Ingesta HTTP (REST API)
                                  ▼
              ┌────────────────────────────────────────┐
              │       auditoriaMerklePy (FastAPI)      │
              │  ┌──────────────────────────────────┐  │
              │  │ Pipeline de Hashing (SHA-256)    │  │
              │  │ Construcción Árboles de Merkle   │  │
              │  │ Motor de Lotes (Batching Engine) │  │
              │  └──────────────────┬───────────────┘  │
              └─────────┬───────────┴──────────┬───────┘
                        │                      │
         Persistencia   │                      │ Sellado On-Chain
                        ▼                      ▼
    ┌─────────────────────────┐      ┌─────────────────────────┐
    │  PostgreSQL (Relacional) │      │ Smart Contract Solidity │
    │  (Logs & Metadatos)     │      │   (Ganache / Hardhat)   │
    └─────────────────────────┘      └─────────────────────────┘
                        ▲
                        │ Verificación de Pruebas (Merkle Proofs)
                        │
              ┌─────────┴──────────────────────────────┐
              │      auditoriaMerkleFront (React)      │
              │   (Dashboard Forense & Verificación)   │
              └────────────────────────────────────────┘

1. **Simulador de Eventos (`auditoriaMerkleLogs`)**: Generador de tráfico y simulación de actividad transaccional (logins, transacciones bancarias, modificaciones de registros y escenarios de ataque como inyección SQL y DBAs comprometidos).
2. **Motor Criptográfico y Backend (`auditoriaMerklePy`)**: API construida en FastAPI responsable de la ingesta en tiempo real, normalización de eventos, cálculo de hashes SHA-256, estructuración del Árbol de Merkle, orquestación de lotes y comunicación Web3.
3. **Anclaje On-Chain (`blockchain/contracts`)**: Contrato inteligente en Solidity (`AuditAnchor.sol`) para el registro inmutable del *Merkle Root* y sellado de tiempo (*timestamping*).
4. **Dashboard de Auditoría Forense (`auditoriaMerkleFront`)**: Interfaz analítica para auditores que permite inspeccionar árboles jerárquicos, verificar pruebas criptográficas de inclusión (*proof path*) y detectar adulteraciones en bases de datos.

---

## 🛠️ Stack Tecnológico

* **Backend & Criptografía:** Python 3.11+, FastAPI, SQLAlchemy, Alembic, Hashlib (SHA-256), Web3.py.
* **Base de Datos:** PostgreSQL.
* **Blockchain & Smart Contracts:** Solidity, Hardhat, Ganache (EVM).
* **Frontend & Visualización:** React 19, Vite, Tailwind CSS, Lucide Icons.
* **Infraestructura & Pruebas:** Docker, Docker Compose, Pytest, Pytest-cov.

---

## 📂 Estructura del Repositorio

```text
.
├── auditoriaMerkleFront/       # Dashboard forense y módulo de verificación (React + Vite)
├── auditoriaMerkleLogs/        # Simulador de eventos de negocio y vectores de ataque (React)
├── auditoriaMerklePy/          # Backend de ingesta, motor criptográfico y contratos
│   ├── app/                    # Código fuente FastAPI (api, core, models, services)
│   ├── alembic/                # Migraciones del esquema relacional
│   ├── blockchain/             # Smart Contracts (Solidity), tests y scripts Hardhat
│   ├── scripts/                # Tareas administrativas y generación de API keys
│   └── tests/                  # Pruebas unitarias, de integración y seguridad
├── docs/                       # Guías de demostración y perfiles de ataque
├── start_all.sh                # Script de orquestación de servicios para entorno local
└── docker-compose.yml          # Despliegue de infraestructura base (DB & Blockchain)
