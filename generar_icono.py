# -*- coding: utf-8 -*-
"""Genera icon.ico a partir de static/logo.png.

Uso:
    python generar_icono.py            # Crea/actualiza icon.ico en la raiz

Si Pillow esta instalado genera iconos de 16 a 256 px. Si no, embebe el PNG
completo en el contenedor ICO (formato PNG-en-ICO compatible con Windows).
"""

import io
import os
import struct

BASE = os.path.dirname(os.path.abspath(__file__))
LOGO = os.path.join(BASE, 'static', 'logo.png')
SALIDA = os.path.join(BASE, 'icon.ico')


def _con_pillow():
    from PIL import Image
    img = Image.open(LOGO).convert('RGBA')
    tamanos = [16, 24, 32, 48, 64, 128, 256]
    datos = []
    for t in tamanos:
        mini = img.copy()
        mini.thumbnail((t, t), Image.LANCZOS)
        buf = io.BytesIO()
        mini.save(buf, 'PNG')
        datos.append((t, buf.getvalue()))

    with open(SALIDA, 'wb') as f:
        f.write(b'\x00\x00')
        f.write(struct.pack('<H', 1))
        f.write(struct.pack('<H', len(datos)))
        offset = 6 + 16 * len(datos)
        for t, enc in datos:
            tam_ico = 0 if t == 256 else t
            f.write(struct.pack('<BBBBHHII', tam_ico, tam_ico, 0, 0, 1, 32, len(enc), offset))
            offset += len(enc)
        for _, enc in datos:
            f.write(enc)
    return SALIDA


def _sin_pillow():
    with open(LOGO, 'rb') as f:
        png = f.read()
    with open(SALIDA, 'wb') as f:
        f.write(b'\x00\x00')
        f.write(struct.pack('<H', 1))
        f.write(struct.pack('<H', 1))
        f.write(struct.pack('<BBBBHHII', 0, 0, 0, 0, 1, 32, len(png), 22))
        f.write(png)
    return SALIDA


def generar():
    """Devuelve la ruta a icon.ico (creandolo si hace falta) o None si no hay logo."""
    if not os.path.exists(LOGO):
        return None
    if os.path.exists(SALIDA):
        return SALIDA
    try:
        return _con_pillow()
    except Exception:
        try:
            return _sin_pillow()
        except Exception as e:
            print('[generar_icono] No se pudo crear icon.ico:', e)
            return None


if __name__ == '__main__':
    ruta = generar()
    if ruta:
        print(f'Icono generado: {ruta}')
    else:
        print('No se pudo generar el icono (falta static/logo.png).')