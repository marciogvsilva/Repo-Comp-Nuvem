import os
import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient

# Ajusta importação para o pacote src
import sys
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR / "src"))

from api import app  # noqa: E402


def test_api_health(tmp_path, monkeypatch):
    """Test health endpoint"""
    db_path = tmp_path / "products.db"
    monkeypatch.setenv("DB_PATH", str(db_path))

    with TestClient(app) as client:
        response = client.get("/api/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


def test_v1_offset_pagination(tmp_path, monkeypatch):
    """Test V1 offset pagination endpoint"""
    db_path = tmp_path / "products.db"
    monkeypatch.setenv("DB_PATH", str(db_path))

    with TestClient(app) as client:
        # Create database and insert test data
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
        for i in range(1, 6):
            conn.execute(
                """
                INSERT INTO produtos (nome, categoria, preco, estoque, criado_em, atualizado_em)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (f"Produto {i}", "Teste", 100.0 + i, 10, "2026-01-01T00:00:00Z", "2026-01-01T00:00:00Z"),
            )
        conn.commit()
        conn.close()

        # Test endpoint
        response = client.get("/v1/produtos?limit=2&offset=0")
        assert response.status_code == 200
        data = response.json()
        assert data["version"] == "v1"
        assert data["pagination"]["strategy"] == "offset"
        assert data["pagination"]["limit"] == 2
        assert data["pagination"]["offset"] == 0
        assert data["pagination"]["total"] == 5
        assert len(data["data"]) == 2


def test_v1_cursor_pagination(tmp_path, monkeypatch):
    """Test V1 cursor pagination endpoint"""
    db_path = tmp_path / "products.db"
    monkeypatch.setenv("DB_PATH", str(db_path))

    with TestClient(app) as client:
        # Create database and insert test data
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
        for i in range(1, 4):
            conn.execute(
                """
                INSERT INTO produtos (nome, categoria, preco, estoque, criado_em, atualizado_em)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (f"Produto {i}", "Teste", 100.0 + i, 10, "2026-01-01T00:00:00Z", "2026-01-01T00:00:00Z"),
            )
        conn.commit()
        conn.close()

        # Test endpoint
        response = client.get("/v1/produtos/cursor?limit=2&cursor=0")
        assert response.status_code == 200
        data = response.json()
        assert data["version"] == "v1"
        assert data["pagination"]["strategy"] == "cursor"
        assert data["pagination"]["limit"] == 2
        assert data["pagination"]["cursor"] == 0
        assert len(data["data"]) <= 2


def test_v2_offset_pagination(tmp_path, monkeypatch):
    """Test V2 offset pagination endpoint with metadata"""
    db_path = tmp_path / "products.db"
    monkeypatch.setenv("DB_PATH", str(db_path))

    with TestClient(app) as client:
        # Create database and insert test data
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
        for i in range(1, 3):
            conn.execute(
                """
                INSERT INTO produtos (nome, categoria, preco, estoque, criado_em, atualizado_em)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (f"Produto {i}", "Teste", 100.0 + i, 10, "2026-01-01T00:00:00Z", "2026-01-01T00:00:00Z"),
            )
        conn.commit()
        conn.close()

        # Test endpoint
        response = client.get("/v2/produtos?limit=1&offset=0")
        assert response.status_code == 200
        data = response.json()
        assert data["version"] == "v2"
        assert "meta" in data
        assert "timestamp" in data["meta"]
        assert len(data["data"]) == 1


def test_content_negotiation_headers(tmp_path, monkeypatch):
    """Test content negotiation via Accept header"""
    db_path = tmp_path / "products.db"
    monkeypatch.setenv("DB_PATH", str(db_path))

    with TestClient(app) as client:
        # Create database and insert test data
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
        conn.execute(
            """
            INSERT INTO produtos (nome, categoria, preco, estoque, criado_em, atualizado_em)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            ("Produto 1", "Teste", 100.0, 10, "2026-01-01T00:00:00Z", "2026-01-01T00:00:00Z"),
        )
        conn.commit()
        conn.close()

        # Test with V2 header
        response = client.get(
            "/produtos?limit=10&offset=0",
            headers={"Accept": "application/vnd.api.v2+json"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["version"] == "v2"
        assert "meta" in data

        # Test with V1 header
        response = client.get(
            "/produtos?limit=10&offset=0",
            headers={"Accept": "application/vnd.api.v1+json"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["version"] == "v1"
        assert "meta" not in data


def test_prometheus_metrics_endpoint(tmp_path, monkeypatch):
    """Test Prometheus metrics endpoint"""
    db_path = tmp_path / "products.db"
    monkeypatch.setenv("DB_PATH", str(db_path))

    with TestClient(app) as client:
        client.get("/api/health")
        response = client.get("/metrics")

    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]
    body = response.text
    assert "http_requests_total" in body
    assert 'path="/api/health"' in body
    assert "ssc0158_products_total" in body
