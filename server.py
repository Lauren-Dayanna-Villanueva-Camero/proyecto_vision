"""
Servicio web del Proyecto Medio de Visión Artificial (gato vs. perro).

Flujo de cada petición a POST /predict:
  1. Llega un JSON con la imagen en Base64 y los metadatos del cliente.
  2. Se valida que vengan todos los campos obligatorios.
  3. La imagen se decodifica (Base64 -> bytes -> matriz NumPy).
  4. Se preprocesa (RGB, 180x180) y se le pasa al modelo.
  5. (Opcional) Se guarda la imagen en MongoDB con GridFS y el registro de la consulta.
  6. Se responde un JSON con la predicción para que el cliente ejecute su acción.

Ejecutar:  python server.py
"""
import base64
import binascii
import io
import socket
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

import keras
import numpy as np
from flask import Flask, Response, jsonify, request
from flask_cors import CORS
from PIL import Image, ImageOps

# ----------------------------------------------------------------------------
# Configuración
# ----------------------------------------------------------------------------
CARPETA = Path(__file__).resolve().parent
RUTA_MODELO = CARPETA / "modelo.keras"
IMG_SIZE = (180, 180)            # tamaño con el que se entrenó el modelo
CLASES = ["gato", "perro"]       # etiqueta 0 = gato, etiqueta 1 = perro
CAMPOS_OBLIGATORIOS = ["client_id", "timestamp", "camera_id", "location", "image"]

PUERTO = 5000
MONGO_URI = "mongodb://localhost:27017"
MONGO_DB = "vision"

app = Flask(__name__)
CORS(app)                                              # permite llamadas desde el cliente web
app.json.ensure_ascii = False                          # tildes legibles en las respuestas
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024    # máximo 16 MB por petición

# ----------------------------------------------------------------------------
# Modelo: se carga UNA sola vez al iniciar el servidor
# ----------------------------------------------------------------------------
print(f"Cargando modelo desde {RUTA_MODELO} ...")
model = keras.models.load_model(RUTA_MODELO)
candado_modelo = threading.Lock()    # una predicción a la vez (Flask atiende en varios hilos)

# Nombre de la activación de la última capa: 'linear' (logits), 'sigmoid' o 'softmax'.
_activacion = getattr(model.layers[-1], "activation", None)
ACTIVACION_SALIDA = getattr(_activacion, "__name__", "linear")
print(f"Modelo listo. Salida: {model.output_shape}, activación final: {ACTIVACION_SALIDA}")


# ----------------------------------------------------------------------------
# MongoDB + GridFS (opcional): si no está encendido, el servidor igual predice
# ----------------------------------------------------------------------------
def conectar_mongo():
    try:
        import gridfs
        from pymongo import MongoClient

        cliente = MongoClient(MONGO_URI, serverSelectionTimeoutMS=2000)
        cliente.admin.command("ping")          # falla rápido si Mongo no está corriendo
        base = cliente[MONGO_DB]
        print("MongoDB conectado: las imágenes se guardarán con GridFS.")
        return base, gridfs.GridFS(base)
    except Exception as e:
        print(f"MongoDB no disponible ({type(e).__name__}). Se continúa sin almacenamiento.")
        return None, None


db, fs = conectar_mongo()


# ----------------------------------------------------------------------------
# Funciones de apoyo
# ----------------------------------------------------------------------------
def convertir_a_rgb(img):
    """Cualquier imagen (grises, 16 bits, paleta, con transparencia...) -> RGB de 8 bits."""
    # Grises de 16 bits (PNG médicos o de escáner): valores 0-65535. Si se convierten
    # directo a RGB, Pillow recorta todo lo que pase de 255 y la imagen queda casi blanca.
    if img.mode.startswith("I") or img.mode == "F":
        arr = np.asarray(img, dtype="float32")
        if arr.max() > 255:
            arr = arr / 257                     # 0-65535 -> 0-255
        img = Image.fromarray(np.clip(arr, 0, 255).astype("uint8"))

    # Transparencia (PNG, GIF): se pone un fondo blanco. Si solo se quitara el canal alfa,
    # aparecería el color "escondido" de los píxeles transparentes (casi siempre negro).
    if img.mode in ("RGBA", "LA", "PA") or "transparency" in img.info:
        img = img.convert("RGBA")
        fondo = Image.new("RGBA", img.size, (255, 255, 255, 255))
        img = Image.alpha_composite(fondo, img)

    return img.convert("RGB")


