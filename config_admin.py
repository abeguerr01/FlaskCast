import json
import os
import sys
import argparse
import fnmatch
import hashlib
import shutil
import tempfile
import threading
import time
import urllib.request
import urllib.parse
import urllib.error
import sqlite3

def _es_frozen():
    return getattr(sys, 'frozen', False)


def _base_dir():
    if _es_frozen():
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def _recursos_dir():
    if _es_frozen():
        return sys._MEIPASS
    return _base_dir()


DIRECTORIO_RAIZ = _base_dir()
RECURSOS_DIR = _recursos_dir()
DATA_PATH = os.path.join(DIRECTORIO_RAIZ, 'data')
CONFIG_PATH = os.path.join(DATA_PATH, 'config.json')
MEDIA_PATH = os.path.join(DATA_PATH, 'media')
ENV_PATH = os.path.join(DIRECTORIO_RAIZ, '.env')
DB_PATH = os.path.join(DATA_PATH, 'flaskcast.db')
LIVE_STREAMS_PATH = os.path.join(DATA_PATH, 'live_streams.json')
OMDB_API_URL = 'https://www.omdbapi.com/'

ARCHIVOS_IGNORADOS = ('flaskcast.db-wal', 'flaskcast.db-shm', 'flaskcast.db-journal')

MODOS_COMPRESION = ('rapido', 'compactado')
BACKUP_COMPRESION_POR_DEFECTO = 'rapido'
BACKUP_EXCLUIR_POR_DEFECTO = ['.thumbnails']
BACKUP_EXCLUIR_MB_POR_DEFECTO = 0
ALCANCES = ('todo', 'datos', 'media')

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
            '\n'
            'Copias de seguridad de data/:\n'
            '  python config_admin.py --export b.fkmedia      Exporta data/ a un .fkmedia\n'
            '  python config_admin.py --import b.fkmedia      Restaura data/ desde un .fkmedia\n'
            '  python config_admin.py --list b.fkmedia        Muestra el contenido sin extraer\n'
            '  python config_admin.py --verificar b.fkmedia   Comprueba el archivo y su sha256\n'
            '  python config_admin.py --export b --compresion rapido\n'
            '  python config_admin.py --export b --exclude .thumbnails --exclude "TEMPORADA 4"\n'
            '  python config_admin.py --export b --exclude-mb 500\n'
            '  python config_admin.py --import b --alcance datos --rollback\n'
        )
    )
    parser.add_argument('--status', action='store_true', help='Muestra la configuración actual')
    parser.add_argument('--toggle-server', action='store_true', help='Activa/desactiva el botón "Apagar Servidor"')
    parser.add_argument('--toggle-all', action='store_true', help='Activa/desactiva el botón "Apagar Todo"')
    parser.add_argument('--api', action='store_true', help='Activa/desactiva la API REST')
    parser.add_argument('--port', type=int, metavar='PUERTO', help='Cambia el puerto del servidor')
    parser.add_argument('--auth', action='store_true', help='Activa/desactiva la autenticación')
    parser.add_argument('--auth-password', type=str, metavar='CONTRASEÑA', help='Establece la contraseña de autenticación')
    parser.add_argument('--export', type=str, metavar='ARCHIVO', help='Exporta la carpeta data/ a un archivo .fkmedia')
    parser.add_argument('--import', type=str, metavar='ARCHIVO', dest='importar', help='Restaura la carpeta data/ desde un archivo .fkmedia')
    parser.add_argument('--omdb-key', type=str, metavar='API_KEY', help='Guarda la API key de OMDb')
    parser.add_argument('--list', type=str, metavar='ARCHIVO', dest='listar', help='Muestra el contenido de un .fkmedia sin extraerlo')
    parser.add_argument('--verificar', type=str, metavar='ARCHIVO', dest='verificar', help='Comprueba que un .fkmedia se abre y su sha256 cuadra')
    parser.add_argument('--compresion', choices=MODOS_COMPRESION, metavar='MODO',
                        help='rapido: no comprime (ideal para vídeo). compactado: LZMA2, archivo más pequeño')
    parser.add_argument('--exclude', action='append', metavar='PATRON', dest='excluir',
                        help='Excluye del export lo que case con el patrón (repetible, ej: .thumbnails, *.mkv, /media/Serie)')
    parser.add_argument('--exclude-mb', type=int, metavar='MB', dest='excluir_mb',
                        help='Excluye del export los archivos de más de MB megabytes')
    parser.add_argument('--alcance', choices=ALCANCES, default='todo',
                        help='Qué restaura --import: todo, datos (ajustes y BD) o media (vídeos)')
    parser.add_argument('--rollback', action='store_true',
                        help='Antes de restaurar, copia los ajustes, streams y la base de datos actuales a un .fkmedia (no los vídeos, así que tarda segundos)')
    parser.add_argument('--solo-datos', action='store_true',
                        help='Con --export solo guarda ajustes, streams y base de datos (no los vídeos)')

    args = parser.parse_args()

    tiene_args = any([args.status, args.toggle_server, args.toggle_all, args.api, args.port, args.auth,
                      args.auth_password, args.export, args.importar, args.omdb_key, args.listar,
                      args.verificar, args.compresion, args.excluir, args.excluir_mb, args.rollback])

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
        print(f'  Autenticación:    {"ON" if cfg.get("auth_enabled") else "OFF"}')
        print(f'  Puerto:            {cfg.get("puerto", 5000)}')
        omdb_key = leer_env().get('OMDB_API_KEY', '')
        print(f'  OMDb API Key:      {"Configurada" if omdb_key else "No configurada"}')
        op = _leer_opciones_backup(cfg)
        print(f'  Compresión:        {op["compresion"]}')
        print(f'  Exclusiones:       {", ".join(op["patrones"]) or "ninguna"}')
        print(f'  Excluir >MB:       {op["excluir_mb"] or "no"}')
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

    if args.auth:
        nuevo = toggle(cfg.get('auth_enabled', False))
        cfg['auth_enabled'] = nuevo
        cambios.append(f'Autenticación -> {"ON" if nuevo else "OFF"}')

    if args.auth_password is not None:
        cfg['auth_password'] = args.auth_password
        cambios.append(f'Contraseña de autenticación -> actualizada')

    if args.port is not None:
        if args.port < 1 or args.port > 65535:
            print('Error: el puerto debe ser un número entre 1 y 65535.')
            sys.exit(1)
        cfg['puerto'] = args.port
        cambios.append(f'Puerto -> {args.port}')

    if args.omdb_key:
        guardar_env({'OMDB_API_KEY': args.omdb_key.strip()})
        cambios.append(f'OMDb API Key -> guardada en .env')

    if args.compresion:
        cfg['backup_compresion'] = args.compresion
        cambios.append(f'Modo de compresión -> {args.compresion}')

    if args.excluir:
        patrones = [p.strip() for p in args.excluir if p.strip()]
        cfg['backup_excluir'] = patrones
        cambios.append(f'Exclusiones -> {", ".join(patrones)}')

    if args.excluir_mb is not None:
        if args.excluir_mb < 0:
            print('Error: --exclude-mb no puede ser negativo.')
            sys.exit(1)
        cfg['backup_excluir_mb'] = args.excluir_mb
        cambios.append(f'Excluir archivos de más de -> {args.excluir_mb} MB')

    if cambios:
        guardar_config(cfg)
        print('Cambios aplicados:')
        for c in cambios:
            print(f'  -> {c}')

    if args.listar:
        print()
        _previsualizar_cli(args.listar)
        return

    if args.verificar:
        print()
        _verificar_cli(args.verificar)
        return

    if args.export:
        print()
        exportar_media_cli(args.export, _leer_opciones_backup(cfg), solo_datos=args.solo_datos)

    if args.importar:
        print()
        try:
            importar_media_cli(args.importar, alcance=args.alcance, rollback=args.rollback,
                               solo_datos=args.solo_datos)
        except ValueError as e:
            print(f'Error: {e}')
            sys.exit(1)


