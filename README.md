# Proyecto Medio de Visión Artificial

Sistema cliente-servidor para consumir un modelo de visión artificial (clasificación **gato vs. perro**) a través de un servicio web.

**Integrantes:** Lauren Dayanna Villanueva Camero / Mariana Cruz Martinez / ...
**Curso:** Electiva de Ingeniería de Software: Ciencia de Datos

## Arquitectura

```
Clientes HTTP (Python, web, móvil)            Cliente IoT (ESP32-CAM + sensor PIR)
   │  imagen → Base64 + metadatos (JSON)         │  imagen → Base64 + metadatos (JSON)
   │                                             ▼
   │                                      Broker MQTT (Mosquitto)
   │                                             │  tema vision/solicitudes
   │                                             ▼
   │                                      puente_mqtt.py
   ▼                                             │
Servicio web (Python + Flask)  ◄─────────────────┘
   │  decodifica Base64 → NumPy → preprocesa (180x180) → modelo → predicción
   │
   ├→ MongoDB + GridFS: guarda la imagen y el registro de la consulta (opcional)
   ▼
Respuesta JSON  →  el cliente ejecuta una acción
                   (al ESP32 le llega por MQTT en vision/respuestas/<client_id>)
```

**Caso de uso:** una puerta para mascotas que solo deja entrar gatos. Si el modelo ve un gato, el cliente abre la puerta; si ve un perro, la deja cerrada y activa una alarma; si la confianza es menor al 80 %, no hace nada.

## Estructura del repositorio

```
proyecto_vision/
├── server.py                  # Servicio web Flask (/predict, /health, /historial, /imagen)
├── modelo.keras               # Modelo entrenado
├── requirements.txt           # Librerías de Python
├── utilidades_cliente.py      # Funciones comunes de los clientes Python (Base64, JSON, acción)
├── cliente_python.py          # Cliente Python: envía una imagen desde archivo
├── cliente_camara.py          # Cliente Python: webcam / cámara IP (OpenCV)
├── puente_mqtt.py             # Recibe los mensajes MQTT y los pasa al servicio web
├── cliente_sensor_simulado.py # Simula el ESP32-CAM con sensor (para probar MQTT sin la placa)
├── mosquitto.conf             # Configuración del broker MQTT
├── esp32/esp32_cam_sensor/    # Sketch de Arduino: ESP32-CAM + sensor PIR + MQTT
├── entrenamiento/             # Notebook para entrenar el modelo
├── cliente_web/               # Cliente web (React + Vite): archivo o cámara
└── cliente_movil/             # Cliente móvil (React Native + Expo): cámara y galería
```

## Modelo

