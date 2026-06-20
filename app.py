import os
import subprocess
import threading
from flask import Flask, send_from_directory, render_template, jsonify
import static_ffmpeg

app = Flask(__name__)

# Configura automáticamente los binarios de FFmpeg según el SO de la máquina
static_ffmpeg.add_paths()

# Rutas del proyecto basadas en tu árbol de directorios
DIRECTORIO_RAIZ = os.path.dirname(os.path.abspath(__file__))
DIRECTORIO_MEDIA = os.path.join(DIRECTORIO_RAIZ, 'data', 'media', 'Por_cuatro_perras')

# Estructuras de control para la gestión de hilos asíncronos
conversiones_activas = set()
lock_conversiones = threading.Lock()

def hilo_conversion(archivo, ruta_origen, ruta_mp4):
    """Función en paralelo para procesar la conversión pesada sin congelar el servidor web"""
    global conversiones_activas
    try:
        subprocess.run([
            'ffmpeg', '-i', ruta_origen, 
            '-vcodec', 'libx264', '-acodec', 'aac', 
            '-crf', '23', '-y', ruta_mp4
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print(f"✅ Conversión completada en segundo plano: {archivo}")
    except Exception as e:
        print(f"❌ Error en hilo de conversión para {archivo}: {e}")
    finally:
        # Al finalizar, eliminamos el archivo del set global de control
        with lock_conversiones:
            conversiones_activas.discard(archivo)

@app.route('/')
def index():
    formatos_web = ('.mp4', '.webm', '.ogg')
    formatos_incompatibles = ('.avi', '.mkv')
    lista_final = []
    
    if os.path.exists(DIRECTORIO_MEDIA):
        archivos = sorted(os.listdir(DIRECTORIO_MEDIA))
        for archivo in archivos:
            extension = os.path.splitext(archivo)[1].lower()
            
            if extension in formatos_web:
                lista_final.append({
                    'nombre': archivo,
                    'tipo': 'web',
                    'estado': 'listo'
                })
            elif extension in formatos_incompatibles:
                with lock_conversiones:
                    en_progreso = archivo in conversiones_activas
                
                lista_final.append({
                    'nombre': archivo,
                    'tipo': 'incompatible',
                    'estado': 'procesando' if en_progreso else 'pendiente'
                })
                
    return render_template('index.html', videos=lista_final)

@app.route('/api/convertir/<path:filename>', methods=['POST'])
def desencadenar_conversion(filename):
    """Lanza la orden para iniciar el hilo de conversión por AJAX"""
    global conversiones_activas
    ruta_origen = os.path.join(DIRECTORIO_MEDIA, filename)
    
    if not os.path.exists(ruta_origen):
        return jsonify({'error': 'El archivo no existe'}), 404
        
    nombre_base = os.path.splitext(filename)[0]
    archivo_mp4 = f"{nombre_base}.mp4"
    ruta_mp4 = os.path.join(DIRECTORIO_MEDIA, archivo_mp4)
    
    with lock_conversiones:
        if filename in conversiones_activas:
            return jsonify({'status': 'ya_en_progreso'})
        if os.path.exists(ruta_mp4):
            return jsonify({'status': 'ya_existe_mp4'})
            
        conversiones_activas.add(filename)
    
    # Arrancamos el hilo asíncrono
    hilo = threading.Thread(target=hilo_conversion, args=(filename, ruta_origen, ruta_mp4))
    hilo.start()
    
    return jsonify({'status': 'procesando'})

@app.route('/api/eliminar/<path:filename>', methods=['POST'])
def eliminar_archivo(filename):
    """Borra físicamente el archivo incompatible del almacenamiento"""
    ruta_archivo = os.path.join(DIRECTORIO_MEDIA, filename)
    if os.path.exists(ruta_archivo):
        try:
            os.remove(ruta_archivo)
            return jsonify({'status': 'eliminado'})
        except Exception as e:
            return jsonify({'error': str(e)}), 500
            
    return jsonify({'error': 'Archivo no encontrado'}), 404

@app.route('/api/estados')
def consultar_estados():
    """Endpoint de polling para comprobar qué archivos siguen convirtiéndose"""
    with lock_conversiones:
        return jsonify({'activos': list(conversiones_activas)})

@app.route('/video/<path:filename>')
def serve_video(filename):
    """Transmite de manera segura el stream de vídeo al reproductor HTML5"""
    return send_from_directory(DIRECTORIO_MEDIA, filename)

if __name__ == '__main__':
    print("🚀 Servidor Flask Abierto a la Red Local.")
    print("👉 En este PC de desarrollo: http://127.0.0.1:5000")
    print("👉 Desde otros equipos de tu red usa la IP local del PC (ej: http://192.168.1.50:5000)")
    
    # Ejecución con host público local
    app.run(host='0.0.0.0', port=5000, debug=True)