"""ViewModels (QObjects puente entre la UI y los casos de uso).

Los ViewModels exponen datos y comandos a Qt (señales/slots, propiedades QML)
sin contener lógica de negocio: delegan en los casos de uso de ``application``.
Esto mantiene la separación presentation -> application -> domain.

Estado: Etapa 0 — vacío; se desarrollará como parte del MVP de la Etapa 3.
"""

from __future__ import annotations
