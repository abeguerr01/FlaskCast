import json
import os
import signal
import subprocess
import threading
import sqlite3
from flask import Flask, send_from_directory, render_template, jsonify, abort, session, request, redirect, url_for
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import static_ffmpeg
import platform

app = Flask(__name__)
app.secret_key = 'flaskcast_ultra_secret_key_2026'

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per minute"],
    storage_uri="memory://"
)

static_ffmpeg.add_paths()

DIRECTORIO_RAIZ = os.path.dirname(os.path.abspath(__file__))
DIRECTORIO_MEDIA = os.path.join(DIRECTORIO_RAIZ, 'data', 'media')
DB_PATH = os.path.join(DIRECTORIO_RAIZ, 'data', 'flaskcast.db')
CONFIG_PATH = os.path.join(DIRECTORIO_RAIZ, 'data', 'config.json')

conversiones_activas = set()
lock_conversiones = threading.Lock()
api_habilitada = False


@app.context_processor
def inject_tema():
    tema = session.get('usuario_tema', 'oscuro')
    return {'tema_actual': tema}


def leer_config():
    try:
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def conectar_db():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn

def inicializar_base_datos():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = conectar_db()
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT UNIQUE NOT NULL,
            emoji TEXT DEFAULT '👤',
            ultimo_acceso TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            auto_marcar INTEGER DEFAULT 1
        )
    ''')
    
    cursor.execute("PRAGMA table_info(usuarios)")
    columnas = [col['name'] for col in cursor.fetchall()]
    if 'emoji' not in columnas:
        cursor.execute("ALTER TABLE usuarios ADD COLUMN emoji TEXT DEFAULT '👤'")
    if 'ultimo_acceso' not in columnas:
        cursor.execute("ALTER TABLE usuarios ADD COLUMN ultimo_acceso TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
    if 'auto_marcar' not in columnas:
        cursor.execute("ALTER TABLE usuarios ADD COLUMN auto_marcar INTEGER DEFAULT 1")
    if 'mostrar_progreso' not in columnas:
        cursor.execute("ALTER TABLE usuarios ADD COLUMN mostrar_progreso INTEGER DEFAULT 1")
    if 'tema' not in columnas:
        cursor.execute("ALTER TABLE usuarios ADD COLUMN tema TEXT DEFAULT 'oscuro'")

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS progreso (
            usuario_id INTEGER,
            serie TEXT,
            filename TEXT,
            segundos REAL DEFAULT 0,
            visto INTEGER DEFAULT 0,
            duracion REAL DEFAULT 0,
            PRIMARY KEY (usuario_id, serie, filename),
            FOREIGN KEY(usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE
        )
    ''')
    
    cursor.execute("PRAGMA table_info(progreso)")
    col_progreso = [col['name'] for col in cursor.fetchall()]
    if 'duracion' not in col_progreso:
        cursor.execute("ALTER TABLE progreso ADD COLUMN duracion REAL DEFAULT 0")

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS favoritos (
            usuario_id INTEGER,
            serie TEXT NOT NULL,
            fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (usuario_id, serie),
            FOREIGN KEY(usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE
        )
    ''')

    conn.commit()
    conn.close()

def hilo_conversion(identificador_unico, ruta_origen, ruta_mp4):
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
    try:
        os.makedirs(os.path.dirname(ruta_output_jpg), exist_ok=True)
        subprocess.run([
            'ffmpeg', '-ss', '00:00:03', '-i', ruta_video,
            '-vframes', '1', '-q:v', '4', '-y', ruta_output_jpg
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except Exception as e:
        print(f"⚠️ No se pudo generar la miniatura para {ruta_video}: {e}")
        return False

@app.route('/usuarios_panel')
def usuarios_panel():
    return_to = request.args.get('return_to', '/')
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM usuarios ORDER BY ultimo_acceso DESC, nombre ASC')
    todos_usuarios = cursor.fetchall()
    conn.close()
    return render_template('usuarios.html', usuarios=todos_usuarios, return_to=return_to)

@app.route('/usuarios/crear', methods=['POST'])
@limiter.limit("5 per minute")
def crear_usuario():
    return_to = request.form.get('return_to', '/usuarios_panel')
    nombre = request.form.get('nombre', '').strip()
    if nombre:
        try:
            conn = conectar_db()
            cursor = conn.cursor()
            cursor.execute('INSERT INTO usuarios (nombre) VALUES (?)', (nombre,))
            conn.commit()
            conn.close()
        except sqlite3.IntegrityError:
            pass 
    return redirect(return_to)

@app.route('/usuarios/seleccionar/<int:user_id>')
def seleccionar_usuario(user_id):
    return_to = request.args.get('return_to', '/')
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute('UPDATE usuarios SET ultimo_acceso = CURRENT_TIMESTAMP WHERE id = ?', (user_id,))
    cursor.execute('SELECT * FROM usuarios WHERE id = ?', (user_id,))
    user = cursor.fetchone()
    conn.commit()
    conn.close()
    if user:
        session['usuario_id'] = user['id']
        session['usuario_nombre'] = user['nombre']
        session['usuario_emoji'] = user['emoji']
        session['usuario_auto_marcar'] = user['auto_marcar']
        session['usuario_mostrar_progreso'] = user['mostrar_progreso']
        session['usuario_tema'] = user['tema'] if user['tema'] else 'oscuro'
    return redirect(return_to)

@app.route('/usuarios/editar/<int:user_id>', methods=['POST'])
@limiter.limit("10 per minute")
def editar_usuario(user_id):
    return_to = request.form.get('return_to', '/usuarios_panel')
    nombre = request.form.get('nombre', '').strip()
    emoji = request.form.get('emoji', '👤').strip()
    if nombre:
        try:
            conn = conectar_db()
            cursor = conn.cursor()
            cursor.execute('UPDATE usuarios SET nombre = ?, emoji = ? WHERE id = ?', (nombre, emoji, user_id))
            conn.commit()
            conn.close()
            if session.get('usuario_id') == user_id:
                session['usuario_nombre'] = nombre
                session['usuario_emoji'] = emoji
        except sqlite3.IntegrityError:
            pass
    return redirect(return_to)

@app.route('/usuarios/eliminar/<int:user_id>', methods=['POST'])
@limiter.limit("5 per minute")
def eliminar_usuario(user_id):
    return_to = request.form.get('return_to', '/usuarios_panel')
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM usuarios WHERE id = ?', (user_id,))
    conn.commit()
    conn.close()
    if session.get('usuario_id') == user_id:
        session.pop('usuario_id', None)
        session.pop('usuario_nombre', None)
        session.pop('usuario_emoji', None)
        session.pop('usuario_auto_marcar', None)
        session.pop('usuario_mostrar_progreso', None)
        session.pop('usuario_tema', None)
    return redirect(return_to)

@app.route('/usuarios/salir')
def salir_usuario():
    return_to = request.args.get('return_to', '/')
    session.pop('usuario_id', None)
    session.pop('usuario_nombre', None)
    session.pop('usuario_emoji', None)
    session.pop('usuario_auto_marcar', None)
    session.pop('usuario_mostrar_progreso', None)
    session.pop('usuario_tema', None)
    return redirect(return_to)

@app.route('/')
def index():
    todas_las_series = []
    if os.path.exists(DIRECTORIO_MEDIA):
        for item in sorted(os.listdir(DIRECTORIO_MEDIA)):
            ruta_item = os.path.join(DIRECTORIO_MEDIA, item)
            if os.path.isdir(ruta_item):
                tiene_portada = os.path.exists(os.path.join(ruta_item, '_img.png'))
                todas_las_series.append({
                    'nombre_carpeta': item,
                    'tiene_portada': tiene_portada
                })

    POR_PAGINA = 24
    total_series = len(todas_las_series)
    total_paginas = max(1, (total_series + POR_PAGINA - 1) // POR_PAGINA)
    pagina_actual = request.args.get('page', 1, type=int)
    pagina_actual = max(1, min(pagina_actual, total_paginas))
    inicio = (pagina_actual - 1) * POR_PAGINA
    fin = inicio + POR_PAGINA
    lista_series = todas_las_series[inicio:fin]

    continuar_viendo = []
    usuario_id = session.get('usuario_id')
    if usuario_id:
        conn = conectar_db()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT serie, filename, segundos, duracion, visto
            FROM progreso
            WHERE usuario_id = ? AND segundos > 0 AND duracion > 0 AND visto = 1
            ORDER BY serie, filename
        ''', (usuario_id,))
        filas = cursor.fetchall()
        conn.close()

        vistos = {}
        for fila in filas:
            clave = fila['serie']
            if clave not in vistos:
                vistos[clave] = []
            vistos[clave].append({
                'filename': fila['filename'],
                'segundos': fila['segundos'],
                'duracion': fila['duracion'],
                'visto': int(fila['visto']) if fila['visto'] is not None else 0
            })

        for nombre_serie, capitulos in vistos.items():
            ruta_serie = os.path.join(DIRECTORIO_MEDIA, nombre_serie)
            tiene_portada = os.path.exists(os.path.join(ruta_serie, '_img.png'))
            for cap in capitulos:
                porcentaje = min(int((cap['segundos'] / cap['duracion']) * 100), 100)
                nombre_limpio = os.path.basename(cap['filename'])
                continuar_viendo.append({
                    'serie': nombre_serie,
                    'filename': cap['filename'],
                    'nombre_capitulo': nombre_limpio,
                    'segundos': cap['segundos'],
                    'duracion': cap['duracion'],
                    'porcentaje': porcentaje,
                    'visto': cap['visto'],
                    'tiene_portada': tiene_portada
                })

        continuar_viendo.sort(key=lambda x: x['segundos'], reverse=True)
        continuar_viendo = continuar_viendo[:12]

    favoritos_nombres = []
    favoritos_detalle = []
    if usuario_id:
        conn = conectar_db()
        cursor = conn.cursor()
        cursor.execute('SELECT serie FROM favoritos WHERE usuario_id = ? ORDER BY fecha DESC', (usuario_id,))
        favoritos_nombres = [fila['serie'] for fila in cursor.fetchall()]
        conn.close()

        series_map = {s['nombre_carpeta']: s for s in todas_las_series}
        for fav_nombre in favoritos_nombres:
            if fav_nombre in series_map:
                favoritos_detalle.append(series_map[fav_nombre])
            else:
                ruta_fav = os.path.join(DIRECTORIO_MEDIA, fav_nombre)
                if os.path.isdir(ruta_fav):
                    tiene_portada = os.path.exists(os.path.join(ruta_fav, '_img.png'))
                    favoritos_detalle.append({
                        'nombre_carpeta': fav_nombre,
                        'tiene_portada': tiene_portada
                    })

    return render_template('index.html',
        series=lista_series,
        active_section='catalogo',
        continuar_viendo=continuar_viendo,
        favoritos=favoritos_detalle,
        pagina_actual=pagina_actual,
        total_paginas=total_paginas,
        total_series=total_series
    )

