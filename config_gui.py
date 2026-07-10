import json
import os
import tkinter as tk
from tkinter import ttk, messagebox

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.json')


def leer_config():
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)


def guardar_config(data):
    with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


class ConfigGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title('Configuración de FlaskCast')
        self.root.geometry('400x250')
        self.root.resizable(False, False)

        cfg = leer_config()

        main = ttk.Frame(self.root, padding=20)
        main.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main, text='Configuración de FlaskCast',
                  font=('Segoe UI', 14, 'bold')).pack(pady=(0, 15))

        self.apagar_var = tk.BooleanVar(value=cfg['boton_apagar_visible'])
        self.apagar_todo_var = tk.BooleanVar(value=cfg['boton_apagar_todo_visible'])

        frame_check = ttk.Frame(main)
        frame_check.pack(fill=tk.X, pady=5)
        ttk.Checkbutton(frame_check, text='Mostrar botón "Apagar Servidor"',
                        variable=self.apagar_var).pack(anchor=tk.W)
        ttk.Checkbutton(frame_check, text='Mostrar botón "Apagar Todo"',
                        variable=self.apagar_todo_var).pack(anchor=tk.W)

        ttk.Separator(main, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=15)

        frame_port = ttk.Frame(main)
        frame_port.pack(fill=tk.X)
        ttk.Label(frame_port, text='Puerto:').pack(side=tk.LEFT)
        self.port_var = tk.StringVar(value=str(cfg['puerto']))
        port_entry = ttk.Entry(frame_port, textvariable=self.port_var, width=10)
        port_entry.pack(side=tk.LEFT, padx=(10, 0))

        ttk.Separator(main, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=15)

        btn_frame = ttk.Frame(main)
        btn_frame.pack()
        ttk.Button(btn_frame, text='Guardar', command=self.guardar).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text='Salir', command=self.root.destroy).pack(side=tk.LEFT, padx=5)

        self.status_label = ttk.Label(main, text='', foreground='green')
        self.status_label.pack(pady=(10, 0))

    def guardar(self):
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
            'puerto': puerto
        }
        guardar_config(data)
        self.status_label.config(text='Configuración guardada correctamente.')
        self.root.after(3000, lambda: self.status_label.config(text=''))

    def run(self):
        self.root.mainloop()


if __name__ == '__main__':
    ConfigGUI().run()
