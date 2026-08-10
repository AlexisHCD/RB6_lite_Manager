"""Capa de infraestructura — implementaciones de los contratos del dominio.

Cada subpaquete adapta una tecnología externa a las interfaces de
``openbuds.domain.interfaces``:

  - ``bluez``:      BlueZ vía D-Bus (PyGObject/Gio). Implementa IBluetoothRepository.
  - ``pipewire``:   PipeWire vía subprocess (pw-dump/wpctl). Implementa IAudioRepository.
  - ``wireplumber``: WirePlumber 0.4 (Lua). Implementa IConfigRepository.
  - ``system``:     Detección del entorno. Parte de IDiagnosticsRepository.
  - ``persistence``: Persistencia propia (config app, historial de benchmarks).

La regla de oro: esta capa puede importar librerías externas, pero las capas
internas (domain/application) NUNCA la importan directamente; reciben las
implementaciones por inyección de dependencias.
"""

from __future__ import annotations
