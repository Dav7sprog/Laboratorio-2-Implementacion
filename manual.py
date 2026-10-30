import builtins
import hashlib
import json
import os
import shutil
import sys
import tempfile
import time
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from contacto import (ContactStore, Contacto, IdNoExisteError, PermisosError,RECORD_SIZE, FIELDS)
import exportador

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.abspath(os.path.join(BASE, "..", "data"))
EXPORTS = os.path.abspath(os.path.join(BASE, "..", "exports"))


def sep(t):
    print("\n" + "=" * 74 + f"\n{t}\n" + "=" * 74)


CONTACTOS = [
    Contacto(1, "María López", "5551-2301", "maria.lopez@correo.com", "Quetzaltenango"),
    Contacto(2, "Julio Pérez", "5552-1102", "julio.perez@correo.com", "Guatemala"),
    Contacto(3, "Ana Sofía Muñoz", "5553-4403", "ana.munoz@correo.com", "Antigua Guatemala"),
    Contacto(4, "Carlos Peña", "5554-9904", "carlos.pena@correo.com", "Cobán"),
    Contacto(5, "Lucía Hernández", "5555-1205", "lucia.hdz@correo.com", "Huehuetenango"),
    Contacto(6, "Andrés Castañeda", "5556-7706", "andres.cast@correo.com", "Escuintla"),
    Contacto(7, "Gabriela Ordóñez", "5557-3307", "gaby.ordonez@correo.com", "Retalhuleu"),
    Contacto(8, "Diego Ramírez", "5558-6608", "diego.ramirez@correo.com", "Mazatenango"),
    Contacto(9, "Valeria Núñez", "5559-4509", "valeria.nunez@correo.com", "Totonicapán"),
    Contacto(10, "Joaquín Álvarez", "5550-2210", "joaquin.alv@correo.com", "San Marcos"),
]


