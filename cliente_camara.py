"""
Cliente Python (cámara): toma fotogramas de la webcam o de una cámara IP con OpenCV
y los envía al servicio web.

Ejemplos:
    python cliente_camara.py                      # webcam del PC, ESPACIO para predecir
    python cliente_camara.py --auto 5             # envía un fotograma cada 5 segundos
    python cliente_camara.py --fuente "rtsp://USUARIO:CLAVE@IP_DE_LA_CAMARA:554/stream1"

Celular como cámara IP (sin ESP32): instala la app "IP Webcam" (Android) o "DroidCam"
(Android y iPhone), conecta el celular al mismo WiFi del PC y usa la dirección que muestra la app:
    python cliente_camara.py --fuente http://192.168.1.20:8080/video --camara celular   # IP Webcam
    python cliente_camara.py --fuente http://192.168.1.20:4747/video --camara celular   # DroidCam

Teclas: ESPACIO = predecir el fotograma actual | Q = salir

Nota: no dejes la URL RTSP con usuario y clave escrita en el código ni la subas a GitHub.
"""
import argparse
import time

import cv2

from utilidades_cliente import SERVIDOR, construir_json, decidir_accion, enviar_http

parser = argparse.ArgumentParser(description="Cliente de cámara para el servicio de visión")
parser.add_argument("--fuente", default="0", help="0 = webcam del PC, o la URL de la cámara IP / del celular")
parser.add_argument("--servidor", default=SERVIDOR, help="URL del servidor Flask")
parser.add_argument("--cliente", default="cliente_python_cam_001", help="ID del cliente")
parser.add_argument("--camara", default="webcam_pc", help="ID de la cámara")
parser.add_argument("--ubicacion", default="Laboratorio 2", help="sitio de la cámara")
parser.add_argument("--auto", type=float, default=0, help="enviar automáticamente cada N segundos")
args = parser.parse_args()

COLORES = {"ABRIR_PUERTA": (0, 200, 0), "ALARMA": (0, 0, 255), "REVISAR": (0, 200, 255)}

fuente = int(args.fuente) if args.fuente.isdigit() else args.fuente
cap = cv2.VideoCapture(fuente)
if not cap.isOpened():
    raise SystemExit("No se pudo abrir la cámara. Revisa --fuente.")

texto, color = "ESPACIO: predecir | Q: salir", (255, 255, 255)
ultimo_envio = 0


def predecir_fotograma(frame):
    """Fotograma (matriz NumPy) -> JPG -> Base64 + metadatos -> servidor -> acción."""
    ok, buffer = cv2.imencode(".jpg", frame)
    if not ok:
        return "No se pudo codificar la imagen", (0, 0, 255)
    payload = construir_json(buffer.tobytes(), args.cliente, args.camara, args.ubicacion)
    try:
        respuesta = enviar_http(payload, args.servidor)
    except Exception as e:
        print("Error:", e)
        return "Error al consultar el servidor", (0, 0, 255)
    codigo, mensaje = decidir_accion(respuesta)
    print(f"{respuesta['prediction']} ({respuesta['confidence']:.1%}) -> {codigo}: {mensaje}")
    return f"{respuesta['prediction']} {respuesta['confidence']:.0%} -> {codigo}", COLORES[codigo]


while True:
    ok, frame = cap.read()
    if not ok:
        print("No se pudo leer la cámara")
        break

    vista = frame.copy()
    cv2.putText(vista, texto, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
    cv2.imshow("Camara", vista)

    tecla = cv2.waitKey(1) & 0xFF
    if tecla in (ord("q"), ord("Q")):
        break
    # Si se cierra la ventana con la X, también se sale (si no, OpenCV la vuelve a abrir)
    if cv2.getWindowProperty("Camara", cv2.WND_PROP_VISIBLE) < 1:
        break

    toca_auto = args.auto > 0 and time.time() - ultimo_envio >= args.auto
    if tecla == 32 or toca_auto:          # 32 = barra espaciadora
        texto, color = predecir_fotograma(frame)   # se envía el fotograma limpio, sin texto
        ultimo_envio = time.time()

cap.release()
cv2.destroyAllWindows()
