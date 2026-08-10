"""Parser de la salida JSON de ``pw-dump`` (PipeWire).

Como no existe binding Python oficial de PipeWire (ver ADR-0003), la
inspección fiable de nodos/devices Bluetooth se hace parseando ``pw-dump``,
cuya salida es un array JSON de objetos con su diccionario de propiedades.

Estado: Fase 1 — esqueleto. Implementación en Fase 3/4.
"""

from __future__ import annotations

import json


def parse_pw_dump(json_text: str) -> list[dict]:
    """Parsea la salida de ``pw-dump`` a una lista de objetos.

    Args:
        json_text: Salida cruda de ``pw-dump`` (un array JSON).

    Returns:
        Lista de diccionarios, cada uno representando un objeto PipeWire
        con sus ``info.properties``.

    Estado: Fase 1 — firma definida; implementación en Fase 3/4.

    """
    # Validación mínima: que sea JSON parseable. La lógica de filtrado de
    # nodos Bluetooth se añade en Fase 3/4.
    try:
        parsed = json.loads(json_text)
    except json.JSONDecodeError:
        raise
    if not isinstance(parsed, list):
        raise ValueError("pw-dump debe devolver un array JSON en la raíz.")
    return parsed