def main():
    for carpeta in (DATA, EXPORTS):
        if os.path.isdir(carpeta):
            for n in os.listdir(carpeta):
                p = os.path.join(carpeta, n)
                if os.path.isfile(p) and not n.endswith(".log"):
                    os.remove(p)
    store = ContactStore(DATA)

    sep("0. ESTRUCTURA DEL REGISTRO")
    pos = 0
    for nombre, ancho in FIELDS:
        print(f"  {nombre:<9} {ancho:>3} bytes   posiciones {pos:>2} - {pos + ancho - 1}")
        pos += ancho
    print(f"  {'\\n':<9} {1:>3} byte    posición   {pos}")
    print(f"  TOTAL REGISTRO = {RECORD_SIZE} bytes")

    sep("1. ARRANQUE CON ARCHIVOS AUSENTES (contactos.dat e indice.json no existen)")
    for a in store.iniciar():
        print("  AVISO:", a)

    sep("2. AGREGAR 10 CONTACTOS (append + tell + índice + hash)")
    for c in CONTACTOS:
        info = store.agregar(c)
        print(f"  id={c.id:<2} {c.nombre:<18} -> {info.texto()}")
    print("\n  Tamaño de contactos.dat:", os.path.getsize(store.dat_path),"bytes  (= 10 registros × 100)")
    print("  Contenido de indice.json:")
    print("  " + open(store.idx_path, encoding="utf-8").read().replace("\n", "\n  ")[:420] + "...")

    sep("3. BÚSQUEDA POR ID: índice -> seek() directo")
    for id_ in (1, 7, 10):
        c, info = store.buscar(id_)
        print(f"  buscar({id_}): {c.nombre} | {info.texto()}")
    try:
        store.buscar(999)
    except IdNoExisteError as e:
        print(f"  buscar(999): [avisa al usuario] {e}")

    sep("4. MODIFICACIÓN EN EL LUGAR (solo se reescribe un registro)")
    with open(store.dat_path, "rb") as f:
        antes = f.read()
    c3, _ = store.buscar(3)
    c3.telefono = "5599-0000"
    c3.ciudad = "Sacatepéquez"
    info = store.modificar(c3)
    print(" ", info.texto())
    with open(store.dat_path, "rb") as f:
        despues = f.read()
    off = info.offset_seek
    iguales_antes = antes[:off] == despues[:off]
    iguales_despues = antes[off + RECORD_SIZE:] == despues[off + RECORD_SIZE:]
    print(f"  bytes [0..{off - 1}] sin cambios        : {iguales_antes}")
    print(f"  bytes [{off + RECORD_SIZE}..fin] sin cambios : {iguales_despues}")
    print(f"  tamaño del archivo antes/después       : {len(antes)} / {len(despues)} bytes")
    print("  registro modificado ->", store.buscar(3)[0])

    sep("5. EXPORTACIÓN JSON + PDF (el PDF se genera a partir del JSON)")
    ruta_json = exportador.exportar_json(store.listar(), EXPORTS)
    ruta_pdf = exportador.generar_pdf_desde_json(ruta_json, EXPORTS)
    print("  JSON:", ruta_json, f"({os.path.getsize(ruta_json)} bytes)")
    print("  PDF :", ruta_pdf, f"({os.path.getsize(ruta_pdf)} bytes)")

    sep("6. INTEGRIDAD SHA-256")
    ok, msg = store.verificar_integridad()
    print("  Estado normal :", "OK" if ok else "FALLA", "\n   ", msg)
    original = open(store.dat_path, "rb").read()
    alterado = bytearray(original)
    alterado[RECORD_SIZE * 4 + 8] = ord("X")       
    with open(store.dat_path, "wb") as f:
        f.write(alterado)
    print("\n  >>> Se alteró manualmente 1 byte de contactos.dat (editor externo)")
    ok, msg = store.verificar_integridad()
    print("  Tras alteración:", "OK" if ok else "FALLA DETECTADA")
    for linea in msg.splitlines():
        print("   ", linea)
    with open(store.dat_path, "wb") as f:            
        f.write(original)
    ok, msg = store.verificar_integridad()
    print("\n  >>> Archivo restaurado:", "OK" if ok else "FALLA")

    sep("7. RESPALDO ZIP (contactos.dat + indice.json)")
    ruta_zip, t_orig, t_zip = store.crear_respaldo_zip(EXPORTS)
    print("  ZIP:", ruta_zip)
    print(f"  Tamaño original  : {t_orig} bytes")
    print(f"  Tamaño comprimido: {t_zip} bytes")
    print(f"  Reducción        : {(1 - t_zip / t_orig) * 100:.1f} %")

    sep("8. METADATOS Y PERMISOS (os.stat / os.access)")
    for k, v in store.info_archivo().items():
        print(f"  {k:<13}: {v}")

    sep("9. MANEJO DE ERRORES (en una carpeta temporal, sin tocar los entregables)")
    tmp = tempfile.mkdtemp(prefix="lab2_err_")
    try:
        s = ContactStore(tmp)
        print("  9a) archivos ausentes ->", s.iniciar())
        s.agregar(CONTACTOS[0])
        s.agregar(CONTACTOS[1])
        with open(s.idx_path, "w", encoding="utf-8") as f:
            f.write("{ esto no es json ,,, ")
        s2 = ContactStore(tmp)
        print("  9b) índice corrupto   ->", s2.iniciar())
        print("      índice reconstruido:", s2.indice)
        with open(s2.dat_path, "ab") as f:
            f.write(b"basura-incompleta")
        s3 = ContactStore(tmp)
        for a in s3.iniciar():
            print("  9c) dat corrupto      ->", a.splitlines()[0])
        with mock.patch("builtins.open", side_effect=PermissionError("[Errno 13] simulado")):
            try:
                s3.buscar(1)
            except PermisosError as e:
                print("  9d) sin permisos (lectura)  ->", e)
            try:
                s3.agregar(Contacto(77, "X", "1", "x@x", "Y"))
            except PermisosError as e:
                print("  9d) sin permisos (escritura)->", e)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    sep("10. BENCHMARK: índice + seek() vs búsqueda secuencial (100 000 registros)")
    tmp = tempfile.mkdtemp(prefix="lab2_bench_")
    try:
        N = 100_000
        b = ContactStore(tmp)
        with open(b.dat_path, "wb") as f:
            from contacto import codificar_registro
            for i in range(1, N + 1):
                f.write(codificar_registro(Contacto(i, f"Persona {i}", "5555-0000",
                                                    f"p{i}@correo.com", "Ciudad")))
        b.reconstruir_indice()
        objetivo, repeticiones = N, 20        

        t0 = time.perf_counter()
        for _ in range(repeticiones):
            with open(b.dat_path, "rb") as f:  
                while True:
                    raw = f.read(RECORD_SIZE)
                    if int(raw[:6]) == objetivo:
                        break
        t_seq = (time.perf_counter() - t0) / repeticiones

        t0 = time.perf_counter()
        for _ in range(repeticiones):
            b.buscar(objetivo)                
        t_idx = (time.perf_counter() - t0) / repeticiones
        print(f"  Archivo: {os.path.getsize(b.dat_path) / 1e6:.1f} MB, {N} registros, "
              f"se busca el id {objetivo} (peor caso)")
        print(f"  Secuencial       : {t_seq * 1000:9.3f} ms (promedio de {repeticiones})")
        print(f"  Índice + seek()  : {t_idx * 1000:9.3f} ms (promedio de {repeticiones})")
        print(f"  Aceleración      : {t_seq / t_idx:,.0f}x")
        with open(os.path.join(EXPORTS, "benchmark.json"), "w", encoding="utf-8") as f:
            json.dump({"registros": N, "secuencial_ms": round(t_seq * 1000, 3),
                       "indice_ms": round(t_idx * 1000, 3),
                       "aceleracion": round(t_seq / t_idx)}, f, indent=2)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    sep("ARCHIVOS ENTREGABLES GENERADOS")
    for carpeta in (DATA, EXPORTS):
        for n in sorted(os.listdir(carpeta)):
            p = os.path.join(carpeta, n)
            if os.path.isfile(p):
                print(f"  {os.path.relpath(p, os.path.join(BASE, '..')):<46}{os.path.getsize(p):>8} bytes")


if __name__ == "__main__":
    main()
