/*
  Proyecto Medio de Visión Artificial - Cliente IoT
  ESP32-CAM (AI Thinker) + sensor de movimiento PIR (HC-SR501) + MQTT

  Qué hace:
    1. El sensor PIR detecta movimiento.
    2. La cámara toma una foto (JPG).
    3. La foto se convierte a Base64 y se arma un JSON con los metadatos
       (client_id, timestamp, camera_id, location, image).
    4. El JSON se publica por MQTT en el tema  vision/solicitudes
    5. En el PC, puente_mqtt.py lo pasa al servicio web (Flask) y publica la
       respuesta en  vision/respuestas/<CLIENT_ID>
    6. El ESP32 recibe la respuesta y actúa: LED verde = gato (abrir puerta),
       LED rojo = perro (alarma).

  Arduino IDE:
    - Placa: "AI Thinker ESP32-CAM" (paquete "esp32" de Espressif)
    - Librería a instalar: "PubSubClient" (de Nick O'Leary)

  Conexiones:
    - PIR:       VCC -> 5V, GND -> GND, OUT -> GPIO 13
    - LED verde: GPIO 14 -> resistencia 220 ohm -> LED -> GND
    - LED rojo:  GPIO 15 -> resistencia 220 ohm -> LED -> GND   (o un buzzer)
*/

#include <WiFi.h>
#include <PubSubClient.h>
#include <time.h>
#include "esp_camera.h"
#include "base64.h"          // viene incluida con el paquete de la placa ESP32

// ============================ CONFIGURACIÓN ============================
const char* WIFI_NOMBRE = "NOMBRE_DE_TU_WIFI";
const char* WIFI_CLAVE  = "CLAVE_DE_TU_WIFI";

const char* MQTT_BROKER = "192.168.1.100";   // IP del PC donde corre Mosquitto
const int   MQTT_PUERTO = 1883;

// Metadatos que exige el proyecto
const char* CLIENT_ID = "esp32cam_001";       // ID del cliente
const char* CAMERA_ID = "esp32cam_puerta";    // identificación de la cámara
const char* LOCATION  = "Entrada principal";  // sitio (sin tildes ni comillas)

const bool          USAR_SENSOR_PIR   = true;    // false = enviar una foto cada INTERVALO_MS
const unsigned long INTERVALO_MS      = 15000;
const unsigned long ESPERA_MINIMA_MS  = 5000;    // tiempo mínimo entre dos fotos
const float         UMBRAL_CONFIANZA  = 0.80;    // por debajo de esto no se actúa

#define PIN_PIR        13
#define PIN_LED_VERDE  14
#define PIN_LED_ROJO   15
// =======================================================================

const char* TOPIC_SOLICITUDES = "vision/solicitudes";
String topicRespuesta = String("vision/respuestas/") + CLIENT_ID;

// Pines de la cámara en la placa AI Thinker ESP32-CAM
#define PWDN_GPIO_NUM   32
#define RESET_GPIO_NUM  -1
#define XCLK_GPIO_NUM    0
#define SIOD_GPIO_NUM   26
#define SIOC_GPIO_NUM   27
#define Y9_GPIO_NUM     35
#define Y8_GPIO_NUM     34
#define Y7_GPIO_NUM     39
#define Y6_GPIO_NUM     36
#define Y5_GPIO_NUM     21
#define Y4_GPIO_NUM     19
#define Y3_GPIO_NUM     18
#define Y2_GPIO_NUM      5
#define VSYNC_GPIO_NUM  25
#define HREF_GPIO_NUM   23
#define PCLK_GPIO_NUM   22

WiFiClient wifi;
PubSubClient mqtt(wifi);

bool movimientoAnterior = false;
unsigned long ultimoEnvio = 0;
bool primerEnvio = true;

