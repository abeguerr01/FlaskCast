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

# Estructuras de control para la conversión asíncrona multi-nivel
conversiones_activas = set()  # Almacena cadenas estilo "Nombre Serie/Temporada 1/capitulo.avi"
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

def generar_fotograma_preview(ruta_video, ruta_output_jpg):
    """Usa FFmpeg para extraer un único fotograma en el segundo 3 del vídeo"""
    try:
        os.makedirs(os.path.dirname(ruta_output_jpg), exist_ok=True)
        # -ss 00:00:03 salta al segundo 3, -vframes 1 toma 1 foto, -q:v 4 ajusta la calidad JPEG
        subprocess.run([
            'ffmpeg', '-ss', '00:00:03', '-i', ruta_video,
            '-vframes', '1', '-q:v', '4', '-y', ruta_output_jpg
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except Exception as e:
        print(f"⚠️ No se pudo generar la miniatura para {ruta_video}: {e}")
        return False

@app.route('/')
def index():
    """PÁGINA PRINCIPAL: Catálogo de Series/Películas"""
    lista_series = []
    if os.path.exists(DIRECTORIO_MEDIA):
        for item in sorted(os.listdir(DIRECTORIO_MEDIA)):
            ruta_item = os.path.join(DIRECTORIO_MEDIA, item)
            if os.path.isdir(ruta_item):
                tiene_portada = os.path.exists(os.path.join(ruta_item, '_img.png'))
                lista_series.append({
                    'nombre_carpeta': item,
                    'tiene_portada': tiene_portada
                })
    return render_template('index.html', series=lista_series)

@app.route('/serie/<nombre_serie>')
def vista_serie(nombre_serie):
    """PÁGINA DE DETALLE: Estructura de temporadas y capítulos agrupados por carpetas"""
    ruta_serie = os.path.join(DIRECTORIO_MEDIA, nombre_serie)
    if not os.path.exists(ruta_serie) or not os.path.isdir(ruta_serie):
        return abort(404)
        
    formatos_web = ('.mp4', '.webm', '.ogg')
    formatos_incompatibles = ('.avi', '.mkv')
    estructura_temporadas = {}
    
    items = sorted(os.listdir(ruta_serie))
    # Filtrar subcarpetas ignorando las ocultas (como nuestra nueva carpeta de .thumbnails)
    subcarpetas = [i for i in items if os.path.isdir(os.path.join(ruta_serie, i)) and not i.startswith('.')]
    
    if subcarpetas:
        for subcarpeta in subcarpetas:
            ruta_subcarpeta = os.path.join(ruta_serie, subcarpeta)
            videos_temporada = []
            
            for archivo in sorted(os.listdir(ruta_subcarpeta)):
                extension = os.path.splitext(archivo)[1].lower()
                ruta_relativa = f"{subcarpeta}/{archivo}"
                identificador_unico = f"{nombre_serie}/{ruta_relativa}"
                
                if extension in formatos_web:
                    videos_temporada.append({
                        'nombre_real': archivo,
                        'ruta_relativa': ruta_relativa,
                        'tipo': 'web',
                        'estado': 'listo'
                    })
                elif extension in formatos_incompatibles:
                    with lock_conversiones:
                        en_progreso = identificador_unico in conversiones_activas
                    videos_temporada.append({
                        'nombre_real': archivo,
                        'ruta_relativa': ruta_relativa,
                        'tipo': 'incompatible',
                        'estado': 'procesando' if en_progreso else 'pendiente'
                    })
            if videos_temporada:
                estructura_temporadas[subcarpeta] = videos_temporada
    else:
        videos_raiz = []
        for archivo in items:
            if os.path.isfile(os.path.join(ruta_serie, archivo)):
                extension = os.path.splitext(archivo)[1].lower()
                if extension in formatos_web:
                    videos_raiz.append({
                        'nombre_real': archivo,
                        'ruta_relativa': archivo,
                        'tipo': 'web',
                        'estado': 'listo'
                    })
                elif extension in formatos_incompatibles:
                    with lock_conversiones:
                        en_progreso = f"{nombre_serie}/{archivo}" in conversiones_activas
                    videos_raiz.append({
                        'nombre_real': archivo,
                        'ruta_relativa': archivo,
                        'tipo': 'incompatible',
                        'estado': 'procesando' if en_progreso else 'pendiente'
                    })
        if videos_raiz:
            estructura_temporadas['Contenido Disponible'] = videos_raiz
            
    return render_template('serie.html', serie=nombre_serie, temporadas=estructura_temporadas)

@app.route('/thumbnail/<nombre_serie>/<path:filename>')
def serve_thumbnail(nombre_serie, filename):
    """Genera bajo demanda (y cachea) la miniatura de un capítulo"""
    ruta_serie = os.path.join(DIRECTORIO_MEDIA, nombre_serie)
    ruta_video = os.path.join(ruta_serie, filename)
    
    # Construimos la ruta de la miniatura reemplazando la extensión por .jpg
    nombre_base, _ = os.path.splitext(filename)
    ruta_thumb = os.path.join(ruta_serie, '.thumbnails', f"{nombre_base}.jpg")
    
    # Si no existe en caché, intentamos fabricarla ahora mismo
    if not os.path.exists(ruta_thumb):
        if os.path.exists(ruta_video):
            generar_fotograma_preview(ruta_video, ruta_thumb)
            
    if os.path.exists(ruta_thumb):
        return send_from_directory(os.path.dirname(ruta_thumb), os.path.basename(ruta_thumb), mimetype='image/jpeg')
    
    return abort(404)

@app.route('/portada/<nombre_serie>')
def serve_portada(nombre_serie):
    ruta_serie = os.path.join(DIRECTORIO_MEDIA, nombre_serie)
    return send_from_directory(ruta_serie, '_img.png', mimetype='image/png')

@app.route('/video/<nombre_serie>/<path:filename>')
def serve_video(nombre_serie, filename):
    ruta_serie = os.path.join(DIRECTORIO_MEDIA, nombre_serie)
    return send_from_directory(ruta_serie, filename)

@app.route('/api/convertir/<nombre_serie>/<path:filename>', methods=['POST'])
def desencadenar_conversion(nombre_serie, filename):
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

@app.route('/api/eliminar/<nombre_serie>/<path:filename>', methods=['POST'])
def eliminar_archivo(nombre_serie, filename):
    ruta_serie = os.path.join(DIRECTORIO_MEDIA, nombre_serie)
    ruta_archivo = os.path.join(ruta_serie, filename)
    
    if os.path.exists(ruta_archivo):
        try:
            os.remove(ruta_archivo)
            # También intentamos borrar su miniatura asociada para dejar limpio el disco
            nombre_base, _ = os.path.splitext(filename)
            ruta_thumb = os.path.join(ruta_serie, '.thumbnails', f"{nombre_base}.jpg")
            if os.path.exists(ruta_thumb):
                os.remove(ruta_thumb)
                
            return jsonify({'status': 'eliminado'})
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    return jsonify({'error': 'Archivo no encontrado'}), 404

@app.route('/api/estados')
def consultar_estados():
    with lock_conversiones:
        return jsonify({'activos': list(conversiones_activas)})

if __name__ == '__main__':
    print("🚀 Servidor Abierto con Miniaturas Dinámicas. Listo para disfrutar.")
    app.run(host='0.0.0.0', port=5000, debug=True)