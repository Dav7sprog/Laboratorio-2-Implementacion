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
class ResultadoV(tk.Toplevel):

    def __init__(self, master, titulo, texto, ancho=78, alto=14):
        super().__init__(master)
        self.title(titulo)
        self.resizable(False, False)
        txt = tk.Text(self, width=ancho, height=alto, wrap="word", font=("Courier", 10),padx=10, pady=10)
        txt.insert("1.0", texto)
        txt.configure(state="disabled")
        txt.pack(padx=8, pady=(8, 4))
        ttk.Button(self, text="Cerrar", command=self.destroy).pack(pady=(0, 8))


class InfoArchivV(tk.Toplevel):

    def __init__(self, master, info: dict):
        super().__init__(master)
        self.title("Información del archivo")
        self.resizable(False, False)
        frm = ttk.Frame(self, padding=16)
        frm.pack()
        if not info.get("existe"):
            filas = [("Estado", "El archivo contactos.dat no existe")]
        else:
            filas = [
                ("Ruta", info["ruta"]),
                ("Tamaño", f'{info["tamano_bytes"]} bytes'),
                ("Tamaño de registro", f'{info["tam_registro"]} bytes'),
                ("Cantidad de registros", str(info["registros"])),
                ("Última modificación", info["modificado"]),
                ("Permiso de lectura", "Sí" if info["lectura"] else "NO"),
                ("Permiso de escritura", "Sí" if info["escritura"] else "NO"),
            ]
        for i, (k, v) in enumerate(filas):
            ttk.Label(frm, text=k + ":", font=("TkDefaultFont", 10, "bold")).grid(
                row=i, column=0, sticky="w", padx=(0, 12), pady=3)
            ttk.Label(frm, text=v, wraplength=360).grid(row=i, column=1, sticky="w", pady=3)
        ttk.Button(frm, text="Cerrar", command=self.destroy).grid(
            row=len(filas), column=0, columnspan=2, pady=(12, 0))


