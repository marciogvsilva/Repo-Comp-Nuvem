import os
import sqlite3
import time
from collections import defaultdict
from contextlib import asynccontextmanager
from pathlib import Path
from threading import Lock
from typing import DefaultDict, Optional

from fastapi import FastAPI, Header, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timezone

BASE_DIR = Path(__file__).resolve().parent
PROMETHEUS_BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, float("inf"))
REQUEST_TOTAL: DefaultDict[tuple[str, str, str], int] = defaultdict(int)
REQUEST_DURATION_COUNT: DefaultDict[tuple[str, str, str], int] = defaultdict(int)
REQUEST_DURATION_SUM: DefaultDict[tuple[str, str, str], float] = defaultdict(float)
REQUEST_DURATION_BUCKETS: dict[tuple[str, str, str], list[int]] = {}
METRICS_LOCK = Lock()


def get_db_path() -> str:
    return os.getenv("DB_PATH", "/app/data/products.db")


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def init_db() -> None:
    db_path = get_db_path()
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS produtos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            categoria TEXT NOT NULL,
            preco REAL NOT NULL,
            estoque INTEGER NOT NULL,
            criado_em TEXT NOT NULL,
            atualizado_em TEXT NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="SSC0158 - REST API Design Evaluation", lifespan=lifespan)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_route_label(request: Request) -> str:
    route = request.scope.get("route")
    return getattr(route, "path", request.url.path)


def format_label_value(value: str) -> str:
    return value.replace("\\", "\\\\").replace('\"', '\\"').replace("\n", "\\n")


def prometheus_labels(method: str, path: str, status: str, extra: Optional[dict[str, str]] = None) -> str:
    labels = {
        "method": method,
        "path": path,
        "status": status,
    }
    if extra:
        labels.update(extra)

    return ",".join(f'{key}="{format_label_value(value)}"' for key, value in labels.items())


def record_request_metric(method: str, path: str, status: int, duration: float) -> None:
    key = (method, path, str(status))

    with METRICS_LOCK:
        REQUEST_TOTAL[key] += 1
        REQUEST_DURATION_COUNT[key] += 1
        REQUEST_DURATION_SUM[key] += duration

        bucket_counts = REQUEST_DURATION_BUCKETS.setdefault(key, [0] * len(PROMETHEUS_BUCKETS))
        for index, bucket in enumerate(PROMETHEUS_BUCKETS):
            if duration <= bucket:
                bucket_counts[index] += 1


def get_products_total() -> int:
    try:
        conn = sqlite3.connect(get_db_path())
        total = conn.execute("SELECT COUNT(*) FROM produtos").fetchone()[0]
        conn.close()
        return int(total)
    except sqlite3.Error:
        return 0


@app.middleware("http")
async def collect_metrics(request: Request, call_next):
    start = time.perf_counter()
    status_code = 500

    try:
        response = await call_next(request)
        status_code = response.status_code
        return response
    finally:
        if request.url.path != "/metrics":
            duration = time.perf_counter() - start
            record_request_metric(request.method, get_route_label(request), status_code, duration)



app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")


@app.get("/", response_class=HTMLResponse)
def homepage() -> str:
    with open(BASE_DIR / "static" / "index.html", "r", encoding="utf-8") as f:
        return f.read()


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "timestamp": utc_timestamp()}


@app.get("/metrics")
def metrics() -> Response:
    with METRICS_LOCK:
        totals = dict(REQUEST_TOTAL)
        duration_counts = dict(REQUEST_DURATION_COUNT)
        duration_sums = dict(REQUEST_DURATION_SUM)
        duration_buckets = {key: list(value) for key, value in REQUEST_DURATION_BUCKETS.items()}

    lines = [
        "# HELP ssc0158_api_info API metadata for the SSC0158 experiment.",
        "# TYPE ssc0158_api_info gauge",
        'ssc0158_api_info{app="rest_api_design_evaluation"} 1',
        "# HELP ssc0158_products_total Current number of products in the database.",
        "# TYPE ssc0158_products_total gauge",
        f"ssc0158_products_total {get_products_total()}",
        "# HELP http_requests_total Total HTTP requests processed by method, path and status.",
        "# TYPE http_requests_total counter",
    ]

    for key in sorted(totals):
        method, path, status = key
        labels = prometheus_labels(method, path, status)
        lines.append(f"http_requests_total{{{labels}}} {totals[key]}")

    lines.extend(
        [
            "# HELP http_request_duration_seconds HTTP request duration in seconds.",
            "# TYPE http_request_duration_seconds histogram",
        ]
    )

    for key in sorted(duration_counts):
        method, path, status = key
        for bucket, count in zip(PROMETHEUS_BUCKETS, duration_buckets.get(key, [])):
            bucket_label = "+Inf" if bucket == float("inf") else str(bucket)
            labels = prometheus_labels(method, path, status, {"le": bucket_label})
            lines.append(f"http_request_duration_seconds_bucket{{{labels}}} {count}")

        labels = prometheus_labels(method, path, status)
        lines.append(f"http_request_duration_seconds_count{{{labels}}} {duration_counts[key]}")
        lines.append(f"http_request_duration_seconds_sum{{{labels}}} {duration_sums[key]:.6f}")

    return Response(
        content="\n".join(lines) + "\n",
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )


