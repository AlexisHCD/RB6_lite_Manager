"""Capa de aplicación — casos de uso.

Los casos de uso orquestan repositorios (interfaces del dominio) para
realizar operaciones significativas para el usuario. No contienen lógica de
presentación ni dependen de librerías externas concretas: solo dependen de
los contratos en ``openbuds.domain.interfaces``.

Principio: cada caso de uso = una intención del usuario (escanear, optimizar,
diagnosticar...). Se modelan como clases con un método ``execute()``.
"""

from __future__ import annotations
