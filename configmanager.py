from __future__ import annotations

import json
import os
import shutil
import stat
import logging
from dataclasses import dataclass, asdict, field
from typing import Any, Dict

logging.basicConfig(
    filename=os.path.join(os.path.dirname(os.path.abspath(__file__)), "app_config.log"),
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    encoding="utf-8",
)
logger = logging.getLogger("config_manager")

class ConfigError(Exception):
    """Excepción base para errores de configuración."""


class ConfigCorruptoError(ConfigError):
    """El archivo existe pero no se pudo parsear / formato inválido."""


class ConfigPermisosError(ConfigError):
    """No hay permisos de lectura o escritura sobre el archivo/carpeta."""

@dataclass
class UserConfig:
    nombre_usuario: str = "Usuario"
    tema_interfaz: str = "claro"          
    idioma: str = "es"                   
    tamano_fuente: int = 12
    color_barra_menu: str = "#2c3e50"
    color_letra: str = "#000000"
    foto_perfil: str = ""            

    @staticmethod
    def valores_por_defecto() -> "UserConfig":
        return UserConfig()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "UserConfig":
        defaults = UserConfig()
        return UserConfig(
            nombre_usuario=str(data.get("nombre_usuario", defaults.nombre_usuario)),
            tema_interfaz=str(data.get("tema_interfaz", defaults.tema_interfaz)),
            idioma=str(data.get("idioma", defaults.idioma)),
            tamano_fuente=int(data.get("tamano_fuente", defaults.tamano_fuente)),
            color_barra_menu=str(data.get("color_barra_menu", defaults.color_barra_menu)),
            color_letra=str(data.get("color_letra", defaults.color_letra)),
            foto_perfil=str(data.get("foto_perfil", defaults.foto_perfil)),
        )


class ConfigManager:
    
    def __init__(self, config_path: str):
        self.config_path = config_path
        self.tmp_path = config_path + ".tmp"
        self.bak_path = config_path + ".bak"

    def cargar(self) -> tuple[UserConfig, str]:
            if not os.path.exists(self.config_path):
                logger.info("Archivo de configuración no encontrado. Usando valores por defecto.")
                return UserConfig.valores_por_defecto(), ("No se encontró un archivo de configuración previo. Se cargaron los valores por defecto.")
    
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    contenido = f.read()
            except PermissionError as e:
                logger.error("Permiso denegado al leer %s: %s", self.config_path, e)
                return UserConfig.valores_por_defecto(), ("No se tienen permisos de lectura sobre el archivo de configuración. Se usaron valores por defecto.")
            except OSError as e:
                logger.error("Error de E/S al leer %s: %s", self.config_path, e)
                return UserConfig.valores_por_defecto(), (
                    f"Error de sistema al leer la configuración ({e}). Se usaron valores por defecto.")
    
            try:
                data = json.loads(contenido)
                if not isinstance(data, dict):
                    raise ValueError("El contenido raíz del JSON no es un objeto.")
            except (json.JSONDecodeError, ValueError) as e:
                logger.error("Archivo de configuración corrupto: %s", e)
                recuperado = self._intentar_recuperar_backup()
                if recuperado is not None:
                    return recuperado, (
                        "El archivo de configuración estaba corrupto o con formato inválido. Se recuperó automáticamente desde el respaldo (.bak).")
                return UserConfig.valores_por_defecto(), ("El archivo de configuración estaba corrupto o con formato inválido y no había respaldo disponible. Se usaron valores por defecto.")
    
            try:
                cfg = UserConfig.from_dict(data)
            except (TypeError, ValueError) as e:
                logger.error("Datos de configuración con tipos inválidos: %s", e)
                return UserConfig.valores_por_defecto(), (
                    "El archivo de configuración tenía valores con formato inválido. Se usaron valores por defecto.")
    
            logger.info("Configuración cargada correctamente desde %s", self.config_path)
            return cfg, "Configuración cargada correctamente."
    
    def _intentar_recuperar_backup(self) -> UserConfig | None:
            if not os.path.exists(self.bak_path):
                return None
            try:
                with open(self.bak_path, "r", encoding="utf-8") as f:
                    data = json.loads(f.read())
                return UserConfig.from_dict(data)
            except Exception as e: 
                logger.error("El respaldo .bak también está corrupto: %s", e)
                return None
    def guardar(self, config: UserConfig) -> None:
                carpeta = os.path.dirname(os.path.abspath(self.config_path)) or "."
                os.makedirs(carpeta, exist_ok=True)
        
                if not os.access(carpeta, os.W_OK):
                    logger.error("Sin permisos de escritura en la carpeta %s", carpeta)
                    raise ConfigPermisosError(
                        f"No se tienen permisos de escritura en la carpeta '{carpeta}'."
                    )
        
                try:
                    with open(self.tmp_path, "w", encoding="utf-8") as f:
                        json.dump(config.to_dict(), f, ensure_ascii=False, indent=2)
                        f.flush()
                        os.fsync(f.fileno())
                except PermissionError as e:
                    logger.error("Permiso denegado al escribir el temporal: %s", e)
                    raise ConfigPermisosError(
                        "No se tienen permisos de escritura para guardar la configuración."
                    ) from e
                except OSError as e:
                    logger.error("Error de E/S al escribir el temporal: %s", e)
                    raise ConfigError(f"Error de sistema al guardar la configuración: {e}") from e
        
                try:
                    if os.path.exists(self.config_path):
                        shutil.copy2(self.config_path, self.bak_path)
                        logger.info("Respaldo creado en %s", self.bak_path)
                except OSError as e:
                    logger.error("No se pudo crear el respaldo: %s", e)
                    self._limpiar_temporal()
                    raise ConfigError(f"No se pudo crear el respaldo (.bak): {e}") from e
        
                try:
                    os.replace(self.tmp_path, self.config_path)
                except OSError as e:
                    logger.error("Fallo el reemplazo atómico: %s", e)
                    self._limpiar_temporal()
                    raise ConfigError(
                        f"No se pudo reemplazar el archivo de configuración final: {e}"
                    ) from e
        
                logger.info("Configuración guardada correctamente en %s", self.config_path)
        
    def _limpiar_temporal(self) -> None:
                try:
                    if os.path.exists(self.tmp_path):
                        os.remove(self.tmp_path)
                except OSError:
                    pass
    def simular_archivo_corrupto(self) -> None:
                with open(self.config_path, "w", encoding="utf-8") as f:
                    f.write("{ esto no es json válido ,,, ")
        
    def simular_sin_permisos(self) -> None:
                if os.path.exists(self.config_path):
                    os.chmod(self.config_path, 0o000)
        
    def restaurar_permisos(self) -> None:
                if os.path.exists(self.config_path):
                    os.chmod(self.config_path, stat.S_IREAD | stat.S_IWRITE)