def _snapshot_db(destino):
    """Copia consistente de la BD vía API de backup de SQLite (segura con el servidor en marcha)."""
    origen = sqlite3.connect(DB_PATH, timeout=10)
    try:
        destino_conn = sqlite3.connect(destino)
        try:
            origen.backup(destino_conn)
        finally:
            destino_conn.close()
    finally:
        origen.close()


class _Cancelado(Exception):
    """Operación cancelada por el usuario."""


def _py7zr():
    try:
        import py7zr
    except ImportError:
        raise RuntimeError('Falta la dependencia "py7zr". Instálala con: pip install py7zr')
    return py7zr


def _filtros_compresion(modo):
    py7zr = _py7zr()
    if modo == 'compactado':
        return [{'id': py7zr.FILTER_LZMA2, 'preset': 1}]
    return [{'id': py7zr.FILTER_COPY}]


def _leer_opciones_backup(cfg=None):
    if cfg is None:
        cfg = {}
        if os.path.exists(CONFIG_PATH):
            try:
                cfg = leer_config()
            except (OSError, ValueError):
                cfg = {}
    patrones = cfg.get('backup_excluir')
    if not isinstance(patrones, list) or not patrones:
        patrones = list(BACKUP_EXCLUIR_POR_DEFECTO)
    patrones = [str(p).strip().replace('\\', '/') for p in patrones if str(p).strip()]
    try:
        excluir_mb = int(cfg.get('backup_excluir_mb', BACKUP_EXCLUIR_MB_POR_DEFECTO) or 0)
    except (TypeError, ValueError):
        excluir_mb = 0
    modo = cfg.get('backup_compresion', BACKUP_COMPRESION_POR_DEFECTO)
    if modo not in MODOS_COMPRESION:
        modo = BACKUP_COMPRESION_POR_DEFECTO
    return {'patrones': patrones, 'excluir_mb': max(0, excluir_mb), 'compresion': modo}


def _excluir_relativo(rel, patrones, excluir_mb=0, tamano=None):
    """rel puede venir como 'data/media/X' o 'media/X'; los patrones son relativos a data/."""
    rel = rel.replace('\\', '/')
    if rel == 'data' or rel.startswith('data/'):
        rel = rel[len('data/'):]
    partes = rel.split('/')
    for patron in patrones:
        if patron.startswith('/'):
            destino = patron.lstrip('/')
            if rel == destino or rel.startswith(destino + '/'):
                return True
            continue
        if patron in partes[:-1] or patron == partes[-1]:
            return True
        if fnmatch.fnmatch(rel, patron) or fnmatch.fnmatch(partes[-1], patron):
            return True
    if excluir_mb and tamano is not None and tamano > excluir_mb * 1024 * 1024:
        return True
    return False


def _escanear_data(opciones, cancelacion=None, solo_datos=False):
    """Recorre data/ sin descender en lo excluido. Devuelve archivos, carpetas, bytes y excluidos."""
    raiz = os.path.abspath(DATA_PATH)
    db_absoluta = os.path.abspath(DB_PATH)
    archivos, carpetas, total, excluidos = [], [], 0, []
    patrones = opciones['patrones']
    excluir_mb = opciones['excluir_mb']
    raiz_rel = os.path.relpath(raiz, DIRECTORIO_RAIZ).replace('\\', '/')

    for carpeta_raiz, dirs, files in os.walk(raiz):
        if cancelacion is not None and cancelacion.is_set():
            raise _Cancelado()
        rel_carpeta = os.path.relpath(carpeta_raiz, DIRECTORIO_RAIZ).replace('\\', '/')
        carpetas.append((carpeta_raiz, rel_carpeta))
        keepers = []
        for carpeta in sorted(dirs):
            if solo_datos:
                continue
            rel = f'{rel_carpeta}/{carpeta}'
            if _excluir_relativo(rel, patrones):
                excluidos.append(rel)
            else:
                keepers.append(carpeta)
        dirs[:] = keepers
        if solo_datos and not keepers and files == []:
            continue
        for archivo in sorted(files):
            if archivo in ARCHIVOS_IGNORADOS or archivo.endswith('.fkmedia') or archivo.endswith('.parcial'):
                continue
            ruta_abs = os.path.join(carpeta_raiz, archivo)
            if os.path.abspath(ruta_abs) == db_absoluta:
                continue
            rel = f'{rel_carpeta}/{archivo}'
            try:
                tamano = os.path.getsize(ruta_abs)
            except OSError:
                tamano = 0
            if _excluir_relativo(rel, patrones, excluir_mb, tamano):
                excluidos.append(rel)
                continue
            archivos.append((ruta_abs, rel, tamano))
            total += tamano

    if solo_datos:
        carpetas = [(raiz, raiz_rel)]
        archivos = [a for a in archivos if '/media/' not in a[1]]
        total = sum(a[2] for a in archivos)
    return archivos, carpetas, total, excluidos


def _sha256(ruta, bloque=4 * 1024 * 1024):
    h = hashlib.sha256()
    with open(ruta, 'rb') as f:
        for trozo in iter(lambda: f.read(bloque), b''):
            h.update(trozo)
    return h.hexdigest()


def _ruta_sha256(archivo):
    return os.path.splitext(archivo)[0] + '.sha256'


def _escribir_sha256(archivo, digest):
    with open(_ruta_sha256(archivo), 'w', encoding='utf-8') as f:
        f.write(f'{digest}  {os.path.basename(archivo)}\n')