def decodificar_imagen(b64_str):
    """Base64 (texto) -> bytes de la imagen, objeto PIL en RGB y tipo (image/jpeg, image/png...)."""
    if not isinstance(b64_str, str):
        raise ValueError("el campo 'image' debe ser un texto en Base64")
    if not b64_str.strip():
        raise ValueError("el campo 'image' está vacío")
    # Algunos clientes web envían el prefijo "data:image/jpeg;base64,...": se quita.
    if b64_str.startswith("data:") and "," in b64_str:
        b64_str = b64_str.split(",", 1)[1]
    try:
        img_bytes = base64.b64decode(b64_str, validate=False)
    except (binascii.Error, ValueError):
        raise ValueError("el Base64 no es válido")
    try:
        img = Image.open(io.BytesIO(img_bytes))
        # Muchas fotos de celulares Android se leen como "MPO" (un JPG con imágenes extra adentro).
        # Se tratan como JPG; si no, /imagen las enviaría como "image/mpo" y el navegador no las muestra.
        formato = "JPEG" if img.format == "MPO" else img.format
        tipo = Image.MIME.get(formato, "image/jpeg")
        # Las fotos de celular se guardan "acostadas" con una marca EXIF que dice cómo girarlas.
        # El visor de fotos la respeta; aquí se aplica para que el modelo vea la foto derecha.
        img = ImageOps.exif_transpose(img)
        img = convertir_a_rgb(img)
    except Image.DecompressionBombError:
        raise ValueError("la imagen tiene demasiados píxeles; redúcela antes de enviarla")
    except Exception:
        raise ValueError("los datos no corresponden a una imagen")
    return img_bytes, img, tipo


def preprocesar(img):
    """Imagen PIL -> matriz NumPy con la forma que espera el modelo: (1, 180, 180, 3)."""
    img = img.resize(IMG_SIZE)
    arr = np.asarray(img, dtype="float32")    # valores 0-255. NO se divide por 255:
    return np.expand_dims(arr, axis=0)        # el modelo ya trae una capa Rescaling(1/255)


def predecir(x):
    """Ejecuta el modelo y devuelve (etiqueta, confianza, probabilidad de perro)."""
    with candado_modelo:
        salida = np.asarray(model.predict(x, verbose=0))[0]

    if salida.shape[-1] == 1:                 # una sola neurona de salida
        valor = float(salida[0])
        # Si la última capa no tiene activación, el valor es un logit: se aplica sigmoide.
        prob_perro = valor if ACTIVACION_SALIDA == "sigmoid" else 1 / (1 + np.exp(-valor))
    else:                                     # dos neuronas: [gato, perro]
        if ACTIVACION_SALIDA != "softmax":
            salida = np.exp(salida - salida.max())
            salida = salida / salida.sum()
        prob_perro = float(salida[1])

    etiqueta = CLASES[1] if prob_perro >= 0.5 else CLASES[0]
    confianza = prob_perro if prob_perro >= 0.5 else 1 - prob_perro
    return etiqueta, float(confianza), float(prob_perro)


def guardar_en_mongo(img_bytes, registro, tipo="image/jpeg"):
    """Guarda la imagen en GridFS y el registro en la colección 'predicciones'."""
    if fs is None:
        return None
    try:
        extension = tipo.split("/")[-1]         # image/png -> png
        nombre = f"{registro['client_id']}_{registro['request_id']}.{extension}"
        # 'tipo' se guarda para que /imagen responda con el formato real (JPG, PNG...)
        image_id = fs.put(img_bytes, filename=nombre, metadata=registro, tipo=tipo)
        db["predicciones"].insert_one({**registro, "image_id": image_id})
        return str(image_id)
    except Exception as e:
        print("Error guardando en Mongo:", e)      # no se rompe la respuesta al cliente
        return None


# ----------------------------------------------------------------------------
# Endpoints
# ----------------------------------------------------------------------------
@app.route("/", methods=["GET"])
def inicio():
    """Página de inicio: al abrir la IP del servidor en el navegador se ve que está funcionando."""
    return jsonify({
        "servicio": "Clasificación de imágenes: gato vs. perro",
        "estado": "funcionando",
        "mongo": fs is not None,
        "endpoints": {
            "POST /predict": "recibe el JSON con la imagen en Base64 y los metadatos",
            "GET /health": "estado del servidor",
            "GET /historial?client_id=...": "últimas consultas guardadas en MongoDB",
            "GET /imagen/<image_id>": "imagen guardada en GridFS",
        },
    })


@app.route("/favicon.ico")
def favicon():
    """El navegador siempre pide un ícono; se responde 'sin contenido' para no llenar el log de 404."""
    return "", 204


