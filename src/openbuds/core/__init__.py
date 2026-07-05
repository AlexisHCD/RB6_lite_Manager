"""Capa core — utilidades transversales.

Contiene primitivas reutilizadas por todas las capas: manejo de errores
funcional (``Result``), jerarquía de excepciones, bus de eventos, configuración
de la propia app y logging estructurado.

Esta capa puede depender de ``openbuds.domain`` pero nunca de infraestructura
ni de presentación.
"""

from __future__ import annotations