# ========== V1: Paginação com OFFSET ==========
@app.get("/v1/produtos")
def list_products_offset_v1(limit: int = 50, offset: int = 0) -> dict:
    """V1: Paginação baseada em Offset"""
    if limit <= 0 or limit > 1000:
        limit = 50
    if offset < 0:
        offset = 0

    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM produtos")
    total = cursor.fetchone()[0]

    cursor.execute(
        "SELECT * FROM produtos ORDER BY id ASC LIMIT ? OFFSET ?",
        (limit, offset),
    )
    rows = cursor.fetchall()
    conn.close()

    return {
        "version": "v1",
        "pagination": {
            "strategy": "offset",
            "limit": limit,
            "offset": offset,
            "total": total,
        },
        "data": [dict(row) for row in rows],
    }


# ========== V1: Paginação com CURSOR ==========
@app.get("/v1/produtos/cursor")
def list_products_cursor_v1(limit: int = 50, cursor: Optional[int] = None) -> dict:
    """V1: Paginação baseada em Cursor"""
    if limit <= 0 or limit > 1000:
        limit = 50
    if cursor is None:
        cursor = 0

    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor_obj = conn.cursor()

    cursor_obj.execute("SELECT COUNT(*) FROM produtos")
    total = cursor_obj.fetchone()[0]

    cursor_obj.execute(
        "SELECT * FROM produtos WHERE id > ? ORDER BY id ASC LIMIT ?",
        (cursor, limit),
    )
    rows = cursor_obj.fetchall()
    conn.close()

    next_cursor = None
    if rows:
        next_cursor = rows[-1]["id"]

    return {
        "version": "v1",
        "pagination": {
            "strategy": "cursor",
            "limit": limit,
            "cursor": cursor,
            "next_cursor": next_cursor,
            "total": total,
        },
        "data": [dict(row) for row in rows],
    }


# ========== V2: Paginação com OFFSET + novos campos ==========
@app.get("/v2/produtos")
def list_products_offset_v2(limit: int = 50, offset: int = 0) -> dict:
    """V2: Paginação com Offset e novos campos de metadados"""
    if limit <= 0 or limit > 1000:
        limit = 50
    if offset < 0:
        offset = 0

    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM produtos")
    total = cursor.fetchone()[0]

    cursor.execute(
        "SELECT * FROM produtos ORDER BY id ASC LIMIT ? OFFSET ?",
        (limit, offset),
    )
    rows = cursor.fetchall()
    conn.close()

    return {
        "version": "v2",
        "pagination": {
            "strategy": "offset",
            "limit": limit,
            "offset": offset,
            "total": total,
        },
        "data": [dict(row) for row in rows],
        "meta": {"timestamp": utc_timestamp()},
    }


# ========== V2: Paginação com CURSOR + novos campos ==========
@app.get("/v2/produtos/cursor")
def list_products_cursor_v2(limit: int = 50, cursor: Optional[int] = None) -> dict:
    """V2: Paginação com Cursor e novos campos de metadados"""
    if limit <= 0 or limit > 1000:
        limit = 50
    if cursor is None:
        cursor = 0

    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor_obj = conn.cursor()

    cursor_obj.execute("SELECT COUNT(*) FROM produtos")
    total = cursor_obj.fetchone()[0]

    cursor_obj.execute(
        "SELECT * FROM produtos WHERE id > ? ORDER BY id ASC LIMIT ?",
        (cursor, limit),
    )
    rows = cursor_obj.fetchall()
    conn.close()

    next_cursor = None
    if rows:
        next_cursor = rows[-1]["id"]

    return {
        "version": "v2",
        "pagination": {
            "strategy": "cursor",
            "limit": limit,
            "cursor": cursor,
            "next_cursor": next_cursor,
            "total": total,
        },
        "data": [dict(row) for row in rows],
        "meta": {"timestamp": utc_timestamp()},
    }


# ========== Versionamento via HEADERS HTTP (Content Negotiation) ==========
@app.get("/produtos")
def list_products_headers(
    limit: int = 50,
    offset: int = 0,
    accept: Optional[str] = Header(None),
) -> dict:
    """Versionamento via Accept headers (Content Negotiation)"""
    version = "v1"
    
    if accept:
        if "v2" in accept:
            version = "v2"

    if limit <= 0 or limit > 1000:
        limit = 50
    if offset < 0:
        offset = 0

    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM produtos")
    total = cursor.fetchone()[0]

    cursor.execute(
        "SELECT * FROM produtos ORDER BY id ASC LIMIT ? OFFSET ?",
        (limit, offset),
    )
    rows = cursor.fetchall()
    conn.close()

    result = {
        "version": version,
        "pagination": {
            "strategy": "offset",
            "limit": limit,
            "offset": offset,
            "total": total,
        },
        "data": [dict(row) for row in rows],
    }

    if version == "v2":
        result["meta"] = {"timestamp": utc_timestamp()}

    return result