Basado en el ejemplo [Image classification from scratch](https://keras.io/examples/vision/image_classification_from_scratch/) de Keras (dataset Cats vs. Dogs).

- Entrada: imagen RGB de 180x180 píxeles, con valores de 0 a 255 (el modelo trae adentro la capa que los pasa a 0-1).
- Salida: un valor (logit) al que el servidor aplica sigmoide para obtener la probabilidad de "perro".
- Entrenado 25 épocas; se eligió la época 23 (`val_acc` ≈ 0.959, `val_loss` ≈ 0.111).

### Entrenamiento

El notebook `entrenamiento/entrenar_modelo.ipynb` entrena el modelo con los pasos vistos en clase:

1. Descarga del dataset.
2. **Limpieza**: se eliminan las imágenes dañadas (sin cabecera JFIF o que no se pueden decodificar).
3. **Balanceo de clases**: se toma la misma cantidad de gatos y de perros.
4. **Partición** 70 % entrenamiento, 15 % validación y 15 % prueba, guardada en `train.csv`, `val.csv` y `test.csv`.
5. Carga de las imágenes desde los CSV con `tf.data` y aumento de datos.
6. Modelo desde cero (Xception pequeña).
7. Entrenamiento con *callbacks* (`ModelCheckpoint`, `EarlyStopping`, `CSVLogger`).
8. **Evaluación con el conjunto de prueba**: accuracy, precision, recall, specificity, F1 y matriz de confusión.
9. Se guarda `modelo.keras`.

Para ejecutarlo: súbelo a [Google Colab](https://colab.research.google.com), elige *Entorno de ejecución → Cambiar tipo de entorno de ejecución → T4 GPU* y luego *Ejecutar todo*. Al terminar se descarga `modelo.keras`; cópialo a esta carpeta (reemplazando el anterior) y reinicia el servidor. Al final del notebook hay una comparación opcional con un modelo pre-entrenado (DenseNet121).

## Requisitos

- Python 3.11 (se recomienda un entorno de Anaconda/conda)
- Node.js LTS (para los clientes web y móvil)
- Aplicación **Expo Go** en el celular (para el cliente móvil)
- MongoDB (opcional, para el almacenamiento con GridFS)
- Mosquitto (opcional, para la parte de MQTT / ESP32)

## Instalación y ejecución

### 1. Servidor

```bash
conda create -n vision python=3.11 -y
conda activate vision
pip install -r requirements.txt
python server.py
```

El servidor queda escuchando en el puerto 5000. Al iniciar muestra la IP local de la máquina (por ejemplo `http://192.168.x.x:5000`); esa es la que usarán el celular, el ESP32 y otros equipos. Para comprobar que está vivo, abre `http://127.0.0.1:5000/health` en el navegador.

> El archivo `modelo.keras` debe estar en la misma carpeta que `server.py`.

### 2. Cliente Python (archivo)

```bash
python cliente_python.py                 # envía gato.jpg
python cliente_python.py otra_foto.jpg --ubicacion "Bodega 1"
```

### 3. Cliente Python (cámara)

```bash
python cliente_camara.py                 # webcam del PC
python cliente_camara.py --auto 5        # envía un fotograma cada 5 segundos
python cliente_camara.py --fuente "rtsp://USUARIO:CLAVE@IP_DE_LA_CAMARA:554/stream1" --camara tapo_entrada
```

Presiona **Espacio** para enviar el fotograma actual y **Q** para salir. La última línea es para una cámara IP (por ejemplo una Tapo): la URL RTSP se pasa al ejecutar, así no queda escrita en el código.

> No subas al repositorio URLs RTSP con usuario y contraseña.

### 4. Cliente web

```bash
cd cliente_web
npm install
npm run dev
```

Abre la dirección que muestra la terminal (normalmente `http://localhost:5173`), selecciona una imagen o pulsa **Usar cámara**, y luego **Predecir**. El cliente toma el host desde el que se abre la página y apunta al puerto 5000. El navegador solo permite usar la cámara en `http://localhost` o en páginas https.

### 5. Cliente móvil

```bash
cd cliente_movil
npm install
npx expo start
```

1. Escanea el QR con Expo Go. El celular y el PC deben estar en la **misma red WiFi**.
2. En la app, escribe en el campo **Servidor** la dirección que muestra `server.py` al iniciar (o cambia `SERVIDOR_INICIAL` en `App.js`).
3. Si el QR no carga, usa `npx expo start --tunnel`.

### 6. Almacenamiento (MongoDB + GridFS)

Si MongoDB está corriendo en `localhost:27017` **antes de iniciar el servidor**, cada imagen se guarda en GridFS y su registro en la base `vision`:

- `fs.files` / `fs.chunks`: las imágenes (en trozos) con sus metadatos.
- `predicciones`: registro de cada consulta (cliente, cámara, ubicación, fecha, predicción, confianza).

Para consultarlo: `http://127.0.0.1:5000/historial?client_id=cliente_001` muestra las consultas de un cliente y cuántas lleva (sirve para el cobro por uso), y `http://127.0.0.1:5000/imagen/<image_id>` muestra una imagen guardada.

Si MongoDB no está disponible, el servidor sigue respondiendo las predicciones normalmente.

### 7. MQTT y sensor (ESP32-CAM)

Los dispositivos IoT no llaman al servicio web directamente: publican el JSON en un broker MQTT y `puente_mqtt.py` lo pasa al servicio web.

| Tema MQTT | Quién publica | Contenido |
|---|---|---|
| `vision/solicitudes` | el dispositivo | el mismo JSON de `/predict` (imagen en Base64 + metadatos) |
| `vision/respuestas/<client_id>` | el puente | `{"prediction": "gato", "confidence": 0.98, "request_id": "..."}` |

Se necesitan tres terminales (además del servidor del paso 1):

```bash
# Terminal A: broker MQTT (instalar Mosquitto desde https://mosquitto.org/download/)
"C:\Program Files\mosquitto\mosquitto.exe" -c mosquitto.conf -v

# Terminal B: puente MQTT -> servicio web
python puente_mqtt.py

# Terminal C: dispositivo simulado (ENTER = el sensor detectó movimiento)
python cliente_sensor_simulado.py
python cliente_sensor_simulado.py --webcam      # toma la foto con la webcam
```

Si Mosquitto dice que el puerto 1883 está ocupado, es porque quedó corriendo como servicio de Windows: abre una terminal como administrador y ejecuta `net stop mosquitto`.

**Con el ESP32-CAM real** (`esp32/esp32_cam_sensor/esp32_cam_sensor.ino`):

1. En el Arduino IDE instala el paquete de placas **esp32** (Espressif) y la librería **PubSubClient**.
2. Elige la placa **AI Thinker ESP32-CAM**.
3. Al inicio del sketch cambia el nombre y la clave del WiFi, y en `MQTT_BROKER` pon la IP del PC.
4. Conexiones: sensor PIR (HC-SR501) `OUT` → GPIO 13, LED verde → GPIO 14, LED rojo o buzzer → GPIO 15.
5. Sube el sketch y abre el monitor serie a 115200. Cuando el sensor detecta movimiento, la placa toma la foto, la publica y enciende el LED verde (gato) o el rojo (perro).

Si no tienes el sensor, pon `USAR_SENSOR_PIR = false` y la placa envía una foto cada 15 segundos.

## API

### `POST /predict`

**Petición (JSON):** todos los campos son obligatorios.

```json
{
  "client_id": "cliente_001",
  "timestamp": "2026-10-10T14:30:00",
  "camera_id": "cam_lab_1",
  "location": "Laboratorio 2",
  "image": "<imagen en Base64>"
}
```

| Campo | Descripción |
|---|---|
| `client_id` | Identificador del cliente (para control de uso y cobro) |
| `timestamp` | Fecha y hora del envío (ISO 8601) |
| `camera_id` | Identificación de la cámara o fuente de la imagen |
| `location` | Sitio desde donde se envía |
| `image` | Imagen codificada en Base64 |

**Respuesta (JSON):**

```json
{
  "request_id": "6c662f5f3af746fd956ba7163ab17fa3",
  "prediction": "gato",
  "confidence": 0.983,
  "probabilities": { "gato": 0.983, "perro": 0.017 },
  "client_id": "cliente_001",
  "camera_id": "cam_lab_1",
  "location": "Laboratorio 2",
  "timestamp": "2026-10-10T14:30:00",
  "server_time": "2026-10-10T19:30:01.207021+00:00",
  "stored": true,
  "image_id": "6afbd65ffd1d9524e70ce565"
}
```

**Errores:** responde `400` con `{"error": "..."}` si falta algún campo o la imagen no es válida.

### Otros endpoints

| Endpoint | Descripción |
|---|---|
| `GET /health` | Indica si el servidor está vivo y si MongoDB está conectado |
| `GET /historial?client_id=...&limit=20` | Últimas consultas guardadas y el total (requiere MongoDB) |
| `GET /imagen/<image_id>` | Devuelve una imagen guardada en GridFS (requiere MongoDB) |

## Estado del proyecto

- [x] Modelo entrenado
- [x] Servicio web Flask
- [x] Cliente Python (archivo)
- [x] Cliente Python (webcam / cámara IP por RTSP)
- [x] Cliente web (React)
- [x] Cliente móvil (React Native)
- [x] Almacenamiento con GridFS
- [x] Protocolo MQTT (broker + puente + dispositivo simulado)
- [x] Notebook de entrenamiento con limpieza, balanceo, partición 70/15/15 y métricas
- [ ] Reentrenar el modelo con el notebook y reemplazar `modelo.keras`
- [ ] Probar el sketch en la placa ESP32-CAM con el sensor
- [ ] Probar la cámara IP Tapo

## Notas

- La IP del servidor cambia si el equipo se reconecta a la red; hay que actualizarla en el cliente móvil y en el sketch del ESP32.
- Si el celular o el ESP32 no logran conectarse, revisa que el Firewall de Windows permita los puertos 5000 (Flask) y 1883 (MQTT) en redes privadas.
- El modelo solo conoce gatos y perros: ante cualquier otra imagen igual responde una de las dos clases.
- El servidor de Flask está en modo desarrollo; no es apto para producción.
