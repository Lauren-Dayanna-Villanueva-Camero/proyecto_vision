"""
Simulador del ESP32-CAM con sensor de movimiento (para probar MQTT sin tener la placa).

Hace exactamente lo mismo que el sketch esp32/esp32_cam_sensor/esp32_cam_sensor.ino:
cuando el "sensor" se activa, toma una imagen, la convierte a Base64, arma el JSON con
los metadatos, lo publica por MQTT y espera la respuesta para ejecutar la acción.

Aquí el sensor se simula con la tecla ENTER (o con --auto N segundos).

Ejemplos:
    python cliente_sensor_simulado.py                      # usa gato.jpg
    python cliente_sensor_simulado.py --imagen perro.jpg
    python cliente_sensor_simulado.py --webcam             # toma la foto con la webcam
    python cliente_sensor_simulado.py --url http://192.168.1.20:8080/shot.jpg   # celular con IP Webcam
    python cliente_sensor_simulado.py --url http://192.168.1.20:4747/video      # celular con DroidCam
    python cliente_sensor_simulado.py --auto 10 --broker 192.168.1.10
"""
import argparse
import json
import queue
import time

import paho.mqtt.client as mqtt
import requests

from utilidades_cliente import construir_json, ejecutar_accion

TOPIC_SOLICITUDES = "vision/solicitudes"
TOPIC_RESPUESTAS = "vision/respuestas"

parser = argparse.ArgumentParser(description="Simula un ESP32-CAM con sensor de movimiento")
parser.add_argument("--broker", default="localhost", help="IP o nombre del broker MQTT")
parser.add_argument("--puerto", type=int, default=1883, help="puerto del broker")
parser.add_argument("--imagen", default="gato.jpg", help="imagen que 'captura' la cámara")
parser.add_argument("--webcam", action="store_true", help="capturar con la webcam del PC")
parser.add_argument("--url", help="capturar desde el celular o una cámara IP "
                    "(ej. http://192.168.1.20:8080/shot.jpg con la app IP Webcam)")
parser.add_argument("--cliente", default="esp32cam_sim_001", help="ID del cliente")
parser.add_argument("--camara", default="esp32cam_puerta", help="ID de la cámara")
parser.add_argument("--ubicacion", default="Entrada principal", help="sitio del dispositivo")
parser.add_argument("--auto", type=float, default=0, help="activar el sensor cada N segundos")
parser.add_argument("--veces", type=int, default=0, help="cuántas capturas hacer (0 = sin límite)")
args = parser.parse_args()

respuestas = queue.Queue()      # aquí deja el hilo de MQTT las respuestas que llegan


def capturar_imagen():
    """Devuelve los bytes JPG de la imagen: del celular (cámara IP), de la webcam o de un archivo."""
    if args.url and args.url.lower().endswith(".jpg"):
        # Una foto suelta (por ejemplo /shot.jpg de IP Webcam): basta con descargarla
        r = requests.get(args.url, timeout=10)
        r.raise_for_status()
        return r.content
    if args.url or args.webcam:
        # Video (webcam o /video del celular): se abre, se toma un fotograma y se cierra
        import cv2
        cap = cv2.VideoCapture(args.url or 0)
        ok, frame = cap.read()
        cap.release()
        if not ok:
            raise RuntimeError(f"no se pudo leer la cámara {args.url or '(webcam)'}")
        return cv2.imencode(".jpg", frame)[1].tobytes()
    with open(args.imagen, "rb") as f:
        return f.read()


def al_conectar(cliente, userdata, flags, codigo, propiedades):
    cliente.subscribe(f"{TOPIC_RESPUESTAS}/{args.cliente}")


def al_recibir(cliente, userdata, mensaje):
    try:
        respuestas.put(json.loads(mensaje.payload.decode("utf-8")))
    except ValueError:      # si llega algo que no es JSON, se ignora (sin esto se detiene el hilo de MQTT)
        print("Llegó una respuesta que no es JSON:", mensaje.payload[:100])


cliente = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=args.cliente)
cliente.on_connect = al_conectar
cliente.on_message = al_recibir
try:
    cliente.connect(args.broker, args.puerto, keepalive=60)
except OSError as e:
    raise SystemExit(f"No hay broker MQTT en {args.broker}:{args.puerto} ({e}). ¿Está encendido Mosquitto?")
cliente.loop_start()            # MQTT queda atendiendo en un hilo aparte

print(f"Dispositivo '{args.cliente}' conectado al broker {args.broker}.")
capturas = 0
try:
    while args.veces == 0 or capturas < args.veces:
        # --- El sensor: ENTER simula que el PIR detectó movimiento ---
        if args.auto > 0:
            time.sleep(args.auto)
        else:
            input("\nPresiona ENTER para simular que el sensor detectó movimiento (Ctrl+C para salir) ")
        capturas += 1
        print("Sensor activado: capturando imagen...")

        # --- Captura -> Base64 + metadatos -> publicación MQTT ---
        try:
            payload = construir_json(capturar_imagen(), args.cliente, args.camara, args.ubicacion)
        except Exception as e:
            print("No se pudo capturar la imagen:", e)
            continue
        # Se descartan respuestas viejas que llegaron tarde, para no confundirlas con la de esta foto
        while not respuestas.empty():
            respuestas.get_nowait()
        try:
            cliente.publish(TOPIC_SOLICITUDES, json.dumps(payload)).wait_for_publish(timeout=10)
        except (RuntimeError, ValueError) as e:     # por ejemplo, se perdió la conexión con el broker
            print("No se pudo publicar el mensaje:", e)
            continue
        print(f"Publicado en '{TOPIC_SOLICITUDES}'. Esperando respuesta...")

        # --- Respuesta -> acción ---
        try:
            respuesta = respuestas.get(timeout=30)
        except queue.Empty:
            print("No llegó respuesta. ¿Están corriendo server.py y puente_mqtt.py?")
            continue
        if "error" in respuesta:
            print("El servidor respondió con error:", respuesta["error"])
        else:
            print("Respuesta:", respuesta)
            ejecutar_accion(respuesta)
except KeyboardInterrupt:
    print("\nSimulador detenido.")
finally:
    cliente.loop_stop()
    cliente.disconnect()
