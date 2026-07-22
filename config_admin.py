import json
import os
import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import py7zr

DIRECTORIO_RAIZ = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(DIRECTORIO_RAIZ, 'data', 'config.json')
MEDIA_PATH = os.path.join(DIRECTORIO_RAIZ, 'data', 'media')


def leer_config():
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)


def guardar_config(data):
    with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


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


if __name__ == '__main__':
    ConfigAdmin().run()
