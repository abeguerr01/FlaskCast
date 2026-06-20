import os
import subprocess
import threading
from flask import Flask, send_from_directory, render_template, jsonify, abort
import static_ffmpeg

app = Flask(__name__)

# Configura automáticamente los binarios de FFmpeg según el SO de la máquina
static_ffmpeg.add_paths()

# Ruta raíz hacia la carpeta donde guardas todas las series/pelis
DIRECTORIO_RAIZ = os.path.dirname(os.path.abspath(__file__))
DIRECTORIO_MEDIA = os.path.join(DIRECTORIO_RAIZ, 'data', 'media')

# Estructuras de control para la conversión asíncrona entre series
conversiones_activas = set()  # Almacenará elementos como "Nombre Serie/capitulo.avi"
lock_conversiones = threading.Lock()

def hilo_conversion(identificador_unico, ruta_origen, ruta_mp4):
    """Procesa la conversión en paralelo por debajo sin congelar Flask"""
    global conversiones_activas
    try:
        subprocess.run([
            'ffmpeg', '-i', ruta_origen, 
            '-vcodec', 'libx264', '-acodec', 'aac', 
            '-crf', '23', '-y', ruta_mp4
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print(f"✅ Conversión completada en segundo plano: {identificador_unico}")
    except Exception as e:
        print(f"❌ Error en la conversión de {identificador_unico}: {e}")
    finally:
        with lock_conversiones:
            conversiones_activas.discard(identificador_unico)

@app.route('/')
def index():
    """PÁGINA PRINCIPAL: Catálogo de Series/Películas"""
    lista_series = []
    
    if os.path.exists(DIRECTORIO_MEDIA):
        for item in sorted(os.listdir(DIRECTORIO_MEDIA)):
            ruta_item = os.path.join(DIRECTORIO_MEDIA, item)
            
            # Cada subcarpeta dentro de data/media es una serie o peli
            if os.path.isdir(ruta_item):
                # Comprobamos si tiene portada en formato .png
                tiene_portada = os.path.exists(os.path.join(ruta_item, '_img.png'))
                
                lista_series.append({
                    'nombre_carpeta': item,
                    'tiene_portada': tiene_portada
                })
                
    return render_template('index.html', series=lista_series)

@app.route('/serie/<path:nombre_serie>')
def vista_serie(nombre_serie):
    """PÁGINA DE DETALLE: Lista de capítulos de una serie concreta"""
    ruta_serie = os.path.join(DIRECTORIO_MEDIA, nombre_serie)
    
    if not os.path.exists(ruta_serie) or not os.path.isdir(ruta_serie):
        return abort(404)
        
    formatos_web = ('.mp4', '.webm', '.ogg')
    formatos_incompatibles = ('.avi', '.mkv')
    lista_videos = []
    
    for archivo in sorted(os.listdir(ruta_serie)):
        extension = os.path.splitext(archivo)[1].lower()
        identificador_unico = f"{nombre_serie}/{archivo}"
        
        if extension in formatos_web:
            lista_videos.append({
                'nombre': archivo,
                'tipo': 'web',
                'estado': 'listo'
            })
        elif extension in formatos_incompatibles:
            with lock_conversiones:
                en_progreso = identificador_unico in conversiones_activas
            
            lista_videos.append({
                'nombre': archivo,
                'tipo': 'incompatible',
                'estado': 'procesando' if en_progreso else 'pendiente'
            })
            
    return render_template('serie.html', serie=nombre_serie, videos=lista_videos)

@app.route('/portada/<path:nombre_serie>')
def serve_portada(nombre_serie):
    """Sirve el archivo _img.png de la carpeta de la serie si existe"""
    ruta_serie = os.path.join(DIRECTORIO_MEDIA, nombre_serie)
    return send_from_directory(ruta_serie, '_img.png', mimetype='image/png')

@app.route('/video/<path:nombre_serie>/<path:filename>')
def serve_video(nombre_serie, filename):
    """Sirve de forma segura los archivos de video desde la carpeta de su serie"""
    ruta_serie = os.path.join(DIRECTORIO_MEDIA, nombre_serie)
    return send_from_directory(ruta_serie, filename)

@app.route('/api/convertir/<path:nombre_serie>/<path:filename>', methods=['POST'])
def desencadenar_conversion(nombre_serie, filename):
    """Petición AJAX para poner a convertir un archivo en segundo plano"""
    global conversiones_activas
    ruta_serie = os.path.join(DIRECTORIO_MEDIA, nombre_serie)
    ruta_origen = os.path.join(ruta_serie, filename)
    
    if not os.path.exists(ruta_origen):
        return jsonify({'error': 'El archivo original no existe'}), 404
        
    nombre_base = os.path.splitext(filename)[0]
    ruta_mp4 = os.path.join(ruta_serie, f"{nombre_base}.mp4")
    identificador_unico = f"{nombre_serie}/{filename}"
    
    with lock_conversiones:
        if identificador_unico in conversiones_activas:
            return jsonify({'status': 'ya_en_progreso'})
        if os.path.exists(ruta_mp4):
            return jsonify({'status': 'ya_existe_mp4'})
            
        conversiones_activas.add(identificador_unico)
        
    hilo = threading.Thread(target=hilo_conversion, args=(identificador_unico, ruta_origen, ruta_mp4))
    hilo.start()
    
    return jsonify({'status': 'procesando'})

@app.route('/api/eliminar/<path:nombre_serie>/<path:filename>', methods=['POST'])
def eliminar_archivo(nombre_serie, filename):
    """Borra físicamente el archivo de la carpeta contenedora"""
    ruta_archivo = os.path.join(DIRECTORIO_MEDIA, nombre_serie, filename)
    if os.path.exists(ruta_archivo):
        try:
            os.remove(ruta_archivo)
            return jsonify({'status': 'eliminado'})
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    return jsonify({'error': 'Archivo no encontrado'}), 404

@app.route('/api/estados')
def consultar_estados():
    """Devuelve el set global de conversiones activas en tiempo real"""
    with lock_conversiones:
        return jsonify({'activos': list(conversiones_activas)})

if __name__ == '__main__':
    print("🚀 Servidor Multimedia Abierto en Red Local.")
    # Mantenemos la escucha global para entrar desde otros equipos
    app.run(host='0.0.0.0', port=5000, debug=True)