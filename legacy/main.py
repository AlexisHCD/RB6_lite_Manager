"""
Punto de entrada principal de OpenBuds Manager.

Por ahora (Fase 1) ejecuta el CLI.
La GUI se añadirá en la Fase 5.
"""

from __future__ import annotations

from backend.cli import main

if __name__ == "__main__":
    main()
