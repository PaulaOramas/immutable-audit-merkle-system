#!/bin/bash
set -e

# Colores para output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}======================================================${NC}"
echo -e "${BLUE}  Iniciando Sistema de Auditoría Merkle Integrado     ${NC}"
echo -e "${BLUE}======================================================${NC}"

# 1. Iniciar Docker Compose (Postgres y Ganache)
echo -e "\n${YELLOW}[1/5] Iniciando servicios base (Postgres y Ganache)...${NC}"
cd auditoriaMerklePy
docker compose up -d

echo "Esperando a que Ganache y Postgres estén listos..."
sleep 3 # Esperar a que ganache inicie completamente

# 2. Desplegar Smart Contract
echo -e "\n${YELLOW}[2/5] Desplegando Smart Contract en Ganache...${NC}"
cd blockchain
export HARDHAT_DISABLE_TELEMETRY=true
npm install --silent
npx hardhat run scripts/deploy.js --network ganache

# Extraer dirección del contrato
CONTRACT_ADDRESS=$(node -e "console.log(require('./deployed_address.json').contractAddress)")
echo -e "${GREEN}Contrato desplegado en: $CONTRACT_ADDRESS${NC}"
cd ..

# 3. Configurar Backend y Base de Datos
echo -e "\n${YELLOW}[3/5] Configurando Backend y ejecutando migraciones...${NC}"

# Crear .env dinámico para el backend con la nueva dirección del contrato
cat <<EOF > .env
DATABASE_URL=postgresql+asyncpg://audit_user:audit_pass@localhost:5432/merkle_audit
DATABASE_URL_SYNC=postgresql+psycopg2://audit_user:audit_pass@localhost:5432/merkle_audit
CONTRACT_ADDRESS=$CONTRACT_ADDRESS
DEPLOYER_PRIVATE_KEY=0x4f3edf983ac636a65a842ce7c78d9aa706d3b113bce9c46f30d7d21715b23b1d
GANACHE_URL=http://127.0.0.1:8545
ANCHOR_ENABLED=True
EOF

# source venv/bin/activate
venv/bin/python -m alembic upgrade head
venv/bin/python -m scripts.seed_admin

# 4. Iniciar Servicios
echo -e "\n${YELLOW}[4/5] Iniciando aplicaciones...${NC}"

# Iniciar Backend
venv/bin/python -m uvicorn app.main:app --reload --port 8000 > backend.log 2>&1 &
BACKEND_PID=$!
echo -e "✓ Backend iniciado (PID: $BACKEND_PID)"

# Iniciar Dashboard Frontend
cd ../auditoriaMerkleFront
npm install --silent
npm run dev -- --port 5173 > frontend.log 2>&1 &
FRONT_PID=$!
echo -e "✓ Frontend Dashboard iniciado (PID: $FRONT_PID)"

# Iniciar Log Simulator Frontend
cd ../auditoriaMerkleLogs
npm install --silent
npm run dev -- --port 5174 > simulator.log 2>&1 &
LOGS_PID=$!
echo -e "✓ Frontend Simulador iniciado (PID: $LOGS_PID)"

cd ..

echo -e "\n${GREEN}======================================================${NC}"
echo -e "${GREEN}  ¡Todos los servicios están en ejecución!            ${NC}"
echo -e "${GREEN}======================================================${NC}"
echo -e "🔌 Backend API:        http://localhost:8000"
echo -e "📊 Frontend Dashboard: http://localhost:5173"
echo -e "🏦 Simulador de Logs:  http://localhost:5174"
echo -e "\nLos logs se están guardando en:"
echo -e " - auditoriaMerklePy/backend.log"
echo -e " - auditoriaMerkleFront/frontend.log"
echo -e " - auditoriaMerkleLogs/simulator.log"
echo -e "\n${YELLOW}Presiona Ctrl+C para detener todos los servicios.${NC}"

# Manejar Ctrl+C para matar los procesos de background
trap "echo -e '\nDeteniendo servicios...'; kill $BACKEND_PID $FRONT_PID $LOGS_PID; docker compose -f auditoriaMerklePy/docker-compose.yml stop; exit" SIGINT SIGTERM

# Esperar infinitamente
wait
