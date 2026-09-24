# -*- mode: python ; coding: utf-8 -*-
# Especificación de PyInstaller para FlaskCast (un solo binario, Windows/Linux).
# Uso:
#   Windows: build_windows.bat   (o: python -m PyInstaller --noconfirm --clean --distpath bin FlaskCast.spec)
#   Linux:   build_linux.sh      (o: python3 -m PyInstaller --noconfirm --clean --distpath bin FlaskCast.spec)

import importlib.util
import os
import sys


def _icono_windows():
    """Solo Windows incorpora icono en el binario; se genera al vuelo desde logo.png."""
    try:
        ruta = os.path.join(SPECPATH, 'generar_icono.py')
        spec = importlib.util.spec_from_file_location('_generar_icono', ruta)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod.generar()
    except Exception as e:
        print('[spec] No se pudo generar el icono (se continua sin el):', e)
        return None


_icon = _icono_windows() if sys.platform.startswith('win') else None

a = Analysis(
    ['app.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        ('templates', 'templates'),
        ('static', 'static'),
    ],
    hiddenimports=[
        'waitress',
        'static_ffmpeg',
        'config_admin',
        'py7zr',
        'tkinter',
        'tkinter.messagebox',
        'tkinter.filedialog',
        'tkinter.simpledialog',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['gunicorn', 'pytest'],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='FlaskCast',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=_icon,
)