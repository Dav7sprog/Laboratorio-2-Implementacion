import os
import sys
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from configmanager import ConfigManager, UserConfig
from configuracion import SettingsWindow
from contacto import (ContactStore, Contacto, ContactoError, IdNoExisteError,IdDuplicadoError, PermisosError, FIELDS, RECORD_SIZE)
import exportador

BASE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.abspath(os.path.join(BASE, "..", "data"))
EXPORT_DIR = os.path.abspath(os.path.join(BASE, "..", "exports"))
CONFIG_PATH = os.path.join(DATA_DIR, "config.json")

TEMAS = {
    "claro": {"bg": "#f5f5f5", "fg": "#000000"},
    "oscuro": {"bg": "#1e1e1e", "fg": "#f0f0f0"},
}
