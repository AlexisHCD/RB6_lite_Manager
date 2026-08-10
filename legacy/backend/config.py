"""
Sistema de configuración centralizado para OpenBuds Manager.

Gestiona la configuración de la aplicación en formato JSON/TOML.
Permite leer, escribir y validar configuraciones de forma segura.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Optional

from ob_logging.logger import get_logger

logger = get_logger(__name__)

_DEFAULT_CONFIG_DIR: Path = Path.home() / ".config" / "openbuds"
_DEFAULT_CONFIG_FILE: Path = _DEFAULT_CONFIG_DIR / "config.json"


@dataclass(frozen=True)
class LoggingConfig:
    """Configuración del subsistema de logging."""

    level: str = "DEBUG"
    enable_console: bool = True
    enable_file: bool = True
    log_dir: Optional[str] = None


@dataclass(frozen=True)
class BluetoothConfig:
    """Configuración del subsistema Bluetooth."""

    auto_detect_adapter: bool = True
    auto_detect_devices: bool = True
    scan_timeout: int = 10
    preferred_codecs: tuple[str, ...] = ("LDAC", "aptX", "AAC", "SBC")


@dataclass(frozen=True)
class AudioConfig:
    """Configuración del subsistema de audio."""

    prefer_a2dp: bool = True
    auto_select_best_codec: bool = True
    auto_select_best_profile: bool = True


@dataclass(frozen=True)
class BackupConfig:
    """Configuración del sistema de backups."""

    enabled: bool = True
    backup_dir: str = str(Path.home() / ".local" / "share" / "openbuds" / "backups")
    max_backups: int = 10


@dataclass(frozen=True)
class AppConfig:
    """Configuración raíz de la aplicación."""

    app_name: str = "OpenBuds Manager"
    version: str = "0.1.0"
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    bluetooth: BluetoothConfig = field(default_factory=BluetoothConfig)
    audio: AudioConfig = field(default_factory=AudioConfig)
    backup: BackupConfig = field(default_factory=BackupConfig)


class ConfigManager:
    """
    Gestor de configuración con carga, guardado y validación.

    Attributes:
        config_path: Ruta al archivo de configuración.
        config: Configuración actual cargada en memoria.
    """

    def __init__(self, config_path: Optional[Path] = None) -> None:
        self.config_path: Path = config_path or _DEFAULT_CONFIG_FILE
        self.config: AppConfig = AppConfig()
        self._load()

    def _load(self) -> None:
        """Carga la configuración desde disco. Si no existe, crea la default."""
        if not self.config_path.exists():
            logger.info("Archivo de configuración no existe. Creando default en %s", self.config_path)
            self.save()
            return

        try:
            raw = self.config_path.read_text(encoding="utf-8")
            data: dict[str, Any] = json.loads(raw)
            self.config = self._dict_to_config(data)
            logger.info("Configuración cargada desde %s", self.config_path)
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            logger.error("Error al leer configuración: %s. Usando defaults.", exc)
            self.config = AppConfig()

    def _dict_to_config(self, data: dict[str, Any]) -> AppConfig:
        """Convierte un diccionario plano en AppConfig."""
        logging_data = data.get("logging", {})
        bluetooth_data = data.get("bluetooth", {})
        audio_data = data.get("audio", {})
        backup_data = data.get("backup", {})

        return AppConfig(
            app_name=data.get("app_name", "OpenBuds Manager"),
            version=data.get("version", "0.1.0"),
            logging=LoggingConfig(
                level=logging_data.get("level", "DEBUG"),
                enable_console=logging_data.get("enable_console", True),
                enable_file=logging_data.get("enable_file", True),
                log_dir=logging_data.get("log_dir"),
            ),
            bluetooth=BluetoothConfig(
                auto_detect_adapter=bluetooth_data.get("auto_detect_adapter", True),
                auto_detect_devices=bluetooth_data.get("auto_detect_devices", True),
                scan_timeout=bluetooth_data.get("scan_timeout", 10),
                preferred_codecs=tuple(
                    bluetooth_data.get("preferred_codecs", ["LDAC", "aptX", "AAC", "SBC"])
                ),
            ),
            audio=AudioConfig(
                prefer_a2dp=audio_data.get("prefer_a2dp", True),
                auto_select_best_codec=audio_data.get("auto_select_best_codec", True),
                auto_select_best_profile=audio_data.get("auto_select_best_profile", True),
            ),
            backup=BackupConfig(
                enabled=backup_data.get("enabled", True),
                backup_dir=backup_data.get(
                    "backup_dir",
                    str(Path.home() / ".local" / "share" / "openbuds" / "backups"),
                ),
                max_backups=backup_data.get("max_backups", 10),
            ),
        )

    def save(self) -> None:
        """Guarda la configuración actual a disco."""
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        data = asdict(self.config)
        try:
            self.config_path.write_text(
                json.dumps(data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            logger.debug("Configuración guardada en %s", self.config_path)
        except OSError as exc:
            logger.error("No se pudo guardar la configuración: %s", exc)

    def get(self) -> AppConfig:
        """Retorna la configuración actual."""
        return self.config

    def reload(self) -> None:
        """Recarga la configuración desde disco."""
        self._load()
