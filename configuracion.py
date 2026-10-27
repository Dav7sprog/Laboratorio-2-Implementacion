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
