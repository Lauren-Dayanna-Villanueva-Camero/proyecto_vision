import base64, io
from datetime import datetime

import numpy as np
from flask import Flask, request, jsonify
from PIL import Image
import keras
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# Se carga UNA sola vez al iniciar
model = keras.models.load_model("modelo.keras")
IMG_SIZE = (180, 180)

def preprocesar(b64_str):
    img_bytes = base64.b64decode(b64_str)
    img = Image.open(io.BytesIO(img_bytes)).convert("RGB").resize(IMG_SIZE)
    arr = np.array(img, dtype="float32")   # sin dividir por 255: el modelo ya lo hace
    return np.expand_dims(arr, axis=0)     # forma (1, 180, 180, 3)

@app.route("/predict", methods=["POST"])
def predict():
    data = request.get_json(silent=True)
    if not data or "image" not in data:
        return jsonify({"error": "Falta el campo 'image'"}), 400

    try:
        x = preprocesar(data["image"])
    except Exception as e:
        return jsonify({"error": f"Imagen inválida: {e}"}), 400

    logit = float(model.predict(x, verbose=0)[0][0])
    score = 1 / (1 + np.exp(-logit))   # sigmoide: probabilidad de perro
    etiqueta = "perro" if score >= 0.5 else "gato"
    confianza = score if score >= 0.5 else 1 - score

    print(f"[{datetime.now()}] cliente={data.get('client_id')} "
          f"camara={data.get('camera_id')} -> {etiqueta} ({confianza:.2f})")

    return jsonify({
        "prediction": etiqueta,
        "confidence": round(confianza, 4),
        "client_id": data.get("client_id")
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)