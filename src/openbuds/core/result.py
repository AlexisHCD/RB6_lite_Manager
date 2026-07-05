"""Tipo ``Result`` para manejo funcional de errores.

Fomenta un estilo de programación donde las operaciones que pueden fallar
devuelven un ``Result`` explícito en lugar de lanzar excepciones. Esto hace
que los puntos de fallo sean visibles en las firmas y facilita el testing.

Uso::

    def parse_codec(byte: int) -> Result[CodecType, str]:
        if byte == 0x00:
            return Result.ok(CodecType.SBC)
        return Result.err("codec byte desconocido")

    r = parse_codec(0x00)
    if r.is_ok():
        codec = r.unwrap()
"""

from __future__ import annotations

from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Nota: ruff UP046 sugiere la sintaxis PEP 695 (``class Result[T, E]:``).
# Como el proyecto declara ``target-version = "py312"`` y PEP 695 requiere
# 3.12+, la usamos para satisfacer el linter y modernizar el código.
# ---------------------------------------------------------------------------
from typing import TypeVar

T = TypeVar("T")
E = TypeVar("E")


@dataclass(frozen=True, slots=True)
class Result[T, E]:
    """Contenedor de un resultado exitoso o de un error.

    Invariante: exactamente uno de ``_value`` / ``_error`` está definido.
    Se construye mediante los factories de clase ``ok()`` y ``err()``.
    """

    _value: T | None
    _error: E | None
    _is_ok: bool

    # --- factories -------------------------------------------------------
    @classmethod
    def ok(cls, value: T) -> Result[T, E]:
        """Construye un resultado exitoso con ``value``."""
        return cls(_value=value, _error=None, _is_ok=True)

    @classmethod
    def err(cls, error: E) -> Result[T, E]:
        """Construye un resultado fallido con ``error``."""
        return cls(_value=None, _error=error, _is_ok=False)

    # --- consultas -------------------------------------------------------
    def is_ok(self) -> bool:
        """Indica si el resultado es exitoso."""
        return self._is_ok

    def is_err(self) -> bool:
        """Indica si el resultado es fallido."""
        return not self._is_ok

    # --- extracción ------------------------------------------------------
    def unwrap(self) -> T:
        """Devuelve el valor si es exitoso; lanza ``ValueError`` si no.

        Usar solo cuando se haya comprobado ``is_ok()`` previamente, o en
        contextos donde se asume el éxito (p. ej. tests).
        """
        if not self._is_ok or self._value is None:
            raise ValueError("unwrap() sobre un Result erróneo")
        return self._value

    def unwrap_err(self) -> E:
        """Devuelve el error si es fallido; lanza ``ValueError`` si es ok."""
        if self._is_ok or self._error is None:
            raise ValueError("unwrap_err() sobre un Result exitoso")
        return self._error

    def unwrap_or(self, default: T) -> T:
        """Devuelve el valor si es ok, o ``default`` si es error."""
        return self._value if self._is_ok and self._value is not None else default

    def map(self, func):
        """Aplica ``func`` al valor si es ok; propaga el error si no.

        El tipo de retorno se infiere del resultado de ``func``.
        """
        if self._is_ok and self._value is not None:
            return Result.ok(func(self._value))
        assert self._error is not None
        return Result.err(self._error)
