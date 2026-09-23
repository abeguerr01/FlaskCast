# =============================================================================
# IMPORTACIONES
# =============================================================================
import json
import os
import signal
import subprocess
import sys
import threading
import sqlite3
import urllib.request
import urllib.parse
from flask import Flask, send_from_directory, render_template, jsonify, abort, session, request, redirect, url_for
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import static_ffmpeg
import platform
from translations import get_text, TRANSLATIONS, translate_metadata

# Windows usa cp1252 por defecto en consolas/redirecciones; forzamos UTF-8
# para que los print() con emojis no lancen UnicodeEncodeError.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

# =============================================================================
# INICIALIZACIÓN DE LA APLICACIÓN FLASK
# =============================================================================
app = Flask(__name__)
app.secret_key = 'flaskcast_ultra_secret_key_2026'

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per minute"],
    storage_uri="memory://"
)

# =============================================================================
# DETECCIÓN DE CÓDEC FFMPEG
# =============================================================================
import shutil

if shutil.which('ffmpeg'):
    pass
else:
    try:
        static_ffmpeg.add_paths()
    except Exception:
        pass

def _detectar_codificador():
    try:
        resultado = subprocess.run(
            ['ffmpeg', '-encoders'], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL
        )
        encoders = resultado.stdout.decode('utf-8', errors='replace')
        prioridad = ['libx264', 'libopenh264', 'h264_nvenc', 'h264_amf', 'h264_qsv', 'h264_vaapi', 'h264_v4l2m2m']
        for codec in prioridad:
            if codec in encoders:
                print(f"🎬 Codificador H.264 detectado: {codec}")
                return codec
    except Exception:
        pass
    print("⚠️ No se detectó codificador H.264, usando fallback libx264")
    return 'libx264'

VENCODER = _detectar_codificador()

def _obtener_duracion(ruta_video):
    try:
        r = subprocess.run(
            ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
             '-of', 'default=noprint_wrappers=1:nokey=1', ruta_video],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL
        )
        return float(r.stdout.decode('utf-8', errors='replace').strip())
    except Exception:
        return None

def _parsear_progreso_ffmpeg(linea):
    import re
    m = re.search(r'time=(\d+):(\d+):(\d+\.?\d*)', linea)
    if m:
        h, m, s = float(m.group(1)), float(m.group(2)), float(m.group(3))
        return h * 3600 + m * 60 + s
    m = re.search(r'time=(\d+\.?\d*)', linea)
    if m:
        return float(m.group(1))
    return None

# =============================================================================
# CONSTANTES DE RUTA Y ESTADO
# =============================================================================
DIRECTORIO_RAIZ = os.path.dirname(os.path.abspath(__file__))
DIRECTORIO_MEDIA = os.path.join(DIRECTORIO_RAIZ, 'data', 'media')
DB_PATH = os.path.join(DIRECTORIO_RAIZ, 'data', 'flaskcast.db')
CONFIG_PATH = os.path.join(DIRECTORIO_RAIZ, 'data', 'config.json')

conversiones_activas = set()
resultados_conversiones = {}
progreso_conversiones = {}
lock_conversiones = threading.Lock()

# =============================================================================
# PROCESADORES DE CONTEXTO Y MIDDLEWARE
# =============================================================================
@app.context_processor
def inject_tema():
    tema = session.get('usuario_tema', 'oscuro')
    idioma = session.get('usuario_idioma', 'es')
    def t(key):
        return get_text(idioma, key)
    return {'tema_actual': tema, 'idioma_actual': idioma, 't': t, 'T': TRANSLATIONS,
            'auth_activa': auth_habilitada(), 'auth_autenticado': esta_autenticado()}


def leer_config():
    try:
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

_cfg = leer_config()
api_habilitada = _cfg.get('api_habilitada', False)

@app.before_request
def check_api_habilitada():
    if request.path.startswith('/api/') and not api_habilitada:
        return jsonify({'error': 'API no habilitada. Actívala en config_admin.py.'}), 403

def esta_autenticado():
    return session.get('auth_autenticado', False)

def auth_habilitada():
    cfg = leer_config()
    return cfg.get('auth_enabled', False) and bool(cfg.get('auth_password', '').strip())

@app.before_request
def check_auth():
    if request.endpoint in ('login', 'logout', 'static'):
        return
    if request.path.startswith('/api/'):
        return
    if not auth_habilitada():
        return
    if esta_autenticado():
        return
    return redirect(url_for('login', next=request.url))

def es_cliente_local():
    remote = request.remote_addr
    return remote in ('127.0.0.1', '::1', 'localhost')