// ----------------------------------------------------------------------
// Cámara
// ----------------------------------------------------------------------
bool iniciarCamara() {
  camera_config_t config;
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer   = LEDC_TIMER_0;
  config.pin_d0 = Y2_GPIO_NUM;
  config.pin_d1 = Y3_GPIO_NUM;
  config.pin_d2 = Y4_GPIO_NUM;
  config.pin_d3 = Y5_GPIO_NUM;
  config.pin_d4 = Y6_GPIO_NUM;
  config.pin_d5 = Y7_GPIO_NUM;
  config.pin_d6 = Y8_GPIO_NUM;
  config.pin_d7 = Y9_GPIO_NUM;
  config.pin_xclk  = XCLK_GPIO_NUM;
  config.pin_pclk  = PCLK_GPIO_NUM;
  config.pin_vsync = VSYNC_GPIO_NUM;
  config.pin_href  = HREF_GPIO_NUM;
  config.pin_sccb_sda = SIOD_GPIO_NUM;
  config.pin_sccb_scl = SIOC_GPIO_NUM;
  config.pin_pwdn  = PWDN_GPIO_NUM;
  config.pin_reset = RESET_GPIO_NUM;
  config.xclk_freq_hz = 20000000;
  config.pixel_format = PIXFORMAT_JPEG;
  config.frame_size   = FRAMESIZE_QVGA;      // 320x240: suficiente, el modelo usa 180x180
  config.jpeg_quality = 12;                  // 0-63, menor número = mejor calidad
  config.fb_count     = 1;
  config.fb_location  = CAMERA_FB_IN_PSRAM;
  config.grab_mode    = CAMERA_GRAB_WHEN_EMPTY;

  if (esp_camera_init(&config) != ESP_OK) {
    Serial.println("Error: no se pudo iniciar la camara");
    return false;
  }
  return true;
}

// ----------------------------------------------------------------------
// WiFi, hora y MQTT
// ----------------------------------------------------------------------
void conectarWiFi() {
  Serial.print("Conectando al WiFi");
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_NOMBRE, WIFI_CLAVE);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.print(" listo. IP: ");
  Serial.println(WiFi.localIP());
}

// Fecha y hora en formato ISO (2026-11-16T22:30:00). Vacío si no hay hora de internet:
// en ese caso el puente del servidor pone la hora.
String fechaHora() {
  struct tm t;
  if (!getLocalTime(&t, 200)) return "";
  char texto[25];
  strftime(texto, sizeof(texto), "%Y-%m-%dT%H:%M:%S", &t);
  return String(texto);
}

void conectarMQTT() {
  while (!mqtt.connected()) {
    Serial.print("Conectando al broker MQTT... ");
    if (mqtt.connect(CLIENT_ID)) {
      mqtt.subscribe(topicRespuesta.c_str());
      Serial.println("conectado");
    } else {
      Serial.print("fallo (estado ");
      Serial.print(mqtt.state());
      Serial.println("). Reintento en 3 s");
      delay(3000);
    }
  }
}

// ----------------------------------------------------------------------
// Respuesta del servidor -> acción
// ----------------------------------------------------------------------
// Saca el valor de una clave de un JSON sencillo, por ejemplo "prediction":"gato"
String valorJson(const String& json, const char* clave) {
  int i = json.indexOf(String("\"") + clave + "\"");
  if (i < 0) return "";
  i = json.indexOf(':', i);
  if (i < 0) return "";
  i++;
  while (i < (int)json.length() && (json[i] == ' ' || json[i] == '"')) i++;
  int fin = i;
  while (fin < (int)json.length() && json[fin] != '"' && json[fin] != ',' && json[fin] != '}') fin++;
  return json.substring(i, fin);
}

void alLlegarRespuesta(char* topic, byte* payload, unsigned int longitud) {
  String json;
  for (unsigned int i = 0; i < longitud; i++) json += (char)payload[i];
  Serial.print("Respuesta: ");
  Serial.println(json);

  String prediccion = valorJson(json, "prediction");
  float confianza = valorJson(json, "confidence").toFloat();

  if (prediccion == "" || confianza < UMBRAL_CONFIANZA) {
    Serial.println("ACCION: ninguna (error o confianza baja)");
  } else if (prediccion == "gato") {
    Serial.println("ACCION: abrir puerta (LED verde)");
    digitalWrite(PIN_LED_VERDE, HIGH);        // aquí iría el servo o el relé de la puerta
    delay(3000);
    digitalWrite(PIN_LED_VERDE, LOW);
  } else {
    Serial.println("ACCION: alarma (LED rojo)");
    for (int i = 0; i < 6; i++) {             // parpadeo del LED rojo o pitidos del buzzer
      digitalWrite(PIN_LED_ROJO, HIGH);
      delay(250);
      digitalWrite(PIN_LED_ROJO, LOW);
      delay(250);
    }
  }
}

