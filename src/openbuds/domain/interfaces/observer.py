"""Tipos compartidos para observación de cambios (patrón observer).

Centraliza los alias de tipos de callback para que todas las interfaces de
repositorio y los casos de uso se refieran al mismo contrato.
"""

from __future__ import annotations

from collections.abc import Callable

from openbuds.domain.enums import ConnectionState
from openbuds.domain.models import DeviceInfo

# Callback invocado cuando un dispositivo cambia (aparición, propiedades,
# conexión/desconexión). Recibe el estado actualizado y el estado anterior.
DeviceChangeCallback = Callable[[DeviceInfo, ConnectionState], None]

# Callback genérico de notificación de un evento con payload arbitrario.
# Se mantiene simple; los eventos tipados viven en openbuds.core.events.
GenericChangeCallback = Callable[[object], None]
