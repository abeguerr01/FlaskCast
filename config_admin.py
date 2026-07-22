import json
import os
import sys
import argparse
import threading

DIRECTORIO_RAIZ = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(DIRECTORIO_RAIZ, 'data', 'config.json')
MEDIA_PATH = os.path.join(DIRECTORIO_RAIZ, 'data', 'media')


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

    args = parser.parse_args()

    tiene_args = any([args.status, args.toggle_server, args.toggle_all, args.api, args.port, args.export, args.importar])

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


def gui():
    import tkinter as tk
    from tkinter import ttk, messagebox, filedialog
    import py7zr

    class ConfigAdmin:
        def __init__(self):
            self.root = tk.Tk()
            self.root.title('Administración de FlaskCast')
            self.root.geometry('420x520')
            self.root.resizable(False, False)

            logo_path = os.path.join(DIRECTORIO_RAIZ, 'static', 'logo.png')
            if os.path.exists(logo_path):
                logo = tk.PhotoImage(file=logo_path)
                self.root.iconphoto(True, logo)

            cfg = leer_config()

            main = ttk.Frame(self.root, padding=20)
            main.pack(fill=tk.BOTH, expand=True)

            ttk.Label(main, text='Administración de FlaskCast',
                      font=('Segoe UI', 14, 'bold')).pack(pady=(0, 12))

            self.apagar_var = tk.BooleanVar(value=cfg.get('boton_apagar_visible', False))
            self.apagar_todo_var = tk.BooleanVar(value=cfg.get('boton_apagar_todo_visible', False))
            self.api_var = tk.BooleanVar(value=cfg.get('api_habilitada', False))

            frame_check = ttk.Frame(main)
            frame_check.pack(fill=tk.X, pady=5)
            ttk.Checkbutton(frame_check, text='Mostrar botón "Apagar Servidor"',
                            variable=self.apagar_var).pack(anchor=tk.W)
            ttk.Checkbutton(frame_check, text='Mostrar botón "Apagar Todo"',
                            variable=self.apagar_todo_var).pack(anchor=tk.W)

            ttk.Separator(main, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=8)

            ttk.Checkbutton(main, text='Habilitar API REST',
                            variable=self.api_var).pack(anchor=tk.W, pady=4)
            ttk.Label(main, text='Activa la API para gestionar vídeos externamente.',
                      foreground='#888', font=('Segoe UI', 8)).pack(anchor=tk.W)

            ttk.Separator(main, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=8)

            frame_port = ttk.Frame(main)
            frame_port.pack(fill=tk.X)
            ttk.Label(frame_port, text='Puerto:').pack(side=tk.LEFT)
            self.port_var = tk.StringVar(value=str(cfg.get('puerto', 5000)))
            port_entry = ttk.Entry(frame_port, textvariable=self.port_var, width=10)
            port_entry.pack(side=tk.LEFT, padx=(10, 0))

            ttk.Separator(main, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=8)

            ttk.Label(main, text='Gestión de contenido',
                      font=('Segoe UI', 10, 'bold')).pack(anchor=tk.W, pady=(0, 6))

            media_frame = ttk.Frame(main)
            media_frame.pack(fill=tk.X, pady=4)
            ttk.Button(media_frame, text='Exportar media (.fkmedia)',
                       command=self.exportar_media).pack(side=tk.LEFT, padx=(0, 5))
            ttk.Button(media_frame, text='Importar media (.fkmedia)',
                       command=self.importar_media).pack(side=tk.LEFT)

            self.status_label = ttk.Label(main, text='', foreground='green')
            self.status_label.pack(pady=(8, 0))

            ttk.Separator(main, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=8)

            btn_frame = ttk.Frame(main)
            btn_frame.pack()
            ttk.Button(btn_frame, text='Guardar y Cerrar', command=self.guardar_y_cerrar).pack(side=tk.LEFT, padx=5)
            ttk.Button(btn_frame, text='Salir', command=self.root.destroy).pack(side=tk.LEFT, padx=5)

        def guardar_y_cerrar(self):
            try:
                puerto = int(self.port_var.get())
                if puerto < 1 or puerto > 65535:
                    raise ValueError
            except ValueError:
                messagebox.showerror('Error', 'El puerto debe ser un número entre 1 y 65535.')
                return

            data = {
                'boton_apagar_visible': self.apagar_var.get(),
                'boton_apagar_todo_visible': self.apagar_todo_var.get(),
                'puerto': puerto,
                'api_habilitada': self.api_var.get()
            }
            guardar_config(data)
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
