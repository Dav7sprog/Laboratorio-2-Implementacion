import os
import tkinter as tk
from tkinter import ttk, colorchooser, filedialog, messagebox

from configmanager import ConfigManager, UserConfig, ConfigPermisosError, ConfigError


class SettingsWindow(tk.Toplevel):
    def __init__(self, master, config_manager: ConfigManager, config: UserConfig, on_saved):
        super().__init__(master)
        self.title("Settings")
        self.geometry("460x420")
        self.resizable(False, False)
        self.config_manager = config_manager
        self.config_actual = config
        self.on_saved = on_saved 

        self.var_nombre = tk.StringVar(value=config.nombre_usuario)
        self.var_tema = tk.StringVar(value=config.tema_interfaz)
        self.var_idioma = tk.StringVar(value=config.idioma)
        self.var_fuente = tk.IntVar(value=config.tamano_fuente)
        self.color_barra = config.color_barra_menu
        self.color_letra = config.color_letra
        self.foto_perfil = config.foto_perfil

        self._construir_ui()
        self.transient(master)
        self.grab_set()

    def _construir_ui(self):
        pad = {"padx": 12, "pady": 6}

        frm = ttk.Frame(self)
        frm.pack(fill="both", expand=True)

        row = 0
        ttk.Label(frm, text="Nombre de usuario:").grid(row=row, column=0, sticky="w", **pad)
        ttk.Entry(frm, textvariable=self.var_nombre, width=28).grid(row=row, column=1, **pad)

        row += 1
        ttk.Label(frm, text="Tema de interfaz:").grid(row=row, column=0, sticky="w", **pad)
        ttk.Combobox(frm, textvariable=self.var_tema, values=["claro", "oscuro"],state="readonly", width=25).grid(row=row, column=1, **pad)

        row += 1
        ttk.Label(frm, text="Idioma:").grid(row=row, column=0, sticky="w", **pad)
        ttk.Combobox(frm, textvariable=self.var_idioma,values=["es", "es-ES", "en", "en-US"], state="readonly", width=25).grid(row=row, column=1, **pad)

        row += 1
        ttk.Label(frm, text="Tamaño de fuente:").grid(row=row, column=0, sticky="w", **pad)
        ttk.Spinbox(frm, from_=8, to=48, textvariable=self.var_fuente, width=26).grid(row=row, column=1, **pad)

        row += 1
        ttk.Label(frm, text="Color barra de menú:").grid(row=row, column=0, sticky="w", **pad)
        self.btn_color_barra = tk.Button(frm, text="Elegir color...", bg=self.color_barra,command=self._elegir_color_barra)
        self.btn_color_barra.grid(row=row, column=1, sticky="w", **pad)

        row += 1
        ttk.Label(frm, text="Color de letra:").grid(row=row, column=0, sticky="w", **pad)
        self.btn_color_letra = tk.Button(frm, text="Elegir color...", bg=self.color_letra,command=self._elegir_color_letra)
        self.btn_color_letra.grid(row=row, column=1, sticky="w", **pad)

        row += 1
        ttk.Label(frm, text="Foto de perfil:").grid(row=row, column=0, sticky="w", **pad)
        self.lbl_foto = ttk.Label(frm, text=self._nombre_corto_foto(), width=22)
        self.lbl_foto.grid(row=row, column=1, sticky="w", **pad)

        row += 1
        ttk.Button(frm, text="Seleccionar imagen...", command=self._elegir_foto).grid(row=row, column=1, sticky="w", **pad)

        row += 1
        self.lbl_estado = ttk.Label(frm, text="", foreground="#555555", wraplength=420)
        self.lbl_estado.grid(row=row, column=0, columnspan=2, sticky="w", padx=12, pady=(10, 0))

        row += 1
        botones = ttk.Frame(frm)
        botones.grid(row=row, column=0, columnspan=2, pady=16)
        ttk.Button(botones, text="Guardar", command=self._guardar).pack(side="left", padx=6)
        ttk.Button(botones, text="Cancelar", command=self.destroy).pack(side="left", padx=6)

    def _nombre_corto_foto(self) -> str:
        if not self.foto_perfil:
            return "(ninguna seleccionada)"
        return os.path.basename(self.foto_perfil)

    def _elegir_color_barra(self):
        color = colorchooser.askcolor(title="Color de la barra de menú", color=self.color_barra)
        if color and color[1]:
            self.color_barra = color[1]
            self.btn_color_barra.configure(bg=self.color_barra)

    def _elegir_color_letra(self):
        color = colorchooser.askcolor(title="Color de letra", color=self.color_letra)
        if color and color[1]:
            self.color_letra = color[1]
            self.btn_color_letra.configure(bg=self.color_letra)

    def _elegir_foto(self):
        ruta = filedialog.askopenfilename(
            title="Seleccionar foto de perfil",
            filetypes=[("Imágenes", "*.png *.jpg *.jpeg *.gif *.bmp"), ("Todos los archivos", "*.*")],)
        if ruta:
            self.foto_perfil = ruta
            self.lbl_foto.configure(text=self._nombre_corto_foto())

    def _guardar(self):
        nueva_config = UserConfig(
            nombre_usuario=self.var_nombre.get().strip() or "Usuario",
            tema_interfaz=self.var_tema.get(),
            idioma=self.var_idioma.get(),
            tamano_fuente=int(self.var_fuente.get()),
            color_barra_menu=self.color_barra,
            color_letra=self.color_letra,
            foto_perfil=self.foto_perfil,
        )
        try:
            self.config_manager.guardar(nueva_config)
        except ConfigPermisosError as e:
            messagebox.showerror("Permisos insuficientes", str(e))
            return
        except ConfigError as e:
            messagebox.showerror("Error al guardar", str(e))
            return

        self.on_saved(nueva_config)
        messagebox.showinfo("Settings", "Configuración guardada correctamente.")
        self.destroy()

