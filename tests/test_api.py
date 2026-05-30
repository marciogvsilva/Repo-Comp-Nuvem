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
    db_path = tmp_path / "measurements.db"
    monkeypatch.setenv("DB_PATH", str(db_path))

    with TestClient(app) as client:
        response = client.get("/api/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


def test_api_history_empty(tmp_path, monkeypatch):
    db_path = tmp_path / "measurements.db"
    monkeypatch.setenv("DB_PATH", str(db_path))

    with TestClient(app) as client:
        response = client.get("/api/history?limit=5")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 0
        assert data["data"] == []


def test_api_latest_and_summary(tmp_path, monkeypatch):
    db_path = tmp_path / "measurements.db"
    monkeypatch.setenv("DB_PATH", str(db_path))

    with TestClient(app) as client:
        # Insere um registro de teste diretamente no banco de dados
        conn = sqlite3.connect(db_path)
        conn.execute(
            "CREATE TABLE IF NOT EXISTS measurements (id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT, sensor_id TEXT, temperature REAL, humidity REAL, pressure REAL)",
        )
        conn.execute(
            "INSERT INTO measurements (timestamp, sensor_id, temperature, humidity, pressure) VALUES (?, ?, ?, ?, ?)",
            ("2026-05-30T12:00:00Z", "simulator-001", 25.0, 50.0, 1010.0),
        )
        conn.commit()
        conn.close()

        latest = client.get("/api/latest")
        assert latest.status_code == 200
        latest_json = latest.json()
        assert latest_json["sensor_id"] == "simulator-001"
        assert latest_json["temperature"] == 25.0

        history = client.get("/api/history?limit=1")
        assert history.status_code == 200
        history_json = history.json()
        assert history_json["count"] == 1
        assert history_json["data"][0]["sensor_id"] == "simulator-001"

        summary = client.get("/api/summary")
        assert summary.status_code == 200
        summary_json = summary.json()
        assert summary_json["count"] == 1
        assert summary_json["average"]["temperature"] == 25.0
        assert summary_json["average"]["humidity"] == 50.0
        assert summary_json["average"]["pressure"] == 1010.0
