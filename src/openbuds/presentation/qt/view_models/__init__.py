"""ViewModels (QObjects puente entre la UI y los casos de uso).

Los ViewModels exponen datos y comandos a Qt (señales/slots, propiedades QML)
sin contener lógica de negocio: delegan en los casos de uso de ``application``.
Esto mantiene la separación presentation -> application -> domain.

Estado: Fase 1 — vacío; se puebla en Fase 6.
"""

from __future__ import annotations