# =============================================================================
# BASE DE DATOS
# =============================================================================
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
    if 'idioma' not in columnas:
        cursor.execute("ALTER TABLE usuarios ADD COLUMN idioma TEXT DEFAULT 'es'")

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

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS listas (
            usuario_id INTEGER,
            serie TEXT NOT NULL,
            estado INTEGER DEFAULT 0,
            fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (usuario_id, serie),
            FOREIGN KEY(usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS content_metadata (
            serie TEXT PRIMARY KEY,
            tipo TEXT DEFAULT 'auto',
            FOREIGN KEY(serie) REFERENCES favoritos(serie)
        )
    ''')

    conn.commit()
    conn.close()

# =============================================================================
# DETECCIÓN DE TIPO DE CONTENIDO
# =============================================================================
def detectar_tipo_contenido(nombre_carpeta):
    """Detecta si una carpeta es pelicula o serie.
    Prioridad: DB > _meta.json > deteccion por estructura.
    Retorna 'pelicula' o 'serie'.
    """
    ruta = os.path.join(DIRECTORIO_MEDIA, nombre_carpeta)
    if not os.path.isdir(ruta):
        return 'serie'

    # 1. Buscar en DB
    try:
        conn = conectar_db()
        cursor = conn.cursor()
        cursor.execute('SELECT tipo FROM content_metadata WHERE serie = ?', (nombre_carpeta,))
        fila = cursor.fetchone()
        conn.close()
        if fila and fila['tipo'] in ('pelicula', 'serie'):
            return fila['tipo']
    except Exception:
        pass

    # 2. Buscar _meta.json
    meta_path = os.path.join(ruta, '_meta.json')
    if os.path.exists(meta_path):
        try:
            import json
            with open(meta_path, 'r', encoding='utf-8') as f:
                meta = json.load(f)
            if meta.get('tipo') in ('pelicula', 'serie'):
                # Guardar en DB para futuras consultas
                try:
                    conn = conectar_db()
                    cursor = conn.cursor()
                    cursor.execute('INSERT OR REPLACE INTO content_metadata (serie, tipo) VALUES (?, ?)',
                                   (nombre_carpeta, meta['tipo']))
                    conn.commit()
                    conn.close()
                except Exception:
                    pass
                return meta['tipo']
        except Exception:
            pass

    # 3. Deteccion por estructura: subcarpetas = serie, sin subcarpetas = pelicula
    ruta_videos = obtener_ruta_serie(nombre_carpeta)
    items = os.listdir(ruta_videos)
    subcarpetas = [i for i in items if os.path.isdir(os.path.join(ruta_videos, i)) and not i.startswith('.')]
    if subcarpetas:
        return 'serie'
    return 'pelicula'

def obtener_ruta_serie(nombre_carpeta):
    """Obtiene la ruta real donde se encuentran los videos de una serie/pelicula.
    Si _meta.json tiene un campo 'ubicacion' no vacio y la ruta existe, la retorna.
    De lo contrario, retorna data/media/{nombre}.
    """
    ruta_default = os.path.join(DIRECTORIO_MEDIA, nombre_carpeta)
    meta_path = os.path.join(ruta_default, '_meta.json')
    if os.path.exists(meta_path):
        try:
            with open(meta_path, 'r', encoding='utf-8') as f:
                meta = json.load(f)
            ubicacion = meta.get('ubicacion', '').strip()
            if ubicacion and os.path.isdir(ubicacion):
                return ubicacion
        except Exception:
            pass
    return ruta_default

# =============================================================================
# CONVERSIÓN (Hilo FFmpeg + auxiliares)
# =============================================================================
def hilo_conversion(identificador_unico, ruta_origen, ruta_mp4):
    global conversiones_activas, resultados_conversiones, progreso_conversiones
    exito = False
    proc = None

    print(f"\n{'='*60}")
    print(f"🔄 [CONVERSIÓN] Iniciando: {identificador_unico}")
    print(f"   Codificador: {VENCODER}")

    duracion_total = _obtener_duracion(ruta_origen)
    print(f"   Duración total: {duracion_total}s")
    with lock_conversiones:
        progreso_conversiones[identificador_unico] = 0

    try:
        cmd = [
            'ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error',
            '-progress', 'pipe:1',
            '-i', ruta_origen,
            '-vcodec', VENCODER, '-acodec', 'aac',
            '-crf', '23', '-y', ruta_mp4
        ]
        print(f"🔄 [CONVERSIÓN] Ejecutando: {' '.join(cmd)}")
        proc = subprocess.Popen(
            cmd, stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            start_new_session=True
        )
        print(f"🔄 [CONVERSIÓN] PID de FFmpeg: {proc.pid}")

        lineas_error = []
        def _drenar_stderr():
            for linea in iter(proc.stderr.readline, b''):
                texto = linea.decode('utf-8', errors='replace').strip()
                if texto:
                    lineas_error.append(texto)
        hilo_stderr = threading.Thread(target=_drenar_stderr, daemon=True)
        hilo_stderr.start()

        try:
            ultimo_log = 0
            for linea in iter(proc.stdout.readline, b''):
                texto = linea.decode('utf-8', errors='replace').strip()
                if not texto.startswith('out_time='):
                    continue
                tiempo = _parsear_progreso_ffmpeg('time=' + texto.split('=', 1)[1])
                if tiempo is not None and duracion_total and duracion_total > 0:
                    pct = min(int((tiempo / duracion_total) * 100), 99)
                    with lock_conversiones:
                        progreso_conversiones[identificador_unico] = pct
                    if pct >= ultimo_log + 10:
                        print(f"📊 [CONVERSIÓN] {identificador_unico}: {pct}% ({tiempo:.0f}s / {duracion_total:.0f}s)")
                        ultimo_log = pct
            proc.stdout.close()
            proc.wait()
        except KeyboardInterrupt:
            print(f"⚠️ [CONVERSIÓN] KeyboardInterrupt, esperando FFmpeg...")
            proc.wait()

        rc = proc.returncode
        proc = None

        print(f"{'='*60}")
        print(f"🔄 [CONVERSIÓN] FFmpeg terminó: {identificador_unico}")
        print(f"   Return code: {rc}")
        print(f"   Archivo mp4 existe: {os.path.exists(ruta_mp4)}")
        if os.path.exists(ruta_mp4):
            print(f"   Tamaño mp4: {os.path.getsize(ruta_mp4)} bytes")
        if lineas_error:
            print(f"   Últimas líneas de stderr ({len(lineas_error)}):")
            for linea in lineas_error[-15:]:
                print(f"      {linea}")

        if rc == 0 and os.path.exists(ruta_mp4) and os.path.getsize(ruta_mp4) > 0:
            exito = True
            with lock_conversiones:
                progreso_conversiones[identificador_unico] = 100
            print(f"✅ [CONVERSIÓN] ÉXITO: {identificador_unico}")
        else:
            print(f"❌ [CONVERSIÓN] FALLO: {identificador_unico} (returncode={rc})")
            if os.path.exists(ruta_mp4):
                os.remove(ruta_mp4)

    except Exception as e:
        print(f"❌ [CONVERSIÓN] EXCEPCIÓN: {identificador_unico}: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        if proc and proc.poll() is None:
            proc.kill()
            proc.wait()
        if os.path.exists(ruta_mp4):
            os.remove(ruta_mp4)
    finally:
        with lock_conversiones:
            resultados_conversiones[identificador_unico] = exito
            conversiones_activas.discard(identificador_unico)
            progreso_conversiones.pop(identificador_unico, None)
        print(f"🔄 [CONVERSIÓN] Resultado: {identificador_unico} -> {'éxito' if exito else 'fallo'}")
        print(f"{'='*60}\n")

# =============================================================================
# GENERACIÓN DE MINIATURAS
# =============================================================================
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

# =============================================================================
# RUTAS DE GESTIÓN DE USUARIOS
# =============================================================================
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
        session['usuario_idioma'] = user['idioma'] if user['idioma'] else 'es'
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

# =============================================================================
# AUTENTICACIÓN
# =============================================================================
@app.route('/login', methods=['GET', 'POST'])
def login():
    if not auth_habilitada():
        return redirect('/')
    if esta_autenticado():
        return redirect('/')
    error = False
    if request.method == 'POST':
        cfg = leer_config()
        password = request.form.get('password', '')
        if password == cfg.get('auth_password', ''):
            session['auth_autenticado'] = True
            next_url = request.args.get('next', '/')
            return redirect(next_url)
        error = True
    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    session.pop('auth_autenticado', None)
    return redirect('/login')

# =============================================================================
# RUTAS DE CATÁLOGO / ÍNDICE
# =============================================================================
@app.route('/')
def index():
    todas_las_series = []
    if os.path.exists(DIRECTORIO_MEDIA):
        for item in sorted(os.listdir(DIRECTORIO_MEDIA)):
            ruta_item = os.path.join(DIRECTORIO_MEDIA, item)
            if os.path.isdir(ruta_item):
                tiene_portada = os.path.exists(os.path.join(ruta_item, '_img.png'))
                tipo = detectar_tipo_contenido(item)
                todas_las_series.append({
                    'nombre_carpeta': item,
                    'tiene_portada': tiene_portada,
                    'tipo': tipo
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
            if not os.path.isdir(ruta_serie):
                continue
            tiene_portada = os.path.exists(os.path.join(ruta_serie, '_img.png'))
            tipo = detectar_tipo_contenido(nombre_serie)
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
                    'tiene_portada': tiene_portada,
                    'tipo': tipo
                })

        continuar_viendo.sort(key=lambda x: x['segundos'], reverse=True)
        continuar_viendo = continuar_viendo[:12]

    return render_template('index.html',
        series=lista_series,
        active_section='catalogo',
        continuar_viendo=continuar_viendo,
        pagina_actual=pagina_actual,
        total_paginas=total_paginas,
        total_series=total_series
    )

@app.route('/serie/<nombre_serie>')
def vista_serie(nombre_serie):
    ruta_serie = os.path.join(DIRECTORIO_MEDIA, nombre_serie)
    if not os.path.exists(ruta_serie) or not os.path.isdir(ruta_serie):
        return abort(404)

    ruta_videos = obtener_ruta_serie(nombre_serie)

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

    items = sorted(os.listdir(ruta_videos))
    subcarpetas = [i for i in items if os.path.isdir(os.path.join(ruta_videos, i)) and not i.startswith('.')]

    with lock_conversiones:
        conversiones_en_curso = set(conversiones_activas)

    if subcarpetas:
        for subcarpeta in subcarpetas:
            ruta_subcarpeta = os.path.join(ruta_videos, subcarpeta)
            videos_temporada = []
            
            for archivo in sorted(os.listdir(ruta_subcarpeta)):
                extension = os.path.splitext(archivo)[1].lower()
                ruta_relativa = f"{subcarpeta}/{archivo}"
                identificador_unico = f"{nombre_serie}/{ruta_relativa}"
                nombre_base = os.path.splitext(archivo)[0]

                if extension in formatos_web:
                    oculto = any(
                        f"{nombre_serie}/{subcarpeta}/{nombre_base}{ext}" in conversiones_en_curso
                        for ext in formatos_incompatibles
                    )
                    if oculto:
                        continue

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
                    en_progreso = identificador_unico in conversiones_en_curso
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
            if os.path.isfile(os.path.join(ruta_videos, archivo)):
                extension = os.path.splitext(archivo)[1].lower()
                nombre_base = os.path.splitext(archivo)[0]

                if extension in formatos_web:
                    oculto = any(
                        f"{nombre_serie}/{nombre_base}{ext}" in conversiones_en_curso
                        for ext in formatos_incompatibles
                    )
                    if oculto:
                        continue

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
                    en_progreso = f"{nombre_serie}/{archivo}" in conversiones_en_curso
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
    lista_estado = -1
    if usuario_id:
        conn = conectar_db()
        cursor = conn.cursor()
        cursor.execute('SELECT 1 FROM favoritos WHERE usuario_id = ? AND serie = ?', (usuario_id, nombre_serie))
        es_favorito = cursor.fetchone() is not None
        cursor.execute('SELECT estado FROM listas WHERE usuario_id = ? AND serie = ?', (usuario_id, nombre_serie))
        fila_lista = cursor.fetchone()
        if fila_lista:
            lista_estado = fila_lista['estado']
        conn.close()

    tipo_contenido = detectar_tipo_contenido(nombre_serie)
    tiene_portada = os.path.exists(os.path.join(ruta_serie, '_img.png'))

    meta = {}
    meta_path = os.path.join(ruta_serie, '_meta.json')
    if os.path.exists(meta_path):
        try:
            import json
            with open(meta_path, 'r', encoding='utf-8') as f:
                meta = json.load(f)
        except Exception:
            pass

    total_videos = sum(len(v) for v in estructura_temporadas.values())
    idioma = session.get('usuario_idioma', 'es')
    meta_traducido = translate_metadata(meta, idioma)
            
    return render_template('serie.html', serie=nombre_serie, temporadas=estructura_temporadas, mostrar_progreso=mostrar_progreso, es_favorito=es_favorito, lista_estado=lista_estado, tipo=tipo_contenido, tiene_portada=tiene_portada, meta=meta_traducido, total_videos=total_videos)

@app.route('/tv/reproducir/<nombre_serie>/<path:filename>')
def reproductor_tv(nombre_serie, filename):
    ruta_videos = obtener_ruta_serie(nombre_serie)
    sub_dir = os.path.dirname(filename)
    ruta_dir_absoluta = os.path.join(ruta_videos, sub_dir)
    
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

# =============================================================================
# EMISIÓN EN DIRECTO
# =============================================================================
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

# =============================================================================
# LISTAS
# =============================================================================
@app.route('/listas')
def listas():
    usuario_id = session.get('usuario_id')
    if not usuario_id:
        return redirect('/')
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute('SELECT serie, estado FROM listas WHERE usuario_id = ? ORDER BY fecha DESC', (usuario_id,))
    filas = cursor.fetchall()

    series_map = {}
    if os.path.exists(DIRECTORIO_MEDIA):
        for item in os.listdir(DIRECTORIO_MEDIA):
            ruta_item = os.path.join(DIRECTORIO_MEDIA, item)
            if os.path.isdir(ruta_item):
                tiene_portada = os.path.exists(os.path.join(ruta_item, '_img.png'))
                tipo = detectar_tipo_contenido(item)
                series_map[item] = {'nombre_carpeta': item, 'tiene_portada': tiene_portada, 'tipo': tipo}

    pendientes = []
    viendo = []
    vistos = []
    favoritos_detalle = []
    for fila in filas:
        nombre = fila['serie']
        estado = fila['estado']
        serie_info = series_map.get(nombre)
        if serie_info is None:
            continue
        if estado == 0:
            pendientes.append(serie_info)
        elif estado == 1:
            viendo.append(serie_info)
        elif estado == 2:
            vistos.append(serie_info)

    cursor.execute('SELECT serie FROM favoritos WHERE usuario_id = ? ORDER BY fecha DESC', (usuario_id,))
    for fila in cursor.fetchall():
        fav_nombre = fila['serie']
        serie_info = series_map.get(fav_nombre)
        if serie_info is None:
            continue
        favoritos_detalle.append(serie_info)
    conn.close()

    return render_template('listas.html', pendientes=pendientes, viendo=viendo, vistos=vistos, favoritos=favoritos_detalle, active_section='listas')

# =============================================================================
# AJUSTES
# =============================================================================
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
            idioma = request.form.get('idioma', 'es')
            if idioma not in ('es', 'en'):
                idioma = 'es'
            cursor.execute('UPDATE usuarios SET auto_marcar = ?, mostrar_progreso = ?, tema = ?, idioma = ? WHERE id = ?', (auto_marcar, mostrar_progreso, tema, idioma, usuario_id))
            conn.commit()
            session['usuario_auto_marcar'] = auto_marcar
            session['usuario_mostrar_progreso'] = mostrar_progreso
            session['usuario_tema'] = tema
            session['usuario_idioma'] = idioma

        return redirect(return_to)
    
    return_to = request.args.get('return_to', '/')
    auto_marcar = 1
    mostrar_progreso = 1
    tema = 'oscuro'
    idioma = 'es'
    if usuario_id:
        conn = conectar_db()
        cursor = conn.cursor()
        cursor.execute('SELECT auto_marcar, mostrar_progreso, tema, idioma FROM usuarios WHERE id = ?', (usuario_id,))
        user = cursor.fetchone()
        conn.close()
        if user:
            auto_marcar = user['auto_marcar']
            mostrar_progreso = user['mostrar_progreso']
            tema = user['tema'] if user['tema'] else 'oscuro'
            idioma = user['idioma'] if user['idioma'] else 'es'
    
    cfg = leer_config()
    return render_template('ajustes.html', auto_marcar=auto_marcar, mostrar_progreso=mostrar_progreso, tema=tema, idioma=idioma,
        boton_apagar_visible=cfg.get('boton_apagar_visible', False),
        boton_apagar_todo_visible=cfg.get('boton_apagar_todo_visible', False),
        es_local=es_cliente_local(), return_to=return_to, usuario_id=usuario_id)

# =============================================================================
# API - GESTIÓN DE VÍDEOS
# =============================================================================
@app.route('/api/videos/add', methods=['POST'])
@limiter.limit("10 per minute")
def api_agregar_video():
    serie = request.form.get('serie', '').strip()
    if not serie:
        return jsonify({'error': 'El campo "serie" es requerido.'}), 400
    
    temporada = request.form.get('temporada', '').strip()
    archivo = request.files.get('archivo')
    if not archivo or archivo.filename == '':
        return jsonify({'error': 'Debes enviar un archivo en el campo "archivo".'}), 400
    
    filename = os.path.basename(archivo.filename)
    serie_dir_meta = os.path.join(DIRECTORIO_MEDIA, serie)
    
    if not os.path.exists(serie_dir_meta):
        return jsonify({'error': f'La serie "{serie}" no existe.'}), 404
    
    ruta_videos = obtener_ruta_serie(serie)
    items = os.listdir(ruta_videos)
    subcarpetas = [i for i in items if os.path.isdir(os.path.join(ruta_videos, i)) and not i.startswith('.')]
    
    if subcarpetas:
        if not temporada:
            return jsonify({'error': 'Esta serie tiene temporadas. El campo "temporada" es obligatorio.'}), 400
        if temporada not in subcarpetas:
            return jsonify({'error': f'La temporada "{temporada}" no existe en esta serie.'}), 404
        destino_dir = os.path.join(ruta_videos, temporada)
    else:
        if temporada:
            return jsonify({'error': 'Esta serie no tiene temporadas. No uses el campo "temporada".'}), 400
        destino_dir = ruta_videos
    
    ruta_destino = os.path.join(destino_dir, filename)
    archivo.save(ruta_destino)
    
    ruta_rel = f"{temporada}/{filename}" if temporada else filename
    return jsonify({'status': 'ok', 'mensaje': f'Video guardado en {serie}/{ruta_rel}'})

@app.route('/api/videos/rm', methods=['POST'])
@limiter.limit("10 per minute")
def api_eliminar_video():
    datos = request.json or {}
    serie = datos.get('serie', '').strip()
    filename = datos.get('filename', '').strip()
    
    if not serie or not filename:
        return jsonify({'error': 'Los campos "serie" y "filename" son requeridos.'}), 400
    
    filename = filename.replace('\\', '/')
    ruta_videos = obtener_ruta_serie(serie)
    ruta_archivo = os.path.normpath(os.path.join(ruta_videos, filename))
    ruta_media = os.path.normpath(os.path.join(DIRECTORIO_MEDIA, serie))
    if not ruta_archivo.startswith(os.path.normpath(ruta_videos)):
        return jsonify({'error': 'Ruta no válida'}), 400
    
    if not os.path.exists(ruta_archivo):
        return jsonify({'error': 'Archivo no encontrado'}), 404
    
    try:
        os.remove(ruta_archivo)
        nombre_base, _ = os.path.splitext(filename)
        ruta_thumb = os.path.join(ruta_media, '.thumbnails', f"{nombre_base}.jpg")
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
    ruta_videos = obtener_ruta_serie(nombre_serie)
    if not os.path.exists(ruta_videos) or not os.path.isdir(ruta_videos):
        return None
    formatos_video = ('.mp4', '.webm', '.ogg', '.avi', '.mkv')
    items = sorted(os.listdir(ruta_videos))
    subcarpetas = [i for i in items if os.path.isdir(os.path.join(ruta_videos, i)) and not i.startswith('.')]
    estructura = {'nombre': nombre_serie, 'temporadas': {}}
    if subcarpetas:
        for sub in subcarpetas:
            ruta_sub = os.path.join(ruta_videos, sub)
            videos = sorted([f for f in os.listdir(ruta_sub) if os.path.isfile(os.path.join(ruta_sub, f)) and f.lower().endswith(formatos_video)])
            estructura['temporadas'][sub] = {'nombre': sub, 'capitulos': videos}
    else:
        videos = sorted([f for f in items if os.path.isfile(os.path.join(ruta_videos, f)) and f.lower().endswith(formatos_video)])
        estructura['temporadas']['Contenido Disponible'] = {'nombre': 'Contenido Disponible', 'capitulos': videos}
    return estructura

@app.route('/api/videos', methods=['GET'])
@app.route('/api/videos/<path:nombre_serie>', methods=['GET'])
def api_listar_videos(nombre_serie=None):
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

@app.route('/thumbnail/<nombre_serie>/<path:filename>')
def serve_thumbnail(nombre_serie, filename):
    ruta_videos = obtener_ruta_serie(nombre_serie)
    ruta_video = os.path.join(ruta_videos, filename)
    nombre_base, _ = os.path.splitext(filename)
    ruta_serie = os.path.join(DIRECTORIO_MEDIA, nombre_serie)
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
    ruta_videos = obtener_ruta_serie(nombre_serie)
    return send_from_directory(ruta_videos, filename)

@app.route('/api/video/<nombre_serie>/<path:filename>')
def api_obtener_video(nombre_serie, filename):
    ruta_videos = obtener_ruta_serie(nombre_serie)
    ruta_archivo = os.path.join(ruta_videos, filename)
    if not os.path.exists(ruta_archivo):
        return jsonify({'error': 'Archivo no encontrado'}), 404
    return send_from_directory(ruta_videos, filename)

# =============================================================================
# API - CONVERSIÓN
# =============================================================================
@app.route('/api/convertir/<nombre_serie>/<path:filename>', methods=['POST'])
@limiter.limit("5 per minute")
def desencadenar_conversion(nombre_serie, filename):
    global conversiones_activas, resultados_conversiones
    ruta_videos = obtener_ruta_serie(nombre_serie)
    ruta_origen = os.path.join(ruta_videos, filename)
    
    print(f"\n🔌 [API] Solicitud de conversión: {nombre_serie}/{filename}")
    print(f"   Ruta resuelta: {ruta_origen}")
    print(f"   Existe: {os.path.exists(ruta_origen)}")
    
    if not os.path.exists(ruta_origen):
        print(f"❌ [API] Archivo no encontrado: {ruta_origen}")
        return jsonify({'error': 'El archivo original no existe'}), 404
        
    nombre_base = os.path.splitext(filename)[0]
    ruta_mp4 = os.path.join(ruta_videos, f"{nombre_base}.mp4")
    identificador_unico = f"{nombre_serie}/{filename}"
    
    with lock_conversiones:
        if identificador_unico in conversiones_activas:
            print(f"⚠️ [API] Ya en progreso: {identificador_unico}")
            return jsonify({'status': 'ya_en_progreso'})
        if os.path.exists(ruta_mp4):
            print(f"⚠️ [API] MP4 ya existe: {ruta_mp4}")
            return jsonify({'status': 'ya_existe_mp4'})
            
        resultados_conversiones.pop(identificador_unico, None)
        conversiones_activas.add(identificador_unico)
        
    print(f"✅ [API] Lanzando hilo de conversión: {identificador_unico}")
    hilo = threading.Thread(target=hilo_conversion, args=(identificador_unico, ruta_origen, ruta_mp4))
    hilo.start()
    return jsonify({'status': 'procesando'})

@app.route('/api/eliminar/<nombre_serie>/<path:filename>', methods=['POST'])
@limiter.limit("10 per minute")
def eliminar_archivo(nombre_serie, filename):
    ruta_videos = obtener_ruta_serie(nombre_serie)
    ruta_archivo = os.path.join(ruta_videos, filename)
    if os.path.exists(ruta_archivo):
        try:
            os.remove(ruta_archivo)
            nombre_base, _ = os.path.splitext(filename)
            ruta_serie = os.path.join(DIRECTORIO_MEDIA, nombre_serie)
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
        return jsonify({
            'activos': list(conversiones_activas),
            'progreso': dict(progreso_conversiones)
        })

@app.route('/api/conversion_result/<nombre_serie>/<path:filename>')
def consultar_resultado_conversion(nombre_serie, filename):
    identificador_unico = f"{nombre_serie}/{filename}"
    with lock_conversiones:
        if identificador_unico in conversiones_activas:
            print(f"🔍 [RESULTADO] {identificador_unico} -> todavía procesando")
            return jsonify({'status': 'procesando'})
        resultado = resultados_conversiones.pop(identificador_unico, None)
    if resultado is None:
        print(f"🔍 [RESULTADO] {identificador_unico} -> desconocido (sin resultado registrado)")
        return jsonify({'status': 'desconocido'})
    nombre_base = os.path.splitext(filename)[0]
    ruta_videos = obtener_ruta_serie(nombre_serie)
    ruta_mp4 = os.path.join(ruta_videos, f"{nombre_base}.mp4")
    mp4_existe = resultado and os.path.exists(ruta_mp4)
    print(f"🔍 [RESULTADO] {identificador_unico} -> backend={resultado}, mp4_existe={mp4_existe}, final={'ok' if mp4_existe else 'error'}")
    return jsonify({'status': 'ok' if mp4_existe else 'error', 'mp4_exists': mp4_existe})

# =============================================================================
# API - PROGRESO
# =============================================================================
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

# =============================================================================
# API - FAVORITOS
# =============================================================================
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

# =============================================================================
# API - LISTAS
# =============================================================================
@app.route('/api/lista/estado')
def api_lista_estado():
    usuario_id = session.get('usuario_id')
    serie = request.args.get('serie', '').strip()
    if not usuario_id or not serie:
        return jsonify({'estado': -1})
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute('SELECT estado FROM listas WHERE usuario_id = ? AND serie = ?', (usuario_id, serie))
    fila = cursor.fetchone()
    conn.close()
    return jsonify({'estado': fila['estado'] if fila else -1})

@app.route('/api/lista/guardar', methods=['POST'])
@limiter.limit("30 per minute")
def api_lista_guardar():
    usuario_id = session.get('usuario_id')
    if not usuario_id:
        return jsonify({'error': 'Inicia sesion para usar listas'}), 401
    datos = request.json or {}
    serie = datos.get('serie', '').strip()
    estado = datos.get('estado')
    if not serie or estado is None:
        return jsonify({'error': 'Campos "serie" y "estado" requeridos'}), 400
    if estado not in (-1, 0, 1, 2):
        return jsonify({'error': 'Estado invalido'}), 400
    conn = conectar_db()
    cursor = conn.cursor()
    if estado == -1:
        cursor.execute('DELETE FROM listas WHERE usuario_id = ? AND serie = ?', (usuario_id, serie))
    else:
        cursor.execute('INSERT INTO listas (usuario_id, serie, estado) VALUES (?, ?, ?) ON CONFLICT(usuario_id, serie) DO UPDATE SET estado = excluded.estado, fecha = CURRENT_TIMESTAMP', (usuario_id, serie, estado))
    conn.commit()
    conn.close()
    return jsonify({'estado': estado})

@app.route('/api/lista/obtener')
def api_lista_obtener():
    usuario_id = session.get('usuario_id')
    if not usuario_id:
        return jsonify({'listas': []})
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute('SELECT serie, estado FROM listas WHERE usuario_id = ? ORDER BY fecha DESC', (usuario_id,))
    filas = cursor.fetchall()
    conn.close()
    return jsonify({'listas': [{'serie': f['serie'], 'estado': f['estado']} for f in filas]})

# =============================================================================
# API - GESTIÓN DE CONTENIDO
# =============================================================================
@app.route('/api/contenido/crear', methods=['POST'])
@limiter.limit("5 per minute")
def api_crear_contenido():
    datos = request.json or {}
    nombre = datos.get('nombre', '').strip()
    titulo = datos.get('titulo', '').strip()

    if not nombre or not titulo:
        return jsonify({'error': 'Los campos "nombre" y "titulo" son requeridos.'}), 400

    tipo = datos.get('tipo', 'serie').strip().lower()
    if tipo not in ('serie', 'pelicula'):
        return jsonify({'error': 'El campo "tipo" debe ser "serie" o "pelicula".'}), 400

    ruta_contenido = os.path.join(DIRECTORIO_MEDIA, nombre)
    if os.path.exists(ruta_contenido):
        return jsonify({'error': f'Ya existe contenido con el nombre "{nombre}".'}), 409

    try:
        os.makedirs(ruta_contenido, exist_ok=True)

        meta = {
            'titulo': titulo,
            'tipo': tipo,
        }
        for campo in ('descripcion', 'anio', 'genero'):
            valor = datos.get(campo, '').strip()
            if valor:
                meta[campo] = valor

        meta_path = os.path.join(ruta_contenido, '_meta.json')
        with open(meta_path, 'w', encoding='utf-8') as f:
            json.dump(meta, f, ensure_ascii=False, indent=4)

        conn = conectar_db()
        cursor = conn.cursor()
        cursor.execute('INSERT OR REPLACE INTO content_metadata (serie, tipo) VALUES (?, ?)',
                       (nombre, tipo))
        conn.commit()
        conn.close()

        return jsonify({'status': 'ok', 'mensaje': f'{"Serie" if tipo == "serie" else "Película"} "{titulo}" creada.'}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/contenido/temporada', methods=['POST'])
@limiter.limit("10 per minute")
def api_crear_temporada():
    datos = request.json or {}
    serie = datos.get('serie', '').strip()
    temporada = datos.get('temporada', '').strip()

    if not serie or not temporada:
        return jsonify({'error': 'Los campos "serie" y "temporada" son requeridos.'}), 400

    ruta_serie = os.path.join(DIRECTORIO_MEDIA, serie)
    if not os.path.exists(ruta_serie) or not os.path.isdir(ruta_serie):
        return jsonify({'error': f'La serie "{serie}" no existe.'}), 404

    ruta_temporada = os.path.join(ruta_serie, temporada)
    if os.path.exists(ruta_temporada):
        return jsonify({'error': f'La temporada "{temporada}" ya existe en "{serie}".'}), 409

    try:
        os.makedirs(ruta_temporada, exist_ok=True)
        return jsonify({'status': 'ok', 'mensaje': f'Temporada "{temporada}" creada en "{serie}".'}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# =============================================================================
# BIBLIOTECA WEB (gestión de contenido desde el navegador)
# =============================================================================
FORMATO_VIDEO_BIB = ('.mp4', '.webm', '.ogg', '.avi', '.mkv')
OMDB_API_URL = 'https://www.omdbapi.com/'
ENV_PATH = os.path.join(DIRECTORIO_RAIZ, '.env')

def leer_env():
    data = {}
    if os.path.exists(ENV_PATH):
        with open(ENV_PATH, 'r', encoding='utf-8') as f:
            for linea in f:
                linea = linea.strip()
                if linea and not linea.startswith('#') and '=' in linea:
                    k, v = linea.split('=', 1)
                    data[k.strip()] = v.strip()
    return data

def guardar_env(data):
    data = dict(data)
    lineas = []
    if os.path.exists(ENV_PATH):
        with open(ENV_PATH, 'r', encoding='utf-8') as f:
            for linea in f:
                line_rstrip = linea.rstrip('\n\r')
                if line_rstrip.strip() and not line_rstrip.startswith('#') and '=' in line_rstrip:
                    key = line_rstrip.split('=', 1)[0].strip()
                    if key in data:
                        lineas.append(f'{key}={data[key]}')
                        del data[key]
                    else:
                        lineas.append(line_rstrip)
                else:
                    lineas.append(line_rstrip)
    for k, v in data.items():
        lineas.append(f'{k}={v}')
    with open(ENV_PATH, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lineas) + '\n')

def omdb_validar_api_key(api_key):
    params = urllib.parse.urlencode({'apikey': api_key, 't': 'Inception'})
    url = f'{OMDB_API_URL}?{params}'
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            return data.get('Response') == 'True'
    except Exception:
        return False

def omdb_buscar(api_key, query, tipo=None):
    params = {'apikey': api_key, 's': query}
    if tipo == 'pelicula':
        params['type'] = 'movie'
    elif tipo == 'serie':
        params['type'] = 'series'
    url = f'{OMDB_API_URL}?{urllib.parse.urlencode(params)}'
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            if data.get('Response') == 'True':
                return data.get('Search', [])
            return []
    except Exception:
        return []

def omdb_obtener_detalles(api_key, imdb_id):
    params = urllib.parse.urlencode({'apikey': api_key, 'i': imdb_id})
    url = f'{OMDB_API_URL}?{params}'
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            if data.get('Response') == 'True':
                return data
            return None
    except Exception:
        return None

def omdb_descargar_poster(poster_url, destino):
    if not poster_url or poster_url == 'N/A':
        return False
    try:
        req = urllib.request.Request(poster_url)
        with urllib.request.urlopen(req, timeout=15) as resp:
            with open(destino, 'wb') as f:
                f.write(resp.read())
        return True
    except Exception:
        return False

def omdb_aplicar_a_carpeta(api_key, carpeta_nombre, imdb_id, tipo_content, descargar_poster=True):
    detalles = omdb_obtener_detalles(api_key, imdb_id)
    if not detalles:
        return False, 'No se pudieron obtener los detalles.'

    ruta_carpeta = _ruta_media_segura(carpeta_nombre)
    if not ruta_carpeta:
        return False, 'Ruta no válida.'
    os.makedirs(ruta_carpeta, exist_ok=True)

    genero_str = detalles.get('Genre', '')
    genero = [g.strip() for g in genero_str.split(',') if g.strip()] if genero_str and genero_str != 'N/A' else []

    rating_str = detalles.get('imdbRating', '0')
    try:
        rating = round(float(rating_str), 1)
    except (ValueError, TypeError):
        rating = 0

    runtime_str = detalles.get('Runtime', '0')
    try:
        duracion = int(runtime_str.replace(' min', '').replace('N/A', '0'))
    except (ValueError, TypeError):
        duracion = 0

    meta_existente = {}
    meta_path = os.path.join(ruta_carpeta, '_meta.json')
    if os.path.exists(meta_path):
        try:
            with open(meta_path, 'r', encoding='utf-8') as f:
                meta_existente = json.load(f)
        except Exception:
            pass

    meta = {
        'tipo': tipo_content,
        'titulo': detalles.get('Title', carpeta_nombre),
        'descripcion': detalles.get('Plot', '') if detalles.get('Plot') != 'N/A' else '',
        'anio': detalles.get('Year', '') if detalles.get('Year') != 'N/A' else '',
        'genero': genero,
        'director': detalles.get('Director', '') if detalles.get('Director') != 'N/A' else '',
        'valoracion': rating,
    }

    if meta_existente.get('ubicacion'):
        meta['ubicacion'] = meta_existente['ubicacion']

    if tipo_content == 'pelicula':
        meta['duracion_min'] = duracion
    else:
        total_seasons = detalles.get('totalSeasons', '')
        if total_seasons and total_seasons != 'N/A':
            meta['temporadas'] = int(total_seasons)

    _guardar_meta(carpeta_nombre, meta)

    if descargar_poster:
        poster_url = detalles.get('Poster', '')
        if poster_url and poster_url != 'N/A':
            img_path = os.path.join(ruta_carpeta, '_img.png')
            omdb_descargar_poster(poster_url, img_path)

    return True, meta.get('titulo', carpeta_nombre)

def _ruta_media_segura(*partes):
    if not partes or any(not p for p in partes):
        return None
    ruta = os.path.normpath(os.path.join(DIRECTORIO_MEDIA, *partes))
    raiz = os.path.normpath(DIRECTORIO_MEDIA)
    if ruta != raiz and not ruta.startswith(raiz + os.sep):
        return None
    return ruta

def _tam_mb(ruta):
    try:
        return f'{os.path.getsize(ruta) / (1024*1024):.1f} MB'
    except OSError:
        return ''

def estructura_biblioteca():
    contenido = []
    if not os.path.isdir(DIRECTORIO_MEDIA):
        return contenido
    for nombre in sorted(os.listdir(DIRECTORIO_MEDIA)):
        ruta = os.path.join(DIRECTORIO_MEDIA, nombre)
        if not os.path.isdir(ruta) or nombre.startswith('.'):
            continue
        tipo = detectar_tipo_contenido(nombre)
        meta = {}
        meta_path = os.path.join(ruta, '_meta.json')
        if os.path.exists(meta_path):
            try:
                with open(meta_path, 'r', encoding='utf-8') as f:
                    meta = json.load(f)
            except Exception:
                pass
        item = {
            'nombre': nombre,
            'tipo': tipo,
            'tiene_meta': bool(meta),
            'tiene_portada': os.path.exists(os.path.join(ruta, '_img.png')),
            'meta': meta,
            'temporadas': [],
        }
        ubicacion = meta.get('ubicacion', '').strip()
        ruta_videos = ubicacion if ubicacion and os.path.isdir(ubicacion) else ruta
        subcarpetas = [i for i in sorted(os.listdir(ruta_videos))
                       if os.path.isdir(os.path.join(ruta_videos, i)) and not i.startswith('.')]
        if subcarpetas:
            for sub in subcarpetas:
                ruta_sub = os.path.join(ruta_videos, sub)
                videos = [{'nombre': v, 'tam_mb': _tam_mb(os.path.join(ruta_sub, v))}
                          for v in sorted(os.listdir(ruta_sub))
                          if os.path.isfile(os.path.join(ruta_sub, v)) and v.lower().endswith(FORMATO_VIDEO_BIB)]
                item['temporadas'].append({'nombre': sub, 'videos': videos})
        else:
            item['videos'] = [{'nombre': v, 'tam_mb': _tam_mb(os.path.join(ruta_videos, v))}
                              for v in sorted(os.listdir(ruta_videos))
                              if os.path.isfile(os.path.join(ruta_videos, v)) and v.lower().endswith(FORMATO_VIDEO_BIB)]
        contenido.append(item)
    return contenido

def _construir_meta(datos):
    tipo = datos.get('tipo', 'pelicula')
    if tipo not in ('pelicula', 'serie'):
        tipo = 'serie'
    genero_raw = (datos.get('genero', '') or '').strip()
    genero = [g.strip() for g in genero_raw.split(',') if g.strip()]
    meta = {
        'tipo': tipo,
        'titulo': (datos.get('titulo', '') or '').strip(),
        'descripcion': (datos.get('descripcion', '') or '').strip(),
        'anio': (datos.get('anio', '') or '').strip(),
        'genero': genero,
        'director': (datos.get('director', '') or '').strip(),
    }
    try:
        meta['valoracion'] = round(float(datos.get('valoracion', 0) or 0), 1)
    except (TypeError, ValueError):
        meta['valoracion'] = 0
    if tipo == 'pelicula':
        try:
            meta['duracion_min'] = int(round(float(datos.get('duracion_min', 0) or 0)))
        except (TypeError, ValueError):
            meta['duracion_min'] = 0
    else:
        try:
            meta['temporadas'] = int(datos.get('temporadas', 1) or 1)
        except (TypeError, ValueError):
            meta['temporadas'] = 1
    ubicacion = (datos.get('ubicacion', '') or '').strip()
    if ubicacion:
        meta['ubicacion'] = ubicacion
    return meta

def _guardar_meta(nombre, meta):
    meta_path = _ruta_media_segura(nombre, '_meta.json')
    if not meta_path:
        return False
    with open(meta_path, 'w', encoding='utf-8') as f:
        json.dump(meta, f, ensure_ascii=False, indent=4)
    try:
        conn = conectar_db()
        cursor = conn.cursor()
        cursor.execute('INSERT OR REPLACE INTO content_metadata (serie, tipo) VALUES (?, ?)',
                       (nombre, meta.get('tipo', 'serie')))
        conn.commit()
        conn.close()
    except Exception:
        pass
    return True

@app.route('/biblioteca')
def biblioteca():
    contenido = estructura_biblioteca()
    meta_data = {item['nombre']: item['meta'] for item in contenido}
    return render_template('biblioteca.html', contenido=contenido, meta_data=meta_data,
                           active_section='biblioteca')

@app.route('/biblioteca/crear', methods=['POST'])
@limiter.limit("5 per minute")
def biblioteca_crear():
    datos = request.json or {}
    nombre = (datos.get('titulo', '') or '').strip()
    if not nombre:
        return jsonify({'error': 'El título es obligatorio.'}), 400
    ruta = _ruta_media_segura(nombre)
    if not ruta:
        return jsonify({'error': 'Nombre no válido.'}), 400
    if os.path.exists(ruta):
        return jsonify({'error': f'Ya existe contenido llamado "{nombre}".'}), 409
    meta = _construir_meta(datos)
    try:
        os.makedirs(ruta, exist_ok=True)
        _guardar_meta(nombre, meta)
        tiene_ubicacion = bool(meta.get('ubicacion', '').strip())
        if meta['tipo'] == 'serie' and not tiene_ubicacion:
            num_temp = meta.get('temporadas', 1) or 1
            for i in range(1, num_temp + 1):
                os.makedirs(os.path.join(ruta, f'Season {i}'), exist_ok=True)
        return jsonify({'status': 'ok'}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/biblioteca/temporada', methods=['POST'])
@limiter.limit("5 per minute")
def biblioteca_crear_temporada():
    datos = request.json or {}
    serie = (datos.get('serie', '') or '').strip()
    temporada = (datos.get('temporada', '') or '').strip()
    if not serie or not temporada:
        return jsonify({'error': 'Serie y temporada son obligatorias.'}), 400
    ruta_serie = _ruta_media_segura(serie)
    ruta_temporada = _ruta_media_segura(serie, temporada)
    if not ruta_serie or not ruta_temporada:
        return jsonify({'error': 'Ruta no válida.'}), 400
    if not os.path.isdir(ruta_serie):
        return jsonify({'error': f'La serie "{serie}" no existe.'}), 404
    if os.path.exists(ruta_temporada):
        return jsonify({'error': f'La temporada "{temporada}" ya existe.'}), 409
    try:
        os.makedirs(ruta_temporada, exist_ok=True)
        return jsonify({'status': 'ok'}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/biblioteca/videos/add', methods=['POST'])
@limiter.limit("10 per minute")
def biblioteca_agregar_videos():
    serie = (request.form.get('serie', '') or '').strip()
    temporada = (request.form.get('temporada', '') or '').strip()
    if not serie:
        return jsonify({'error': 'Falta la serie.'}), 400
    ruta_serie = _ruta_media_segura(serie)
    if not ruta_serie or not os.path.isdir(ruta_serie):
        return jsonify({'error': f'La serie "{serie}" no existe.'}), 404
    ruta_videos = obtener_ruta_serie(serie)
    subcarpetas = [i for i in os.listdir(ruta_videos)
                   if os.path.isdir(os.path.join(ruta_videos, i)) and not i.startswith('.')]
    if subcarpetas:
        if not temporada:
            return jsonify({'error': 'Esta serie tiene temporadas. Selecciona una.'}), 400
        if temporada not in subcarpetas:
            return jsonify({'error': f'La temporada "{temporada}" no existe.'}), 404
        destino_dir = os.path.join(ruta_videos, temporada)
    else:
        if temporada:
            return jsonify({'error': 'Esta serie no tiene temporadas.'}), 400
        destino_dir = ruta_videos
    archivos = request.files.getlist('archivos')
    if not archivos:
        return jsonify({'error': 'No se envió ningún archivo.'}), 400
    copiados = 0
    errores = []
    for archivo in archivos:
        if not archivo or not archivo.filename:
            continue
        nombre = os.path.basename(archivo.filename)
        destino = os.path.join(destino_dir, nombre)
        try:
            archivo.save(destino)
            copiados += 1
        except Exception as e:
            errores.append(f'{nombre}: {e}')
    return jsonify({'status': 'ok', 'copiados': copiados, 'errores': errores[:5]})

@app.route('/biblioteca/meta', methods=['POST'])
@limiter.limit("10 per minute")
def biblioteca_guardar_meta():
    datos = request.json or {}
    nombre = (datos.get('nombre', '') or '').strip()
    if not nombre:
        return jsonify({'error': 'Falta el nombre.'}), 400
    ruta = _ruta_media_segura(nombre)
    if not ruta or not os.path.isdir(ruta):
        return jsonify({'error': f'"{nombre}" no existe.'}), 404
    meta_existente = {}
    meta_path = os.path.join(ruta, '_meta.json')
    if os.path.exists(meta_path):
        try:
            with open(meta_path, 'r', encoding='utf-8') as f:
                meta_existente = json.load(f)
        except Exception:
            pass
    nuevo_meta = _construir_meta(datos)
    if not nuevo_meta.get('titulo'):
        nuevo_meta['titulo'] = meta_existente.get('titulo', nombre)
    if not (datos.get('ubicacion') or '').strip() and meta_existente.get('ubicacion'):
        nuevo_meta['ubicacion'] = meta_existente['ubicacion']
    try:
        _guardar_meta(nombre, nuevo_meta)
        return jsonify({'status': 'ok'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/biblioteca/renombrar', methods=['POST'])
@limiter.limit("10 per minute")
def biblioteca_renombrar():
    datos = request.json or {}
    nivel = datos.get('nivel', '')
    nombre = (datos.get('nombre', '') or '').strip()
    nuevo = (datos.get('nuevo', '') or '').strip()
    serie = (datos.get('serie', '') or '').strip()
    temporada = (datos.get('temporada', '') or '').strip()
    if not nombre or not nuevo or nuevo == nombre:
        return jsonify({'error': 'Nombres no válidos.'}), 400
    try:
        if nivel == 'raiz':
            ruta = _ruta_media_segura(nombre)
            nueva = _ruta_media_segura(nuevo)
            if not ruta or not nueva:
                return jsonify({'error': 'Ruta no válida.'}), 400
            if not os.path.isdir(ruta):
                return jsonify({'error': 'Contenido no encontrado.'}), 404
            if os.path.exists(nueva):
                return jsonify({'error': f'Ya existe "{nuevo}".'}), 409
            os.rename(ruta, nueva)
            try:
                conn = conectar_db()
                cursor = conn.cursor()
                cursor.execute('UPDATE content_metadata SET serie = ? WHERE serie = ?', (nuevo, nombre))
                cursor.execute('UPDATE favoritos SET serie = ? WHERE serie = ?', (nuevo, nombre))
                cursor.execute('UPDATE progreso SET serie = ? WHERE serie = ?', (nuevo, nombre))
                cursor.execute('UPDATE listas SET serie = ? WHERE serie = ?', (nuevo, nombre))
                conn.commit()
                conn.close()
            except Exception:
                pass
        elif nivel == 'temporada':
            if not serie:
                return jsonify({'error': 'Falta la serie.'}), 400
            ruta = _ruta_media_segura(serie, nombre)
            nueva = _ruta_media_segura(serie, nuevo)
            if not ruta or not nueva:
                return jsonify({'error': 'Ruta no válida.'}), 400
            if not os.path.isdir(ruta):
                return jsonify({'error': 'Temporada no encontrada.'}), 404
            if os.path.exists(nueva):
                return jsonify({'error': f'Ya existe "{nuevo}".'}), 409
            os.rename(ruta, nueva)
            try:
                conn = conectar_db()
                cursor = conn.cursor()
                cursor.execute('UPDATE progreso SET filename = ? WHERE serie = ? AND filename = ?',
                               (f'{nuevo}/{nombre}', serie, f'{temporada}/{nombre}'))
                conn.commit()
                conn.close()
            except Exception:
                pass
        elif nivel == 'video':
            if not serie:
                return jsonify({'error': 'Falta la serie.'}), 400
            ruta_videos = obtener_ruta_serie(serie)
            base_dir = os.path.join(ruta_videos, temporada) if temporada else ruta_videos
            ext = os.path.splitext(nombre)[1]
            ruta = os.path.normpath(os.path.join(base_dir, nombre))
            nueva = os.path.normpath(os.path.join(base_dir, nuevo + ext))
            raiz = os.path.normpath(ruta_videos)
            if not ruta.startswith(raiz + os.sep) or not nueva.startswith(raiz + os.sep):
                return jsonify({'error': 'Ruta no válida.'}), 400
            if not os.path.isfile(ruta):
                return jsonify({'error': 'Vídeo no encontrado.'}), 404
            if os.path.exists(nueva):
                return jsonify({'error': f'Ya existe "{os.path.basename(nueva)}".'}), 409
            os.rename(ruta, nueva)
            nombre_rel = f"{temporada}/{nombre}" if temporada else nombre
            nuevo_arch_rel = f"{temporada}/{os.path.basename(nueva)}" if temporada else os.path.basename(nueva)
            try:
                conn = conectar_db()
                cursor = conn.cursor()
                cursor.execute('UPDATE progreso SET filename = ? WHERE serie = ? AND filename = ?',
                               (nuevo_arch_rel, serie, nombre_rel))
                conn.commit()
                conn.close()
            except Exception:
                pass
            base_viejo = os.path.splitext(nombre)[0]
            base_nuevo = os.path.splitext(os.path.basename(nueva))[0]
            if base_viejo != base_nuevo:
                thumb_viejo = _ruta_media_segura(serie, '.thumbnails', f'{base_viejo}.jpg')
                thumb_nuevo = _ruta_media_segura(serie, '.thumbnails', f'{base_nuevo}.jpg')
                if thumb_viejo and thumb_nuevo and os.path.exists(thumb_viejo):
                    os.rename(thumb_viejo, thumb_nuevo)
        else:
            return jsonify({'error': 'Nivel no válido.'}), 400
        return jsonify({'status': 'ok'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/biblioteca/eliminar', methods=['POST'])
@limiter.limit("5 per minute")
def biblioteca_eliminar():
    datos = request.json or {}
    nivel = datos.get('nivel', '')
    nombre = (datos.get('nombre', '') or '').strip()
    serie = (datos.get('serie', '') or '').strip()
    temporada = (datos.get('temporada', '') or '').strip()
    if not nombre:
        return jsonify({'error': 'Falta el nombre.'}), 400
    try:
        if nivel == 'raiz':
            ruta = _ruta_media_segura(nombre)
            if not ruta:
                return jsonify({'error': 'Ruta no válida.'}), 400
            if not os.path.isdir(ruta):
                return jsonify({'error': 'Contenido no encontrado.'}), 404
            shutil.rmtree(ruta)
            try:
                conn = conectar_db()
                cursor = conn.cursor()
                cursor.execute('DELETE FROM content_metadata WHERE serie = ?', (nombre,))
                cursor.execute('DELETE FROM favoritos WHERE serie = ?', (nombre,))
                cursor.execute('DELETE FROM progreso WHERE serie = ?', (nombre,))
                cursor.execute('DELETE FROM listas WHERE serie = ?', (nombre,))
                conn.commit()
                conn.close()
            except Exception:
                pass
        elif nivel == 'temporada':
            if not serie:
                return jsonify({'error': 'Falta la serie.'}), 400
            ruta = _ruta_media_segura(serie, nombre)
            if not ruta:
                return jsonify({'error': 'Ruta no válida.'}), 400
            if not os.path.isdir(ruta):
                return jsonify({'error': 'Temporada no encontrada.'}), 404
            shutil.rmtree(ruta)
            try:
                conn = conectar_db()
                cursor = conn.cursor()
                cursor.execute('DELETE FROM progreso WHERE serie = ? AND filename LIKE ?', (serie, f'{nombre}/%'))
                conn.commit()
                conn.close()
            except Exception:
                pass
        elif nivel == 'video':
            if not serie:
                return jsonify({'error': 'Falta la serie.'}), 400
            ruta_videos = obtener_ruta_serie(serie)
            base_dir = os.path.join(ruta_videos, temporada) if temporada else ruta_videos
            ruta = os.path.normpath(os.path.join(base_dir, nombre))
            raiz = os.path.normpath(ruta_videos)
            if not ruta.startswith(raiz + os.sep):
                return jsonify({'error': 'Ruta no válida.'}), 400
            if not os.path.isfile(ruta):
                return jsonify({'error': 'Vídeo no encontrado.'}), 404
            os.remove(ruta)
            nombre_base, _ = os.path.splitext(nombre)
            ruta_thumb = _ruta_media_segura(serie, '.thumbnails', f'{nombre_base}.jpg')
            if ruta_thumb and os.path.exists(ruta_thumb):
                os.remove(ruta_thumb)
            nombre_rel = f"{temporada}/{nombre}" if temporada else nombre
            try:
                conn = conectar_db()
                cursor = conn.cursor()
                cursor.execute('DELETE FROM progreso WHERE serie = ? AND filename = ?', (serie, nombre_rel))
                conn.commit()
                conn.close()
            except Exception:
                pass
        else:
            return jsonify({'error': 'Nivel no válido.'}), 400
        return jsonify({'status': 'ok'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/biblioteca/omdb/estado')
def biblioteca_omdb_estado():
    clave = leer_env().get('OMDB_API_KEY', '').strip()
    return jsonify({'tiene_key': bool(clave), 'api_key': clave})

@app.route('/biblioteca/omdb/validar', methods=['POST'])
@limiter.limit("5 per minute")
def biblioteca_omdb_validar():
    datos = request.json or {}
    clave = (datos.get('api_key', '') or '').strip()
    if not clave:
        return jsonify({'ok': False})
    ok = omdb_validar_api_key(clave)
    if ok:
        guardar_env({'OMDB_API_KEY': clave})
    return jsonify({'ok': ok})

@app.route('/biblioteca/omdb/aplicar', methods=['POST'])
@limiter.limit("2 per minute")
def biblioteca_omdb_aplicar():
    datos = request.json or {}
    nombre = (datos.get('nombre', '') or '').strip()
    descargar = bool(datos.get('descargar_portada', True))
    if not nombre:
        return jsonify({'error': 'Falta el nombre.'}), 400
    ruta = _ruta_media_segura(nombre)
    if not ruta or not os.path.isdir(ruta):
        return jsonify({'error': f'"{nombre}" no existe.'}), 404
    clave = leer_env().get('OMDB_API_KEY', '').strip()
    if not clave:
        return jsonify({'error': 'Introduce una API key de OMDb primero.'}), 400
    tipo = detectar_tipo_contenido(nombre)
    query = nombre.replace('_', ' ').replace('-', ' ')
    resultados = omdb_buscar(clave, query, tipo) or []
    match = None
    for r in resultados:
        r_type = r.get('Type', '')
        if (tipo == 'pelicula' and r_type == 'movie') or (tipo == 'serie' and r_type == 'series'):
            match = r
            break
    if not match and resultados:
        match = resultados[0]
    if not match or not match.get('imdbID'):
        return jsonify({'error': f'{nombre} → Sin resultados'}), 404
    ok, info = omdb_aplicar_a_carpeta(clave, nombre, match['imdbID'], tipo, descargar)
    if not ok:
        return jsonify({'error': f'{nombre} → {info}'}), 500
    return jsonify({'status': 'ok', 'info': info})

# =============================================================================
# API - SISTEMA (ping, apagado, admin)
# =============================================================================
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

# =============================================================================
# PUNTO DE ENTRADA PRINCIPAL
# =============================================================================
if __name__ == '__main__':
    inicializar_base_datos()
    
    cfg = leer_config()
    puerto = cfg.get('puerto', 5000)
    sistema = platform.system()
    
    if sistema == "Windows":
        from waitress import serve
        print(f"Iniciado servidor con Waitress (Windows) en puerto {puerto}")
        serve(app, host='0.0.0.0', port=puerto, threads=6)
        
    else:
        import subprocess
        print(f"Iniciando servidor Gunicorn (Linux/Unix) en puerto {puerto} (1 worker, 6 threads)")
        subprocess.run([
            sys.executable, "-m", "gunicorn",
            "--bind", f"0.0.0.0:{puerto}",
            "--workers", "1",
            "--threads", "6",
            "app:app"
        ])