LIVE_STREAMS_PATH = os.path.join(DIRECTORIO_RAIZ, 'data', 'live_streams.json')

def detectar_tipo(url):
    ext = os.path.splitext(url.split('?')[0])[1].lower()
    if ext in ('.mp4', '.webm', '.ogg'):
        return 'video'
    if ext == '.m3u8':
        return 'hls'
    return 'iframe'

def parsear_m3u(url):
    import urllib.request
    canales = []
    try:
        if url.startswith('http://') or url.startswith('https://'):
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            respuesta = urllib.request.urlopen(req, timeout=10)
            contenido = respuesta.read().decode('utf-8', errors='ignore')
        else:
            ruta_local = os.path.join(DIRECTORIO_RAIZ, url)
            with open(ruta_local, 'r', encoding='utf-8') as f:
                contenido = f.read()
        lineas = contenido.strip().split('\n')
        nombre_temp = None
        for linea in lineas:
            linea = linea.strip()
            if not linea or linea.startswith('#EXTM3U'):
                continue
            if linea.startswith('#EXTINF:'):
                parte = linea.split(',', 1)
                nombre_temp = parte[1].strip() if len(parte) > 1 else None
            elif linea.startswith('http') or linea.startswith('rtmp'):
                canales.append({
                    'titulo': nombre_temp or linea.split('/')[-1] or 'Canal',
                    'url': linea,
                    'tipo': detectar_tipo(linea)
                })
                nombre_temp = None
    except Exception as e:
        print("Error al parsear M3U: " + str(e))
    return canales