def _leer_sha256(archivo):
    ruta = _ruta_sha256(archivo)
    if not os.path.isfile(ruta):
        return None
    try:
        with open(ruta, 'r', encoding='utf-8') as f:
            return f.read().split()[0]
    except (OSError, IndexError):
        return None


def _verificar_fkmedia(archivo, esperado=None):
    """Abre el .fkmedia y comprueba que se lee y que cuadra el número de entradas."""
    py7zr = _py7zr()
    if not os.path.isfile(archivo):
        raise ValueError(f'El archivo {archivo} no existe.')
    with py7zr.SevenZipFile(archivo, 'r') as archive:
        nombres = [n.replace('\\', '/') for n in archive.getnames()]
    return {
        'ruta': os.path.abspath(archivo),
        'bytes': os.path.getsize(archivo),
        'entradas': len(nombres),
        'esperado': esperado,
        'ok': esperado is None or len(nombres) == esperado,
    }


def _verificar_integridad(archivo):
    """Comprueba el .sha256 si existe y que el archivo se pueda abrir."""
    info = _verificar_fkmedia(archivo)
    esperado = _leer_sha256(archivo)
    if esperado is None:
        info['sha256'] = None
        info['sha256_ok'] = None
    else:
        info['sha256'] = esperado
        info['sha256_ok'] = _sha256(archivo) == esperado
    return info


def _validar_exportacion(destino):
    """Normaliza la extensión y rechaza destinos dentro de data/. Devuelve la ruta absoluta."""
    if not os.path.isdir(DATA_PATH) or not os.listdir(DATA_PATH):
        raise ValueError('La carpeta data/ está vacía o no existe.')
    if not destino.lower().endswith('.fkmedia'):
        destino += '.fkmedia'
    destino = os.path.abspath(destino)
    raiz = os.path.abspath(DATA_PATH)
    if destino == raiz or destino.startswith(raiz + os.sep):
        raise ValueError('El archivo de destino no puede guardarse dentro de data/.')
    return destino


def _crear_progreso_extraccion(cancelacion, progreso):
    py7zr = _py7zr()
    from py7zr.callbacks import ExtractCallback

    estado = {'bytes': 0, 'cancelado': False}

    class Progreso(ExtractCallback):
        def report_start_preparation(self):
            pass

        def report_start(self, processing_file_path, processing_bytes):
            pass

        def report_update(self, decompressed_bytes):
            try:
                estado['bytes'] += int(decompressed_bytes)
            except (TypeError, ValueError):
                return
            if cancelacion is not None and cancelacion.is_set():
                estado['cancelado'] = True
                raise _Cancelado()
            if progreso:
                progreso(estado['bytes'])

        def report_end(self, processing_file_path, wrote_bytes):
            pass

        def report_warning(self, message):
            pass

        def report_postprocess(self):
            pass

    return Progreso()


def _exportar_fkmedia(destino, opciones, cancelacion=None, progreso=None, solo_datos=False):
    """Comprime data/ en un .fkmedia. La DB va como snapshot atómico. Escribe en .parcial y renombra al final."""
    py7zr = _py7zr()
    destino = os.path.abspath(destino)
    archivos, carpetas, total, excluidos = _escanear_data(opciones, cancelacion, solo_datos)

    parcial = destino + '.parcial'
    temp_dir = tempfile.mkdtemp(prefix='flaskcast_fkmedia_')
    snapshot = None
    try:
        if os.path.exists(DB_PATH):
            snapshot = os.path.join(temp_dir, 'flaskcast.db')
            _snapshot_db(snapshot)
            total += os.path.getsize(snapshot)

        with py7zr.SevenZipFile(parcial, 'w', filters=_filtros_compresion(opciones['compresion'])) as archive:
            for abs_carpeta, rel_carpeta in carpetas:
                archive.write(abs_carpeta, rel_carpeta)
            hechos = 0
            total_archivos = len(archivos) + (1 if snapshot else 0)
            for indice, (ruta_abs, rel, tamano) in enumerate(archivos, 1):
                if cancelacion is not None and cancelacion.is_set():
                    raise _Cancelado()
                archive.write(ruta_abs, rel)
                hechos += tamano
                if progreso:
                    progreso(hechos, total, indice, total_archivos)
            if snapshot:
                rel_db = os.path.relpath(DB_PATH, DIRECTORIO_RAIZ).replace('\\', '/')
                archive.write(snapshot, rel_db)
                hechos += os.path.getsize(snapshot)
                if progreso:
                    progreso(hechos, total, total_archivos, total_archivos)

        info = _verificar_fkmedia(parcial, esperado=len(archivos) + len(carpetas) + (1 if snapshot else 0))
        if not info['ok']:
            raise RuntimeError(
                f'La verificación falló: se esperaban {info["esperado"]} entradas y hay {info["entradas"]}.'
            )
        os.makedirs(os.path.dirname(destino) or '.', exist_ok=True)
        os.replace(parcial, destino)
        info['ruta'] = destino
        info['sha256'] = _sha256(destino)
        _escribir_sha256(destino, info['sha256'])
        info['bytes_origen'] = total
        info['excluidos'] = excluidos
        info['compresion'] = opciones['compresion']
        return info
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
        if os.path.exists(parcial):
            try:
                os.remove(parcial)
            except OSError:
                pass


def _prefijo_archivo(nombres):
    """Los .fkmedia antiguos guardaban 'media/...'; los nuevos guardan 'data/...'."""
    for nombre in nombres:
        limpio = nombre.replace('\\', '/')
        if limpio == 'data' or limpio.startswith('data/'):
            return 'data/'
    return ''


def _listar_fkmedia(archivo):
    """Vista previa del contenido de un .fkmedia sin extraerlo."""
    py7zr = _py7zr()
    if not os.path.isfile(archivo):
        raise ValueError(f'El archivo {archivo} no existe.')
    entradas = []
    with py7zr.SevenZipFile(archivo, 'r') as archive:
        for info in archive.list():
            nombre = info.filename.replace('\\', '/')
            entradas.append({
                'nombre': nombre,
                'es_dir': bool(info.is_directory),
                'bytes': info.uncompressed or 0,
            })
    archivos = [e for e in entradas if not e['es_dir']]
    nombres = [e['nombre'] for e in entradas]
    prefijo = _prefijo_archivo(nombres)
    con_db = any(n.endswith('flaskcast.db') for n in nombres)
    resumen = {
        'ruta': os.path.abspath(archivo),
        'bytes': os.path.getsize(archivo),
        'entradas': len(entradas),
        'archivos': len(archivos),
        'carpetas': len(entradas) - len(archivos),
        'bytes_descomprimidos': sum(e['bytes'] for e in archivos),
        'prefijo': prefijo,
        'tiene_db': con_db,
        'tiene_config': any(n.endswith('config.json') for n in nombres),
        'tiene_streams': any(n.endswith('live_streams.json') for n in nombres),
        'tiene_media': any('/media/' in n for n in nombres),
        'antiguo': prefijo == '',
        'entradas_detalle': entradas,
    }
    resumen['sha256'] = _leer_sha256(archivo)
    return resumen


