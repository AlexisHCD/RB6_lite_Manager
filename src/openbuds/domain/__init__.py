"""Capa de dominio.

El dominio contiene el vocabulario y los contratos estables del proyecto.
No depende de ninguna librería externa (BlueZ, PipeWire, WirePlumber, Qt):
solo de la stdlib de Python. Esto garantiza que el núcleo sea testeable,
reutilizable y agnóstico al stack concreto.

Submódulos:
  - ``models``:    dataclasses con los datos del dominio (DeviceInfo, etc.).
  - ``enums``:     enumeraciones estables (BluetoothProfile, CodecType, ...).
  - ``interfaces``: contratos (ABCs/Protocols) que la infraestructura implementa.
"""

from __future__ import annotations