// ----------------------------------------------------------------------
// Captura -> Base64 -> JSON -> MQTT
// ----------------------------------------------------------------------
void capturarYEnviar() {
  // Se descarta una foto vieja que queda guardada en memoria y se toma una nueva
  camera_fb_t* foto = esp_camera_fb_get();
  if (foto) esp_camera_fb_return(foto);
  foto = esp_camera_fb_get();
  if (!foto) {
    Serial.println("Error: no se pudo tomar la foto");
    return;
  }

  // Imagen binaria -> texto Base64
  String imagenB64 = base64::encode(foto->buf, foto->len);
  size_t bytesFoto = foto->len;
  esp_camera_fb_return(foto);

  // JSON con los metadatos. La imagen va al final.
  String inicio = String("{\"client_id\":\"") + CLIENT_ID +
                  "\",\"timestamp\":\"" + fechaHora() +
                  "\",\"camera_id\":\"" + CAMERA_ID +
                  "\",\"location\":\"" + LOCATION +
                  "\",\"image\":\"";
  String fin = "\"}";
  unsigned int total = inicio.length() + imagenB64.length() + fin.length();

  // El mensaje es grande, así que se envía por partes
  if (!mqtt.beginPublish(TOPIC_SOLICITUDES, total, false)) {
    Serial.println("Error: no se pudo iniciar la publicacion MQTT");
    return;
  }
  mqtt.write((const uint8_t*)inicio.c_str(), inicio.length());
  const uint8_t* datos = (const uint8_t*)imagenB64.c_str();
  unsigned int enviados = 0;
  while (enviados < imagenB64.length()) {
    unsigned int parte = min((unsigned int)1024, (unsigned int)imagenB64.length() - enviados);
    mqtt.write(datos + enviados, parte);
    enviados += parte;
  }
  mqtt.write((const uint8_t*)fin.c_str(), fin.length());
  bool ok = mqtt.endPublish();

  Serial.printf("Foto de %u bytes -> JSON de %u bytes publicado: %s\n",
                (unsigned int)bytesFoto, total, ok ? "OK" : "ERROR");
}

// ----------------------------------------------------------------------
void setup() {
  Serial.begin(115200);
  pinMode(PIN_PIR, INPUT);
  pinMode(PIN_LED_VERDE, OUTPUT);
  pinMode(PIN_LED_ROJO, OUTPUT);

  if (!iniciarCamara()) {
    while (true) delay(1000);
  }
  conectarWiFi();
  configTime(-5 * 3600, 0, "pool.ntp.org");    // hora de Colombia (UTC-5)

  mqtt.setServer(MQTT_BROKER, MQTT_PUERTO);
  mqtt.setCallback(alLlegarRespuesta);
  mqtt.setBufferSize(1024);                    // para que quepa el JSON de respuesta
  conectarMQTT();
  Serial.println("Listo. Esperando al sensor...");
}

void loop() {
  if (WiFi.status() != WL_CONNECTED) conectarWiFi();
  if (!mqtt.connected()) conectarMQTT();
  mqtt.loop();                                 // atiende los mensajes que llegan

  bool disparo = false;
  if (USAR_SENSOR_PIR) {
    bool hayMovimiento = digitalRead(PIN_PIR) == HIGH;
    if (hayMovimiento && !movimientoAnterior) {      // solo cuando pasa de quieto a movimiento
      Serial.println("Sensor: movimiento detectado");
      disparo = true;
    }
    movimientoAnterior = hayMovimiento;
  } else if (primerEnvio || millis() - ultimoEnvio >= INTERVALO_MS) {
    disparo = true;
  }

  if (disparo && (primerEnvio || millis() - ultimoEnvio >= ESPERA_MINIMA_MS)) {
    capturarYEnviar();
    ultimoEnvio = millis();
    primerEnvio = false;
  }
  delay(50);
}
