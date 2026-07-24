import json
import os
import sys
import argparse
import threading
import urllib.request
import urllib.parse
import urllib.error
import sqlite3

DIRECTORIO_RAIZ = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(DIRECTORIO_RAIZ, 'data', 'config.json')
MEDIA_PATH = os.path.join(DIRECTORIO_RAIZ, 'data', 'media')
ENV_PATH = os.path.join(DIRECTORIO_RAIZ, '.env')
DB_PATH = os.path.join(DIRECTORIO_RAIZ, 'data', 'flaskcast.db')
LIVE_STREAMS_PATH = os.path.join(DIRECTORIO_RAIZ, 'data', 'live_streams.json')
OMDB_API_URL = 'https://www.omdbapi.com/'

_admin_lang = 'es'


def t(key):
    from translations import get_admin_text
    return get_admin_text(_admin_lang, key)


def conectar_db():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


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


def leer_config():
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)


def guardar_config(data):
    with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


def toggle(valor):
    return not valor


def cli():
    parser = argparse.ArgumentParser(
        description='Panel de administración de FlaskCast',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            'Ejemplos:\n'
            '  python config_admin.py                          Abre la interfaz gráfica\n'
            '  python config_admin.py --status                 Muestra la configuración actual\n'
            '  python config_admin.py --toggle-server          Activa/desactiva botón "Apagar Servidor"\n'
            '  python config_admin.py --toggle-all             Activa/desactiva botón "Apagar Todo"\n'
            '  python config_admin.py --api                    Activa/desactiva la API REST\n'
            '  python config_admin.py --port 8080              Cambia el puerto\n'
            '  python config_admin.py --omdb-key abc123       Guarda la API key de OMDb\n'
            '  python config_admin.py --export backup.fkmedia  Exporta media/ a archivo\n'
            '  python config_admin.py --import backup.fkmedia  Importa media/ desde archivo\n'
        )
    )
    parser.add_argument('--status', action='store_true', help='Muestra la configuración actual')
    parser.add_argument('--toggle-server', action='store_true', help='Activa/desactiva el botón "Apagar Servidor"')
    parser.add_argument('--toggle-all', action='store_true', help='Activa/desactiva el botón "Apagar Todo"')
    parser.add_argument('--api', action='store_true', help='Activa/desactiva la API REST')
    parser.add_argument('--port', type=int, metavar='PUERTO', help='Cambia el puerto del servidor')
    parser.add_argument('--export', type=str, metavar='ARCHIVO', help='Exporta data/media/ a un archivo .fkmedia')
    parser.add_argument('--import', type=str, metavar='ARCHIVO', dest='importar', help='Importa un archivo .fkmedia en data/media/')
    parser.add_argument('--omdb-key', type=str, metavar='API_KEY', help='Guarda la API key de OMDb')

    args = parser.parse_args()

    tiene_args = any([args.status, args.toggle_server, args.toggle_all, args.api, args.port, args.export, args.importar, args.omdb_key])

    if not tiene_args:
        gui()
        return

    cfg = leer_config()
    cambios = []

    if args.status:
        print('=== Configuración actual ===')
        print(f'  Apagar Servidor:   {"ON" if cfg.get("boton_apagar_visible") else "OFF"}')
        print(f'  Apagar Todo:       {"ON" if cfg.get("boton_apagar_todo_visible") else "OFF"}')
        print(f'  API REST:          {"ON" if cfg.get("api_habilitada") else "OFF"}')
        print(f'  Puerto:            {cfg.get("puerto", 5000)}')
        omdb_key = leer_env().get('OMDB_API_KEY', '')
        print(f'  OMDb API Key:      {"Configurada" if omdb_key else "No configurada"}')
        return

    if args.toggle_server:
        nuevo = toggle(cfg.get('boton_apagar_visible', False))
        cfg['boton_apagar_visible'] = nuevo
        cambios.append(f'Apagar Servidor -> {"ON" if nuevo else "OFF"}')

    if args.toggle_all:
        nuevo = toggle(cfg.get('boton_apagar_todo_visible', False))
        cfg['boton_apagar_todo_visible'] = nuevo
        cambios.append(f'Apagar Todo -> {"ON" if nuevo else "OFF"}')

    if args.api:
        nuevo = toggle(cfg.get('api_habilitada', False))
        cfg['api_habilitada'] = nuevo
        cambios.append(f'API REST -> {"ON" if nuevo else "OFF"}')

    if args.port is not None:
        if args.port < 1 or args.port > 65535:
            print('Error: el puerto debe ser un número entre 1 y 65535.')
            sys.exit(1)
        cfg['puerto'] = args.port
        cambios.append(f'Puerto -> {args.port}')

    if args.omdb_key:
        guardar_env({'OMDB_API_KEY': args.omdb_key.strip()})
        cambios.append(f'OMDb API Key -> guardada en .env')

    if cambios:
        guardar_config(cfg)
        print('Cambios aplicados:')
        for c in cambios:
            print(f'  -> {c}')

    if args.export:
        exportar_media_cli(args.export)

    if args.importar:
        importar_media_cli(args.importar)


def exportar_media_cli(destino):
    import py7zr

    if not os.path.exists(MEDIA_PATH) or not os.listdir(MEDIA_PATH):
        print('Error: la carpeta data/media/ está vacía o no existe.')
        sys.exit(1)

    if not destino.endswith('.fkmedia'):
        destino += '.fkmedia'

    print(f'Exportando media/ -> {destino} ...')
    with py7zr.SevenZipFile(destino, 'w') as archive:
        for raiz, dirs, archivos in os.walk(MEDIA_PATH):
            for archivo in archivos:
                ruta_abs = os.path.join(raiz, archivo)
                ruta_rel = os.path.relpath(ruta_abs, os.path.dirname(MEDIA_PATH))
                archive.write(ruta_abs, ruta_rel)
    print(f'Exportado correctamente: {destino}')


def importar_media_cli(archivo):
    import py7zr

    if not os.path.exists(archivo):
        print(f'Error: el archivo {archivo} no existe.')
        sys.exit(1)

    if not os.path.exists(MEDIA_PATH):
        os.makedirs(MEDIA_PATH, exist_ok=True)

    print(f'Importando {archivo} -> data/media/ ...')
    with py7zr.SevenZipFile(archivo, 'r') as archive:
        archive.extractall(path=os.path.dirname(MEDIA_PATH))
    print('Importado correctamente.')


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

    ruta_carpeta = os.path.join(MEDIA_PATH, carpeta_nombre)
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

    meta = {
        'tipo': tipo_content,
        'titulo': detalles.get('Title', carpeta_nombre),
        'descripcion': detalles.get('Plot', '') if detalles.get('Plot') != 'N/A' else '',
        'anio': detalles.get('Year', '') if detalles.get('Year') != 'N/A' else '',
        'genero': genero,
        'director': detalles.get('Director', '') if detalles.get('Director') != 'N/A' else '',
        'valoracion': rating,
    }

    if tipo_content == 'pelicula':
        meta['duracion_min'] = duracion
    else:
        total_seasons = detalles.get('totalSeasons', '')
        if total_seasons and total_seasons != 'N/A':
            meta['temporadas'] = int(total_seasons)

    meta_path = os.path.join(ruta_carpeta, '_meta.json')
    with open(meta_path, 'w', encoding='utf-8') as f:
        json.dump(meta, f, indent=4, ensure_ascii=False)

    if descargar_poster:
        poster_url = detalles.get('Poster', '')
        if poster_url and poster_url != 'N/A':
            img_path = os.path.join(ruta_carpeta, '_img.png')
            omdb_descargar_poster(poster_url, img_path)

    return True, meta.get('titulo', carpeta_nombre)


