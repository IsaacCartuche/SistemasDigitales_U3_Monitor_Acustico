import paho.mqtt.client as mqtt
import mysql.connector
import json

# ==========================================
# CONFIGURACIÓN
# ==========================================
# Configuración de MySQL
db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': '',
    'database': 'monitor_ruido'
}

# Configuración MQTT
MQTT_BROKER = "localhost" # O la IP de tu broker Mosquitto si está en otra máquina
MQTT_PORT = 1883
MQTT_TOPIC = "sensores/ruido"

# ==========================================
# FUNCIONES
# ==========================================
def conectar_db():
    return mysql.connector.connect(**db_config)

def on_connect(client, userdata, flags, rc):
    print(f"Conectado a MQTT con código de resultado: {rc}")
    client.subscribe(MQTT_TOPIC)
    print(f"Suscrito al tema: {MQTT_TOPIC}")

def on_message(client, userdata, msg):
    try:
        # 1. Decodificar el mensaje JSON
        payload = msg.payload.decode('utf-8')
        datos = json.loads(payload)
        
        # 2. Extraer los valores
        # Se espera un JSON tipo: {"id_nodo": "zona1", "valor_adc": 2500}
        id_nodo = datos.get("id_nodo")
        valor_adc = datos.get("valor_adc")
        
        if not id_nodo or valor_adc is None:
            print("Mensaje ignorado: Formato JSON incorrecto o datos faltantes.")
            return

        # 3. Guardar en la nueva estructura de la base de datos
        conn = conectar_db()
        cursor = conn.cursor()
        
        query = "INSERT INTO lecturas (id_nodo, valor_adc) VALUES (%s, %s)"
        cursor.execute(query, (id_nodo, valor_adc))
        conn.commit()
        
        print(f"Guardado OK -> Nodo: {id_nodo} | ADC: {valor_adc}")
        
        cursor.close()
        conn.close()

    except json.JSONDecodeError:
        print("Error: El mensaje recibido no es un JSON válido.")
    except Exception as e:
        print(f"Error procesando mensaje: {e}")

# ==========================================
# BUCLE PRINCIPAL
# ==========================================
if __name__ == "__main__":
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message

    print("Iniciando Worker MQTT...")
    try:
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
        client.loop_forever()
    except KeyboardInterrupt:
        print("\nWorker detenido por el usuario.")
    except Exception as e:
        print(f"No se pudo conectar al Broker MQTT: {e}")