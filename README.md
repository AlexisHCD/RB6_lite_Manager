# OpenBuds Manager

Administrador profesional de **auriculares Bluetooth** para **Linux** (Ubuntu 24.04 LTS).

El objetivo es crear el equivalente en Linux a aplicaciones como *Xiaomi Earbuds*,
*Sony Headphones Connect*, *Galaxy Wearable* o *Nothing X*, comenzando por los
**Redmi Buds 6 Lite**.

> **Filosofía:** este proyecto **no** desarrolla drivers, **no** modifica firmware,
> **no** escribe en el hardware ni **no** envía comandos propietarios al dispositivo.
> Únicamente **administra y optimiza el stack Bluetooth del sistema Linux**
> (BlueZ, PipeWire, WirePlumber) de forma segura y reversible.

## Estado del proyecto

🚧 **Fase 1 — Planificación y Arquitectura (completada).**

Actualmente el repositorio contiene los **cimientos** del proyecto: arquitectura
por capas (Clean Architecture), contratos del dominio, modelos, jerarquía de
errores, utilidades core y esqueletos de todos los módulos previstos en el
roadmap. **No hay lógica de negocio implementada todavía.**

Ver el roadmap completo en [`docs/ROADMAP.md`](docs/ROADMAP.md).

## Requisitos del sistema

- **Ubuntu 24.04 LTS** (Noble Numbat)
- **BlueZ** ≥ 5.72
- **PipeWire** ≥ 1.0
- **WirePlumber** 0.4.x (Ubuntu 24.04 trae 0.4.17 — sintaxis de configuración Lua)
- **Python** ≥ 3.12 (probado con 3.14)
- Adaptador USB Bluetooth (o integrado)

> ⚠️ **Importante sobre WirePlumber:** Ubuntu 24.04 usa WirePlumber **0.4.x**
> (configuración Lua `.lua.d/`), **no** la versión 0.5 (`.conf.d/`). Este proyecto
> está diseñado para la 0.4.x. Ver [ADR-0002](docs/ADR/0002-wireplumber-0.4-lua-config-scope.md).

## Instalación (entorno de desarrollo)

### 1. Paquetes de sistema

PyGObject (D-Bus vía GLib) requiere cabeceras del sistema en Ubuntu:

```bash
sudo apt update
sudo apt install -y \
    python3-gi python3-gi-cairo gir1.2-glib-2.0 gobject-introspection \
    libgirepository1.0-dev pkg-config \
    bluez pipewire wireplumber
```

> Si `pip install PyGObject` falla durante la instalación de dependencias,
> instala el paquete `python3-gi` desde `apt` (más fiable en Ubuntu) y omite
> `PyGObject` en `requirements.txt`.

### 2. Entorno Python

```bash
make install-dev   # crea .venv, instala requirements-dev.txt y el paquete en modo editable
```

O manualmente:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/pip install -e .
```

### 3. Verificar el entorno

```bash
.venv/bin/openbuds doctor
```

Muestra las versiones detectadas del stack y si el entorno está soportado.

## Uso

### CLI

```bash
.venv/bin/openbuds doctor      # detecta y muestra el entorno del sistema
.venv/bin/openbuds devices     # lista dispositivos (Fase 3)
.venv/bin/openbuds health      # Health Check (Fase 5)
```

### GUI (PySide6)

La interfaz gráfica se implementa en la **Fase 6**. Incluirá las 10 vistas
requeridas (Dashboard, Dispositivo, Audio, Optimización, Health Check,
Diagnóstico, Benchmark, Logs, Configuración, Laboratorio Experimental) y un
icono residente en la bandeja del sistema.

## Desarrollo

```bash
make lint       # ruff check + format check
make typecheck  # mypy
make test       # pytest (suite completa)
make test-quick # pytest solo tests unitarios
```

## Arquitectura

El proyecto sigue **Clean Architecture** con dependencias unidireccionales:

```
presentation → application → domain ← infrastructure
```

- **`domain`** — núcleo puro: modelos, enumeraciones y contratos (interfaces).
  Sin dependencias externas. Es lo primero que se completa y lo más estable.
- **`application`** — casos de uso que orquestan repositorios.
- **`infrastructure`** — implementaciones concretas (BlueZ/D-Bus, PipeWire,
  WirePlumber, detección del sistema).
- **`presentation`** — interfaz gráfica (PySide6) y notificaciones.

Ver [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) para el detalle y el diagrama.

### Decisiones técnicas documentadas (ADRs)

| ADR | Decisión |
|-----|----------|
| [0001](docs/ADR/0001-decision-dbus-pygobject-gio.md) | Biblioteca D-Bus: PyGObject/Gio (GDBus) |
| [0002](docs/ADR/0002-wireplumber-0.4-lua-config-scope.md) | WirePlumber 0.4 Lua, scope `~/.config/wireplumber/` |
| [0003](docs/ADR/0003-no-pipewire-python-binding.md) | Sin binding Python de PipeWire; usar `pw-dump`/`wpctl` |
| [0004](docs/ADR/0004-clean-architecture-dependency-rule.md) | Regla de dependencias de Clean Architecture |
| [0005](docs/ADR/0005-device-profile-contract.md) | Contrato de perfiles de dispositivo |

## Seguridad

Toda modificación de configuración sigue un flujo **obligatorio** y reversible:

1. **Detectar** entorno (¿es seguro operar?)
2. **Backup** con timestamp (antes de tocar nada)
3. **Validar** el cambio
4. **Aplicar** (solo en `~/.config/wireplumber/`, nunca con root)
5. **Verificar** el resultado
6. **Revertir** automáticamente si cualquier paso falla

Si el backup falla, **no se aplica el cambio**. Ver
[`docs/ADR/0002`](docs/ADR/0002-wireplumber-0.4-lua-config-scope.md).

## Licencia

GPL-3.0-or-later.
