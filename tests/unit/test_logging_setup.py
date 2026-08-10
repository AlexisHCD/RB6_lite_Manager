"""Tests de configuración de logging."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

import pytest

from openbuds.core.config import default_config
from openbuds.core.errors import ConfigError
from openbuds.core.events import Event, EventBus
from openbuds.core.logging_setup import (
    DATEFMT,
    FMT,
    LOG_EVENT_NAME,
    EventBusLogHandler,
    LogEntry,
    get_logger,
    setup_logging,
    setup_logging_from_config,
)


class TestGetLogger:
    def test_returns_named_logger(self) -> None:
        logger = get_logger("openbuds.test.module")
        assert logger.name == "openbuds.test.module"


class TestSetupLogging:
    def test_file_handler_oserror_is_wrapped_as_config_error(
        self, monkeypatch, tmp_path: Path
    ) -> None:
        log_file = tmp_path / "openbuds.log"

        def fail_handler(*args: object, **kwargs: object) -> RotatingFileHandler:
            raise OSError("permiso denegado")

        monkeypatch.setattr("openbuds.core.logging_setup.RotatingFileHandler", fail_handler)

        with pytest.raises(ConfigError, match=str(log_file)) as raised:
            setup_logging(log_file=str(log_file))
        assert isinstance(raised.value.__cause__, OSError)

    def test_root_level_is_set(self) -> None:
        setup_logging(level="DEBUG")
        assert logging.getLogger().level == logging.DEBUG

    def test_stream_handler_always_present(self) -> None:
        setup_logging(level="INFO")
        handlers = logging.getLogger().handlers
        assert any(isinstance(h, logging.StreamHandler) for h in handlers)

    def test_file_handler_is_rotating_when_log_file_given(self, tmp_path: Path) -> None:
        log_file = tmp_path / "openbuds.log"
        setup_logging(level="INFO", log_file=str(log_file))
        handlers = logging.getLogger().handlers
        rotating = [h for h in handlers if isinstance(h, RotatingFileHandler)]
        assert len(rotating) == 1
        assert rotating[0].maxBytes == 1 * 1024 * 1024
        assert rotating[0].backupCount == 5

    def test_no_file_handler_when_log_file_empty(self) -> None:
        setup_logging(level="INFO", log_file="")
        handlers = logging.getLogger().handlers
        assert not any(isinstance(h, RotatingFileHandler) for h in handlers)

    def test_writes_to_file(self, tmp_path: Path) -> None:
        log_file = tmp_path / "openbuds.log"
        setup_logging(level="INFO", log_file=str(log_file))
        logger = get_logger("openbuds.test.write")
        logger.info("mensaje de prueba")

        # Flush para asegurar que el contenido llega al disco.
        for h in logging.getLogger().handlers:
            h.flush()

        content = log_file.read_text(encoding="utf-8")
        assert "mensaje de prueba" in content

    def test_invalid_level_falls_back_to_info(self) -> None:
        # Un nivel no reconocido no debe romper el logging.
        setup_logging(level="NO_EXISTE")
        assert logging.getLogger().level == logging.INFO

    def test_lowercase_level_accepted(self) -> None:
        setup_logging(level="warning")
        assert logging.getLogger().level == logging.WARNING

    def test_log_record_is_published_as_log_entry(self) -> None:
        bus = EventBus()
        received: list[Event] = []
        bus.subscribe(LOG_EVENT_NAME, received.append)
        setup_logging(level="INFO", event_bus=bus)

        get_logger("openbuds.test.events").info("mensaje")

        assert len(received) == 1
        assert received[0].name == LOG_EVENT_NAME
        assert isinstance(received[0].payload, LogEntry)
        entry = received[0].payload
        assert entry.level_name == "INFO"
        assert entry.logger_name == "openbuds.test.events"
        assert entry.message == "mensaje"
        assert entry.timestamp.tzinfo is not None
        assert entry.timestamp.utcoffset() is not None
        assert entry.exception_text is None

    def test_log_arguments_are_interpolated(self) -> None:
        bus = EventBus()
        received: list[Event] = []
        bus.subscribe(LOG_EVENT_NAME, received.append)
        setup_logging(event_bus=bus)

        get_logger("openbuds.test.events").info("valor=%s", 7)

        assert received[0].payload.message == "valor=7"

    def test_exception_is_included_in_log_entry(self) -> None:
        bus = EventBus()
        received: list[Event] = []
        bus.subscribe(LOG_EVENT_NAME, received.append)
        setup_logging(event_bus=bus)

        try:
            raise ValueError("fallo de prueba")
        except ValueError:
            get_logger("openbuds.test.events").exception("operación fallida")

        entry = received[0].payload
        assert entry.exception_text is not None
        assert "ValueError: fallo de prueba" in entry.exception_text

    def test_subscriber_exception_does_not_escape_logging(self) -> None:
        bus = EventBus()
        bus.subscribe(LOG_EVENT_NAME, lambda _event: (_ for _ in ()).throw(RuntimeError("fallo")))
        setup_logging(event_bus=bus)
        previous_raise_exceptions = logging.raiseExceptions
        logging.raiseExceptions = False
        try:
            get_logger("openbuds.test.events").error("no debe escapar")
        finally:
            logging.raiseExceptions = previous_raise_exceptions

    def test_repeated_setup_does_not_accumulate_event_handlers(self) -> None:
        bus = EventBus()
        setup_logging(event_bus=bus)
        setup_logging(event_bus=bus)

        handlers = logging.getLogger().handlers
        assert sum(isinstance(handler, EventBusLogHandler) for handler in handlers) == 1


class TestSetupLoggingFromConfig:
    def test_applies_level_from_config(self) -> None:
        from dataclasses import replace

        config = replace(default_config(), log_level="DEBUG")
        setup_logging_from_config(config)
        assert logging.getLogger().level == logging.DEBUG

    def test_applies_log_file_from_config(self, tmp_path: Path) -> None:
        from dataclasses import replace

        log_file = tmp_path / "from_config.log"
        config = replace(default_config(), log_file=str(log_file))
        setup_logging_from_config(config)
        handlers = logging.getLogger().handlers
        assert any(isinstance(h, RotatingFileHandler) for h in handlers)

    def test_empty_log_file_no_file_handler(self) -> None:
        from dataclasses import replace

        config = replace(default_config(), log_file="")
        setup_logging_from_config(config)
        handlers = logging.getLogger().handlers
        assert not any(isinstance(h, RotatingFileHandler) for h in handlers)


class TestFormatConstants:
    def test_format_constants_stable(self) -> None:
        # Contrato: el formato y datefmt no deben cambiar sin coordinación,
        # porque afecta a la vista de Logs y a los parsers de la GUI.
        assert FMT == "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
        assert DATEFMT == "%Y-%m-%d %H:%M:%S"