def _alcance_a_targets(alcance, entradas, prefijo):
    """None = todo. Si no, la lista exacta de entradas a extraer (nunca directorios sueltos)."""
    if alcance == 'todo':
        return None
    base_media = prefijo + 'media'
    if alcance == 'media':
        return [e['nombre'] for e in entradas
                if e['nombre'] == base_media or e['nombre'].startswith(base_media + '/')]
    return [e['nombre'] for e in entradas
            if not e['es_dir']
            and e['nombre'].startswith(prefijo)
            and e['nombre'] != prefijo.rstrip('/')
            and e['nombre'][len(prefijo):].count('/') == 0]


def _validar_extraccion(temp_dir, entradas, objetivos):
    """Comprueba que se extrajo todo lo esperado antes de tocar data/."""
    faltantes = []
    for entrada in entradas:
        limpio = entrada['nombre']
        if objetivos is not None and not any(
                limpio == o or limpio.startswith(o.rstrip('/') + '/') or o.rstrip('/') == limpio
                for o in objetivos):
            continue
        if not os.path.exists(os.path.join(temp_dir, *limpio.split('/'))):
            faltantes.append(limpio)
            if len(faltantes) > 20:
                break
    if faltantes:
        raise RuntimeError(
            'La extracción está incompleta, no se ha tocado data/. Faltan:\n  '
            + '\n  '.join(faltantes)
        )
    db = os.path.join(temp_dir, 'data', 'flaskcast.db')
    if os.path.isfile(db):
        try:
            conn = sqlite3.connect(db)
            conn.execute('PRAGMA integrity_check').fetchone()
            conn.close()
        except sqlite3.Error as e:
            raise RuntimeError(f'La base de datos extraída está dañada, no se ha tocado data/.\n{e}')


def _commit_extraccion(temp_dir, destino_raiz):
    """Mueve lo extraído a su sitio. Renombrados en el mismo volumen, sin copiar datos."""
    movidos = 0
    origen_raiz = os.path.join(temp_dir, os.path.basename(destino_raiz.rstrip(os.sep)))
    if not os.path.isdir(origen_raiz):
        origen_raiz = temp_dir
    for carpeta_raiz, dirs, files in os.walk(origen_raiz):
        for carpeta in dirs:
            origen = os.path.join(carpeta_raiz, carpeta)
            destino = os.path.join(carpeta_raiz[len(origen_raiz):].lstrip(os.sep), carpeta)
            destino = os.path.join(destino_raiz, destino) if destino else os.path.join(destino_raiz, carpeta)
            os.makedirs(destino, exist_ok=True)
            movidos += 1
        for archivo in files:
            origen = os.path.join(carpeta_raiz, archivo)
            destino = os.path.join(carpeta_raiz[len(origen_raiz):].lstrip(os.sep), archivo)
            destino = os.path.join(destino_raiz, destino)
            os.makedirs(os.path.dirname(destino), exist_ok=True)
            if os.path.abspath(origen) == os.path.abspath(destino):
                movidos += 1
                continue
            os.replace(origen, destino)
            movidos += 1
    for sufijo in ('-wal', '-shm'):
        obsoleto = DB_PATH + sufijo
        if os.path.exists(obsoleto):
            try:
                os.remove(obsoleto)
            except OSError:
                pass
    return movidos


def _importar_fkmedia(archivo, alcance='todo', cancelacion=None, progreso=None, directorio_temporal=None):
    """Extrae a un temporal, valida y solo entonces mueve a data/. Devuelve el resumen."""
    py7zr = _py7zr()
    if not os.path.isfile(archivo):
        raise ValueError(f'El archivo {archivo} no existe.')

    previo = _listar_fkmedia(archivo)
    necesita = previo['bytes_descomprimidos']
    libre = shutil.disk_usage(DIRECTORIO_RAIZ).free
    if necesita > libre * 0.9:
        raise RuntimeError(
            f'No hay espacio suficiente para restaurar de forma segura.\n'
            f'Necesitas al menos {necesita / 1073741824:.1f} GB libres y hay {libre / 1073741824:.1f} GB.\n'
            f'Libera espacio o borra alguna copia anterior.'
        )

    temp_dir = directorio_temporal or tempfile.mkdtemp(prefix='.restore_', dir=DIRECTORIO_RAIZ)
    try:
        with py7zr.SevenZipFile(archivo, 'r') as archive:
            entradas = [
                {'nombre': i.filename.replace('\\', '/'), 'es_dir': bool(i.is_directory)}
                for i in archive.list()
            ]
            prefijo = _prefijo_archivo([e['nombre'] for e in entradas])
            destino_raiz = DIRECTORIO_RAIZ if prefijo else os.path.dirname(MEDIA_PATH)
            objetivos = _alcance_a_targets(alcance, entradas, prefijo)
            movidos = 0
            if objetivos is not None:
                if not objetivos:
                    raise RuntimeError(
                        f'El archivo no contiene nada del alcance "{alcance}", no se ha tocado data/.')
                cb = _crear_progreso_extraccion(cancelacion, progreso)
                archive.extract(temp_dir, targets=objetivos, recursive=True, callback=cb)
            else:
                cb = _crear_progreso_extraccion(cancelacion, progreso)
                archive.extractall(path=temp_dir, callback=cb)

        _validar_extraccion(temp_dir, entradas, objetivos)
        movidos = _commit_extraccion(temp_dir, destino_raiz)
        return {
            'ruta': os.path.abspath(archivo),
            'raiz': destino_raiz,
            'alcance': alcance,
            'entradas': movidos,
            'bytes': previo['bytes_descomprimidos'],
            'sha256_previo': previo['sha256'],
        }
    finally:
        if directorio_temporal is None:
            shutil.rmtree(temp_dir, ignore_errors=True)


def _formato_bytes(num):
    if not num:
        return '0 B'
    for unidad in ('B', 'KB', 'MB', 'GB', 'TB'):
        if num < 1024 or unidad == 'TB':
            return f'{num:.1f} {unidad}' if unidad != 'B' else f'{int(num)} B'
        num /= 1024.0
    return f'{num:.1f} TB'


def _barra_progreso(hechos, total, tag):
    if not total:
        return f'  {tag}'
    porcentaje = min(100.0, hechos * 100.0 / total)
    relleno = int(porcentaje / 2)
    barra = '#' * relleno + '-' * (50 - relleno)
    return f'  [{barra}] {porcentaje:5.1f}%  {_formato_bytes(hechos)}/{_formato_bytes(total)}  {tag}'


