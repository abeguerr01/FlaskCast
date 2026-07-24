import json
import os
import sys
import argparse
import threading
import urllib.request
import urllib.parse
import urllib.error

DIRECTORIO_RAIZ = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(DIRECTORIO_RAIZ, 'data', 'config.json')
MEDIA_PATH = os.path.join(DIRECTORIO_RAIZ, 'data', 'media')
ENV_PATH = os.path.join(DIRECTORIO_RAIZ, '.env')
OMDB_API_URL = 'https://www.omdbapi.com/'


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


def gui():
    import tkinter as tk
    from tkinter import ttk, messagebox, filedialog
    import webbrowser
    import py7zr

    class ConfigAdmin:
        def __init__(self):
            self.root = tk.Tk()
            self.root.title('Administración de FlaskCast')
            self.root.geometry('700x700')
            self.root.resizable(True, True)

            logo_path = os.path.join(DIRECTORIO_RAIZ, 'static', 'logo.png')
            if os.path.exists(logo_path):
                logo = tk.PhotoImage(file=logo_path)
                self.root.iconphoto(True, logo)

            cfg = leer_config()

            notebook = ttk.Notebook(self.root)
            notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            tab_general = ttk.Frame(notebook, padding=15)
            tab_omdb = ttk.Frame(notebook, padding=15)
            notebook.add(tab_general, text=' General ')
            notebook.add(tab_omdb, text=' OMDb ')

            self._build_tab_general(tab_general, cfg)
            self._build_tab_omdb(tab_omdb, cfg)

        def _build_tab_general(self, parent, cfg):
            ttk.Label(parent, text='Administración de FlaskCast',
                      font=('Segoe UI', 14, 'bold')).pack(pady=(0, 12))

            self.apagar_var = tk.BooleanVar(value=cfg.get('boton_apagar_visible', False))
            self.apagar_todo_var = tk.BooleanVar(value=cfg.get('boton_apagar_todo_visible', False))
            self.api_var = tk.BooleanVar(value=cfg.get('api_habilitada', False))

            frame_check = ttk.Frame(parent)
            frame_check.pack(fill=tk.X, pady=5)
            ttk.Checkbutton(frame_check, text='Mostrar botón "Apagar Servidor"',
                            variable=self.apagar_var).pack(anchor=tk.W)
            ttk.Checkbutton(frame_check, text='Mostrar botón "Apagar Todo"',
                            variable=self.apagar_todo_var).pack(anchor=tk.W)

            ttk.Separator(parent, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=8)

            ttk.Checkbutton(parent, text='Habilitar API REST',
                            variable=self.api_var).pack(anchor=tk.W, pady=4)
            ttk.Label(parent, text='Activa la API para gestionar vídeos externamente.',
                      foreground='#888', font=('Segoe UI', 8)).pack(anchor=tk.W)

            ttk.Separator(parent, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=8)

            frame_port = ttk.Frame(parent)
            frame_port.pack(fill=tk.X)
            ttk.Label(frame_port, text='Puerto:').pack(side=tk.LEFT)
            self.port_var = tk.StringVar(value=str(cfg.get('puerto', 5000)))
            port_entry = ttk.Entry(frame_port, textvariable=self.port_var, width=10)
            port_entry.pack(side=tk.LEFT, padx=(10, 0))

            ttk.Separator(parent, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=8)

            ttk.Label(parent, text='Gestión de contenido',
                      font=('Segoe UI', 10, 'bold')).pack(anchor=tk.W, pady=(0, 6))

            media_frame = ttk.Frame(parent)
            media_frame.pack(fill=tk.X, pady=4)
            ttk.Button(media_frame, text='Exportar media (.fkmedia)',
                       command=self.exportar_media).pack(side=tk.LEFT, padx=(0, 5))
            ttk.Button(media_frame, text='Importar media (.fkmedia)',
                       command=self.importar_media).pack(side=tk.LEFT)

            self.status_label = ttk.Label(parent, text='', foreground='green')
            self.status_label.pack(pady=(8, 0))

            btn_frame = ttk.Frame(parent)
            btn_frame.pack(pady=(10, 0))
            ttk.Button(btn_frame, text='Guardar y Cerrar', command=self.guardar_y_cerrar).pack(side=tk.LEFT, padx=5)
            ttk.Button(btn_frame, text='Salir', command=self.root.destroy).pack(side=tk.LEFT, padx=5)

        def _build_tab_omdb(self, parent, cfg):
            ttk.Label(parent, text='Integración con OMDb',
                      font=('Segoe UI', 14, 'bold')).pack(pady=(0, 6))
            ttk.Label(parent, text='Obtén portadas, descripciones y valoraciones automáticamente.',
                      foreground='#888').pack(pady=(0, 10))

            api_frame = ttk.LabelFrame(parent, text=' API Key ', padding=10)
            api_frame.pack(fill=tk.X, pady=(0, 10))

            api_row = ttk.Frame(api_frame)
            api_row.pack(fill=tk.X)
            ttk.Label(api_row, text='OMDb API Key:').pack(side=tk.LEFT)
            env_data = leer_env()
            self.omdb_api_var = tk.StringVar(value=env_data.get('OMDB_API_KEY', ''))
            api_entry = ttk.Entry(api_row, textvariable=self.omdb_api_var, width=40, show='*')
            api_entry.pack(side=tk.LEFT, padx=(8, 5))

            def abrir_omdb_api():
                webbrowser.open('https://www.omdbapi.com/apikey.aspx')
            ttk.Button(api_row, text='Obtener API Key →', command=abrir_omdb_api).pack(side=tk.LEFT, padx=(0, 8))

            self.omdb_api_status = ttk.Label(api_row, text='', font=('Segoe UI', 9))
            self.omdb_api_status.pack(side=tk.LEFT)

            def validar_api():
                key = self.omdb_api_var.get().strip()
                if not key:
                    self.omdb_api_status.config(text='Introduce una API key', foreground='#ff8800')
                    return
                self.omdb_api_status.config(text='Validando...', foreground='#888')
                self.root.update_idletasks()
                def _hilo():
                    ok = omdb_validar_api_key(key)
                    def _resultado():
                        if ok:
                            self.omdb_api_status.config(text='✓ API key válida', foreground='#00cc66')
                        else:
                            self.omdb_api_status.config(text='✗ API key inválida', foreground='red')
                    self.root.after(0, _resultado)
                threading.Thread(target=_hilo, daemon=True).start()

            ttk.Button(api_row, text='Validar', command=validar_api).pack(side=tk.LEFT)

            ttk.Separator(parent, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=8)

            lib_header = ttk.Frame(parent)
            lib_header.pack(fill=tk.X, pady=(0, 6))
            ttk.Label(lib_header, text='Biblioteca detectada',
                      font=('Segoe UI', 10, 'bold')).pack(side=tk.LEFT)
            ttk.Button(lib_header, text='Refrescar', command=self._refrescar_biblioteca).pack(side=tk.RIGHT)

            list_frame = ttk.Frame(parent)
            list_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 8))

            cols = ('nombre', 'tipo', 'meta', 'portada')
            self.tree = ttk.Treeview(list_frame, columns=cols, show='headings', selectmode='extended', height=10)
            self.tree.heading('nombre', text='Carpeta')
            self.tree.heading('tipo', text='Tipo')
            self.tree.heading('meta', text='Meta')
            self.tree.heading('portada', text='Portada')
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
            ttk.Checkbutton(apply_frame, text='Descargar portada',
                            variable=self.omdb_descargar_img_var).pack(side=tk.LEFT)

            self.omdb_status_label = ttk.Label(apply_frame, text='', font=('Segoe UI', 9))
            self.omdb_status_label.pack(side=tk.LEFT, padx=(10, 0))

            ttk.Button(apply_frame, text='Aplicar OMDb a seleccionados',
                       command=self._aplicar_omdb).pack(side=tk.RIGHT)

        def _refrescar_biblioteca(self):
            for item in self.tree.get_children():
                self.tree.delete(item)
            contenido = listar_contenido_media()
            for c in contenido:
                estado_meta = '✓' if c['tiene_meta'] else '✗'
                estado_portada = '✓' if c['tiene_portada'] else '✗'
                tipo_display = '🎬 Película' if c['tipo'] == 'pelicula' else '📺 Serie'
                self.tree.insert('', tk.END, iid=c['nombre'],
                                 values=(c['nombre'], tipo_display, estado_meta, estado_portada))

        def _aplicar_omdb(self):
            api_key = self.omdb_api_var.get().strip()
            if not api_key:
                messagebox.showerror('Error', 'Introduce una API key de OMDb primero.')
                return

            seleccion = self.tree.selection()
            if not seleccion:
                messagebox.showinfo('OMDb', 'Selecciona al menos una carpeta de la biblioteca.')
                return

            descarga_poster = self.omdb_descargar_img_var.get()
            self.omdb_status_label.config(text='Procesando...', foreground='#888')
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
