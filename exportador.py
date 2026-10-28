import json
import os
from datetime import datetime
from typing import List

from fpdf import FPDF

from contacto import Contacto, ContactoError, PermisosError

def exportar_json(contactos: List[Contacto], carpeta: str) -> str:
    os.makedirs(carpeta, exist_ok=True)
    ruta = os.path.join(carpeta, "contactos_exportados.json")
    payload = {
        "generado": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total": len(contactos),
        "contactos": [c.to_dict() for c in contactos],
    }
    tmp = ruta + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, ruta)
    except PermissionError as e:
        raise PermisosError("Sin permisos para escribir el JSON exportado.") from e
    except OSError as e:
        raise ContactoError(f"No se pudo exportar el JSON: {e}") from e
    return ruta

def _latin1(texto: str) -> str:
    return str(texto).encode("latin-1", errors="replace").decode("latin-1")

def generar_pdf_desde_json(ruta_json: str, carpeta: str) -> str:
    try:
        with open(ruta_json, "r", encoding="utf-8") as f:
            datos = json.load(f)
    except FileNotFoundError as e:
        raise ContactoError("Primero debe exportar el JSON.") from e
    except json.JSONDecodeError as e:
        raise ContactoError(f"El JSON exportado está corrupto: {e}") from e
    except PermissionError as e:
        raise PermisosError("Sin permisos de lectura sobre el JSON exportado.") from e

    pdf = FPDF(orientation="L", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    pdf.set_font("helvetica", "B", 16)
    pdf.cell(0, 10, _latin1("Reporte de Agenda de Contactos"), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("helvetica", "", 10)
    pdf.cell(0, 6, _latin1(f"Fecha de generación: {datetime.now():%Y-%m-%d %H:%M:%S}"),
             new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, _latin1(f"Total de contactos: {datos.get('total', 0)}"),
             new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    columnas = [("ID", 15), ("Nombre", 65), ("Teléfono", 35), ("Correo", 90), ("Ciudad", 60)]

    def encabezado():
        pdf.set_font("helvetica", "B", 10)
        pdf.set_fill_color(26, 61, 99)
        pdf.set_text_color(255, 255, 255)
        for nombre, ancho in columnas:
            pdf.cell(ancho, 8, _latin1(nombre), border=1, fill=True)
        pdf.ln()
        pdf.set_text_color(0, 0, 0)
        pdf.set_font("helvetica", "", 9)

    encabezado()
    for i, c in enumerate(datos.get("contactos", [])):
        if pdf.get_y() > 185:
            pdf.add_page()
            encabezado()
        pdf.set_fill_color(245, 247, 250) if i % 2 else pdf.set_fill_color(255, 255, 255)
        fila = [c["id"], c["nombre"], c["telefono"], c["correo"], c["ciudad"]]
        for valor, (_, ancho) in zip(fila, columnas):
            pdf.cell(ancho, 7, _latin1(valor), border=1, fill=True)
        pdf.ln()

    ruta_pdf = os.path.join(carpeta, "reporte_contactos.pdf")
    try:
        pdf.output(ruta_pdf)
    except PermissionError as e:
        raise PermisosError("Sin permisos para escribir el PDF.") from e
    except OSError as e:
        raise ContactoError(f"No se pudo escribir el PDF: {e}") from e
    return ruta_pdf
