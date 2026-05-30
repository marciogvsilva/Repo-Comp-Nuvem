#!/bin/bash

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RESULTS_DIR="$PROJECT_DIR/results"
DB_PATH="/app/data/products.db"
NUM_PRODUCTS=10000

echo "=========================================="
echo "SSC0158 - REST API Design Evaluation"
echo "=========================================="

# Create results directory
mkdir -p "$RESULTS_DIR"

# Start Docker containers
echo -e "\n[1/4] Iniciando containers Docker..."
cd "$PROJECT_DIR"
docker compose down 2>/dev/null
docker compose up -d --build

# Wait for API to be ready
echo -e "\n[2/4] Aguardando API ficar pronta..."
for i in {1..30}; do
    if curl -s http://localhost:8000/api/health > /dev/null 2>&1; then
        echo "✅ API pronta"
        break
    fi
    sleep 1
done

# Populate database
echo -e "\n[3/4] Populando base de dados com $NUM_PRODUCTS produtos..."
docker exec ssc0158_api python scripts/populate_db.py "$DB_PATH" "$NUM_PRODUCTS"

# Run K6 load tests
echo -e "\n[4/4] Executando testes de carga..."
if command -v k6 &> /dev/null; then
    k6 run -e BASE_URL=http://localhost:8000 \
           --out json="$RESULTS_DIR/load_test_results.json" \
           "$PROJECT_DIR/experiments/load_test.js"
    echo "✅ Testes concluídos"
else
    echo "⚠️  K6 não instalado. Pulando testes de carga."
    echo "    Instale com: npm install -g k6"
fi

echo -e "\n=========================================="
echo "Experimento concluído!"
echo "Resultados salvos em: $RESULTS_DIR"
echo "=========================================="
