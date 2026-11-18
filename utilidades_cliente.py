"""
Funciones que comparten los clientes de Python (archivo, cámara y sensor simulado):

  imagen -> Base64 -> JSON con metadatos -> envío al servidor -> acción según la respuesta
"""
import base64
from datetime import datetime

import requests

SERVIDOR = "http://127.0.0.1:5000"    # cambia la IP si el servidor está en otro PC
UMBRAL_CONFIANZA = 0.80               # por debajo de esto no se toma ninguna decisión


def construir_json(img_bytes, client_id, camera_id, location):
    """Empaqueta la imagen (bytes de un JPG/PNG) en Base64 junto con los metadatos."""
    return {
        "client_id": client_id,                          # quién consulta (control de uso / cobro)
        "timestamp": datetime.now().isoformat(timespec="seconds"),   # fecha y hora del envío
        "camera_id": camera_id,                          # qué cámara tomó la imagen
        "location": location,                            # sitio desde donde se transmite
        "image": base64.b64encode(img_bytes).decode("utf-8"),
    }


def enviar_http(payload, servidor=SERVIDOR):
    """Envía el JSON al servicio web y devuelve la respuesta como diccionario."""
    r = requests.post(f"{servidor}/predict", json=payload, timeout=30)
    try:
        respuesta = r.json()
    except ValueError:      # la respuesta no es JSON (por ejemplo, otro programa en ese puerto)
        raise RuntimeError(f"El servidor respondió {r.status_code} pero no envió un JSON. ¿Es la URL correcta?")
    if r.status_code != 200:
        raise RuntimeError(respuesta.get("error", f"Error {r.status_code} del servidor"))
    return respuesta


def decidir_accion(respuesta):
    """
    Lógica de negocio del cliente. Caso de uso: puerta para mascotas que solo deja
    entrar gatos. Devuelve (código, mensaje).
    """
    prediccion = respuesta.get("prediction")
    confianza = respuesta.get("confidence", 0)

    if confianza < UMBRAL_CONFIANZA:
        return "REVISAR", f"No estoy seguro ({prediccion}, {confianza:.0%}). La puerta sigue cerrada."
    if prediccion == "gato":
        return "ABRIR_PUERTA", f"Es un gato ({confianza:.0%}). Se abre la puerta."
    return "ALARMA", f"Es un perro ({confianza:.0%}). Puerta cerrada y se activa la alarma."


def ejecutar_accion(respuesta):
    """Muestra la acción. Aquí iría el código real: relé, servomotor, notificación, etc."""
    codigo, mensaje = decidir_accion(respuesta)
    print(f"ACCIÓN -> {codigo}: {mensaje}")
    return codigo, mensaje
