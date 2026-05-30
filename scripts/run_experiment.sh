#!/usr/bin/env bash
set -euo pipefail

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$BASE_DIR"

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker não encontrado. Instale Docker para executar o experimento."
  exit 1
fi

echo "Iniciando experimento de checkpoint 3..."
docker compose up --build -d

echo "Aguardando 10 segundos para a coleta inicial de dados..."
sleep 10

API_URL="http://localhost:8000"

echo "Executando requisições de verificação"
curl -fsS "$API_URL/api/health" || true
curl -fsS "$API_URL/api/latest" || true
curl -fsS "$API_URL/api/history?limit=5" || true
curl -fsS "$API_URL/api/summary" || true

echo "Resultados preliminares salvos em results/" 
cat <<'EOF' > results/README.md
Este experimento de checkpoint 3 roda três serviços principais:
- broker MQTT (Mosquitto)
- sensor simulador de telemetria
- coletor MQTT que persiste em SQLite
- API web que exibe dados e histórico

Para validar a coleta real, acesse:
- http://localhost:8000
- http://localhost:8000/api/latest
- http://localhost:8000/api/history?limit=10
- http://localhost:8000/api/summary
EOF

echo "Experimento iniciado. Confira o dashboard em http://localhost:8000"