def detectar_tipo_contenido(carpeta_nombre):
    ruta = os.path.join(MEDIA_PATH, carpeta_nombre)
    if not os.path.isdir(ruta):
        return 'serie'
    meta_path = os.path.join(ruta, '_meta.json')
    if os.path.exists(meta_path):
        try:
            with open(meta_path, 'r', encoding='utf-8') as f:
                meta = json.load(f)
            if meta.get('tipo') in ('pelicula', 'serie'):
                return meta['tipo']
        except Exception:
            pass
    formatos_video = ('.mp4', '.webm', '.ogg', '.avi', '.mkv')
    try:
        items = os.listdir(ruta)
    except OSError:
        return 'serie'
    subcarpetas = [i for i in items if os.path.isdir(os.path.join(ruta, i)) and not i.startswith('.')]
    if subcarpetas:
        return 'serie'
    return 'pelicula'


def listar_contenido_media():
    if not os.path.exists(MEDIA_PATH):
        return []
    items = []
    for nombre in sorted(os.listdir(MEDIA_PATH)):
        ruta = os.path.join(MEDIA_PATH, nombre)
        if os.path.isdir(ruta) and not nombre.startswith('.'):
            tipo = detectar_tipo_contenido(nombre)
            tiene_meta = os.path.exists(os.path.join(ruta, '_meta.json'))
            tiene_portada = os.path.exists(os.path.join(ruta, '_img.png'))
            items.append({
                'nombre': nombre,
                'tipo': tipo,
                'tiene_meta': tiene_meta,
                'tiene_portada': tiene_portada,
            })
    return items


