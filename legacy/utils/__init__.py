"""Utilidades compartidas para OpenBuds Manager."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Optional

from ob_logging.logger import get_logger

logger = get_logger(__name__)


def run_command(
    cmd: list[str],
    timeout: int = 10,
    capture: bool = True,
) -> tuple[int, str, str]:
    """
    Ejecuta un comando del sistema de forma segura.

    Args:
        cmd: Lista con el comando y sus argumentos.
        timeout: Tiempo máximo de espera en segundos.
        capture: Si True, captura stdout y stderr.

    Returns:
        Tupla (código de salida, stdout, stderr).
    """
    logger.debug("Ejecutando: %s", " ".join(cmd))
    try:
        result = subprocess.run(
            cmd,
            capture_output=capture,
            text=True,
            timeout=timeout,
        )
        return result.returncode, result.stdout or "", result.stderr or ""
    except subprocess.TimeoutExpired:
        logger.error("Timeout ejecutando: %s", " ".join(cmd))
        return -1, "", "Timeout"
    except FileNotFoundError:
        logger.error("Comando no encontrado: %s", cmd[0])
        return -1, "", f"{cmd[0]} no encontrado"
    except OSError as exc:
        logger.error("Error ejecutando %s: %s", " ".join(cmd), exc)
        return -1, "", str(exc)


def which(binary: str) -> Optional[str]:
    """Retorna la ruta completa de un binario o None."""
    return shutil.which(binary)


def ensure_dir(path: Path) -> Path:
    """Crea un directorio si no existe. Retorna la ruta."""
    path.mkdir(parents=True, exist_ok=True)
    return path