@app.route("/health", methods=["GET"])
def health():
    """Para comprobar desde el navegador o un cliente que el servidor está vivo."""
    return jsonify({"status": "ok", "modelo": RUTA_MODELO.name, "mongo": fs is not None})


@app.route("/predict", methods=["POST"])
def predict():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "El cuerpo de la petición debe ser un JSON"}), 400

    faltantes = [c for c in CAMPOS_OBLIGATORIOS if not data.get(c)]
    if faltantes:
        return jsonify({"error": f"Faltan campos obligatorios: {', '.join(faltantes)}"}), 400

    try:
        img_bytes, img, tipo = decodificar_imagen(data["image"])
    except ValueError as e:
        return jsonify({"error": f"Imagen inválida: {e}"}), 400

    etiqueta, confianza, prob_perro = predecir(preprocesar(img))

    registro = {
        "request_id": uuid.uuid4().hex,
        "client_id": str(data["client_id"]),
        "camera_id": str(data["camera_id"]),
        "location": str(data["location"]),
        "timestamp": str(data["timestamp"]),                     # hora que reporta el cliente
        "server_time": datetime.now(timezone.utc).isoformat(),   # hora en que llegó al servidor
        "prediction": etiqueta,
        "confidence": round(confianza, 4),
    }
    image_id = guardar_en_mongo(img_bytes, dict(registro), tipo)

    print(f"[{datetime.now():%H:%M:%S}] cliente={registro['client_id']} "
          f"camara={registro['camera_id']} sitio={registro['location']} "
          f"-> {etiqueta} ({confianza:.2%})")

    return jsonify({
        **registro,
        "probabilities": {"gato": round(1 - prob_perro, 4), "perro": round(prob_perro, 4)},
        "stored": image_id is not None,
        "image_id": image_id,
    })


@app.route("/historial", methods=["GET"])
def historial():
    """Últimas consultas guardadas. Con ?client_id=... sirve para el cobro por uso."""
    if db is None:
        return jsonify({"error": "MongoDB no está disponible"}), 503
    filtro = {}
    if request.args.get("client_id"):
        filtro["client_id"] = request.args["client_id"]
    # Entre 1 y 100 registros (en MongoDB, limit(0) significa "sin límite")
    limite = max(1, min(request.args.get("limit", 20, type=int), 100))

    try:
        registros = []
        for doc in db["predicciones"].find(filtro).sort("server_time", -1).limit(limite):
            doc["image_id"] = str(doc.get("image_id"))
            doc.pop("_id", None)
            registros.append(doc)
        total = db["predicciones"].count_documents(filtro)
    except Exception as e:                      # por ejemplo, si MongoDB se apagó después de iniciar
        return jsonify({"error": f"No se pudo consultar MongoDB ({type(e).__name__})"}), 503
    return jsonify({"total": total, "registros": registros})


@app.route("/imagen/<image_id>", methods=["GET"])
def imagen(image_id):
    """Devuelve una imagen guardada en GridFS (se puede abrir en el navegador)."""
    if fs is None:
        return jsonify({"error": "MongoDB no está disponible"}), 503
    try:
        from bson import ObjectId
        archivo = fs.get(ObjectId(image_id))
    except Exception:
        return jsonify({"error": "Imagen no encontrada"}), 404
    # Las imágenes guardadas antes de este cambio no tienen 'tipo': se asumen JPG
    return Response(archivo.read(), mimetype=getattr(archivo, "tipo", "image/jpeg"))


# ----------------------------------------------------------------------------
# Errores: siempre se responde JSON, porque todos los clientes leen la respuesta como JSON
# ----------------------------------------------------------------------------
@app.errorhandler(413)
def imagen_muy_grande(e):
    limite_mb = app.config["MAX_CONTENT_LENGTH"] // (1024 * 1024)
    return jsonify({"error": f"La petición pasa de {limite_mb} MB. Envía una imagen más pequeña."}), 413


@app.errorhandler(404)
def no_encontrado(e):
    return jsonify({"error": "Esa dirección no existe. Abre / para ver los endpoints."}), 404


@app.errorhandler(405)
def metodo_no_permitido(e):
    return jsonify({"error": "Método no permitido (por ejemplo, /predict solo acepta POST)."}), 405


@app.errorhandler(500)
def error_interno(e):
    return jsonify({"error": "Error interno del servidor. Revisa la consola de server.py."}), 500


def ip_local():
    """IP del PC en la red local: es la que deben usar el celular y el ESP32."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except OSError:
        return "127.0.0.1"


if __name__ == "__main__":
    print(f"\nServidor listo. Desde otros equipos usa: http://{ip_local()}:{PUERTO}\n")
    app.run(host="0.0.0.0", port=PUERTO, debug=False)
