import json
import os
import sqlite3
import time
from paho.mqtt import client as mqtt_client

MQTT_HOST = os.getenv("MQTT_HOST", "mqtt-broker")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_TOPIC = os.getenv("MQTT_TOPIC", "sensors/telemetry")
DB_PATH = os.getenv("DB_PATH", "/app/data/measurements.db")

CLIENT_ID = f"collector-{int(time.time())}"


def init_db() -> None:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS measurements (id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT, sensor_id TEXT, temperature REAL, humidity REAL, pressure REAL)"
    )
    conn.commit()
    conn.close()


def save_measurement(data: dict) -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO measurements (timestamp, sensor_id, temperature, humidity, pressure) VALUES (?, ?, ?, ?, ?)",
        (
            data.get("timestamp"),
            data.get("sensor_id"),
            data.get("temperature"),
            data.get("humidity"),
            data.get("pressure"),
        ),
    )
    conn.commit()
    conn.close()


def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print(f"Conectado ao broker MQTT em {MQTT_HOST}:{MQTT_PORT}")
        client.subscribe(MQTT_TOPIC)
    else:
        print(f"Falha ao conectar no broker MQTT, código {rc}")


def on_message(client, userdata, msg):
    try:
        payload = msg.payload.decode("utf-8")
        data = json.loads(payload)
        print(f"Recebido mensagem: {data}")
        save_measurement(data)
    except Exception as exc:
        print(f"Erro processando mensagem: {exc}")


def run() -> None:
    init_db()
    client = mqtt_client.Client(CLIENT_ID)
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(MQTT_HOST, MQTT_PORT)
    client.loop_forever()


if __name__ == "__main__":
    print("Iniciando collector...\n")
    run()