class _ConsolaProgreso:
    def __init__(self):
        self.inicio = time.time()
        self.ultimo = 0.0

    def __call__(self, hechos, total, archivos, archivos_totales):
        ahora = time.time()
        if ahora - self.ultimo < 0.2 and archivos != archivos_totales:
            return
        self.ultimo = ahora
        transcurrido = max(0.001, ahora - self.inicio)
        restante = (total - hechos) / (hechos / transcurrido) if hechos > 0 else 0
        eta = time.strftime('%H:%M:%S', time.gmtime(restante)) if restante > 0 else '--:--:--'
        print('\r' + _barra_progreso(hechos, total, f'{archivos}/{archivos_totales} ETA {eta}') + '   ', end='', flush=True)


def exportar_media_cli(destino, opciones=None, solo_datos=False):
    opciones = opciones or _leer_opciones_backup()
    destino = _validar_exportacion(destino)
    print(f'Exportando data/ -> {destino}')
    print(f'  Modo: {opciones["compresion"]}  Excluir: {", ".join(opciones["patrones"]) or "nada"}'
          + (f'  >{opciones["excluir_mb"]}MB' if opciones["excluir_mb"] else ''))
    progreso = _ConsolaProgreso()
    try:
        info = _exportar_fkmedia(destino, opciones, progreso=progreso, solo_datos=solo_datos)
    except _Cancelado:
        print('\nExportación cancelada. No se ha dejado ningún archivo a medias.')
        return None
    print()
    print(f'  Archivo:   {info["ruta"]}')
    print(f'  Checksum:  {info["ruta"]}.sha256 (sha256)')
    print(f'  Tamaño:    {_formato_bytes(info["bytes"])} de {_formato_bytes(info["bytes_origen"])} origen')
    print(f'  Entradas:  {info["entradas"]} (verificadas)')
    if info['excluidos']:
        print(f'  Excluidos: {len(info["excluidos"])} elementos')
    return info


def _previsualizar_cli(archivo):
    info = _listar_fkmedia(archivo)
    print(f'Archivo:    {info["ruta"]}')
    print(f'Tamaño:     {_formato_bytes(info["bytes"])}')
    print(f'Entradas:   {info["entradas"]} ({info["archivos"]} archivos, {info["carpetas"]} carpetas)')
    if info['bytes_descomprimidos']:
        print(f'Descomprime: ~{_formato_bytes(info["bytes_descomprimidos"])}')
    print(f'Formato:    {"antiguo (media/...)" if info["antiguo"] else "actual (data/...)"}')
    print('Contenido:')
    for clave, etiqueta in (('tiene_config', 'data/config.json'),
                            ('tiene_db', 'data/flaskcast.db'),
                            ('tiene_streams', 'data/live_streams.json'),
                            ('tiene_media', 'data/media/')):
        if info[clave]:
            print(f'  [si] {etiqueta}')
    if info['sha256']:
        print(f'Checksum:   {info["sha256"]} (lado a lado)')
    else:
        print('Checksum:   sin archivo .sha256')
    return info


def _verificar_cli(archivo):
    info = _verificar_integridad(archivo)
    print(f'Archivo:   {info["ruta"]}')
    print(f'Tamaño:    {_formato_bytes(info["bytes"])}')
    print(f'Entradas:  {info["entradas"]}')
    print(f'Abre:      si')
    if info['sha256_ok'] is None:
        print('SHA256:    sin archivo .sha256, no se puede comprobar')
    else:
        print(f'SHA256:    {"correcto" if info["sha256_ok"] else "NO COINCIDE"}')
    if not info['sha256_ok']:
        print('El archivo puede estar dañado o haber cambiado.')
    return info


