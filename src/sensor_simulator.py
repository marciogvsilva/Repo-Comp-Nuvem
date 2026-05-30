import json
import os
import random
import time
from datetime import datetime
from paho.mqtt import client as mqtt_client

MQTT_HOST = os.getenv("MQTT_HOST", "mqtt-broker")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_TOPIC = os.getenv("MQTT_TOPIC", "sensors/telemetry")
SENSOR_ID = os.getenv("SENSOR_ID", "simulator-001")
CLIENT_ID = f"sensor-{int(time.time())}"


def connect_mqtt():
    client = mqtt_client.Client(CLIENT_ID)
    client.connect(MQTT_HOST, MQTT_PORT)
    return client


def generate_payload() -> str:
    timestamp = datetime.utcnow().isoformat() + "Z"
    payload = {
        "sensor_id": SENSOR_ID,
        "timestamp": timestamp,
        "temperature": round(random.uniform(20.0, 28.0), 2),
        "humidity": round(random.uniform(35.0, 65.0), 2),
        "pressure": round(random.uniform(1005.0, 1025.0), 2),
    }
    return json.dumps(payload)


def run() -> None:
    client = connect_mqtt()
    client.loop_start()
    print(f"Iniciando sensor simulado {SENSOR_ID} para {MQTT_HOST}:{MQTT_PORT}")
    try:
        while True:
            payload = generate_payload()
            client.publish(MQTT_TOPIC, payload)
            print(f"Publicado: {payload}")
            time.sleep(2)
    except KeyboardInterrupt:
        print("Sensor simulado interrompido pelo usuário")
    finally:
        client.loop_stop()


if __name__ == "__main__":
    run()
