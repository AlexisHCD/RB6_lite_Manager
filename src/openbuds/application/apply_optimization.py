"""Caso de uso: aplicar una optimización de audio de forma segura.

Este caso de uso materializa la POLÍTICA DE SEGURIDAD central del proyecto.
Todo cambio de configuración de WirePlumber sigue este flujo obligatorio:

    1. Detectar entorno  (¿es seguro operar?)
    2. Crear backup      (timestamped, antes de tocar nada)
    3. Validar cambio    (sintaxis correcta, reversible)
    4. Aplicar cambio    (escribir override en ~/.config/wireplumber/)
    5. Verificar         (el cambio surte efecto sin errores)
    6. Rollback si error (restaurar backup y dejar el sistema como estaba)

Si CUALQUIER paso falla, el cambio se revierte y se lanza una excepción del
dominio. Nada queda en estado intermedio.

Estado: Fase 1 — flujo y contrato definidos; sin implementación (Fase 4).
"""

from __future__ import annotations

from dataclasses import dataclass

from openbuds.domain.interfaces import IConfigRepository, IDiagnosticsRepository


@dataclass(frozen=True, slots=True)
class OptimizationPlan:
    """Descripción de una optimización a aplicar.

    Atributos:
        relative_path: Archivo override dentro de ``~/.config/wireplumber/``.
            p. ej. "bluetooth.lua.d/50-bluez-config.lua".
        content: Contenido completo (sintaxis WirePlumber 0.4 Lua) a escribir.
        description: Descripción legible del cambio (para logs/UI).
        verification: Identificador de la verificación post-aplicación.
    """

    relative_path: str
    content: str
    description: str
    verification: str = ""


class ApplyOptimizationUseCase:
    """Aplica una optimización siguiendo estrictamente el flujo seguro."""

    def __init__(
        self,
        config_repo: IConfigRepository,
        diagnostics_repo: IDiagnosticsRepository,
    ) -> None:
        self._config = config_repo
        self._diagnostics = diagnostics_repo

    def execute(self, plan: OptimizationPlan) -> None:
        """Aplica ``plan`` de forma segura, con rollback automático ante error.

        Lanza ``BackupError``/``RollbackError``/``UnsafeEnvironmentError`` si
        procede. En caso de éxito devuelve sin excepción.
        """
        raise NotImplementedError("Implementación diferida a Fase 4 (Optimización).")
