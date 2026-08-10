# OpenBuds Manager — tareas comunes de desarrollo.
# Uso: make <target>

PYTHON ?= /usr/bin/python3
VENV   ?= .venv
USE_SYSTEM_PYGOBJECT ?= 1

ifeq ($(origin VENV_FLAGS), undefined)
ifeq ($(USE_SYSTEM_PYGOBJECT),1)
VENV_FLAGS = --system-site-packages
else
VENV_FLAGS =
endif
endif

PIP    := $(VENV)/bin/pip
PY     := $(VENV)/bin/python

.DEFAULT_GOAL := help

.PHONY: help venv check-runtime install install-dev lint typecheck test test-quick clean

help: ## Mostrar esta ayuda
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

venv: ## Crear entorno virtual (.venv)
	@if [ -d "$(VENV)" ]; then \
		echo "Entorno virtual existente: $(VENV)/ (no se recrea)"; \
	else \
		$(PYTHON) -m venv $(VENV_FLAGS) "$(VENV)" || exit $$?; \
		echo "Entorno virtual creado en $(VENV)/"; \
	fi

ifeq ($(USE_SYSTEM_PYGOBJECT),1)
	@if ! $(MAKE) --no-print-directory check-runtime VENV="$(VENV)"; then \
		echo "ERROR: el venv existente no ve PyGObject/Gio." >&2; \
		echo "Usa el Python del sistema y recréalo manualmente con: $(PYTHON) -m venv $(VENV_FLAGS) $(VENV)" >&2; \
		echo "El venv no se ha eliminado automáticamente: $(VENV)" >&2; \
	exit 1; \
	fi
endif

check-runtime: ## Comprobar que el venv puede importar PyGObject/Gio
	@$(PY) -c 'import gi; gi.require_version("Gio", "2.0"); from gi.repository import Gio, GLib; print("Runtime OK: PyGObject/Gio 2.0 y GLib disponibles")'

install: venv ## Instalar dependencias de runtime
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt
	$(PIP) install -e .
	$(MAKE) --no-print-directory check-runtime VENV="$(VENV)"

install-dev: venv ## Instalar dependencias de desarrollo (incluye runtime)
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements-dev.txt
	$(PIP) install -e .
	$(MAKE) --no-print-directory check-runtime VENV="$(VENV)"

lint: ## Ejecutar ruff (lint + format check)
	$(VENV)/bin/ruff check src tests
	$(VENV)/bin/ruff format --check src tests

typecheck: ## Ejecutar mypy
	$(VENV)/bin/mypy src

test: ## Ejecutar toda la suite de tests
	$(VENV)/bin/pytest

test-quick: ## Ejecutar solo tests unitarios rápidos
	$(VENV)/bin/pytest tests/unit -m "not slow"

clean: ## Limpiar artefactos generados (no toca el venv ni backups)
	rm -rf build/ dist/ *.egg-info src/*.egg-info
	rm -rf .mypy_cache .ruff_cache .pytest_cache
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
