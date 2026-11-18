"""
Puente MQTT -> servicio web (para los dispositivos IoT, como el ESP32-CAM con sensor).

Un dispositivo IoT no llama al servidor por HTTP: publica su JSON (imagen en Base64 +
metadatos) en un tema MQTT. Este programa está suscrito a ese tema y, por cada mensaje:

  1. recibe el JSON del dispositivo,
  2. lo reenvía al servicio web de Flask (POST /predict), que es quien ejecuta el modelo,
  3. publica la respuesta en  vision/respuestas/<client_id>  para que el dispositivo actúe.

Requisitos: el broker Mosquitto encendido y server.py corriendo.
Ejecutar:   python puente_mqtt.py
            python puente_mqtt.py --broker 192.168.1.10
"""
import argparse
import json
from datetime import datetime

import paho.mqtt.client as mqtt
import requests

TOPIC_SOLICITUDES = "vision/solicitudes"
TOPIC_RESPUESTAS = "vision/respuestas"      # se le agrega /<client_id>

parser = argparse.ArgumentParser(description="Puente entre MQTT y el servicio web")
parser.add_argument("--broker", default="localhost", help="IP o nombre del broker MQTT")
parser.add_argument("--puerto", type=int, default=1883, help="puerto del broker")
parser.add_argument("--servidor", default="http://127.0.0.1:5000", help="URL del servidor Flask")
args = parser.parse_args()


def al_conectar(cliente, userdata, flags, codigo, propiedades):
    if codigo == 0:
        cliente.subscribe(TOPIC_SOLICITUDES)
        print(f"Conectado al broker {args.broker}:{args.puerto}. Escuchando '{TOPIC_SOLICITUDES}'")
    else:
        print("No se pudo conectar al broker:", codigo)


def al_recibir(cliente, userdata, mensaje):
    # 1. El mensaje MQTT llega como bytes: se convierte a diccionario
    try:
        data = json.loads(mensaje.payload.decode("utf-8"))
        if not isinstance(data, dict):
            raise ValueError("no es un objeto JSON")
    except Exception as e:
        print("Mensaje descartado, no es un JSON válido:", e)
        return

    client_id = str(data.get("client_id") or "desconocido")
    if not data.get("timestamp"):          # un ESP32 sin internet no sabe la hora
        data["timestamp"] = datetime.now().isoformat(timespec="seconds")

    # 2. Se reenvía al servicio web, que ejecuta el modelo
    try:
        respuesta = requests.post(f"{args.servidor}/predict", json=data, timeout=30).json()
    except Exception as e:
        respuesta = {"error": f"No se pudo consultar el servicio web: {e}"}

    # 3. Se publica la respuesta para ese dispositivo (JSON compacto: el ESP32 tiene poca memoria)
    resumen = {k: respuesta[k] for k in ("prediction", "confidence", "request_id", "error")
               if k in respuesta}
    try:
        cliente.publish(f"{TOPIC_RESPUESTAS}/{client_id}", json.dumps(resumen, separators=(",", ":")))
    except ValueError as e:
        # Un client_id con '+' o '#' no sirve como tema MQTT. Sin este try, un solo
        # mensaje así detendría el puente para todos los dispositivos.
        print(f"No se pudo responder a '{client_id}': {e}")
        return
    print(f"[{datetime.now():%H:%M:%S}] {client_id} ({len(mensaje.payload)} bytes) -> {resumen}")


cliente = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="puente_vision")
cliente.on_connect = al_conectar
cliente.on_message = al_recibir

try:
    cliente.connect(args.broker, args.puerto, keepalive=60)
except OSError as e:
    raise SystemExit(f"No hay broker MQTT en {args.broker}:{args.puerto} ({e}). ¿Está encendido Mosquitto?")

try:
    cliente.loop_forever()
except KeyboardInterrupt:
    print("\nPuente detenido.")
