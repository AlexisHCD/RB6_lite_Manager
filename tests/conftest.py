"""Configuración compartida de pytest.

Define los marcadores y fixtures comunes. ``pythonpath = ["src"]`` está en
pyproject.toml, así que ``import openbuds`` funciona sin instalar el paquete.
"""

from __future__ import annotations

import pytest


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Marca automáticamente los tests según su ruta (unit/integration/e2e)."""
    for item in items:
        path = str(item.fspath)
        if "/unit/" in path and "unit" not in item.keywords:
            item.add_marker(pytest.mark.unit)
        elif "/integration/" in path and "integration" not in item.keywords:
            item.add_marker(pytest.mark.integration)
        elif "/e2e/" in path and "e2e" not in item.keywords:
            item.add_marker(pytest.mark.e2e)
