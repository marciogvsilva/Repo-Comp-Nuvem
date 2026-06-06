# SSC0158 - REST API Design Evaluation

Estudo empírico sobre o impacto de decisões de design em APIs RESTful, comparando estratégias de **paginação** (Offset vs Cursor) e **versionamento** (URI vs Headers HTTP).

## Objetivo

Avaliar, através de testes controlados e métricas quantitativas, como diferentes decisões arquiteturais em APIs REST afetam:
- **Desempenho**: latência, throughput, taxa de erro
- **Consumo de recursos**: CPU e memória
- **Evolutividade**: esforço para evoluir a API sem quebrar clientes

## Arquitetura

```
┌─────────────────────────────────────────────────────────────────┐
│                    Teste de Carga (K6)                          │
│                  (HTTP Requests em paralelo)                    │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │   FastAPI (Port 8000)│
                    │   /v1/produtos       │
                    │   /v2/produtos       │
                    │   /produtos (headers)│
                    │   /metrics           │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │  SQLite Database     │
                    │  (products.db)       │
                    └──────────────────────┘

    ┌──────────────────────────────────────────────────────┐
    │        Observabilidade e Coleta de Métricas          │
    ├──────────────────────────────────────────────────────┤
    │ • Prometheus (9090): coleta de métricas              │
    │ • Grafana (3000): visualização                       │
    └──────────────────────────────────────────────────────┘
```

## Endpoints Implementados

### Paginação com Offset (V1)
```bash
GET /v1/produtos?limit=50&offset=0
```

### Paginação com Cursor (V1)
```bash
GET /v1/produtos/cursor?limit=50&cursor=0
```

### Versionamento via URI (V2 com Offset)
```bash
GET /v2/produtos?limit=50&offset=0
```

### Versionamento via URI (V2 com Cursor)
```bash
GET /v2/produtos/cursor?limit=50&cursor=0
```

### Versionamento via Headers HTTP (Content Negotiation)
```bash
GET /produtos?limit=50&offset=0
Accept: application/vnd.api.v1+json  # ou v2

GET /produtos?limit=50&offset=0
Accept: application/vnd.api.v2+json
```

## Execução

### 1. Iniciar a aplicação com Docker Compose
```bash
cd ~/Documents/Disciplinas/Projeto\ de\ SI/SSC0158_checkpoint3
docker compose up -d --build
```

### 2. Popular a base de dados
```bash
docker exec ssc0158_api python /app/scripts/populate_db.py /app/data/products.db 10000
```

Alternativa fora do Docker:
```bash
python scripts/populate_db.py data/products.db 10000
```

### 3. Executar testes de carga com K6
```bash
k6 run -e BASE_URL=http://localhost:8000 experiments/load_test.js
```

### 4. Acessar Grafana para visualizar métricas
```
http://localhost:3000 (admin / admin)
```

## Estrutura do Projeto

```
├── docker-compose.yml          # Orquestração (API, Prometheus, Grafana)
├── README.md                   # Este arquivo
├── .gitignore                  # Arquivos ignorados pelo Git
│
├── src/
│   ├── Dockerfile              # Imagem Python
│   ├── requirements.txt         # Dependências (fastapi, uvicorn)
│   ├── api.py                  # API RESTful, healthcheck e métricas
│   └── static/
│       └── index.html          # Dashboard básico
│
├── scripts/
│   ├── populate_db.py          # Geração de dados (produtos artificiais)
│   ├── load_test_python.py     # Teste de carga em Python (alternativa K6)
│   ├── benchmark_api.py        # Benchmark controlado e agregação estatística
│   ├── run_final_experiment.py # Execução final: banco, API, benchmark e recursos
│   └── run_experiment.sh       # Script de execução do experimento
│
├── experiments/
│   └── load_test.js            # Configuração K6 para testes de carga
│
├── prometheus/
│   └── prometheus.yml          # Configuração do Prometheus
│
├── data/
│   ├── products.db             # Banco SQLite (gerado)
│   ├── prometheus/             # Dados do Prometheus
│   └── grafana/                # Dados do Grafana
│
└── results/
    └── benchmark/              # Resultados finais usados no relatório
```

## Variáveis de Ambiente

- `DB_PATH`: Caminho do banco SQLite (padrão: `/app/data/products.db`)
- `BASE_URL`: URL base para testes (padrão: `http://localhost:8000`)

## Banco de Dados

Tabela `produtos`:
```sql
CREATE TABLE produtos (
    id INTEGER PRIMARY KEY,
    nome TEXT,
    categoria TEXT,
    preco REAL,
    estoque INTEGER,
    criado_em TEXT,
    atualizado_em TEXT
)
```

## Hipóteses

**H1 (Desempenho/Paginação)**: Cursor apresentará latência mais estável em consultas a páginas profundas.

**H2 (Evolutividade/Versionamento)**: Headers HTTP reduzem acoplamento entre URI e versão, facilitando evolução.

## Executando os Testes

```bash
# Com pytest
./.venv/bin/python -m pytest -v

# Com K6 (load testing) - via Docker
docker run -i grafana/k6 run - < experiments/load_test.js \
  -e BASE_URL=http://host.docker.internal:8000

# Com Python (alternativa ao K6, sem instalar K6)
python scripts/load_test_python.py

# Experimento final usado no relatório
./.venv/bin/python scripts/run_final_experiment.py \
  --port 8010 --products 10000 --repetitions 5 \
  --output-dir results/benchmark

# Benchmark controlado contra uma API já em execução
./.venv/bin/python scripts/benchmark_api.py \
  --base-url http://127.0.0.1:8000 \
  --output-dir results/benchmark \
  --repetitions 5 --products 10000

# Com cobertura
./.venv/bin/python -m pytest --cov=src tests/
```

### Resultados experimentais medidos

Os resultados atuais estão em `results/benchmark/`:

- `raw.json` e `raw.csv`: execuções individuais.
- `summary.json` e `summary.csv`: estatísticas agregadas.
- `table_pagination.tex` e `table_versioning.tex`: tabelas LaTeX usadas no relatório.
- `resource_usage.json` e `resource_usage.csv`: amostras de CPU e memória da API.
- `table_resources.tex`: tabela LaTeX de consumo de recursos.
- `latency_chart.svg`: gráfico de latência média.

Resumo da execução registrada: 15.600 requisições HTTP, 3 cenários de carga, 4 alvos, 5 repetições por combinação e 0% de erro. A paginação por cursor apresentou menor latência média em C1 e C3, menor p95 nos três cenários e resultado médio pior em C2; por isso, a hipótese H1 é apoiada de forma moderada, não absoluta. URI e headers tiveram desempenho semelhante para versionamento.

## Observabilidade

A API expõe métricas Prometheus em `GET /metrics`, incluindo contadores por rota/status, histograma de latência e total atual de produtos.

- **Prometheus**: http://localhost:9090
- **Grafana**: http://localhost:3000 (admin / admin)

## Referências

- [RFC 7232: HTTP Conditional Requests](https://tools.ietf.org/html/rfc7232)
- [REST API Design Handbook](https://restfulapi.net/)
- [K6 Load Testing](https://k6.io/docs/)
- [Prometheus Documentation](https://prometheus.io/docs/)
