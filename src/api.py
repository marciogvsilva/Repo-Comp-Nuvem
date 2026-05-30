import os
import sqlite3
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parent
app = FastAPI(title="SSC0158 Checkpoint 3")

def get_db_path() -> str:
    return os.getenv("DB_PATH", "/app/data/measurements.db")

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
        "CREATE TABLE IF NOT EXISTS measurements (id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT, sensor_id TEXT, temperature REAL, humidity REAL, pressure REAL)"
    )
    conn.commit()
    conn.close()

app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

@app.get("/", response_class=HTMLResponse)
def homepage() -> str:
    with open(BASE_DIR / "static" / "index.html", "r", encoding="utf-8") as f:
        return f.read()

@app.get("/api/latest")
def latest_measurement() -> dict:
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM measurements ORDER BY id DESC LIMIT 1"
    )
    row = cursor.fetchone()
    conn.close()
    if row is None:
        raise HTTPException(status_code=404, detail="Nenhum dado coletado ainda")
    return dict(row)

@app.get("/api/history")
def history(limit: int = 20) -> dict:
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM measurements ORDER BY id DESC LIMIT ?", (limit,)
    )
    rows = cursor.fetchall()
    conn.close()
    return {"count": len(rows), "data": [dict(row) for row in rows]}

@app.get("/api/summary")
def summary() -> dict:
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM measurements")
    count = cursor.fetchone()[0]
    cursor.execute("SELECT AVG(temperature), AVG(humidity), AVG(pressure) FROM measurements")
    avg_temperature, avg_humidity, avg_pressure = cursor.fetchone()
    cursor.execute("SELECT MIN(timestamp), MAX(timestamp) FROM measurements")
    first_ts, last_ts = cursor.fetchone()
    conn.close()
    return {
        "count": count,
        "average": {
            "temperature": avg_temperature,
            "humidity": avg_humidity,
            "pressure": avg_pressure,
        },
        "period": {
            "first": first_ts,
            "last": last_ts,
        },
    }

@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat() + "Z"}
