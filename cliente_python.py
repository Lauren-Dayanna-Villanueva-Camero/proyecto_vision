"""
Cliente Python (archivo): envía una imagen guardada en disco al servicio web.

Ejemplos:
    python cliente_python.py
    python cliente_python.py fotos/perro.jpg
    python cliente_python.py gato.jpg --servidor http://192.168.1.10:5000 --ubicacion "Bodega 1"
"""
import argparse
import json
import sys

from utilidades_cliente import SERVIDOR, construir_json, ejecutar_accion, enviar_http

parser = argparse.ArgumentParser(description="Envía una imagen al servicio web de visión")
parser.add_argument("imagen", nargs="?", default="gato.jpg", help="ruta de la imagen")
parser.add_argument("--servidor", default=SERVIDOR, help="URL del servidor Flask")
parser.add_argument("--cliente", default="cliente_001", help="ID del cliente")
parser.add_argument("--camara", default="archivo_local", help="ID de la cámara o fuente")
parser.add_argument("--ubicacion", default="Laboratorio 2", help="sitio desde donde se envía")
args = parser.parse_args()

# 1. Captura: se lee la imagen binaria desde el archivo
try:
    with open(args.imagen, "rb") as f:
        img_bytes = f.read()
except FileNotFoundError:
    sys.exit(f"No encontré la imagen '{args.imagen}'")

# 2. Base64 + metadatos en un JSON
payload = construir_json(img_bytes, args.cliente, args.camara, args.ubicacion)

# 3. Envío al servicio web
try:
    respuesta = enviar_http(payload, args.servidor)
except Exception as e:
    sys.exit(f"No se pudo obtener la predicción: {e}")

# 4. Respuesta del servidor y acción del cliente
print(json.dumps(respuesta, indent=2, ensure_ascii=False))
ejecutar_accion(respuesta)
