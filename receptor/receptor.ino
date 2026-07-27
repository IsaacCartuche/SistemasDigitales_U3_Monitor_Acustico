#include <esp_now.h>
#include <WiFi.h>
#include <PubSubClient.h>

// ================= Configuración de Red =================
const char* ssid = "Velocity_Johanna_Delgado";
const char* password = "1104088826";
const char* mqtt_server = "192.168.101.10"; // IP de tu PC
const int mqtt_port = 1883;

WiFiClient espClient;
PubSubClient client(espClient);

// Variables para manejar el tiempo sin delay()
unsigned long ultimoIntentoMQTT = 0;
const long intervaloMQTT = 5000; // Intentar reconectar MQTT cada 5 segundos

unsigned long ultimoIntentoWiFi = 0;
const long intervaloWiFi = 5000; // Intentar reconectar Wi-Fi cada 5 segundos

// Callback de recepción de ESP-NOW adaptado a ESP32 Core 3.x
void OnDataRecv(const esp_now_recv_info *info, const uint8_t *incomingData, int len) {
  // Copiamos los bytes recibidos a una cadena de caracteres
  char mensajeRecibido[len + 1]; // +1 para asegurar el terminador nulo
  memcpy(mensajeRecibido, incomingData, len);
  mensajeRecibido[len] = '\0'; // Terminación nula obligatoria para Strings
  
  String jsonString = String(mensajeRecibido);
  
  Serial.print("JSON Recibido por ESP-NOW: ");
  Serial.println(jsonString);

  // Si estamos conectados a MQTT, publicamos
  if (client.connected()) {
    client.publish("sensores/ruido", jsonString.c_str());
    Serial.println("--> Publicado en MQTT exitosamente");
  } else {
    Serial.println("--> Error: No conectado a MQTT, dato descartado");
  }
}

void setup() {
  Serial.begin(115200);
  
  // Iniciamos la conexión Wi-Fi (proceso asíncrono)
  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid, password);
  
  // Configuramos el servidor MQTT
  client.setServer(mqtt_server, mqtt_port);

  // Inicializamos ESP-NOW
  if (esp_now_init() != ESP_OK) {
    Serial.println("Error inicializando ESP-NOW");
    return;
  }
  
  esp_now_register_recv_cb(OnDataRecv);
}

void loop() {
  unsigned long tiempoActual = millis();

  // 1. Control No Bloqueante de la Conexión Wi-Fi
  if (WiFi.status() != WL_CONNECTED) {
    if (tiempoActual - ultimoIntentoWiFi >= intervaloWiFi) {
      ultimoIntentoWiFi = tiempoActual;
      Serial.println("Wi-Fi desconectado. Intentando reconectar...");
      WiFi.disconnect();
      WiFi.begin(ssid, password);
    }
  } 
  // 2. Control No Bloqueante de la Conexión MQTT (solo si hay Wi-Fi)
  else if (!client.connected()) {
    if (tiempoActual - ultimoIntentoMQTT >= intervaloMQTT) {
      ultimoIntentoMQTT = tiempoActual;
      Serial.println("Intentando conexión a MQTT...");
      
      // Intentamos conectar
      if (client.connect("ESP32_Gateway")) {
        Serial.println("¡Conectado a MQTT!");
      } else {
        Serial.print("Falló conexión MQTT, error: ");
        Serial.print(client.state());
        Serial.println(" - Intentando de nuevo en 5 segundos.");
      }
    }
  } 
  // 3. Mantenimiento rutinario de MQTT
  else {
    client.loop(); // Mantiene viva la conexión
  }
}