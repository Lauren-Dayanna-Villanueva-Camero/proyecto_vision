import base64, requests
from datetime import datetime

with open("gato.jpg", "rb") as f:
    b64 = base64.b64encode(f.read()).decode("utf-8")

payload = {
    "client_id": "cliente_001",
    "timestamp": datetime.now().isoformat(),
    "camera_id": "cam_lab_1",
    "location": "Laboratorio 2",
    "image": b64,
}

r = requests.post("http://127.0.0.1:5000/predict", json=payload)
print(r.json())