def importar_media_cli(archivo, alcance='todo', rollback=False, solo_datos=False):
    if alcance not in ALCANCES:
        raise ValueError(f'Alcance no válido: {alcance}. Usa: {", ".join(ALCANCES)}.')
    info = _previsualizar_cli(archivo)
    print()

    destino_rollback = None
    if rollback:
        sello = time.strftime('%Y%m%d-%H%M%S')
        destino_rollback = os.path.join(
            os.path.dirname(os.path.abspath(archivo)),
            f'flaskcast-antes-de-restaurar-{sello}.fkmedia')
        print('Creando copia de seguridad previa (ajustes, streams y base de datos)...')
        print(f'  -> {destino_rollback}')
        exportar_media_cli(destino_rollback, solo_datos=True)
        print()

    alcance_txt = {'todo': 'toda la carpeta data/', 'datos': 'solo ajustes y base de datos',
                   'media': 'solo data/media/'}[alcance]
    print(f'Restaurando {alcance_txt} desde {archivo} ...')
    progreso = _ConsolaProgreso()
    try:
        resumen = _importar_fkmedia(archivo, alcance=alcance, progreso=progreso)
    except _Cancelado:
        print('\nRestauración cancelada. data/ no se ha modificado.')
        return None
    except RuntimeError as e:
        print('\n' + str(e))
        return None
    print()
    print(f'  Restaurado: {resumen["entradas"]} elementos en {resumen["raiz"]}\\data')
    if destino_rollback:
        print(f'  Copia previa: {destino_rollback}')
    return resumen


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

    meta_path = os.path.join(ruta_carpeta, '_meta.json')
    meta_existente = {}
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
    ubicacion = ''
    if os.path.exists(meta_path):
        try:
            with open(meta_path, 'r', encoding='utf-8') as f:
                meta = json.load(f)
            ubicacion = meta.get('ubicacion', '').strip()
        except Exception:
            pass
    ruta_videos = ubicacion if ubicacion and os.path.isdir(ubicacion) else ruta
    formatos_video = ('.mp4', '.webm', '.ogg', '.avi', '.mkv')
    try:
        items = os.listdir(ruta_videos)
    except OSError:
        return 'serie'
    subcarpetas = [i for i in items if os.path.isdir(os.path.join(ruta_videos, i)) and not i.startswith('.')]
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

            ttk.Label(frame, text=t('meta_ubicacion'), font=('Segoe UI', 9, 'bold')).pack(anchor=tk.W)
            self.ubicacion_var = tk.StringVar(value=meta.get('ubicacion', '') if meta else '')
            ttk.Entry(frame, textvariable=self.ubicacion_var, width=50).pack(fill=tk.X, pady=(0, 2))
            ttk.Label(frame, text=t('meta_ubicacion_desc'), foreground='#888', font=('Segoe UI', 8)).pack(anchor=tk.W, pady=(0, 4))

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
                'ubicacion': self.ubicacion_var.get().strip(),
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
                logo_path = os.path.join(RECURSOS_DIR, 'static', 'logo.png')
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

            ttk.Label(parent, text=t('gen_auth'),
                      font=('Segoe UI', 10, 'bold')).pack(anchor=tk.W, pady=(0, 4))

            self.auth_var = tk.BooleanVar(value=cfg.get('auth_enabled', False))
            auth_row = ttk.Frame(parent)
            auth_row.pack(fill=tk.X, pady=2)
            ttk.Checkbutton(auth_row, text=t('gen_auth_habilitar'),
                             variable=self.auth_var,
                             command=self._toggle_auth_fields).pack(side=tk.LEFT)
            ttk.Label(auth_row, text=t('gen_auth_contrasena')).pack(side=tk.LEFT, padx=(20, 0))
            self.auth_password_var = tk.StringVar(value=cfg.get('auth_password', ''))
            self.auth_password_entry = ttk.Entry(auth_row, textvariable=self.auth_password_var, width=25, show='*')
            self.auth_password_entry.pack(side=tk.LEFT, padx=(8, 0))

            ttk.Label(parent, text=t('gen_auth_desc'),
                      foreground='#888', font=('Segoe UI', 8)).pack(anchor=tk.W)

            ttk.Separator(parent, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=8)

            ttk.Label(parent, text=t('gen_copia_titulo'),
                      font=('Segoe UI', 10, 'bold')).pack(anchor=tk.W, pady=(0, 6))

            opciones = _leer_opciones_backup(cfg)
            comp_frame = ttk.LabelFrame(parent, text=t('gen_compresion'), padding=8)
            comp_frame.pack(fill=tk.X, pady=2)
            self.compresion_var = tk.StringVar(value=opciones['compresion'])
            ttk.Radiobutton(comp_frame, text=t('gen_comp_rapido'), value='rapido',
                            variable=self.compresion_var).pack(anchor=tk.W)
            ttk.Label(comp_frame, text=t('gen_comp_rapido_desc'), foreground='#888',
                      font=('Segoe UI', 8), wraplength=560).pack(anchor=tk.W, padx=(18, 0))
            ttk.Radiobutton(comp_frame, text=t('gen_comp_compactado'), value='compactado',
                            variable=self.compresion_var).pack(anchor=tk.W, pady=(6, 0))
            ttk.Label(comp_frame, text=t('gen_comp_compactado_desc'), foreground='#888',
                      font=('Segoe UI', 8), wraplength=560).pack(anchor=tk.W, padx=(18, 0))

            exc_frame = ttk.LabelFrame(parent, text=t('gen_exclusiones'), padding=8)
            exc_frame.pack(fill=tk.X, pady=(6, 2))
            self.excluir_var = tk.StringVar(value=', '.join(opciones['patrones']))
            ttk.Entry(exc_frame, textvariable=self.excluir_var).pack(fill=tk.X)
            ttk.Label(exc_frame, text=t('gen_exclusiones_desc'), foreground='#888',
                      font=('Segoe UI', 8), wraplength=560).pack(anchor=tk.W, pady=(4, 0))
            self.excluir_mb_var = tk.StringVar(value=str(opciones['excluir_mb'] or ''))
            mb_frame = ttk.Frame(exc_frame)
            mb_frame.pack(fill=tk.X, pady=(6, 0))
            ttk.Label(mb_frame, text=t('gen_excluir_mb')).pack(side=tk.LEFT)
            ttk.Entry(mb_frame, textvariable=self.excluir_mb_var, width=8).pack(side=tk.LEFT, padx=(6, 0))
            ttk.Label(mb_frame, text='MB', foreground='#888').pack(side=tk.LEFT, padx=(4, 0))

            media_frame = ttk.Frame(parent)
            media_frame.pack(fill=tk.X, pady=(8, 0))
            ttk.Button(media_frame, text=t('gen_exportar'),
                       command=self.exportar_media).pack(side=tk.LEFT, padx=(0, 5))
            ttk.Button(media_frame, text=t('gen_importar'),
                       command=self.importar_media).pack(side=tk.LEFT, padx=(0, 5))
            ttk.Button(media_frame, text=t('gen_ver_contenido'),
                       command=self.ver_contenido).pack(side=tk.LEFT)

            self.status_label = ttk.Label(parent, text='', foreground='green', wraplength=600)
            self.status_label.pack(pady=(8, 0))

            prog_frame = ttk.Frame(parent)
            prog_frame.pack(fill=tk.X, pady=(4, 0))
            self.barra_progreso = ttk.Progressbar(prog_frame, mode='determinate', length=400)
            self.barra_progreso.pack(side=tk.LEFT, fill=tk.X, expand=True)
            self.cancel_event = threading.Event()
            self.btn_cancelar = ttk.Button(prog_frame, text=t('gen_cancelar'),
                                           command=self._cancelar, state='disabled')
            self.btn_cancelar.pack(side=tk.RIGHT, padx=(8, 0))

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

        def _toggle_auth_fields(self):
            if self.auth_var.get():
                self.auth_password_entry.config(state='normal')
            else:
                self.auth_password_entry.config(state='disabled')

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

                ubicacion = meta.get('ubicacion', '').strip()
                ruta_videos = ubicacion if ubicacion and os.path.isdir(ubicacion) else ruta
                if ubicacion:
                    info_str += ' 📁'

                nodo_raiz = self.ct_tree.insert('', tk.END, text=nombre, values=(display_tipo, info_str), open=True)

                if tipo == 'serie':
                    if os.path.isdir(ruta_videos):
                        subcarpetas = [i for i in sorted(os.listdir(ruta_videos))
                                       if os.path.isdir(os.path.join(ruta_videos, i)) and not i.startswith('.')]
                        for sub in subcarpetas:
                            ruta_sub = os.path.join(ruta_videos, sub)
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
                    vids = [f for f in os.listdir(ruta_videos)
                            if os.path.isfile(os.path.join(ruta_videos, f)) and f.lower().endswith(FORMATOS_VIDEO)]
                    for v in sorted(vids):
                        tam = os.path.getsize(os.path.join(ruta_videos, v))
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

            if 'Temporada' in tipo_display:
                return 'temporada', texto, item_id

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

            tiene_ubicacion = bool(meta.get('ubicacion', '').strip())
            if not tiene_ubicacion and meta.get('tipo') == 'serie':
                num_temp = meta.get('temporadas', 1)
                if num_temp >= 1:
                    for i in range(1, num_temp + 1):
                        os.makedirs(os.path.join(ruta, f'Season {i}'), exist_ok=True)

            self._contenido_refrescar()
            tipo_texto = 'Película' if meta.get('tipo') == 'pelicula' else 'Serie'
            extra = f' con {num_temp} temporada(s)' if meta.get('tipo') == 'serie' and not tiene_ubicacion and num_temp >= 1 else ''
            ubicacion_msg = f'\nVideos en: {meta["ubicacion"]}' if tiene_ubicacion else ''
            messagebox.showinfo('Éxito', f'{tipo_texto} "{nombre}" creada{extra}.{ubicacion_msg}\nAhora puedes añadir vídeos con "+Añadir Vídeo".')

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
            data = leer_config()
            data['boton_apagar_visible'] = self.apagar_var.get()
            data['boton_apagar_todo_visible'] = self.apagar_todo_var.get()
            data['api_habilitada'] = self.api_var.get()
            data['auth_enabled'] = self.auth_var.get()
            data['auth_password'] = self.auth_password_var.get()
            data['backup_compresion'] = self.compresion_var.get()
            data['backup_excluir'] = [p.strip() for p in self.excluir_var.get().split(',') if p.strip()]
            try:
                data['backup_excluir_mb'] = max(0, int(self.excluir_mb_var.get().strip() or 0))
            except ValueError:
                data['backup_excluir_mb'] = 0
            guardar_config(data)

            omdb_key = self.omdb_api_var.get().strip()
            guardar_env({'OMDB_API_KEY': omdb_key})
            self.root.destroy()

        def _set_status(self, texto, color='green'):
            self.status_label.config(text=texto, foreground=color)
            self.root.update_idletasks()

        def _opciones_desde_panel(self):
            patrones = [p.strip() for p in self.excluir_var.get().split(',') if p.strip()]
            try:
                mb = max(0, int(self.excluir_mb_var.get().strip() or 0))
            except ValueError:
                mb = 0
            return {'patrones': patrones, 'excluir_mb': mb, 'compresion': self.compresion_var.get()}

        def _cancelar(self):
            self.cancel_event.set()
            self._set_status(t('gen_cancelando'), '#ff8800')

        def _iniciar_progreso(self, mensaje):
            self.cancel_event.clear()
            self.barra_progreso.config(value=0)
            self.btn_cancelar.config(state='normal')
            self.root.config(cursor='watch')
            self._set_status(mensaje, '#ff8800')

        def _fin_progreso(self):
            self.btn_cancelar.config(state='disabled')
            self.root.config(cursor='')

        def _progreso_export(self, etiqueta):
            inicio = time.time()
            ultimo = [0.0]

            def _callback(hechos, total, archivos, archivos_totales):
                ahora = time.time()
                if ahora - ultimo[0] < 0.15 and archivos != archivos_totales:
                    return
                ultimo[0] = ahora
                porcentaje = min(100.0, hechos * 100.0 / total) if total else 100.0
                transcurrido = max(0.001, ahora - inicio)
                restante = (total - hechos) / (hechos / transcurrido) if hechos > 0 else 0
                eta = time.strftime('%H:%M:%S', time.gmtime(restante)) if restante > 0 else '--:--'
                texto = (f'{etiqueta} {porcentaje:.1f}%  '
                         f'{_formato_bytes(hechos)} de {_formato_bytes(total)}  '
                         f'({archivos}/{archivos_totales})  ETA {eta}')
                self.root.after(0, lambda: self.barra_progreso.config(value=porcentaje))
                self.root.after(0, lambda: self._set_status(texto, '#ff8800'))

            return _callback

        def ver_contenido(self):
            archivo = filedialog.askopenfilename(
                title=t('gen_ver_contenido'),
                filetypes=[('FlaskCast Data', '*.fkmedia')])
            if not archivo:
                return
            try:
                info = _listar_fkmedia(archivo)
            except Exception as e:
                messagebox.showerror(t('gen_ver_contenido'), f'{e}')
                return
            lineas = [
                t('gen_ver_ruta').format(ruta=info['ruta']),
                t('gen_ver_tamano').format(tamano=_formato_bytes(info['bytes'])),
                t('gen_ver_entradas').format(
                    entradas=info['entradas'], archivos=info['archivos'], carpetas=info['carpetas']),
            ]
            if info['bytes_descomprimidos']:
                lineas.append(t('gen_ver_descomprime').format(
                    total=_formato_bytes(info['bytes_descomprimidos'])))
            lineas.append('')
            lineas.append(t('gen_ver_formato') + ': ' +
                          (t('gen_ver_formato_antiguo') if info['antiguo'] else t('gen_ver_formato_actual')))
            for clave, etiqueta in (('tiene_config', 'data/config.json'),
                                    ('tiene_db', 'data/flaskcast.db'),
                                    ('tiene_streams', 'data/live_streams.json'),
                                    ('tiene_media', 'data/media/')):
                if info[clave]:
                    lineas.append('  [✓] ' + etiqueta)
            lineas.append('')
            if info['sha256']:
                lineas.append('SHA-256: ' + info['sha256'][:32] + '...')
                verificada = _verificar_integridad(archivo)
                lineas.append(t('gen_ver_sha_ok') if verificada['sha256_ok']
                              else t('gen_ver_sha_mal'))
            else:
                lineas.append(t('gen_ver_sha_no'))
            messagebox.showinfo(t('gen_ver_contenido'), '\n'.join(lineas))

        def _dialogo_restaurar(self, archivo):
            """Toplevel con vista previa, alcance a restaurar y copia de seguridad previa."""
            dialogo = tk.Toplevel(self.root)
            dialogo.title(t('gen_importar'))
            dialogo.transient(self.root)
            dialogo.resizable(False, False)
            marco = ttk.Frame(dialogo, padding=15)
            marco.pack(fill=tk.BOTH, expand=True)

            try:
                info = _listar_fkmedia(archivo)
            except Exception as e:
                messagebox.showerror(t('gen_importar'), f'{e}')
                dialogo.destroy()
                return None

            ttk.Label(marco, text=os.path.basename(archivo), font=('Segoe UI', 11, 'bold')).pack(anchor=tk.W)
            ttk.Label(marco, text=archivo, foreground='#888', font=('Segoe UI', 8),
                      wraplength=460).pack(anchor=tk.W, pady=(0, 8))
            resumen = (f"{_formato_bytes(info['bytes'])}  ·  {info['entradas']} entradas  ·  "
                       + (t('gen_ver_formato_antiguo') if info['antiguo'] else t('gen_ver_formato_actual')))
            ttk.Label(marco, text=resumen, font=('Segoe UI', 9)).pack(anchor=tk.W, pady=(0, 10))

            alcance_var = tk.StringVar(value='todo')
            ttk.Label(marco, text=t('gen_alcance')).pack(anchor=tk.W)
            for valor, etiqueta in (('todo', t('gen_alcance_todo')),
                                    ('datos', t('gen_alcance_datos')),
                                    ('media', t('gen_alcance_media'))):
                ttk.Radiobutton(marco, text=etiqueta, value=valor,
                                variable=alcance_var).pack(anchor=tk.W)

            rollback_var = tk.BooleanVar(value=True)
            ttk.Checkbutton(marco, text=t('gen_rollback'), variable=rollback_var).pack(anchor=tk.W, pady=(10, 0))
            ttk.Label(marco, text=t('gen_rollback_desc'), foreground='#888', font=('Segoe UI', 8),
                      wraplength=460).pack(anchor=tk.W, padx=(20, 0))

            ttk.Label(marco, text=t('gen_restaurar_aviso'), foreground='#c00', font=('Segoe UI', 8),
                      wraplength=460).pack(anchor=tk.W, pady=(10, 0))

            resultado = {}

            def _aceptar():
                resultado['alcance'] = alcance_var.get()
                resultado['rollback'] = rollback_var.get()
                dialogo.destroy()

            botones = ttk.Frame(marco)
            botones.pack(pady=(14, 0))
            ttk.Button(botones, text=t('gen_restaurar'), command=_aceptar).pack(side=tk.LEFT, padx=5)
            ttk.Button(botones, text=t('gen_salir'), command=dialogo.destroy).pack(side=tk.LEFT, padx=5)
            dialogo.grab_set()
            self.root.wait_window(dialogo)
            return resultado

        def exportar_media(self):
            sello = time.strftime('%Y-%m-%d')
            destino = filedialog.asksaveasfilename(
                title=t('gen_exportar'),
                defaultextension='.fkmedia',
                filetypes=[('FlaskCast Data', '*.fkmedia')],
                initialfile=f'flaskcast-{sello}.fkmedia',
                parent=self.root)
            if not destino:
                return

            opciones = self._opciones_desde_panel()
            try:
                destino = _validar_exportacion(destino)
            except ValueError as e:
                messagebox.showwarning(t('gen_exportar'), str(e))
                return

            self._iniciar_progreso(t('gen_exportando'))
            progreso = self._progreso_export(t('gen_exportando'))

            def _hilo():
                try:
                    info = _exportar_fkmedia(destino, opciones,
                                             cancelacion=self.cancel_event, progreso=progreso)
                    resumen = (t('gen_exportado').format(ruta=info['ruta'])
                               + '\n' + t('gen_checksum').format(ruta=info['ruta'] + '.sha256')
                               + '\n' + t('gen_export_tamano').format(
                                   tamano=_formato_bytes(info['bytes']),
                                   origen=_formato_bytes(info['bytes_origen']))
                               + '\n' + t('gen_export_entradas').format(entradas=info['entradas']))
                    if info['excluidos']:
                        resumen += '\n' + t('gen_export_excluidos').format(cantidad=len(info['excluidos']))
                    self.root.after(0, lambda: self.barra_progreso.config(value=100))
                    self.root.after(0, lambda: self._set_status(t('gen_exportado').format(ruta=info['ruta'])))
                    self.root.after(0, lambda: messagebox.showinfo(t('gen_exportar'), resumen))
                except _Cancelado:
                    self.root.after(0, lambda: self._set_status(t('gen_export_cancelado'), '#888'))
                except Exception as e:
                    self.root.after(0, lambda: self._set_status(f'{e}', 'red'))
                    self.root.after(0, lambda: messagebox.showerror(t('gen_exportar'), f'{e}'))
                finally:
                    self.root.after(0, self._fin_progreso)

            threading.Thread(target=_hilo, daemon=True).start()

        def importar_media(self):
            archivo = filedialog.askopenfilename(
                title=t('gen_importar'),
                filetypes=[('FlaskCast Data', '*.fkmedia')],
                parent=self.root)
            if not archivo:
                return

            decision = self._dialogo_restaurar(archivo)
            if not decision:
                return

            rollback = decision['rollback']
            destino_rollback = None
            if rollback:
                sello = time.strftime('%Y%m%d-%H%M%S')
                destino_rollback = os.path.join(
                    os.path.dirname(os.path.abspath(archivo)),
                    f'flaskcast-antes-de-restaurar-{sello}.fkmedia')
                self._iniciar_progreso(t('gen_rollback_en_curso').format(ruta=destino_rollback))
                progreso = self._progreso_export(t('gen_rollback_en_curso'))

                def _hilo_rollback():
                    try:
                        opciones = self._opciones_desde_panel()
                        info = _exportar_fkmedia(destino_rollback, opciones, solo_datos=True,
                                                 cancelacion=self.cancel_event, progreso=progreso)
                        if self.cancel_event.is_set():
                            raise _Cancelado()
                        self.root.after(0, lambda: self._iniciar_progreso(t('gen_restaurando')))
                        self._restaurar(archivo, decision['alcance'], info['ruta'])
                    except _Cancelado:
                        self.root.after(0, lambda: self._set_status(t('gen_cancelado'), '#888'))
                        self.root.after(0, self._fin_progreso)
                    except Exception as e:
                        self.root.after(0, lambda: self._set_status(f'{e}', 'red'))
                        self.root.after(0, lambda: messagebox.showerror(t('gen_importar'), f'{e}'))
                        self.root.after(0, self._fin_progreso)

                threading.Thread(target=_hilo_rollback, daemon=True).start()
                return

            self._iniciar_progreso(t('gen_restaurando'))
            threading.Thread(target=lambda: self._restaurar(
                archivo, decision['alcance'], None), daemon=True).start()

        def _restaurar(self, archivo, alcance, ruta_rollback):
            try:
                resumen = _importar_fkmedia(archivo, alcance=alcance, cancelacion=self.cancel_event)
                mensaje = t('gen_restaurado').format(entradas=resumen['entradas'])
                if ruta_rollback:
                    mensaje += '\n\n' + t('gen_rollback_guardado').format(ruta=ruta_rollback)
                mensaje += '\n\n' + t('gen_reiniciar')
                self.root.after(0, lambda: self.barra_progreso.config(value=100))
                self.root.after(0, lambda: self._set_status(t('gen_restaurado').format(entradas=resumen['entradas'])))
                self.root.after(0, lambda: messagebox.showwarning(t('gen_importar'), mensaje))
            except _Cancelado:
                self.root.after(0, lambda: self._set_status(t('gen_restaurar_cancelado'), '#888'))
            except Exception as e:
                self.root.after(0, lambda: self._set_status(f'{e}', 'red'))
                self.root.after(0, lambda: messagebox.showerror(t('gen_importar'), f'{e}'))
            finally:
                self.root.after(0, self._fin_progreso)

        def run(self):
            self.root.mainloop()

    ConfigAdmin().run()


if __name__ == '__main__':
    cli()