def normalizar_urls(stream):
    urls_raw = stream.get('urls', stream.get('url', ''))
    if isinstance(urls_raw, list):
        stream['urls'] = urls_raw
    else:
        stream['urls'] = [urls_raw] if urls_raw else []
    stream['url'] = stream['urls'][0] if stream['urls'] else ''
    return stream

def cargar_streams():
    streams = []
    if os.path.exists(LIVE_STREAMS_PATH):
        with open(LIVE_STREAMS_PATH, 'r', encoding='utf-8') as f:
            raw = json.load(f)
        for item in raw:
            if item.get('tipo') == 'm3u':
                m3u_url = item.get('url', '')
                canales = parsear_m3u(m3u_url)
                for canal in canales:
                    canal = normalizar_urls(canal)
                streams.extend(canales)
            elif item.get('tipo') == 'auto':
                item['tipo'] = detectar_tipo(item.get('url', ''))
                item = normalizar_urls(item)
                streams.append(item)
            else:
                item = normalizar_urls(item)
                streams.append(item)
    return streams

@app.route('/live')
def live():
    streams = cargar_streams()
    return render_template('live.html', streams=streams, active_section='directo')

@app.route('/live/tv/<int:indice>')
def live_tv(indice):
    streams = cargar_streams()
    if indice < 0 or indice >= len(streams):
        return abort(404)
    s = streams[indice]
    return render_template('live_tv.html', titulo=s.get('titulo', 'Stream'), url=s['url'], urls=s.get('urls', [s['url']]), tipo=s.get('tipo', 'iframe'))

