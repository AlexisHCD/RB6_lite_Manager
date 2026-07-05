"""Tests del tipo ``Result`` (cimiento de manejo funcional de errores).

Estos tests validan que el núcleo funciona y que la infraestructura de tests
(pytest + pythonpath) está correctamente configurada.
"""

from __future__ import annotations

import pytest

from openbuds.core.result import Result


class TestResultOk:
    def test_ok_holds_value(self) -> None:
        r = Result.ok(42)
        assert r.is_ok()
        assert not r.is_err()
        assert r.unwrap() == 42

    def test_ok_with_none_value(self) -> None:
        # ok(None) es un resultado exitoso cuyo valor es None.
        r: Result[None, str] = Result.ok(None)
        assert r.is_ok()

    def test_unwrap_or_returns_value(self) -> None:
        r = Result.ok("hola")
        assert r.unwrap_or("default") == "hola"


class TestResultErr:
    def test_err_holds_error(self) -> None:
        r: Result[int, str] = Result.err("fallo")
        assert r.is_err()
        assert not r.is_ok()
        assert r.unwrap_err() == "fallo"

    def test_unwrap_raises_on_err(self) -> None:
        r: Result[int, str] = Result.err("fallo")
        with pytest.raises(ValueError):
            r.unwrap()

    def test_unwrap_or_returns_default_on_err(self) -> None:
        r: Result[int, str] = Result.err("fallo")
        assert r.unwrap_or(0) == 0


class TestResultMap:
    def test_map_transforms_ok_value(self) -> None:
        r: Result[int, str] = Result.ok(5)
        mapped = r.map(lambda x: x * 2)
        assert mapped.is_ok()
        assert mapped.unwrap() == 10

    def test_map_propagates_error(self) -> None:
        r: Result[int, str] = Result.err("fallo")
        mapped = r.map(lambda x: x * 2)
        assert mapped.is_err()
        assert mapped.unwrap_err() == "fallo"
