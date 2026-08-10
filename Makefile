# OpenBuds Manager — tareas comunes de desarrollo.
# Uso: make <target>

PYTHON ?= python3
VENV   ?= .venv
PIP    := $(VENV)/bin/pip
PY     := $(VENV)/bin/python

.DEFAULT_GOAL := help

.PHONY: help venv install install-dev lint typecheck test test-quick clean

help: ## Mostrar esta ayuda
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

venv: ## Crear entorno virtual (.venv)
	$(PYTHON) -m venv $(VENV)
	@echo "Entorno virtual creado en $(VENV)/"

install: venv ## Instalar dependencias de runtime
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt
	$(PIP) install -e .

install-dev: venv ## Instalar dependencias de desarrollo (incluye runtime)
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements-dev.txt
	$(PIP) install -e .

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