def es_cliente_local():
    remote = request.remote_addr
    return remote in ('127.0.0.1', '::1', 'localhost')

@app.route('/ajustes', methods=['GET', 'POST'])
def ajustes():
    global api_habilitada
    usuario_id = session.get('usuario_id')
    
    if request.method == 'POST':
        return_to = request.form.get('return_to', '/')

        if usuario_id:
            conn = conectar_db()
            cursor = conn.cursor()
            auto_marcar = 1 if request.form.get('auto_marcar') == 'on' else 0
            mostrar_progreso = 1 if request.form.get('mostrar_progreso') == 'on' else 0
            tema = request.form.get('tema', 'oscuro')
            if tema not in ('oscuro', 'claro'):
                tema = 'oscuro'
            cursor.execute('UPDATE usuarios SET auto_marcar = ?, mostrar_progreso = ?, tema = ? WHERE id = ?', (auto_marcar, mostrar_progreso, tema, usuario_id))
            conn.commit()
            session['usuario_auto_marcar'] = auto_marcar
            session['usuario_mostrar_progreso'] = mostrar_progreso
            session['usuario_tema'] = tema

        return redirect(return_to)
    
    return_to = request.args.get('return_to', '/')
    auto_marcar = 1
    mostrar_progreso = 1
    tema = 'oscuro'
    if usuario_id:
        conn = conectar_db()
        cursor = conn.cursor()
        cursor.execute('SELECT auto_marcar, mostrar_progreso, tema FROM usuarios WHERE id = ?', (usuario_id,))
        user = cursor.fetchone()
        conn.close()
        if user:
            auto_marcar = user['auto_marcar']
            mostrar_progreso = user['mostrar_progreso']
            tema = user['tema'] if user['tema'] else 'oscuro'
    
    cfg = leer_config()
    return render_template('ajustes.html', auto_marcar=auto_marcar, mostrar_progreso=mostrar_progreso, tema=tema,
        boton_apagar_visible=cfg.get('boton_apagar_visible', False),
        boton_apagar_todo_visible=cfg.get('boton_apagar_todo_visible', False),
        es_local=es_cliente_local(), return_to=return_to, usuario_id=usuario_id)

def api_habilitada_check():
    global api_habilitada
    return api_habilitada

@app.route('/api/videos/add', methods=['POST'])
@limiter.limit("10 per minute")
def api_agregar_video():
    if not api_habilitada_check():
        return jsonify({'error': 'API no habilitada. Actívala en config_admin.py.'}), 403
    
    serie = request.form.get('serie', '').strip()
    if not serie:
        return jsonify({'error': 'El campo "serie" es requerido.'}), 400
    
    temporada = request.form.get('temporada', '').strip()
    archivo = request.files.get('archivo')
    if not archivo or archivo.filename == '':
        return jsonify({'error': 'Debes enviar un archivo en el campo "archivo".'}), 400
    
    filename = os.path.basename(archivo.filename)
    serie_dir = os.path.join(DIRECTORIO_MEDIA, serie)
    
    if not os.path.exists(serie_dir):
        return jsonify({'error': f'La serie "{serie}" no existe.'}), 404
    
    items = os.listdir(serie_dir)
    subcarpetas = [i for i in items if os.path.isdir(os.path.join(serie_dir, i)) and not i.startswith('.')]
    
    if subcarpetas:
        if not temporada:
            return jsonify({'error': 'Esta serie tiene temporadas. El campo "temporada" es obligatorio.'}), 400
        if temporada not in subcarpetas:
            return jsonify({'error': f'La temporada "{temporada}" no existe en esta serie.'}), 404
        destino_dir = os.path.join(serie_dir, temporada)
    else:
        if temporada:
            return jsonify({'error': 'Esta serie no tiene temporadas. No uses el campo "temporada".'}), 400
        destino_dir = serie_dir
    
    ruta_destino = os.path.join(destino_dir, filename)
    archivo.save(ruta_destino)
    
    ruta_rel = f"{temporada}/{filename}" if temporada else filename
    return jsonify({'status': 'ok', 'mensaje': f'Video guardado en {serie}/{ruta_rel}'})

