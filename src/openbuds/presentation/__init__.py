"""Capa de presentación (UI).

Contiene la interfaz gráfica (PySide6/Qt) y las notificaciones de escritorio.
La UI NUNCA contiene lógica de negocio: delega en casos de uso (``application``)
y se comunica con ellos mediante ViewModels (QObjects puente).

Regla: presentation -> application -> domain. Nunca al revés.
"""

from __future__ import annotations
