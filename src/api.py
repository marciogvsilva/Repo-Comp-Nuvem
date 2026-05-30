import os
import sqlite3
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, Header
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parent
app = FastAPI(title="SSC0158 - REST API Design Evaluation")


def get_db_path() -> str:
    return os.getenv("DB_PATH", "/app/data/products.db")


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup_event() -> None:
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


app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")


@app.get("/", response_class=HTMLResponse)
def homepage() -> str:
    with open(BASE_DIR / "static" / "index.html", "r", encoding="utf-8") as f:
        return f.read()


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat() + "Z"}


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
        "meta": {"timestamp": datetime.utcnow().isoformat() + "Z"},
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
        "meta": {"timestamp": datetime.utcnow().isoformat() + "Z"},
    }


# ========== Versionamento via HEADERS HTTP (Content Negotiation) ==========
@app.get("/produtos")
def list_products_headers(
    limit: int = 50,
    offset: int = 0,
    accept: str = Header(None),
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
        result["meta"] = {"timestamp": datetime.utcnow().isoformat() + "Z"}

    return result