@app.route('/api/videos/rm', methods=['POST'])
@limiter.limit("10 per minute")
def api_eliminar_video():
    if not api_habilitada_check():
        return jsonify({'error': 'API no habilitada. Actívala en config_admin.py.'}), 403
    
    datos = request.json or {}
    serie = datos.get('serie', '').strip()
    filename = datos.get('filename', '').strip()
    
    if not serie or not filename:
        return jsonify({'error': 'Los campos "serie" y "filename" son requeridos.'}), 400
    
    filename = filename.replace('\\', '/')
    ruta_archivo = os.path.normpath(os.path.join(DIRECTORIO_MEDIA, serie, filename))
    if not ruta_archivo.startswith(os.path.normpath(DIRECTORIO_MEDIA)):
        return jsonify({'error': 'Ruta no válida'}), 400
    
    if not os.path.exists(ruta_archivo):
        return jsonify({'error': 'Archivo no encontrado'}), 404
    
    try:
        os.remove(ruta_archivo)
        nombre_base, _ = os.path.splitext(filename)
        ruta_thumb = os.path.join(DIRECTORIO_MEDIA, serie, '.thumbnails', f"{nombre_base}.jpg")
        if os.path.exists(ruta_thumb):
            os.remove(ruta_thumb)
        usuario_id = session.get('usuario_id')
        if usuario_id:
            conn = conectar_db()
            cursor = conn.cursor()
            cursor.execute('DELETE FROM progreso WHERE serie = ? AND filename = ?', (serie, filename))
            conn.commit()
            conn.close()
        return jsonify({'status': 'eliminado'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def escanear_estructura_serie(ruta_serie, nombre_serie):
    if not os.path.exists(ruta_serie) or not os.path.isdir(ruta_serie):
        return None
    formatos_video = ('.mp4', '.webm', '.ogg', '.avi', '.mkv')
    items = sorted(os.listdir(ruta_serie))
    subcarpetas = [i for i in items if os.path.isdir(os.path.join(ruta_serie, i)) and not i.startswith('.')]
    estructura = {'nombre': nombre_serie, 'temporadas': {}}
    if subcarpetas:
        for sub in subcarpetas:
            ruta_sub = os.path.join(ruta_serie, sub)
            videos = sorted([f for f in os.listdir(ruta_sub) if os.path.isfile(os.path.join(ruta_sub, f)) and f.lower().endswith(formatos_video)])
            estructura['temporadas'][sub] = {'nombre': sub, 'capitulos': videos}
    else:
        videos = sorted([f for f in items if os.path.isfile(os.path.join(ruta_serie, f)) and f.lower().endswith(formatos_video)])
        estructura['temporadas']['Contenido Disponible'] = {'nombre': 'Contenido Disponible', 'capitulos': videos}
    return estructura

@app.route('/api/videos', methods=['GET'])
@app.route('/api/videos/<path:nombre_serie>', methods=['GET'])
def api_listar_videos(nombre_serie=None):
    if not api_habilitada_check():
        return jsonify({'error': 'API no habilitada. Actívala en config_admin.py.'}), 403
    
    if nombre_serie:
        ruta_serie = os.path.join(DIRECTORIO_MEDIA, nombre_serie)
        estructura = escanear_estructura_serie(ruta_serie, nombre_serie)
        if estructura is None:
            return jsonify({'error': f'La serie "{nombre_serie}" no existe.'}), 404
        return jsonify({'status': 'ok', 'serie': estructura})
    
    series = []
    if os.path.exists(DIRECTORIO_MEDIA):
        for item in sorted(os.listdir(DIRECTORIO_MEDIA)):
            ruta_item = os.path.join(DIRECTORIO_MEDIA, item)
            if os.path.isdir(ruta_item):
                estructura = escanear_estructura_serie(ruta_item, item)
                if estructura:
                    series.append(estructura)
    return jsonify({'status': 'ok', 'series': series})

@app.route('/serie/<nombre_serie>')
def vista_serie(nombre_serie):
    ruta_serie = os.path.join(DIRECTORIO_MEDIA, nombre_serie)
    if not os.path.exists(ruta_serie) or not os.path.isdir(ruta_serie):
        return abort(404)
        
    formatos_web = ('.mp4', '.webm', '.ogg')
    formatos_incompatibles = ('.avi', '.mkv')
    estructura_temporadas = {}
    
    progreso_usuario = {}
    usuario_id = session.get('usuario_id')
    mostrar_progreso = 1
    if usuario_id:
        conn = conectar_db()
        cursor = conn.cursor()
        cursor.execute('SELECT filename, segundos, duracion, visto FROM progreso WHERE usuario_id = ? AND serie = ?', (usuario_id, nombre_serie))
        filas = cursor.fetchall()
        cursor.execute('SELECT mostrar_progreso FROM usuarios WHERE id = ?', (usuario_id,))
        user_row = cursor.fetchone()
        conn.close()
        if user_row:
            mostrar_progreso = int(user_row['mostrar_progreso'])
        for fila in filas:
            dur = fila['duracion'] if fila['duracion'] else 0
            seg = fila['segundos'] if fila['segundos'] else 0
            porcentaje = min(int((seg / dur) * 100), 100) if dur > 0 else 0
            progreso_usuario[fila['filename']] = {
                'segundos': seg,
                'duracion': dur,
                'visto': int(fila['visto']) if fila['visto'] is not None else 0,
                'porcentaje': porcentaje
            }

    items = sorted(os.listdir(ruta_serie))
    subcarpetas = [i for i in items if os.path.isdir(os.path.join(ruta_serie, i)) and not i.startswith('.')]
    
    if subcarpetas:
        for subcarpeta in subcarpetas:
            ruta_subcarpeta = os.path.join(ruta_serie, subcarpeta)
            videos_temporada = []
            
            for archivo in sorted(os.listdir(ruta_subcarpeta)):
                extension = os.path.splitext(archivo)[1].lower()
                ruta_relativa = f"{subcarpeta}/{archivo}"
                identificador_unico = f"{nombre_serie}/{ruta_relativa}"
                
                prog = progreso_usuario.get(ruta_relativa, {'segundos': 0, 'duracion': 0, 'visto': 0, 'porcentaje': 0})
                
                if extension in formatos_web:
                    videos_temporada.append({
                        'nombre_real': archivo,
                        'ruta_relativa': ruta_relativa,
                        'tipo': 'web',
                        'estado': 'listo',
                        'visto': prog['visto'],
                        'segundos': prog['segundos'],
                        'duracion': prog['duracion'],
                        'porcentaje': prog['porcentaje']
                    })
                elif extension in formatos_incompatibles:
                    with lock_conversiones:
                        en_progreso = identificador_unico in conversiones_activas
                    videos_temporada.append({
                        'nombre_real': archivo,
                        'ruta_relativa': ruta_relativa,
                        'tipo': 'incompatible',
                        'estado': 'procesando' if en_progreso else 'pendiente',
                        'visto': 0,
                        'segundos': 0
                    })
            if videos_temporada:
                estructura_temporadas[subcarpeta] = videos_temporada
    else:
        videos_raiz = []
        for archivo in items:
            if os.path.isfile(os.path.join(ruta_serie, archivo)):
                extension = os.path.splitext(archivo)[1].lower()
                prog = progreso_usuario.get(archivo, {'segundos': 0, 'duracion': 0, 'visto': 0, 'porcentaje': 0})
                
                if extension in formatos_web:
                    videos_raiz.append({
                        'nombre_real': archivo,
                        'ruta_relativa': archivo,
                        'tipo': 'web',
                        'estado': 'listo',
                        'visto': prog['visto'],
                        'segundos': prog['segundos'],
                        'duracion': prog['duracion'],
                        'porcentaje': prog['porcentaje']
                    })
                elif extension in formatos_incompatibles:
                    with lock_conversiones:
                        en_progreso = f"{nombre_serie}/{archivo}" in conversiones_activas
                    videos_raiz.append({
                        'nombre_real': archivo,
                        'ruta_relativa': archivo,
                        'tipo': 'incompatible',
                        'estado': 'procesando' if en_progreso else 'pendiente',
                        'visto': 0,
                        'segundos': 0
                    })
        if videos_raiz:
            estructura_temporadas['Contenido Disponible'] = videos_raiz

    es_favorito = False
    if usuario_id:
        conn = conectar_db()
        cursor = conn.cursor()
        cursor.execute('SELECT 1 FROM favoritos WHERE usuario_id = ? AND serie = ?', (usuario_id, nombre_serie))
        es_favorito = cursor.fetchone() is not None
        conn.close()
            
    return render_template('serie.html', serie=nombre_serie, temporadas=estructura_temporadas, mostrar_progreso=mostrar_progreso, es_favorito=es_favorito)

@app.route('/tv/reproducir/<nombre_serie>/<path:filename>')
def reproductor_tv(nombre_serie, filename):
    ruta_serie = os.path.join(DIRECTORIO_MEDIA, nombre_serie)
    sub_dir = os.path.dirname(filename)
    ruta_dir_absoluta = os.path.join(ruta_serie, sub_dir)
    
    formatos_web = ('.mp4', '.webm', '.ogg')
    next_filename = None
    segundo_inicio = 0
    
    usuario_id = session.get('usuario_id')
    if usuario_id:
        conn = conectar_db()
        cursor = conn.cursor()
        cursor.execute('SELECT segundos FROM progreso WHERE usuario_id = ? AND serie = ? AND filename = ?', (usuario_id, nombre_serie, filename))
        fila = cursor.fetchone()
        conn.close()
        if fila:
            segundo_inicio = fila['segundos']
    
    if os.path.exists(ruta_dir_absoluta) and os.path.isdir(ruta_dir_absoluta):
        archivos_compatibles = sorted([
            f for f in os.listdir(ruta_dir_absoluta)
            if os.path.isfile(os.path.join(ruta_dir_absoluta, f)) and f.lower().endswith(formatos_web)
        ])
        
        nombre_actual = os.path.basename(filename)
        if nombre_actual in archivos_compatibles:
            indice_actual = archivos_compatibles.index(nombre_actual)
            if indice_actual + 1 < len(archivos_compatibles):
                siguiente_base = archivos_compatibles[indice_actual + 1]
                next_filename = os.path.join(sub_dir, siguiente_base).replace('\\', '/')

    return render_template('player_tv.html', serie=nombre_serie, filename=filename, next_filename=next_filename, segundo_inicio=segundo_inicio)

@app.route('/api/progreso/guardar', methods=['POST'])
@limiter.limit("60 per minute")
def api_guardar_progreso():
    usuario_id = session.get('usuario_id')
    if not usuario_id:
        return jsonify({'status': 'ignorado_invitado'}) 
        
    datos = request.json or {}
    serie = datos.get('serie')
    filename = datos.get('filename')
    segundos = datos.get('segundos', 0)
    duracion = datos.get('duracion', 0)
    
    if not serie or not filename:
        return jsonify({'error': 'Parámetros insuficientes'}), 400
        
    conn = conectar_db()
    cursor = conn.cursor()
    
    cursor.execute('SELECT auto_marcar FROM usuarios WHERE id = ?', (usuario_id,))
    user_row = cursor.fetchone()
    auto_marcar = user_row['auto_marcar'] if user_row else 1
    
    cursor.execute('SELECT visto, duracion FROM progreso WHERE usuario_id = ? AND serie = ? AND filename = ?', (usuario_id, serie, filename))
    existing = cursor.fetchone()
    
    if duracion == 0 and existing:
        duracion = existing['duracion']
        
    if 'visto' in datos:
        # Forzado manual (Click en el Badge)
        nuevo_visto = int(datos['visto'])
    else:
        # Reproducción Automática
        if auto_marcar == 1 and duracion > 0:
            porcentaje = segundos / duracion
            if porcentaje >= 0.85:
                nuevo_visto = 2
            elif porcentaje >= 0.10:
                nuevo_visto = 1
            else:
                nuevo_visto = 0
        else:
            nuevo_visto = existing['visto'] if existing else 0
            
    cursor.execute('''
        INSERT INTO progreso (usuario_id, serie, filename, segundos, visto, duracion)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(usuario_id, serie, filename) DO UPDATE SET
            segundos = excluded.segundos,
            visto = excluded.visto,
            duracion = max(progreso.duracion, excluded.duracion)
    ''', (usuario_id, serie, filename, segundos, nuevo_visto, duracion))
    conn.commit()
    conn.close()
    return jsonify({'status': 'guardado', 'nuevo_visto': nuevo_visto})

@app.route('/api/progreso/obtener')
def api_obtener_progreso():
    usuario_id = session.get('usuario_id')
    serie = request.args.get('serie')
    filename = request.args.get('filename')
    
    if not usuario_id or not serie or not filename:
        return jsonify({'segundos': 0, 'visto': 0})
        
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute('SELECT segundos, visto FROM progreso WHERE usuario_id = ? AND serie = ? AND filename = ?', (usuario_id, serie, filename))
    fila = cursor.fetchone()
    conn.close()
    
    if fila:
        return jsonify({'segundos': fila['segundos'], 'visto': int(fila['visto'])})
    return jsonify({'segundos': 0, 'visto': 0})

@app.route('/api/favoritos', methods=['GET'])
def api_obtener_favoritos():
    usuario_id = session.get('usuario_id')
    if not usuario_id:
        return jsonify({'favoritos': []})
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute('SELECT serie FROM favoritos WHERE usuario_id = ? ORDER BY fecha DESC', (usuario_id,))
    filas = cursor.fetchall()
    conn.close()
    return jsonify({'favoritos': [fila['serie'] for fila in filas]})

@app.route('/api/favoritos/toggle', methods=['POST'])
@limiter.limit("30 per minute")
def api_toggle_favorito():
    usuario_id = session.get('usuario_id')
    if not usuario_id:
        return jsonify({'error': 'Inicia sesión para usar favoritos'}), 401
    datos = request.json or {}
    serie = datos.get('serie', '').strip()
    if not serie:
        return jsonify({'error': 'El campo "serie" es requerido'}), 400
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute('SELECT 1 FROM favoritos WHERE usuario_id = ? AND serie = ?', (usuario_id, serie))
    existe = cursor.fetchone()
    if existe:
        cursor.execute('DELETE FROM favoritos WHERE usuario_id = ? AND serie = ?', (usuario_id, serie))
        conn.commit()
        conn.close()
        return jsonify({'favorito': False})
    else:
        cursor.execute('INSERT INTO favoritos (usuario_id, serie) VALUES (?, ?)', (usuario_id, serie))
        conn.commit()
        conn.close()
        return jsonify({'favorito': True})

@app.route('/thumbnail/<nombre_serie>/<path:filename>')
def serve_thumbnail(nombre_serie, filename):
    ruta_serie = os.path.join(DIRECTORIO_MEDIA, nombre_serie)
    ruta_video = os.path.join(ruta_serie, filename)
    nombre_base, _ = os.path.splitext(filename)
    ruta_thumb = os.path.join(ruta_serie, '.thumbnails', f"{nombre_base}.jpg")
    
    if not os.path.exists(ruta_thumb) and os.path.exists(ruta_video):
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

@app.route('/api/video/<nombre_serie>/<path:filename>')
def api_obtener_video(nombre_serie, filename):
    if not api_habilitada_check():
        return jsonify({'error': 'API no habilitada. Actívala en config_admin.py.'}), 403
    ruta_serie = os.path.join(DIRECTORIO_MEDIA, nombre_serie)
    ruta_archivo = os.path.join(ruta_serie, filename)
    if not os.path.exists(ruta_archivo):
        return jsonify({'error': 'Archivo no encontrado'}), 404
    return send_from_directory(ruta_serie, filename)

@app.route('/api/convertir/<nombre_serie>/<path:filename>', methods=['POST'])
@limiter.limit("5 per minute")
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
@limiter.limit("10 per minute")
def eliminar_archivo(nombre_serie, filename):
    ruta_serie = os.path.join(DIRECTORIO_MEDIA, nombre_serie)
    ruta_archivo = os.path.join(ruta_serie, filename)
    if os.path.exists(ruta_archivo):
        try:
            os.remove(ruta_archivo)
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
    
@app.route('/api/abrir_config_admin')
def abrir_config_admin():
    if not es_cliente_local():
        return jsonify({'error': 'Solo disponible en la máquina local.'}), 403
    config_admin_path = os.path.join(DIRECTORIO_RAIZ, 'config_admin.py')
    if platform.system() == "Windows":
        subprocess.Popen(['python', config_admin_path], creationflags=subprocess.DETACHED_PROCESS)
    else:
        subprocess.Popen(['python3', config_admin_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return jsonify({'status': 'ok'})

@app.route('/api/ping')
def ping():
    return jsonify({'status': 'servidor en linea'})

@app.route('/api/off')
@limiter.limit("2 per minute")
def off():
    cfg = leer_config()
    if not cfg.get('boton_apagar_visible', False):
        return jsonify({'error': 'Funcion no habilitada'}), 403
    threading.Thread(target=_apagar_servidor, daemon=True).start()
    return jsonify({'status': 'Apagando servidor...'})

def _apagar_servidor():
    os.kill(os.getpid(), signal.SIGINT)

@app.route('/api/off/all')
@limiter.limit("1 per minute")
def off_all():
    cfg = leer_config()
    if not cfg.get('boton_apagar_todo_visible', False):
        return jsonify({'error': 'Funcion no habilitada'}), 403
    threading.Thread(target=_apagar_todo, daemon=True).start()
    return jsonify({'status': 'Apagando sistema...'})

def _apagar_todo():
    if platform.system() == "Windows":
        subprocess.run("shutdown -s -t 0 ", shell=True)
    else:
        subprocess.run("sudo shutdown -h now", shell=True)

if __name__ == '__main__':
    inicializar_base_datos()
    
    cfg = leer_config()
    api_habilitada = cfg.get('api_habilitada', False)
    puerto = cfg.get('puerto', 5000)
    sistema = platform.system()
    
    if sistema == "Windows":
        from waitress import serve
        print(f"Iniciado servidor con Waitress (Windows) en puerto {puerto}")
        serve(app, host='0.0.0.0', port=puerto, threads=6)
        
    else:
        import subprocess
        print(f"Iniciado servidor Gunicorn (Linux/Unix) en puerto {puerto}")
        subprocess.run([
            "gunicorn", 
            "--bind", f"0.0.0.0:{puerto}", 
            "--workers", "4", 
            "app:app"
        ])