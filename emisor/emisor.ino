#include <esp_now.h>
#include <WiFi.h>
#include <esp_wifi.h> 
#include <ArduinoJson.h>

// MAC Address del Gateway (Reemplázala con la tuya)
uint8_t broadcastAddress[] = {0x00, 0x00, 0x00, 0x00, 0x00, 0x00};

// ¡CAMBIAR ESTO PARA CADA NODO FÍSICO! ("zona1" o "zona2")
String ID_NODO = "zona2"; 
const int pinMicrofono = 34; 

// Variables para millis()
unsigned long tiempoAnterior = 0;
const long intervalo = 2000; // Enviar datos cada 2 segundos

// Callback adaptado a la versión 3.x del Core ESP32
void OnDataSent(const wifi_tx_info_t *info, esp_now_send_status_t status) {
  Serial.print("\r\nEstado del envío: ");
  Serial.println(status == ESP_NOW_SEND_SUCCESS ? "Éxito (ACK recibido)" : "Fallo");
}

void setup() {
  Serial.begin(115200);
  
  // Configurar en modo estación
  WiFi.mode(WIFI_STA);
  
  // Forzar el canal Wi-Fi 11
  esp_wifi_set_channel(11, WIFI_SECOND_CHAN_NONE);

  if (esp_now_init() != ESP_OK) {
    Serial.println("Error inicializando ESP-NOW");
    return;
  }

  esp_now_register_send_cb(OnDataSent);

  esp_now_peer_info_t peerInfo = {};
  memcpy(peerInfo.peer_addr, broadcastAddress, 6);
  peerInfo.channel = 11; 
  peerInfo.encrypt = false;

  if (esp_now_add_peer(&peerInfo) != ESP_OK){
    Serial.println("Fallo al añadir el Gateway");
    return;
  }
}

void loop() {
  unsigned long tiempoActual = millis();

  if (tiempoActual - tiempoAnterior >= intervalo) {
    tiempoAnterior = tiempoActual;

    int valorADC = analogRead(pinMicrofono);

    // Crear el documento JSON
    StaticJsonDocument<200> doc;
    doc["id_nodo"] = ID_NODO;
    doc["valor_adc"] = valorADC;

    // Convertir el JSON a String
    String salidaJson;
    serializeJson(doc, salidaJson);

    // Enviar por ESP-NOW
    esp_now_send(broadcastAddress, (uint8_t *)salidaJson.c_str(), salidaJson.length() + 1);

    Serial.println("Enviando JSON: " + salidaJson);
  }
}
