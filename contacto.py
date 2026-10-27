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
