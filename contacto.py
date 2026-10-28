from __future__ import annotations

import hashlib
import json
import logging
import os
import time
import zipfile
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger("contact_store")

FIELDS: List[Tuple[str, int]] = [
    ("id", 6),
    ("nombre", 30),
    ("telefono", 15),
    ("correo", 30),
    ("ciudad", 18),
]
RECORD_SIZE = sum(w for _, w in FIELDS) + 1    
assert RECORD_SIZE == 100

class ContactoError(Exception):
    """Error base de la agenda."""


class PermisosError(ContactoError):
    """No hay permisos de lectura/escritura."""


class ArchivoCorruptoError(ContactoError):
    """El archivo de datos no tiene el formato esperado."""


class IdNoExisteError(ContactoError):
    """Se buscó un id que no existe en el índice."""


class IdDuplicadoError(ContactoError):
    """Se intentó agregar un id que ya existe."""


@dataclass
class Contacto:
    id: int
    nombre: str
    telefono: str
    correo: str
    ciudad: str

    def to_dict(self) -> Dict:
        return asdict(self)
    
@dataclass
class AccesoInfo:
    registro: int        
    offset_seek: int     
    tell_antes: int       
    tell_despues: int    
    bytes_io: int      

    def texto(self) -> str:
        return (f"registro #{self.registro} -> seek({self.offset_seek}) | "f"tell() tras seek = {self.tell_antes} | "f"tell() tras E/S = {self.tell_despues} | {self.bytes_io} bytes")

def _ajustar_bytes(texto: str, ancho: int) -> bytes:
    datos = str(texto).replace("\n", " ").replace("\r", " ").encode("utf-8")
    if len(datos) > ancho:
        datos = datos[:ancho]
        datos = datos.decode("utf-8", errors="ignore").encode("utf-8")
    return datos.ljust(ancho, b" ")


def codificar_registro(c: Contacto) -> bytes:
    partes = []
    valores = [str(c.id), c.nombre, c.telefono, c.correo, c.ciudad]
    for (nombre_campo, ancho), valor in zip(FIELDS, valores):
        partes.append(_ajustar_bytes(valor, ancho))
    registro = b"".join(partes) + b"\n"
    assert len(registro) == RECORD_SIZE, "registro con tamaño incorrecto"
    return registro


def decodificar_registro(raw: bytes) -> Contacto:
    if len(raw) != RECORD_SIZE or not raw.endswith(b"\n"):
        raise ArchivoCorruptoError("Registro con longitud o terminador inválido.")
    pos = 0
    valores = []
    for _, ancho in FIELDS:
        valores.append(raw[pos:pos + ancho].decode("utf-8").strip())
        pos += ancho
    try:
        return Contacto(int(valores[0]), valores[1], valores[2], valores[3], valores[4])
    except ValueError as e:
        raise ArchivoCorruptoError(f"id no numérico en el registro: {e}") from e

