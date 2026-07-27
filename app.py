from flask import Flask, render_template, jsonify
import mysql.connector

app = Flask(__name__)

db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': '',
    'database': 'monitor_ruido'
}

# ==========================================
# PARÁMETROS DE NORMATIVA Y CALIBRACIÓN
# ==========================================
LIMITE_NORMAL_DB = 55.0  
LIMITE_ALERTA_DB = 75.0  

def convertir_adc_a_db(adc):
    """Transforma el valor crudo del ADC a Decibelios (dB)."""
    if adc is None or adc <= 0:
        return 30.0 
    
    m = 0.021
    b = 15.5
    db = (adc * m) + b
    return round(db, 1)

def evaluar_estado(db_actual):
    """Evalúa el nivel de ruido frente a la normativa."""
    if db_actual <= LIMITE_NORMAL_DB:
        return "NORMAL", "Dentro de rango"
    elif db_actual <= LIMITE_ALERTA_DB:
        return "PRECAUCIÓN", "Nivel elevado"
    else:
        return "ALERTA", "Límite excedido"

def conectar_db():
    return mysql.connector.connect(**db_config)

# ==========================================
# RUTAS DE LA APLICACIÓN
# ==========================================

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/datos')
def api_datos():
    conn = None
    try:
        conn = conectar_db()
        cursor = conn.cursor(dictionary=True)
        
        # 1. Obtener coordenadas dinámicamente desde la tabla 'nodos'
        cursor.execute("SELECT id_nodo, nombre, latitud, longitud FROM nodos")
        nodos_db = cursor.fetchall()
        coordenadas_zonas = {
            nodo['id_nodo']: {
                "lat": float(nodo['latitud']), 
                "lng": float(nodo['longitud']), 
                "nombre": nodo['nombre']
            } for nodo in nodos_db
        }
        
        # 2. Obtener el historial reciente (Adaptado a la nueva tabla 'lecturas')
        # Traemos los últimos 60 registros generales para asegurar tener datos de ambas zonas
        query_ultimos = """
            SELECT id_nodo, valor_adc, DATE_FORMAT(fecha_registro, '%H:%i:%s') as hora 
            FROM lecturas 
            ORDER BY fecha_registro DESC LIMIT 60
        """
        cursor.execute(query_ultimos)
        ultimos = cursor.fetchall()

        if not ultimos:
            return jsonify({
                "historico": [], 
                "estadisticas": {"max_ruido_historico": 0, "promedio_general": 0, "estado": "SIN DATOS", "estado_sub": "--"}, 
                "coordenadas": coordenadas_zonas
            })

        ultimos_cronologico = ultimos[::-1] # Invertir para orden cronológico

        # Agrupamos por 'hora' para que el gráfico del frontend reciba la estructura que espera
        historico_dict = {}
        for fila in ultimos_cronologico:
            hora = fila["hora"]
            nodo = fila["id_nodo"]
            
            if hora not in historico_dict:
                # Inicializamos con 30dB (silencio) por si un nodo no envió dato en ese segundo
                historico_dict[hora] = {"hora": hora, "zona1": 30.0, "zona2": 30.0}
            
            # Solo procesamos si el nodo es zona1 o zona2
            if nodo in ["zona1", "zona2"]:
                historico_dict[hora][nodo] = convertir_adc_a_db(fila["valor_adc"])

        # Nos quedamos con los últimos 20 puntos de tiempo
        historico_db = list(historico_dict.values())[-20:]

        # 3. Obtener estadísticas globales
        query_stats = """
            SELECT 
                COALESCE(MAX(valor_adc), 0) as max_ruido_historico,
                COALESCE(AVG(valor_adc), 0) as promedio_general
            FROM lecturas
        """
        cursor.execute(query_stats)
        stats = cursor.fetchone()

        max_db = convertir_adc_a_db(float(stats["max_ruido_historico"]))
        prom_db = convertir_adc_a_db(float(stats["promedio_general"]))

        # 4. Evaluar el estado actual basándonos en la última lectura más alta del historial
        ultimo_registro = historico_db[-1]
        max_actual_db = max(ultimo_registro.get("zona1", 30), ultimo_registro.get("zona2", 30))
        estado_texto, estado_sub = evaluar_estado(max_actual_db)

        stats_clean = {
            "max_ruido_historico": max_db,
            "promedio_general": prom_db,
            "estado": estado_texto,
            "estado_sub": estado_sub
        }

        cursor.close()
        conn.close()

        return jsonify({
            "historico": historico_db,
            "estadisticas": stats_clean,
            "coordenadas": coordenadas_zonas
        })

    except Exception as e:
        print(f"\n[ERROR CRÍTICO EN API]: {e}\n")
        if conn and conn.is_connected():
            conn.close()
        return jsonify({"error": str(e)}), 500

# ==========================================
# NUEVA RUTA PARA EL MAPA DE CALOR Y ETIQUETAS
# ==========================================
@app.route('/api/datos_mapa')
def api_datos_mapa():
    conn = None
    try:
        conn = conectar_db()
        cursor = conn.cursor(dictionary=True)
        
        # Obtenemos solo la lectura más reciente de cada nodo
        query_mapa = """
            SELECT n.id_nodo, n.nombre, n.latitud, n.longitud, 
                   l.valor_adc, l.fecha_registro
            FROM nodos n
            JOIN lecturas l ON n.id_nodo = l.id_nodo
            WHERE l.id IN (
                SELECT MAX(id) 
                FROM lecturas 
                GROUP BY id_nodo
            )
        """
        cursor.execute(query_mapa)
        resultados = cursor.fetchall()
        cursor.close()
        conn.close()

        datos_nodos = []
        for fila in resultados:
            db_calculado = convertir_adc_a_db(fila["valor_adc"])
            estado_txt, _ = evaluar_estado(db_calculado)
            
            estado_formateado = estado_txt.capitalize() 

            datos_nodos.append({
                "id_nodo": fila["id_nodo"],
                "nombre": fila["nombre"],
                "latitud": float(fila["latitud"]),
                "longitud": float(fila["longitud"]),
                "decibelios": db_calculado,
                "estado": estado_formateado,
                "ultima_actualizacion": str(fila["fecha_registro"]) # <-- Cambio aquí también
            })

        return jsonify(datos_nodos)

    except Exception as e:
        print(f"Error en API Mapa: {e}")
        if conn and conn.is_connected():
            conn.close()
        return jsonify({"error": "No se pudieron obtener los datos"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)