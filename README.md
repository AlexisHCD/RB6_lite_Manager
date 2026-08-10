# OpenBuds Manager

Administrador de auriculares Bluetooth para Linux. Construye una capa inteligente de administración sobre el stack Bluetooth existente (BlueZ, PipeWire, WirePlumber, DBus). Comienza con los **Redmi Buds 6 Lite**.

## Estado

**Fase 1** — Fundaciones (arquitectura, logging, configuración, CLI, detección del sistema).

## Requisitos

- Python 3.12+
- Linux con BlueZ, PipeWire y WirePlumber

## Instalación

```bash
cd /home/alexdev/proyectos/RedmiBuds6LinuxAPP
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Uso

```bash
# Diagnóstico completo del sistema
openbuds doctor

# Ver configuración
openbuds config

# Versión
openbuds version

# Estado de BlueZ y dispositivos Bluetooth
openbuds bluetooth status
```

## Arquitectura

```
backend/         Lógica de negocio (Bluetooth, PipeWire, sistema, backups, diagnósticos)
frontend/        Interfaz gráfica PySide6 (Fase 5)
profiles/        Perfiles de dispositivos (Redmi Buds 6 Lite)
plugins/         Sistema de plugins (Fase 7)
benchmark/       Medición de rendimiento (Fase 4)
logging/         Logging centralizado
utils/           Utilidades compartidas
tests/           Pruebas
```

## Filosofía

- Modifica Linux, **nunca** el hardware.
- No toca firmware, EEPROM ni NVRAM.
- Toda modificación es reversible y con backup previo.
