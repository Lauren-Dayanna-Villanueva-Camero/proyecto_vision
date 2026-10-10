# Proyecto Medio de Visión Artificial

Sistema cliente-servidor para consumir un modelo de visión artificial (clasificación **gato vs. perro**) a través de un servicio web.

**Integrantes:** Lauren Dayanna Villanueva Camero / Mariana Cruz Martinez / ...
**Curso:** Electiva de Ingeniería de Softwa: Ciencia de Datos

## Arquitectura

```
Cliente (captura imagen)
   │  imagen → Base64 + metadatos (JSON)
   ▼
Servicio web (Python + Flask)
   │  decodifica Base64 → preprocesa (180x180) → carga modelo → inferencia
   ▼
Respuesta JSON  →  Cliente ejecuta una acción
                │
                └→ (opcional) MongoDB + GridFS guarda imagen y metadatos
```

## Estructura del repositorio

```
proyecto_vision/
├── server.py            # Servicio web Flask (endpoint /predict)
├── modelo.keras         # Modelo entrenado (Keras, época 23)
├── cliente_python.py    # Cliente Python: envía una imagen desde archivo
├── cliente_camara.py    # Cliente Python: webcam / cámara IP (OpenCV)
├── cliente_web/         # Cliente web (React + Vite): subir archivo
└── cliente_movil/       # Cliente móvil (React Native + Expo): cámara y galería
```

## Modelo

Basado en el ejemplo [Image classification from scratch](https://keras.io/examples/vision/image_classification_from_scratch/) de Keras (dataset Cats vs. Dogs).

- Entrada: imagen RGB de 180x180 píxeles.
- Salida: un valor (logit) al que el servidor aplica sigmoide para obtener la probabilidad de "perro".
- Entrenado 25 épocas; se eligió la época 23 (`val_acc` ≈ 0.959, `val_loss` ≈ 0.111).

## Requisitos

- Python 3.11 (se recomienda un entorno de Anaconda/conda)
- Node.js LTS (para los clientes web y móvil)
- Aplicación **Expo Go** en el celular (para el cliente móvil)
- MongoDB (opcional, solo para el almacenamiento con GridFS)

## Instalación y ejecución

### 1. Servidor

```bash
conda create -n vision python=3.11 -y
conda activate vision
pip install flask flask-cors pillow numpy requests tensorflow opencv-python pymongo
python server.py
```

El servidor queda escuchando en `http://0.0.0.0:5000`. Al iniciar muestra la IP local de la máquina (por ejemplo `http://192.168.x.x:5000`); esa es la que usarán el celular y otros equipos.

> El archivo `modelo.keras` debe estar en la misma carpeta que `server.py`.

### 2. Cliente Python (archivo)

Coloca una imagen llamada `gato.jpg` junto al script y ejecuta:

```bash
python cliente_python.py
```

### 3. Cliente Python (cámara)

```bash
python cliente_camara.py
```

Presiona **Espacio** para enviar el fotograma actual y **Q** para salir. Para una cámara IP, cambia la variable `FUENTE` por la URL RTSP de la cámara.

> No subas al repositorio URLs RTSP con usuario y contraseña.

### 4. Cliente web

```bash
cd cliente_web
npm install
npm run dev
```

Abre la dirección que muestra la terminal (normalmente `http://localhost:5173`), selecciona una imagen y pulsa **Predecir**. El cliente toma el host desde el que se abre la página y apunta al puerto 5000.

### 5. Cliente móvil

```bash
cd cliente_movil
npm install
npx expo start
```

1. Abre `App.js` y cambia `API_URL` por la IP de la máquina donde corre el servidor.
2. Escanea el QR con Expo Go. El celular y el PC deben estar en la **misma red WiFi**.
3. Si el QR no carga, usa `npx expo start --tunnel`.

## API

### `POST /predict`

**Petición (JSON):**

```json
{
  "client_id": "cliente_001",
  "timestamp": "2026-10-10T14:30:00",
  "camera_id": "cam_lab_1",
  "location": "Laboratorio 2",
  "image": "<imagen en Base64, sin prefijo data:image/...>"
}
```

| Campo | Descripción |
|---|---|
| `client_id` | Identificador del cliente (para control de uso y cobro) |
| `timestamp` | Fecha y hora del envío (ISO 8601) |
| `camera_id` | Identificación de la cámara o fuente de la imagen |
| `location` | Sitio desde donde se envía |
| `image` | Imagen codificada en Base64 (obligatorio) |

**Respuesta (JSON):**

```json
{
  "prediction": "gato",
  "confidence": 0.9948,
  "client_id": "cliente_001"
}
```

**Errores:** responde `400` con `{"error": "..."}` si falta el campo `image` o la imagen no es válida.

## Almacenamiento (MongoDB + GridFS)

Si MongoDB está corriendo en `localhost:27017`, el servidor guarda cada imagen en GridFS y su registro en la base `vision`:

- `fs.files` / `fs.chunks`: imágenes y sus metadatos.
- `predicciones`: registro de cada consulta (cliente, cámara, ubicación, fecha, predicción, confianza).

Si MongoDB no está disponible, el servidor sigue respondiendo las predicciones normalmente.

## Estado del proyecto

- [x] Modelo entrenado
- [x] Servicio web Flask
- [x] Cliente Python (archivo)
- [x] Cliente Python (webcam)
- [x] Cliente web (React)
- [x] Cliente móvil (React Native)
- [x] Almacenamiento con GridFS
- [ ] Cámara IP Tapo
- [ ] IoT: ESP32-CAM
- [ ] Protocolo MQTT

## Notas

- La IP del servidor cambia si el equipo se reconecta a la red; hay que actualizarla en el cliente móvil.
- El servidor de Flask está en modo desarrollo; no es apto para producción.