class ContactStore:
    def __init__(self, carpeta_datos: str):
        self.carpeta = os.path.abspath(carpeta_datos)
        os.makedirs(self.carpeta, exist_ok=True)
        self.dat_path = os.path.join(self.carpeta, "contactos.dat")
        self.idx_path = os.path.join(self.carpeta, "indice.json")
        self.sha_path = os.path.join(self.carpeta, "contactos.sha256")
        self.indice: Dict[int, int] = {}    
        self.avisos: List[str] = []     
        self._configurar_log()

    def _configurar_log(self) -> None:
        ruta = os.path.join(self.carpeta, "contactos.log")
        for h in logger.handlers:
            if getattr(h, "baseFilename", None) == os.path.abspath(ruta):
                return
        try:
            h = logging.FileHandler(ruta, encoding="utf-8")
            h.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
            logger.addHandler(h)
            logger.setLevel(logging.INFO)
            logger.propagate = False
        except OSError:
            logger.addHandler(logging.NullHandler())

    def iniciar(self) -> List[str]:
        self.avisos = []

        if not os.path.exists(self.dat_path):
            try:
                open(self.dat_path, "wb").close()
                self.avisos.append("No existía contactos.dat: se creó un archivo vacío.")
            except PermissionError:
                self.avisos.append("Sin permisos para crear contactos.dat en la carpeta de datos.")
            except OSError as e:
                self.avisos.append(f"No se pudo crear contactos.dat: {e}")
        else:
            try:
                tam = os.path.getsize(self.dat_path)
                if tam % RECORD_SIZE != 0:
                    self.avisos.append(f"contactos.dat está corrupto: su tamaño ({tam} bytes) no es múltiplo "f"de {RECORD_SIZE}. Los registros incompletos serán ignorados.")
            except OSError as e:
                self.avisos.append(f"No se pudo leer el tamaño de contactos.dat: {e}")

        self._cargar_indice()

        ok, msg = self.verificar_integridad(crear_si_falta=True)
        if not ok:
            self.avisos.append(msg)
        return self.avisos

    def _cargar_indice(self) -> None:
        if not os.path.exists(self.idx_path):
            if os.path.exists(self.dat_path) and os.path.getsize(self.dat_path) >= RECORD_SIZE:
                self.reconstruir_indice()
                self.avisos.append("No existía indice.json: se reconstruyó a partir de contactos.dat.")
            else:
                self.indice = {}
            return
        try:
            with open(self.idx_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.indice = {int(k): int(v) for k, v in data["indice"].items()}
            total = self.total_registros()
            if any(v >= total for v in self.indice.values()):
                raise ValueError("el índice apunta fuera del archivo de datos")
        except PermissionError:
            self.indice = {}
            self.avisos.append("Sin permisos de lectura sobre indice.json; índice vacío.")
        except (json.JSONDecodeError, KeyError, TypeError, ValueError, AttributeError) as e:
            logger.error("Índice corrupto: %s", e)
            self.reconstruir_indice()
            self.avisos.append("indice.json estaba corrupto o inconsistente: se reconstruyó recorriendo contactos.dat.")

    def reconstruir_indice(self) -> None:
        self.indice = {}
        try:
            with open(self.dat_path, "rb") as f:
                n = 0
                while True:
                    raw = f.read(RECORD_SIZE)
                    if len(raw) < RECORD_SIZE:
                        break
                    try:
                        self.indice[decodificar_registro(raw).id] = n
                    except ArchivoCorruptoError:
                        pass
                    n += 1
        except OSError as e:
            logger.error("No se pudo reconstruir el índice: %s", e)
        try:
            self._guardar_indice()
        except ContactoError:
            pass

    def _guardar_indice(self) -> None:
        tmp = self.idx_path + ".tmp"
        contenido = {"version": 1, "record_size": RECORD_SIZE,"indice": {str(k): v for k, v in sorted(self.indice.items())}}
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(contenido, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, self.idx_path)
        except PermissionError as e:
            raise PermisosError("Sin permisos de escritura para guardar indice.json.") from e
        except OSError as e:
            raise ContactoError(f"No se pudo guardar indice.json: {e}") from e

    def total_registros(self) -> int:
        try:
            return os.path.getsize(self.dat_path) // RECORD_SIZE
        except OSError:
            return 0

    def siguiente_id(self) -> int:
        return (max(self.indice) + 1) if self.indice else 1

    def agregar(self, c: Contacto) -> AccesoInfo:
        if c.id in self.indice:
            raise IdDuplicadoError(f"Ya existe un contacto con id {c.id}.")
        registro = codificar_registro(c)
        try:
            with open(self.dat_path, "ab") as f:
                f.seek(0, os.SEEK_END)
                pos = f.tell()                  
                if pos % RECORD_SIZE != 0:
                    raise ArchivoCorruptoError(
                        "contactos.dat está corrupto (tamaño no múltiplo del registro); no se puede agregar sin dañarlo más.")
                f.write(registro)
                f.flush()
                os.fsync(f.fileno())
                despues = f.tell()
        except PermissionError as e:
            raise PermisosError("Sin permisos de escritura sobre contactos.dat.") from e
        except OSError as e:
            raise ContactoError(f"Error al escribir contactos.dat: {e}") from e

        n = pos // RECORD_SIZE
        self.indice[c.id] = n
        self._guardar_indice()   
        self.actualizar_hash()
        return AccesoInfo(n, pos, pos, despues, len(registro))

    def buscar(self, id_: int) -> Tuple[Contacto, AccesoInfo]:
        if id_ not in self.indice:
            raise IdNoExisteError(f"No existe ningún contacto con id {id_}.")
        n = self.indice[id_]
        offset = n * RECORD_SIZE
        try:
            with open(self.dat_path, "rb") as f:
                f.seek(offset)           
                antes = f.tell()
                raw = f.read(RECORD_SIZE)
                despues = f.tell()
        except FileNotFoundError as e:
            raise ContactoError("contactos.dat no existe.") from e
        except PermissionError as e:
            raise PermisosError("Sin permisos de lectura sobre contactos.dat.") from e
        except OSError as e:
            raise ContactoError(f"Error al leer contactos.dat: {e}") from e
        c = decodificar_registro(raw)
        if c.id != id_:
            raise ArchivoCorruptoError(f"El índice indica el registro #{n} para id {id_}, pero ahí hay id {c.id}. Archivo o índice alterados.")
        return c, AccesoInfo(n, offset, antes, despues, len(raw))

    def modificar(self, c: Contacto) -> AccesoInfo:
        if c.id not in self.indice:
            raise IdNoExisteError(f"No existe ningún contacto con id {c.id}.")
        n = self.indice[c.id]
        offset = n * RECORD_SIZE
        registro = codificar_registro(c)
        try:
            with open(self.dat_path, "rb+") as f: 
                f.seek(offset)
                antes = f.tell()
                f.write(registro)        
                f.flush()
                os.fsync(f.fileno())
                despues = f.tell()
        except PermissionError as e:
            raise PermisosError("Sin permisos de escritura sobre contactos.dat.") from e
        except OSError as e:
            raise ContactoError(f"Error al modificar contactos.dat: {e}") from e
        self.actualizar_hash()
        return AccesoInfo(n, offset, antes, despues, len(registro))

    def listar(self) -> List[Contacto]:
        contactos = []
        try:
            with open(self.dat_path, "rb") as f:
                while True:
                    raw = f.read(RECORD_SIZE)
                    if len(raw) < RECORD_SIZE:
                        break
                    try:
                        contactos.append(decodificar_registro(raw))
                    except ArchivoCorruptoError:
                        continue
        except FileNotFoundError:
            return []
        except PermissionError as e:
            raise PermisosError("Sin permisos de lectura sobre contactos.dat.") from e
        except OSError as e:
            raise ContactoError(f"Error al leer contactos.dat: {e}") from e
        return contactos