def cargar_streams():
    if not os.path.exists(LIVE_STREAMS_PATH):
        return []
    try:
        with open(LIVE_STREAMS_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return []


def guardar_streams(streams):
    with open(LIVE_STREAMS_PATH, 'w', encoding='utf-8') as f:
        json.dump(streams, f, indent=4, ensure_ascii=False)


def gui():
    import tkinter as tk
    from tkinter import ttk, messagebox, filedialog, simpledialog
    import webbrowser
    import shutil
    import py7zr

    FORMATOS_VIDEO = ('.mp4', '.webm', '.ogg', '.avi', '.mkv')

    class DialogoMetadata(tk.Toplevel):
        def __init__(self, parent, titulo_ventana='Metadata', meta=None, es_nuevo=False):
            super().__init__(parent)
            self.title(titulo_ventana)
            self.geometry('450x500')
            self.resizable(False, False)
            self.transient(parent)
            self.grab_set()
            self.resultado = None
            self.es_nuevo = es_nuevo

            frame = ttk.Frame(self, padding=15)
            frame.pack(fill=tk.BOTH, expand=True)

            ttk.Label(frame, text=t('meta_titulo'), font=('Segoe UI', 9, 'bold')).pack(anchor=tk.W)
            self.titulo_var = tk.StringVar(value=meta.get('titulo', '') if meta else '')
            ttk.Entry(frame, textvariable=self.titulo_var, width=50).pack(fill=tk.X, pady=(0, 4))
            ttk.Label(frame, text=t('meta_obligatorio'), foreground='#888', font=('Segoe UI', 8)).pack(anchor=tk.W, pady=(0, 6))

            ttk.Label(frame, text=t('meta_descripcion'), font=('Segoe UI', 9, 'bold')).pack(anchor=tk.W)
            self.descripcion_text = tk.Text(frame, height=4, width=50, wrap=tk.WORD)
            self.descripcion_text.pack(fill=tk.X, pady=(0, 8))
            if meta and meta.get('descripcion'):
                self.descripcion_text.insert('1.0', meta['descripcion'])

            row1 = ttk.Frame(frame)
            row1.pack(fill=tk.X, pady=(0, 8))
            ttk.Label(row1, text=t('meta_anio')).pack(side=tk.LEFT)
            self.anio_var = tk.StringVar(value=meta.get('anio', '') if meta else '')
            ttk.Entry(row1, textvariable=self.anio_var, width=8).pack(side=tk.LEFT, padx=(5, 15))
            ttk.Label(row1, text=t('meta_valoracion')).pack(side=tk.LEFT)
            self.valoracion_var = tk.StringVar(value=str(meta.get('valoracion', 0)) if meta else '0')
            ttk.Entry(row1, textvariable=self.valoracion_var, width=6).pack(side=tk.LEFT, padx=(5, 0))

            row2 = ttk.Frame(frame)
            row2.pack(fill=tk.X, pady=(0, 8))
            ttk.Label(row2, text=t('meta_director')).pack(side=tk.LEFT)
            self.director_var = tk.StringVar(value=meta.get('director', '') if meta else '')
            ttk.Entry(row2, textvariable=self.director_var, width=35).pack(side=tk.LEFT, padx=(5, 0), fill=tk.X, expand=True)

            ttk.Label(frame, text=t('meta_generos'), font=('Segoe UI', 9, 'bold')).pack(anchor=tk.W)
            genero_str = ', '.join(meta.get('genero', [])) if meta and isinstance(meta.get('genero'), list) else (meta.get('genero', '') if meta else '')
            self.genero_var = tk.StringVar(value=genero_str)
            ttk.Entry(frame, textvariable=self.genero_var, width=50).pack(fill=tk.X, pady=(0, 8))

            row3 = ttk.Frame(frame)
            row3.pack(fill=tk.X, pady=(0, 8))
            ttk.Label(row3, text=t('meta_tipo')).pack(side=tk.LEFT)
            self.tipo_var = tk.StringVar(value=meta.get('tipo', 'pelicula') if meta else 'pelicula')
            ttk.Combobox(row3, textvariable=self.tipo_var, values=['pelicula', 'serie'],
                         state='readonly', width=12).pack(side=tk.LEFT, padx=(5, 15))
            ttk.Label(row3, text=t('meta_duracion')).pack(side=tk.LEFT)
            self.duracion_var = tk.StringVar(value=str(meta.get('duracion_min', '')) if meta and meta.get('duracion_min') else '')
            ttk.Entry(row3, textvariable=self.duracion_var, width=8).pack(side=tk.LEFT, padx=(5, 0))

            row4 = ttk.Frame(frame)
            row4.pack(fill=tk.X, pady=(0, 8))
            ttk.Label(row4, text=t('meta_temporadas')).pack(side=tk.LEFT)
            self.temporadas_var = tk.StringVar(value=str(meta.get('temporadas', 1)) if meta and meta.get('temporadas') else '1')
            ttk.Entry(row4, textvariable=self.temporadas_var, width=6).pack(side=tk.LEFT, padx=(5, 0))

            btn_frame = ttk.Frame(frame)
            btn_frame.pack(pady=(10, 0))
            ttk.Button(btn_frame, text=t('meta_aceptar'), command=self._aceptar).pack(side=tk.LEFT, padx=5)
            ttk.Button(btn_frame, text=t('meta_cancelar'), command=self.destroy).pack(side=tk.LEFT, padx=5)

            self.protocol("WM_DELETE_WINDOW", self.destroy)
            self.wait_window()

        def _aceptar(self):
            titulo = self.titulo_var.get().strip()
            if not titulo:
                messagebox.showerror('Error', 'El título no puede estar vacío.', parent=self)
                return
            try:
                valoracion = round(float(self.valoracion_var.get()), 1)
            except ValueError:
                valoracion = 0
            try:
                duracion = int(self.duracion_var.get()) if self.duracion_var.get().strip() else 0
            except ValueError:
                duracion = 0
            try:
                temporadas = int(self.temporadas_var.get()) if self.temporadas_var.get().strip() else 1
            except ValueError:
                temporadas = 1

            genero_raw = self.genero_var.get().strip()
            genero = [g.strip() for g in genero_raw.split(',') if g.strip()] if genero_raw else []

            self.resultado = {
                'tipo': self.tipo_var.get(),
                'titulo': titulo,
                'descripcion': self.descripcion_text.get('1.0', tk.END).strip(),
                'anio': self.anio_var.get().strip(),
                'genero': genero,
                'director': self.director_var.get().strip(),
                'valoracion': valoracion,
                'duracion_min': duracion,
                'temporadas': temporadas,
            }
            self.destroy()

    class ConfigAdmin:
        def __init__(self, root=None):
            if root is None:
                self.root = tk.Tk()
                self._first_init = True
            else:
                self.root = root
                self._first_init = False

            self.root.title(t('window_title'))
            self.root.geometry('750x750')
            self.root.resizable(True, True)

            if self._first_init:
                logo_path = os.path.join(DIRECTORIO_RAIZ, 'static', 'logo.png')
                if os.path.exists(logo_path):
                    logo = tk.PhotoImage(file=logo_path)
                    self.root.iconphoto(True, logo)

            cfg = leer_config()
            global _admin_lang
            _admin_lang = cfg.get('admin_idioma', 'es')

            notebook = ttk.Notebook(self.root)
            notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            tab_general = ttk.Frame(notebook, padding=15)
            tab_omdb = ttk.Frame(notebook, padding=15)
            tab_contenido = ttk.Frame(notebook, padding=15)
            tab_streamings = ttk.Frame(notebook, padding=15)
            tab_lang = ttk.Frame(notebook, padding=15)
            notebook.add(tab_general, text=t('tab_general'))
            notebook.add(tab_omdb, text=t('tab_omdb'))
            notebook.add(tab_contenido, text=t('tab_biblioteca'))
            notebook.add(tab_streamings, text=t('tab_streamings'))
            notebook.add(tab_lang, text=' Language ')

            ttk.Label(tab_lang, text='Language / Idioma', font=('Segoe UI', 14, 'bold')).pack(pady=(20, 15))
            self.lang_var = tk.StringVar(value=_admin_lang)
            lang_frame = ttk.Frame(tab_lang)
            lang_frame.pack()
            ttk.Radiobutton(lang_frame, text='🇪🇸 Español', variable=self.lang_var, value='es',
                             command=self._cambiar_idioma).pack(side=tk.LEFT, padx=15)
            ttk.Radiobutton(lang_frame, text='🇬🇧 English', variable=self.lang_var, value='en',
                             command=self._cambiar_idioma).pack(side=tk.LEFT, padx=15)

            tab_general = ttk.Frame(notebook, padding=15)
            tab_omdb = ttk.Frame(notebook, padding=15)
            tab_contenido = ttk.Frame(notebook, padding=15)
            tab_streamings = ttk.Frame(notebook, padding=15)
            notebook.add(tab_general, text=t('tab_general'))
            notebook.add(tab_omdb, text=t('tab_omdb'))
            notebook.add(tab_contenido, text=t('tab_biblioteca'))
            notebook.add(tab_streamings, text=t('tab_streamings'))

            self._build_tab_general(tab_general, cfg)
            self._build_tab_omdb(tab_omdb, cfg)
            self._build_tab_contenido(tab_contenido)
            self._build_tab_streamings(tab_streamings)

        def _build_tab_general(self, parent, cfg):
            ttk.Label(parent, text=t('gen_title'),
                      font=('Segoe UI', 14, 'bold')).pack(pady=(0, 12))

            self.apagar_var = tk.BooleanVar(value=cfg.get('boton_apagar_visible', False))
            self.apagar_todo_var = tk.BooleanVar(value=cfg.get('boton_apagar_todo_visible', False))
            self.api_var = tk.BooleanVar(value=cfg.get('api_habilitada', False))

            frame_check = ttk.Frame(parent)
            frame_check.pack(fill=tk.X, pady=5)
            ttk.Checkbutton(frame_check, text=t('gen_apagar_servidor'),
                            variable=self.apagar_var).pack(anchor=tk.W)
            ttk.Checkbutton(frame_check, text=t('gen_apagar_todo'),
                            variable=self.apagar_todo_var).pack(anchor=tk.W)

            ttk.Separator(parent, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=8)

            ttk.Checkbutton(parent, text=t('gen_api'),
                            variable=self.api_var).pack(anchor=tk.W, pady=4)
            ttk.Label(parent, text=t('gen_api_desc'),
                      foreground='#888', font=('Segoe UI', 8)).pack(anchor=tk.W)

            ttk.Separator(parent, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=8)

            frame_port = ttk.Frame(parent)
            frame_port.pack(fill=tk.X)
            ttk.Label(frame_port, text=t('gen_puerto')).pack(side=tk.LEFT)
            self.port_var = tk.StringVar(value=str(cfg.get('puerto', 5000)))
            port_entry = ttk.Entry(frame_port, textvariable=self.port_var, width=10)
            port_entry.pack(side=tk.LEFT, padx=(10, 0))

            ttk.Separator(parent, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=8)

            ttk.Label(parent, text=t('gen_gestion_contenido'),
                      font=('Segoe UI', 10, 'bold')).pack(anchor=tk.W, pady=(0, 6))

            media_frame = ttk.Frame(parent)
            media_frame.pack(fill=tk.X, pady=4)
            ttk.Button(media_frame, text=t('gen_exportar'),
                       command=self.exportar_media).pack(side=tk.LEFT, padx=(0, 5))
            ttk.Button(media_frame, text=t('gen_importar'),
                       command=self.importar_media).pack(side=tk.LEFT)

            self.status_label = ttk.Label(parent, text='', foreground='green')
            self.status_label.pack(pady=(8, 0))

            btn_frame = ttk.Frame(parent)
            btn_frame.pack(pady=(10, 0))
            ttk.Button(btn_frame, text=t('gen_guardar_cerrar'), command=self.guardar_y_cerrar).pack(side=tk.LEFT, padx=5)
            ttk.Button(btn_frame, text=t('gen_salir'), command=self.root.destroy).pack(side=tk.LEFT, padx=5)

        def _cambiar_idioma(self, event=None):
            global _admin_lang
            _admin_lang = self.lang_var.get()
            cfg = leer_config()
            cfg['admin_idioma'] = _admin_lang
            guardar_config(cfg)
            for widget in self.root.winfo_children():
                widget.destroy()
            ConfigAdmin(self.root)

        def _build_tab_omdb(self, parent, cfg):
            ttk.Label(parent, text=t('omdb_title'),
                      font=('Segoe UI', 14, 'bold')).pack(pady=(0, 6))
            ttk.Label(parent, text=t('omdb_desc'),
                      foreground='#888').pack(pady=(0, 10))

            api_frame = ttk.LabelFrame(parent, text=' API Key ', padding=10)
            api_frame.pack(fill=tk.X, pady=(0, 10))

            api_row = ttk.Frame(api_frame)
            api_row.pack(fill=tk.X)
            ttk.Label(api_row, text=t('omdb_api_key')).pack(side=tk.LEFT)
            env_data = leer_env()
            self.omdb_api_var = tk.StringVar(value=env_data.get('OMDB_API_KEY', ''))
            api_entry = ttk.Entry(api_row, textvariable=self.omdb_api_var, width=40, show='*')
            api_entry.pack(side=tk.LEFT, padx=(8, 5))

            def abrir_omdb_api():
                webbrowser.open('https://www.omdbapi.com/apikey.aspx')
            ttk.Button(api_row, text=t('omdb_obtener_key'), command=abrir_omdb_api).pack(side=tk.LEFT, padx=(0, 8))

            self.omdb_api_status = ttk.Label(api_row, text='', font=('Segoe UI', 9))
            self.omdb_api_status.pack(side=tk.LEFT)

            def validar_api():
                key = self.omdb_api_var.get().strip()
                if not key:
                    self.omdb_api_status.config(text=t('omdb_intro_key'), foreground='#ff8800')
                    return
                self.omdb_api_status.config(text=t('omdb_validando'), foreground='#888')
                self.root.update_idletasks()
                def _hilo():
                    ok = omdb_validar_api_key(key)
                    def _resultado():
                        if ok:
                            guardar_env({'OMDB_API_KEY': key})
                            self.omdb_api_status.config(text=t('omdb_key_valida'), foreground='#00cc66')
                        else:
                            self.omdb_api_status.config(text=t('omdb_key_invalida'), foreground='red')
                    self.root.after(0, _resultado)
                threading.Thread(target=_hilo, daemon=True).start()

            ttk.Button(api_row, text=t('omdb_validar'), command=validar_api).pack(side=tk.LEFT)

            ttk.Separator(parent, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=8)

            lib_header = ttk.Frame(parent)
            lib_header.pack(fill=tk.X, pady=(0, 6))
            ttk.Label(lib_header, text=t('omdb_biblioteca'),
                      font=('Segoe UI', 10, 'bold')).pack(side=tk.LEFT)
            ttk.Button(lib_header, text=t('omdb_refrescar'), command=self._refrescar_biblioteca).pack(side=tk.RIGHT)

            list_frame = ttk.Frame(parent)
            list_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 8))

            cols = ('nombre', 'tipo', 'meta', 'portada')
            self.tree = ttk.Treeview(list_frame, columns=cols, show='headings', selectmode='extended', height=10)
            self.tree.heading('nombre', text=t('omdb_carpeta'))
            self.tree.heading('tipo', text=t('omdb_tipo'))
            self.tree.heading('meta', text=t('omdb_meta'))
            self.tree.heading('portada', text=t('omdb_portada'))
            self.tree.column('nombre', width=250)
            self.tree.column('tipo', width=80, anchor=tk.CENTER)
            self.tree.column('meta', width=70, anchor=tk.CENTER)
            self.tree.column('portada', width=70, anchor=tk.CENTER)

            scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.tree.yview)
            self.tree.configure(yscrollcommand=scrollbar.set)
            self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

            self._refrescar_biblioteca()

            ttk.Separator(parent, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=8)

            apply_frame = ttk.Frame(parent)
            apply_frame.pack(fill=tk.X)

            self.omdb_descargar_img_var = tk.BooleanVar(value=True)
            ttk.Checkbutton(apply_frame, text=t('omdb_descargar_portada'),
                            variable=self.omdb_descargar_img_var).pack(side=tk.LEFT)

            self.omdb_status_label = ttk.Label(apply_frame, text='', font=('Segoe UI', 9))
            self.omdb_status_label.pack(side=tk.LEFT, padx=(10, 0))

            ttk.Button(apply_frame, text=t('omdb_aplicar'),
                       command=self._aplicar_omdb).pack(side=tk.RIGHT)

        def _refrescar_biblioteca(self):
            for item in self.tree.get_children():
                self.tree.delete(item)
            contenido = listar_contenido_media()
            for c in contenido:
                estado_meta = '✓' if c['tiene_meta'] else '✗'
                estado_portada = '✓' if c['tiene_portada'] else '✗'
                tipo_display = t('bib_pelicula') if c['tipo'] == 'pelicula' else t('bib_serie')
                self.tree.insert('', tk.END, iid=c['nombre'],
                                 values=(c['nombre'], tipo_display, estado_meta, estado_portada))

        def _aplicar_omdb(self):
            api_key = self.omdb_api_var.get().strip()
            if not api_key:
                messagebox.showerror('Error', 'Introduce una API key de OMDb primero.')
                return

            seleccion = self.tree.selection()
            if not seleccion:
                messagebox.showinfo('OMDb', t('msg_selecciona_biblioteca'))
                return

            descarga_poster = self.omdb_descargar_img_var.get()
            self.omdb_status_label.config(text=t('omdb_procesando'), foreground='#888')
            self.root.config(cursor='watch')
            self.root.update_idletasks()

            resultados_ok = []
            resultados_error = []

            def _hilo():
                for nombre in seleccion:
                    tipo = detectar_tipo_contenido(nombre)
                    query = nombre.replace('_', ' ').replace('-', ' ')
                    try:
                        resultados = omdb_buscar(api_key, query, tipo)
                        match = None
                        for r in resultados:
                            r_type = r.get('Type', '')
                            if tipo == 'pelicula' and r_type == 'movie':
                                match = r
                                break
                            elif tipo == 'serie' and r_type == 'series':
                                match = r
                                break
                        if not match and resultados:
                            match = resultados[0]

                        if match and match.get('imdbID'):
                            ok, info = omdb_aplicar_a_carpeta(api_key, nombre, match['imdbID'], tipo, descarga_poster)
                            if ok:
                                resultados_ok.append(f'{nombre} → {info}')
                            else:
                                resultados_error.append(f'{nombre} → {info}')
                        else:
                            resultados_error.append(f'{nombre} → Sin resultados')
                    except Exception as e:
                        resultados_error.append(f'{nombre} → {e}')

                def _final():
                    self.root.config(cursor='')
                    total = len(seleccion)
                    ok = len(resultados_ok)
                    fail = len(resultados_error)
                    msg = f'Procesados: {total}\n✓ Correctos: {ok}\n✗ Errores: {fail}'
                    if resultados_error:
                        msg += '\n\nErrores:\n' + '\n'.join(resultados_error[:10])
                        if len(resultados_error) > 10:
                            msg += f'\n... y {len(resultados_error) - 10} más'
                    self.omdb_status_label.config(
                        text=f'Completado: {ok}/{total}',
                        foreground='#00cc66' if fail == 0 else '#ff8800')
                    messagebox.showinfo('OMDb', msg)
                    self._refrescar_biblioteca()

                self.root.after(0, _final)

            threading.Thread(target=_hilo, daemon=True).start()

        def _build_tab_contenido(self, parent):
            ttk.Label(parent, text=t('bib_title'),
                      font=('Segoe UI', 14, 'bold')).pack(pady=(0, 6))
            ttk.Label(parent, text=t('bib_desc'),
                      foreground='#888').pack(pady=(0, 10))

            tree_frame = ttk.Frame(parent)
            tree_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 8))

            self.ct_tree = ttk.Treeview(tree_frame, columns=('tipo', 'info'), show='tree headings', selectmode='browse', height=14)
            self.ct_tree.heading('#0', text=t('bib_nombre'))
            self.ct_tree.heading('tipo', text=t('bib_tipo'))
            self.ct_tree.heading('info', text=t('bib_info'))
            self.ct_tree.column('#0', width=280)
            self.ct_tree.column('tipo', width=100, anchor=tk.CENTER)
            self.ct_tree.column('info', width=200)

            scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.ct_tree.yview)
            self.ct_tree.configure(yscrollcommand=scrollbar.set)
            self.ct_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

            self.ct_tree.bind('<ButtonRelease-3>', self._contenido_menu_contextual)

            btn_frame = ttk.Frame(parent)
            btn_frame.pack(fill=tk.X, pady=(0, 4))

            ttk.Button(btn_frame, text=t('bib_anadir_pelicula_serie'), command=self._contenido_nuevo).pack(side=tk.LEFT, padx=(0, 4))
            ttk.Button(btn_frame, text=t('bib_anadir_temporada'), command=self._contenido_nueva_temporada).pack(side=tk.LEFT, padx=(0, 4))
            ttk.Button(btn_frame, text=t('bib_anadir_video'), command=self._contenido_anadir_video).pack(side=tk.LEFT, padx=(0, 4))

            btn_frame2 = ttk.Frame(parent)
            btn_frame2.pack(fill=tk.X)

            ttk.Button(btn_frame2, text=t('bib_editar_metadata'), command=self._contenido_editar_metadata).pack(side=tk.LEFT, padx=(0, 4))
            ttk.Button(btn_frame2, text=t('bib_renombrar'), command=self._contenido_renombrar).pack(side=tk.LEFT, padx=(0, 4))
            ttk.Button(btn_frame2, text=t('bib_eliminar'), command=self._contenido_eliminar).pack(side=tk.LEFT, padx=(0, 4))
            ttk.Button(btn_frame2, text=t('bib_refrescar'), command=self._contenido_refrescar).pack(side=tk.RIGHT)

            self._contenido_refrescar()

        def _contenido_refrescar(self):
            for item in self.ct_tree.get_children():
                self.ct_tree.delete(item)
            if not os.path.exists(MEDIA_PATH):
                return
            for nombre in sorted(os.listdir(MEDIA_PATH)):
                ruta = os.path.join(MEDIA_PATH, nombre)
                if not os.path.isdir(ruta) or nombre.startswith('.'):
                    continue
                tipo = detectar_tipo_contenido(nombre)
                tiene_meta = os.path.exists(os.path.join(ruta, '_meta.json'))
                tiene_portada = os.path.exists(os.path.join(ruta, '_img.png'))

                meta = {}
                meta_path = os.path.join(ruta, '_meta.json')
                if os.path.exists(meta_path):
                    try:
                        with open(meta_path, 'r', encoding='utf-8') as f:
                            meta = json.load(f)
                    except Exception:
                        pass

                display_tipo = t('bib_pelicula') if tipo == 'pelicula' else t('bib_serie')
                info_parts = []
                if meta.get('titulo'):
                    info_parts.append(meta['titulo'])
                if meta.get('anio'):
                    info_parts.append(meta['anio'])
                info_str = ' — '.join(info_parts) if info_parts else t('bib_sin_metadata')
                if tiene_portada:
                    info_str += ' 🖼'

                nodo_raiz = self.ct_tree.insert('', tk.END, text=nombre, values=(display_tipo, info_str), open=True)

                if tipo == 'serie':
                    subcarpetas = [i for i in sorted(os.listdir(ruta))
                                   if os.path.isdir(os.path.join(ruta, i)) and not i.startswith('.')]
                    for sub in subcarpetas:
                        ruta_sub = os.path.join(ruta, sub)
                        vids = [f for f in os.listdir(ruta_sub)
                                if os.path.isfile(os.path.join(ruta_sub, f)) and f.lower().endswith(FORMATOS_VIDEO)]
                        nodo_temp = self.ct_tree.insert(nodo_raiz, tk.END, text=sub,
                                                        values=(t('bib_temporada'), f'{len(vids)} {t("bib_videos")}'),
                                                        open=False)
                        for v in sorted(vids):
                            tam = os.path.getsize(os.path.join(ruta_sub, v))
                            tam_mb = f'{tam / (1024*1024):.1f} MB'
                            self.ct_tree.insert(nodo_temp, tk.END, text=v,
                                                values=(t('bib_video'), tam_mb))
                else:
                    vids = [f for f in os.listdir(ruta)
                            if os.path.isfile(os.path.join(ruta, f)) and f.lower().endswith(FORMATOS_VIDEO)]
                    for v in sorted(vids):
                        tam = os.path.getsize(os.path.join(ruta, v))
                        tam_mb = f'{tam / (1024*1024):.1f} MB'
                        self.ct_tree.insert(nodo_raiz, tk.END, text=v,
                                            values=(t('bib_video'), tam_mb))

        def _contenido_obtener_seleccion(self):
            sel = self.ct_tree.selection()
            if not sel:
                return None, None, None
            item_id = sel[0]
            texto = self.ct_tree.item(item_id, 'text')
            valores = self.ct_tree.item(item_id, 'values')
            tipo_display = valores[0] if valores else ''
            padre_id = self.ct_tree.parent(item_id)

            if not padre_id:
                return 'raiz', texto, item_id
            padre_texto = self.ct_tree.item(padre_id, 'text')
            padre_valores = self.ct_tree.item(padre_id, 'values')
            padre_tipo = padre_valores[0] if padre_valores else ''
            abuelo_id = self.ct_tree.parent(padre_id)

            if 'Temporada' in padre_tipo:
                if 'Vídeo' in tipo_display:
                    return 'video', texto, item_id
                return 'temporada', padre_texto, padre_id

            if 'Película' in tipo_display or 'Serie' in tipo_display:
                return 'raiz', texto, item_id

            if 'Vídeo' in tipo_display:
                return 'video', texto, item_id

            return 'raiz', texto, item_id

        def _contenido_nuevo(self):
            meta_dialog = DialogoMetadata(self.root, t('meta_anadir_title'), es_nuevo=True)
            if not meta_dialog.resultado:
                return
            meta = meta_dialog.resultado
            nombre = meta['titulo'].strip()
            if not nombre:
                return
            ruta = os.path.join(MEDIA_PATH, nombre)
            if os.path.exists(ruta):
                messagebox.showerror('Error', f'Ya existe una carpeta llamada "{nombre}".')
                return

            os.makedirs(ruta, exist_ok=True)
            meta_path = os.path.join(ruta, '_meta.json')
            with open(meta_path, 'w', encoding='utf-8') as f:
                json.dump(meta, f, indent=4, ensure_ascii=False)

            if meta.get('tipo') == 'serie':
                num_temp = meta.get('temporadas', 1)
                if num_temp >= 1:
                    for t in range(1, num_temp + 1):
                        os.makedirs(os.path.join(ruta, f'Season {t}'), exist_ok=True)

            self._contenido_refrescar()
            tipo_texto = 'Película' if meta.get('tipo') == 'pelicula' else 'Serie'
            extra = f' con {num_temp} temporada(s)' if meta.get('tipo') == 'serie' and num_temp >= 1 else ''
            messagebox.showinfo('Éxito', f'{tipo_texto} "{nombre}" creada{extra}.\nAhora puedes añadir vídeos con "+Añadir Vídeo".')

        def _contenido_nueva_temporada(self):
            nivel, nombre, item_id = self._contenido_obtener_seleccion()
            if nivel != 'raiz':
                messagebox.showinfo('Info', 'Selecciona una serie (carpeta raíz) en el árbol.')
                return
            tipo_display = self.ct_tree.item(item_id, 'values')[0]
            if 'Película' in tipo_display:
                messagebox.showinfo('Info', 'Las películas no tienen temporadas.')
                return

            ruta_serie = os.path.join(MEDIA_PATH, nombre)
            subcarpetas = [i for i in os.listdir(ruta_serie)
                           if os.path.isdir(os.path.join(ruta_serie, i)) and not i.startswith('.')]
            num = len(subcarpetas) + 1
            nombre_temp = f'Season {num}'
            ruta_temp = os.path.join(ruta_serie, nombre_temp)

            while os.path.exists(ruta_temp):
                num += 1
                nombre_temp = f'Season {num}'
                ruta_temp = os.path.join(ruta_serie, nombre_temp)

            os.makedirs(ruta_temp, exist_ok=True)
            self._contenido_refrescar()
            messagebox.showinfo('Éxito', f'Temporada "{nombre_temp}" creada en "{nombre}".')

        def _contenido_anadir_video(self):
            nivel, nombre, item_id = self._contenido_obtener_seleccion()
            if nivel is None:
                messagebox.showinfo('Info', 'Selecciona una serie, película o temporada.')
                return

            ruta_destino = None
            if nivel == 'raiz':
                tipo_display = self.ct_tree.item(item_id, 'values')[0]
                if 'Serie' in tipo_display:
                    messagebox.showinfo('Info', 'Selecciona una temporada dentro de la serie para añadir vídeos.')
                    return
                ruta_destino = os.path.join(MEDIA_PATH, nombre)
            elif nivel == 'temporada':
                serie_nombre = self.ct_tree.item(self.ct_tree.parent(item_id), 'text')
                ruta_destino = os.path.join(MEDIA_PATH, serie_nombre, nombre)
            elif nivel == 'video':
                parent_id = self.ct_tree.parent(item_id)
                if not parent_id:
                    messagebox.showinfo('Info', 'Selecciona una temporada o película padre.')
                    return
                padre_tipo = self.ct_tree.item(parent_id, 'values')[0]
                if 'Temporada' in padre_tipo:
                    serie_nombre = self.ct_tree.item(self.ct_tree.parent(parent_id), 'text')
                    temporada_nombre = self.ct_tree.item(parent_id, 'text')
                    ruta_destino = os.path.join(MEDIA_PATH, serie_nombre, temporada_nombre)
                else:
                    ruta_destino = os.path.join(MEDIA_PATH, self.ct_tree.item(parent_id, 'text'))

            if not ruta_destino or not os.path.exists(ruta_destino):
                messagebox.showerror('Error', 'La carpeta destino no existe.')
                return

            archivos = filedialog.askopenfilenames(
                title='Seleccionar vídeo(s)',
                filetypes=[('Vídeos', '*.mp4 *.webm *.ogg *.avi *.mkv'), ('Todos', '*.*')],
                parent=self.root
            )
            if not archivos:
                return

            self.root.config(cursor='watch')
            self.root.update_idletasks()

            copiados = 0
            errores = []
            for archivo_origen in archivos:
                nombre_arch = os.path.basename(archivo_origen)
                destino = os.path.join(ruta_destino, nombre_arch)
                if os.path.exists(destino):
                    if not messagebox.askyesno('Sobrescribir',
                                               f'Ya existe "{nombre_arch}".\n¿Sobrescribir?'):
                        continue
                try:
                    shutil.copy2(archivo_origen, destino)
                    copiados += 1
                except Exception as e:
                    errores.append(f'{nombre_arch}: {e}')

            self.root.config(cursor='')
            self._contenido_refrescar()

            msg = f'{copiados} vídeo(s) copiado(s).'
            if errores:
                msg += f'\n\nErrores:\n' + '\n'.join(errores[:5])
            messagebox.showinfo('Añadir vídeo', msg)

        def _contenido_editar_metadata(self):
            nivel, nombre, item_id = self._contenido_obtener_seleccion()
            if nivel != 'raiz':
                messagebox.showinfo('Info', 'Selecciona una serie o película (carpeta raíz) para editar su metadata.')
                return

            ruta = os.path.join(MEDIA_PATH, nombre)
            meta_path = os.path.join(ruta, '_meta.json')
            meta = {}
            if os.path.exists(meta_path):
                try:
                    with open(meta_path, 'r', encoding='utf-8') as f:
                        meta = json.load(f)
                except Exception:
                    pass

            tipo_display = self.ct_tree.item(item_id, 'values')[0]
            titulo_ventana = f'Editar: {nombre}'
            meta_dialog = DialogoMetadata(self.root, titulo_ventana, meta=meta)
            if not meta_dialog.resultado:
                return

            nuevo_meta = meta_dialog.resultado
            with open(meta_path, 'w', encoding='utf-8') as f:
                json.dump(nuevo_meta, f, indent=4, ensure_ascii=False)

            try:
                conn = conectar_db()
                cursor = conn.cursor()
                cursor.execute('INSERT OR REPLACE INTO content_metadata (serie, tipo) VALUES (?, ?)',
                               (nombre, nuevo_meta.get('tipo', 'auto')))
                conn.commit()
                conn.close()
            except Exception:
                pass

            self._contenido_refrescar()
            messagebox.showinfo('Éxito', f'Metadata de "{nombre}" actualizada.')

        def _contenido_renombrar(self):
            nivel, nombre, item_id = self._contenido_obtener_seleccion()
            if nivel is None:
                return

            if nivel == 'raiz':
                ruta_original = os.path.join(MEDIA_PATH, nombre)
                nuevo_nombre = simpledialog.askstring('Renombrar',
                                                    f'Nuevo nombre para "{nombre}":',
                                                    initialvalue=nombre, parent=self.root)
                if not nuevo_nombre or nuevo_nombre == nombre:
                    return
                nuevo_nombre = nuevo_nombre.strip()
                nueva_ruta = os.path.join(MEDIA_PATH, nuevo_nombre)
                if os.path.exists(nueva_ruta):
                    messagebox.showerror('Error', f'Ya existe "{nuevo_nombre}".')
                    return
                os.rename(ruta_original, nueva_ruta)
                try:
                    conn = conectar_db()
                    cursor = conn.cursor()
                    cursor.execute('UPDATE content_metadata SET serie = ? WHERE serie = ?', (nuevo_nombre, nombre))
                    cursor.execute('UPDATE favoritos SET serie = ? WHERE serie = ?', (nuevo_nombre, nombre))
                    cursor.execute('UPDATE progreso SET serie = ? WHERE serie = ?', (nuevo_nombre, nombre))
                    cursor.execute('UPDATE listas SET serie = ? WHERE serie = ?', (nuevo_nombre, nombre))
                    conn.commit()
                    conn.close()
                except Exception:
                    pass

            elif nivel == 'temporada':
                serie_nombre = self.ct_tree.item(self.ct_tree.parent(item_id), 'text')
                ruta_original = os.path.join(MEDIA_PATH, serie_nombre, nombre)
                nuevo_nombre = simpledialog.askstring('Renombrar temporada',
                                                    f'Nuevo nombre para "{nombre}":',
                                                    initialvalue=nombre, parent=self.root)
                if not nuevo_nombre or nuevo_nombre == nombre:
                    return
                nueva_ruta = os.path.join(MEDIA_PATH, serie_nombre, nuevo_nombre)
                if os.path.exists(nueva_ruta):
                    messagebox.showerror('Error', f'Ya existe "{nuevo_nombre}".')
                    return
                os.rename(ruta_original, nueva_ruta)

            elif nivel == 'video':
                parent_id = self.ct_tree.parent(item_id)
                if not parent_id:
                    return
                padre_tipo = self.ct_tree.item(parent_id, 'values')[0]
                if 'Temporada' in padre_tipo:
                    serie_nombre = self.ct_tree.item(self.ct_tree.parent(parent_id), 'text')
                    temporada_nombre = self.ct_tree.item(parent_id, 'text')
                    carpeta = os.path.join(MEDIA_PATH, serie_nombre, temporada_nombre)
                else:
                    carpeta = os.path.join(MEDIA_PATH, self.ct_tree.item(parent_id, 'text'))

                ruta_original = os.path.join(carpeta, nombre)
                ext = os.path.splitext(nombre)[1]
                nuevo_nombre_base = simpledialog.askstring('Renombrar vídeo',
                                                         f'Nuevo nombre (sin extensión):',
                                                         initialvalue=os.path.splitext(nombre)[0],
                                                         parent=self.root)
                if not nuevo_nombre_base or nuevo_nombre_base == os.path.splitext(nombre)[0]:
                    return
                nuevo_nombre_arch = nuevo_nombre_base + ext
                nueva_ruta = os.path.join(carpeta, nuevo_nombre_arch)
                if os.path.exists(nueva_ruta):
                    messagebox.showerror('Error', f'Ya existe "{nuevo_nombre_arch}".')
                    return
                os.rename(ruta_original, nueva_ruta)

            self._contenido_refrescar()

        def _contenido_eliminar(self):
            nivel, nombre, item_id = self._contenido_obtener_seleccion()
            if nivel is None:
                return

            if nivel == 'raiz':
                tipo_display = self.ct_tree.item(item_id, 'values')[0]
                confirmar = messagebox.askyesno('Eliminar',
                                                f'¿Eliminar "{nombre}" y todo su contenido?\n\n'
                                                f'Tipo: {tipo_display}\n'
                                                f'Esta acción no se puede deshacer.')
                if not confirmar:
                    return
                ruta = os.path.join(MEDIA_PATH, nombre)
                try:
                    import shutil
                    shutil.rmtree(ruta)
                except Exception as e:
                    messagebox.showerror('Error', f'No se pudo eliminar: {e}')
                    return
                try:
                    conn = conectar_db()
                    cursor = conn.cursor()
                    cursor.execute('DELETE FROM content_metadata WHERE serie = ?', (nombre,))
                    conn.commit()
                    conn.close()
                except Exception:
                    pass

            elif nivel == 'temporada':
                serie_nombre = self.ct_tree.item(self.ct_tree.parent(item_id), 'text')
                confirmar = messagebox.askyesno('Eliminar temporada',
                                                f'¿Eliminar la temporada "{nombre}" de "{serie_nombre}"?\n'
                                                f'Se borrarán todos los vídeos dentro.')
                if not confirmar:
                    return
                ruta = os.path.join(MEDIA_PATH, serie_nombre, nombre)
                try:
                    import shutil
                    shutil.rmtree(ruta)
                except Exception as e:
                    messagebox.showerror('Error', f'No se pudo eliminar: {e}')
                    return

            elif nivel == 'video':
                parent_id = self.ct_tree.parent(item_id)
                if not parent_id:
                    return
                padre_tipo = self.ct_tree.item(parent_id, 'values')[0]
                if 'Temporada' in padre_tipo:
                    serie_nombre = self.ct_tree.item(self.ct_tree.parent(parent_id), 'text')
                    temporada_nombre = self.ct_tree.item(parent_id, 'text')
                    ruta_arch = os.path.join(MEDIA_PATH, serie_nombre, temporada_nombre, nombre)
                else:
                    ruta_arch = os.path.join(MEDIA_PATH, self.ct_tree.item(parent_id, 'text'), nombre)

                confirmar = messagebox.askyesno('Eliminar vídeo',
                                                f'¿Eliminar el archivo "{nombre}"?')
                if not confirmar:
                    return
                try:
                    os.remove(ruta_arch)
                except Exception as e:
                    messagebox.showerror('Error', f'No se pudo eliminar: {e}')
                    return

            self._contenido_refrescar()

        def _contenido_menu_contextual(self, event):
            item = self.ct_tree.identify_row(event.y)
            if not item:
                return
            self.ct_tree.selection_set(item)

            menu = tk.Menu(self.root, tearoff=0)
            valores = self.ct_tree.item(item, 'values')
            tipo_display = valores[0] if valores else ''

            es_pelicula = tipo_display in (t('bib_pelicula'), '🎬 Película', '🎬 Movie')
            es_serie = tipo_display in (t('bib_serie'), '📺 Serie', '📺 Series')

            if es_pelicula or es_serie:
                menu.add_command(label=t('bib_editar_metadata'), command=self._contenido_editar_metadata)
                menu.add_command(label=t('bib_renombrar'), command=self._contenido_renombrar)
                menu.add_separator()
                menu.add_command(label=t('bib_eliminar'), command=self._contenido_eliminar)
            elif tipo_display in (t('bib_temporada'), '📁 Temporada', '📁 Season'):
                menu.add_command(label=t('bib_anadir_video'), command=self._contenido_anadir_video)
                menu.add_command(label=t('bib_renombrar'), command=self._contenido_renombrar)
                menu.add_separator()
                menu.add_command(label=t('bib_eliminar'), command=self._contenido_eliminar)
            elif tipo_display in (t('bib_video'), '🎬 Vídeo', '🎬 Video'):
                menu.add_command(label=t('bib_renombrar'), command=self._contenido_renombrar)
                menu.add_separator()
                menu.add_command(label=t('bib_eliminar'), command=self._contenido_eliminar)

            try:
                menu.tk_popup(event.x_root, event.y_root)
            finally:
                menu.grab_release()

        def _build_tab_streamings(self, parent):
            ttk.Label(parent, text=t('str_title'),
                      font=('Segoe UI', 14, 'bold')).pack(pady=(0, 6))
            ttk.Label(parent, text=t('str_desc'),
                      foreground='#888').pack(pady=(0, 10))

            tree_frame = ttk.Frame(parent)
            tree_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 8))

            self.st_tree = ttk.Treeview(tree_frame, columns=('url', 'tipo'), show='tree headings', selectmode='browse', height=12)
            self.st_tree.heading('#0', text=t('str_titulo'))
            self.st_tree.heading('url', text=t('str_url_principal'))
            self.st_tree.heading('tipo', text=t('str_tipo'))
            self.st_tree.column('#0', width=200)
            self.st_tree.column('url', width=320)
            self.st_tree.column('tipo', width=80, anchor=tk.CENTER)

            scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.st_tree.yview)
            self.st_tree.configure(yscrollcommand=scrollbar.set)
            self.st_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

            btn_frame = ttk.Frame(parent)
            btn_frame.pack(fill=tk.X, pady=(0, 4))

            ttk.Button(btn_frame, text=t('str_anadir'), command=self._stream_anadir).pack(side=tk.LEFT, padx=(0, 4))
            ttk.Button(btn_frame, text=t('str_editar'), command=self._stream_editar).pack(side=tk.LEFT, padx=(0, 4))
            ttk.Button(btn_frame, text=t('str_eliminar'), command=self._stream_eliminar).pack(side=tk.LEFT, padx=(0, 4))
            ttk.Button(btn_frame, text=t('str_subir'), command=self._stream_subir).pack(side=tk.LEFT, padx=(0, 4))
            ttk.Button(btn_frame, text=t('str_bajar'), command=self._stream_bajar).pack(side=tk.LEFT, padx=(0, 4))
            ttk.Button(btn_frame, text=t('str_refrescar'), command=self._stream_refrescar).pack(side=tk.RIGHT)

            self._stream_refrescar()

        def _stream_refrescar(self):
            for item in self.st_tree.get_children():
                self.st_tree.delete(item)
            streams = cargar_streams()
            for i, s in enumerate(streams):
                titulo = s.get('titulo', t('str_sin_titulo'))
                url = s.get('url', s.get('urls', [''])[0] if s.get('urls') else '')
                tipo = s.get('tipo', 'iframe')
                tipo_display = {'hls': t('str_hls'), 'video': t('str_video'), 'iframe': t('str_iframe')}.get(tipo, tipo)
                self.st_tree.insert('', tk.END, iid=str(i), text=titulo, values=(url, tipo_display))

        def _stream_dialogo(self, titulo_ventana='Stream', stream=None):
            dialogo = tk.Toplevel(self.root)
            dialogo.title(titulo_ventana)
            dialogo.geometry('500x280')
            dialogo.resizable(False, False)
            dialogo.transient(self.root)
            dialogo.grab_set()

            frame = ttk.Frame(dialogo, padding=15)
            frame.pack(fill=tk.BOTH, expand=True)

            ttk.Label(frame, text=t('str_titulo') + ':', font=('Segoe UI', 9, 'bold')).pack(anchor=tk.W)
            titulo_var = tk.StringVar(value=stream.get('titulo', '') if stream else '')
            ttk.Entry(frame, textvariable=titulo_var, width=55).pack(fill=tk.X, pady=(0, 8))

            ttk.Label(frame, text=t('str_url_label'), font=('Segoe UI', 9, 'bold')).pack(anchor=tk.W)
            url_var = tk.StringVar(value=stream.get('url', '') if stream else '')
            ttk.Entry(frame, textvariable=url_var, width=55).pack(fill=tk.X, pady=(0, 8))

            ttk.Label(frame, text=t('str_backups'), font=('Segoe UI', 9, 'bold')).pack(anchor=tk.W)
            backups_text = tk.Text(frame, height=3, width=55, wrap=tk.WORD)
            backups_text.pack(fill=tk.X, pady=(0, 8))
            if stream:
                urls = stream.get('urls', [])
                url_principal = stream.get('url', '')
                backups = [u for u in urls if u != url_principal]
                if backups:
                    backups_text.insert('1.0', '\n'.join(backups))

            row = ttk.Frame(frame)
            row.pack(fill=tk.X, pady=(0, 8))
            ttk.Label(row, text=t('meta_tipo')).pack(side=tk.LEFT)
            tipo_var = tk.StringVar(value=stream.get('tipo', 'hls') if stream else 'hls')
            ttk.Combobox(row, textvariable=tipo_var, values=['hls', 'iframe', 'video'],
                         state='readonly', width=10).pack(side=tk.LEFT, padx=(5, 0))

            resultado = [None]

            def aceptar():
                titulo_val = titulo_var.get().strip()
                url_val = url_var.get().strip()
                if not titulo_val or not url_val:
                    messagebox.showerror(t('msg_error'), t('msg_titulo_url_obligatorios'), parent=dialogo)
                    return
                backups_raw = backups_text.get('1.0', tk.END).strip()
                backups_lista = [b.strip() for b in backups_raw.split('\n') if b.strip()]
                urls_total = [url_val] + backups_lista
                resultado[0] = {
                    'titulo': titulo_val,
                    'url': url_val,
                    'urls': urls_total,
                    'tipo': tipo_var.get(),
                }
                dialogo.destroy()

            btn_frame = ttk.Frame(frame)
            btn_frame.pack(pady=(10, 0))
            ttk.Button(btn_frame, text=t('meta_aceptar'), command=aceptar).pack(side=tk.LEFT, padx=5)
            ttk.Button(btn_frame, text=t('meta_cancelar'), command=dialogo.destroy).pack(side=tk.LEFT, padx=5)

            dialogo.protocol("WM_DELETE_WINDOW", dialogo.destroy)
            self.root.wait_window(dialogo)
            return resultado[0]

        def _stream_anadir(self):
            resultado = self._stream_dialogo(t('str_anadir_stream'))
            if not resultado:
                return
            streams = cargar_streams()
            streams.append(resultado)
            guardar_streams(streams)
            self._stream_refrescar()

        def _stream_editar(self):
            sel = self.st_tree.selection()
            if not sel:
                messagebox.showinfo(t('msg_info'), t('msg_selecciona_stream_editar'))
                return
            idx = int(sel[0])
            streams = cargar_streams()
            if idx >= len(streams):
                return
            resultado = self._stream_dialogo(t('str_editar_stream'), streams[idx])
            if not resultado:
                return
            streams[idx] = resultado
            guardar_streams(streams)
            self._stream_refrescar()

        def _stream_eliminar(self):
            sel = self.st_tree.selection()
            if not sel:
                messagebox.showinfo(t('msg_info'), t('msg_selecciona_stream_eliminar'))
                return
            idx = int(sel[0])
            streams = cargar_streams()
            if idx >= len(streams):
                return
            titulo = streams[idx].get('titulo', 'Sin título')
            if not messagebox.askyesno(t('msg_info'), t('msg_eliminar_stream').format(titulo=titulo)):
                return
            streams.pop(idx)
            guardar_streams(streams)
            self._stream_refrescar()

        def _stream_subir(self):
            sel = self.st_tree.selection()
            if not sel:
                return
            idx = int(sel[0])
            if idx == 0:
                return
            streams = cargar_streams()
            streams[idx], streams[idx - 1] = streams[idx - 1], streams[idx]
            guardar_streams(streams)
            self._stream_refrescar()
            self.st_tree.selection_set(str(idx - 1))

        def _stream_bajar(self):
            sel = self.st_tree.selection()
            if not sel:
                return
            idx = int(sel[0])
            streams = cargar_streams()
            if idx >= len(streams) - 1:
                return
            streams[idx], streams[idx + 1] = streams[idx + 1], streams[idx]
            guardar_streams(streams)
            self._stream_refrescar()
            self.st_tree.selection_set(str(idx + 1))

        def guardar_y_cerrar(self):
            try:
                puerto = int(self.port_var.get())
                if puerto < 1 or puerto > 65535:
                    raise ValueError
            except ValueError:
                messagebox.showerror('Error', 'El puerto debe ser un número entre 1 y 65535.')
                return

            data = leer_config()
            data['boton_apagar_visible'] = self.apagar_var.get()
            data['boton_apagar_todo_visible'] = self.apagar_todo_var.get()
            data['puerto'] = puerto
            data['api_habilitada'] = self.api_var.get()
            guardar_config(data)

            omdb_key = self.omdb_api_var.get().strip()
            guardar_env({'OMDB_API_KEY': omdb_key})
            self.root.destroy()

        def _set_status(self, texto, color='green'):
            self.status_label.config(text=texto, foreground=color)
            self.root.update_idletasks()

        def exportar_media(self):
            if not os.path.exists(MEDIA_PATH) or not os.listdir(MEDIA_PATH):
                messagebox.showinfo('Exportar', 'La carpeta media/ está vacía o no existe.')
                return

            destino = filedialog.asksaveasfilename(
                title='Exportar media',
                defaultextension='.fkmedia',
                filetypes=[('FlaskCast Media', '*.fkmedia')],
                initialfile='data.fkmedia'
            )
            if not destino:
                return

            self._set_status('Exportando... esto puede tardar.', '#ff8800')
            self.root.config(cursor='watch')

            def _hilo():
                try:
                    with py7zr.SevenZipFile(destino, 'w') as archive:
                        for raiz, dirs, archivos in os.walk(MEDIA_PATH):
                            for archivo in archivos:
                                ruta_abs = os.path.join(raiz, archivo)
                                ruta_rel = os.path.relpath(ruta_abs, os.path.dirname(MEDIA_PATH))
                                archive.write(ruta_abs, ruta_rel)
                    self.root.after(0, lambda: self._set_status(f'Exportado: {os.path.basename(destino)}'))
                    self.root.after(0, lambda: messagebox.showinfo('Exportar', f'Exportado correctamente.\n{destino}'))
                except Exception as e:
                    self.root.after(0, lambda: self._set_status(f'Error: {e}', 'red'))
                finally:
                    self.root.after(0, lambda: self.root.config(cursor=''))

            threading.Thread(target=_hilo, daemon=True).start()

        def importar_media(self):
            archivo = filedialog.askopenfilename(
                title='Importar media',
                filetypes=[('FlaskCast Media', '*.fkmedia')]
            )
            if not archivo:
                return

            if not os.path.exists(MEDIA_PATH):
                os.makedirs(MEDIA_PATH, exist_ok=True)

            confirmar = messagebox.askyesno(
                'Importar media',
                'Se extraerán los vídeos en data/media/.\n'
                'Si ya existen archivos con el mismo nombre, se sobreescribirán.\n\n¿Continuar?'
            )
            if not confirmar:
                return

            self._set_status('Importando... esto puede tardar.', '#ff8800')
            self.root.config(cursor='watch')

            def _hilo():
                try:
                    with py7zr.SevenZipFile(archivo, 'r') as archive:
                        archive.extractall(path=os.path.dirname(MEDIA_PATH))
                    self.root.after(0, lambda: self._set_status('Importado correctamente.'))
                    self.root.after(0, lambda: messagebox.showinfo('Importar', 'Importado correctamente.'))
                except Exception as e:
                    self.root.after(0, lambda: self._set_status(f'Error: {e}', 'red'))
                finally:
                    self.root.after(0, lambda: self.root.config(cursor=''))

            threading.Thread(target=_hilo, daemon=True).start()

        def run(self):
            self.root.mainloop()

    ConfigAdmin().run()


if __name__ == '__main__':
    cli()