class ContactoDialog(tk.Toplevel):

    def __init__(self, master, titulo, contacto: Contacto, id_editable, on_ok):
        super().__init__(master)
        self.title(titulo)
        self.resizable(False, False)
        self.on_ok = on_ok
        self.vars = {
            "id": tk.StringVar(value=str(contacto.id)),
            "nombre": tk.StringVar(value=contacto.nombre),
            "telefono": tk.StringVar(value=contacto.telefono),
            "correo": tk.StringVar(value=contacto.correo),
            "ciudad": tk.StringVar(value=contacto.ciudad),
        }
        frm = ttk.Frame(self, padding=14)
        frm.pack()
        etiquetas = {"id": "ID", "nombre": "Nombre", "telefono": "Teléfono","correo": "Correo", "ciudad": "Ciudad"}
        anchos = dict(FIELDS)
        for i, campo in enumerate(["id", "nombre", "telefono", "correo", "ciudad"]):
            ttk.Label(frm, text=f"{etiquetas[campo]} (máx. {anchos[campo]} bytes):").grid(row=i, column=0, sticky="w", pady=4, padx=(0, 8))
            e = ttk.Entry(frm, textvariable=self.vars[campo], width=34,state="normal" if (campo != "id" or id_editable) else "disabled")
            e.grid(row=i, column=1, pady=4)
        bt = ttk.Frame(frm)
        bt.grid(row=6, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(bt, text="Guardar", command=self._guardar).pack(side="left", padx=6)
        ttk.Button(bt, text="Cancelar", command=self.destroy).pack(side="left", padx=6)
        self.transient(master)
        self.grab_set()

    def _guardar(self):
        try:
            id_ = int(self.vars["id"].get().strip())
            if id_ <= 0 or id_ > 999999:
                raise ValueError
        except ValueError:
            messagebox.showerror("Dato inválido", "El ID debe ser un entero entre 1 y 999999.",parent=self)
            return
        nombre = self.vars["nombre"].get().strip()
        if not nombre:
            messagebox.showerror("Dato inválido", "El nombre es obligatorio.", parent=self)
            return
        c = Contacto(id_, nombre, self.vars["telefono"].get().strip(),self.vars["correo"].get().strip(), self.vars["ciudad"].get().strip())
        if self.on_ok(c):
            self.destroy()

class AgendaApp(tk.Tk):
    def __init__(self, data_dir=DATA_DIR, mostrar_avisos=True):
        super().__init__()
        self.title("Agenda de Contactos - Acceso Aleatorio (Laboratorio 2)")
        self.geometry("900x600")
        self.config_manager = ConfigManager(os.path.join(data_dir, "config.json"))
        self.config_actual, _ = self.config_manager.cargar()

        self.store = ContactStore(data_dir)
        self.avisos_inicio = self.store.iniciar()

        self._construir_menu()
        self._construir_cuerpo()
        self._aplicar_config_visual()
        self.refrescar_tabla()
        self.log(f"Archivo: {self.store.dat_path}")
        self.log(f"Tamaño de registro fijo = {RECORD_SIZE} bytes | "f"registros en archivo = {self.store.total_registros()}")
        if self.avisos_inicio and mostrar_avisos:self.after(300, lambda: ResultadoV(self, "Avisos de inicio", "\n\n".join(self.avisos_inicio), alto=10))

    def _construir_menu(self):
        barra = tk.Menu(self)

        m = tk.Menu(barra, tearoff=0)
        m.add_command(label="Agregar contacto...", command=self.agregar)
        m.add_command(label="Buscar por ID...", command=self.buscar)
        m.add_command(label="Modificar contacto...", command=self.modificar)
        m.add_separator()
        m.add_command(label="Salir", command=self.destroy)
        barra.add_cascade(label="Contactos", menu=m)

        m = tk.Menu(barra, tearoff=0)
        m.add_command(label="Exportar a JSON", command=self.exportar_json)
        m.add_command(label="Generar reporte PDF", command=self.generar_pdf)
        barra.add_cascade(label="Exportar", menu=m)

        m = tk.Menu(barra, tearoff=0)
        m.add_command(label="Verificar integridad (SHA-256)", command=self.verificar)
        m.add_command(label="Crear respaldo ZIP", command=self.respaldo_zip)
        m.add_command(label="Información del archivo", command=self.info_archivo)
        m.add_separator()
        m.add_command(label="Configuración (Lab 1)...", command=self.abrir_settings)
        barra.add_cascade(label="Herramientas", menu=m)

        m = tk.Menu(barra, tearoff=0)    
        m.add_command(label="Manual de usuario (simulado)")
        m.add_command(label="Acerca de (simulado)")
        barra.add_cascade(label="Ayuda", menu=m)

        self.config(menu=barra)

    def _construir_cuerpo(self):
        self.franja = tk.Frame(self, height=8)
        self.franja.pack(side="top", fill="x")

        self.cuerpo = tk.Frame(self)
        self.cuerpo.pack(fill="both", expand=True, padx=8, pady=8)

        cols = ("id", "nombre", "telefono", "correo", "ciudad")
        self.tabla = ttk.Treeview(self.cuerpo, columns=cols, show="headings", height=10)
        titulos = {"id": "ID", "nombre": "Nombre", "telefono": "Teléfono","correo": "Correo", "ciudad": "Ciudad"}
        for col, ancho in zip(cols, (60, 200, 110, 240, 140)):
            self.tabla.heading(col, text=titulos[col])
            self.tabla.column(col, width=ancho, anchor="w")
        sb = ttk.Scrollbar(self.cuerpo, orient="vertical", command=self.tabla.yview)
        self.tabla.configure(yscrollcommand=sb.set)
        self.tabla.grid(row=0, column=0, sticky="nsew")
        sb.grid(row=0, column=1, sticky="ns")

        self.lbl_log = tk.Label(self.cuerpo, text="Bitácora de acceso aleatorio (seek / tell):",anchor="w")
        self.lbl_log.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(10, 2))
        self.txt_log = tk.Text(self.cuerpo, height=9, font=("Courier", 9), state="disabled")
        self.txt_log.grid(row=2, column=0, columnspan=2, sticky="nsew")
        self.cuerpo.rowconfigure(0, weight=3)
        self.cuerpo.rowconfigure(2, weight=2)
        self.cuerpo.columnconfigure(0, weight=1)

    def _aplicar_config_visual(self):
        cfg = self.config_actual
        tema = TEMAS.get(cfg.tema_interfaz, TEMAS["claro"])
        self.configure(bg=tema["bg"])
        self.cuerpo.configure(bg=tema["bg"])
        self.franja.configure(bg=cfg.color_barra_menu)
        self.lbl_log.configure(bg=tema["bg"], fg=cfg.color_letra if tema is TEMAS["claro"]else tema["fg"])
        self.txt_log.configure(bg="#ffffff" if tema is TEMAS["claro"] else "#2b2b2b",fg=cfg.color_letra if tema is TEMAS["claro"] else tema["fg"])
