import base64, cv2, requests
from datetime import datetime

API_URL = "http://127.0.0.1:5000/predict"
FUENTE = 0   # 0 = webcam del PC. Para cámara IP va una URL RTSP (ver abajo)
# FUENTE = "rtsp://USUARIO:CLAVE@IP_DE_LA_CAMARA:554/stream1"-- Para cámara IP. Cambiar USUARIO, CLAVE e IP_DE_LA_CAMARA por los correctos

cap = cv2.VideoCapture(FUENTE)
resultado = ""

while True:
    ok, frame = cap.read()
    if not ok:
        print("No se pudo leer la cámara")
        break

    cv2.putText(frame, resultado, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
    cv2.imshow("Camara - ESPACIO: predecir | Q: salir", frame)

    tecla = cv2.waitKey(1) & 0xFF
    if tecla == ord("q"):
        break
    if tecla == 32:  # espacio
        _, buf = cv2.imencode(".jpg", frame)
        b64 = base64.b64encode(buf).decode("utf-8")
        payload = {
            "client_id": "cliente_python_cam_001",
            "timestamp": datetime.now().isoformat(),
            "camera_id": "webcam_pc",
            "location": "Laboratorio 2",
            "image": b64,
        }
        try:
            r = requests.post(API_URL, json=payload, timeout=10).json()
            resultado = f"{r['prediction']} ({r['confidence']*100:.1f}%)"
            print(r)
        except Exception as e:
            resultado = "Error"
            print(e)

cap.release()
cv2.destroyAllWindows()