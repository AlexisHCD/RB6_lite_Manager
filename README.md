# OpenBuds Manager

Administrador profesional de **auriculares Bluetooth** para **Linux** (Ubuntu 24.04 LTS).

El objetivo es crear el equivalente en Linux a aplicaciones como *Xiaomi Earbuds*,
*Sony Headphones Connect*, *Galaxy Wearable* o *Nothing X*, comenzando por los
**Redmi Buds 6 Lite**.

> **Filosofía:** este proyecto **no** desarrolla drivers, **no** modifica firmware,
> **no** escribe en el hardware ni envía comandos propietarios al dispositivo.
> Únicamente **administra y optimiza el stack Bluetooth del sistema Linux**
> (BlueZ, PipeWire, WirePlumber) de forma segura y reversible.

## Estado del proyecto

✅ **Fase 2 — Backend base (completada).** 🚧 **Fase 3 — Bluetooth (en curso).**

El repositorio contiene la arquitectura por capas, los cimientos del dominio,
la configuración TOML, logging, detección del entorno y una CLI base funcional.

La Fase 3 implementa el acceso a BlueZ vía D-Bus (PyGObject/Gio) por
incrementos. El **Incremento 1 — snapshot `GetManagedObjects`** ya está
implementado y verificado (`bluez/dbus_protocol.py` → `GioDBusProtocol` +
`BlueZDBusClient.snapshot`), y también el **mapeo de objetos D-Bus → modelos**
(`bluez/object_mapper.py`, puro y sin GI) y las **consultas snapshot del
repositorio** (`bluez/bluez_repository.py`:
`list_adapters`/`list_devices`/`get_device`/`get_battery`/`get_rssi`, con
cliente D-Bus inyectable y snapshot fresco por llamada); la integración real
solo lectura se verificó en **Python 3.12 / Gio**. La suscripción a cambios
(`subscribe_device_changes`, Incremento 2 de señales) sigue pendiente, por lo
que el repositorio todavía no cumple su contrato completo. La CLI `devices`
puede construirse ya sobre las consultas snapshot y es el siguiente incremento
(ver [`docs/bluez/gio-dbus-client-design.md`](docs/bluez/gio-dbus-client-design.md)
y [`docs/bluez/repository-design.md`](docs/bluez/repository-design.md)).
La aplicación completa aún no está terminada: diagnóstico y la GUI se
implementan en las fases siguientes.

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

PyGObject (D-Bus vía GLib) se usa a través del paquete de la distribución en
Ubuntu; no necesita compilarse si el venv reutiliza los paquetes de sistema:

```bash
sudo apt update
sudo apt install -y \
    python3-gi python3-gi-cairo gir1.2-glib-2.0 gobject-introspection \
    bluez pipewire wireplumber
```

> ⚠️ **Usa el Python del sistema, no el de Homebrew/Linuxbrew.** Si tu `python3`
> proviene de Homebrew/Linuxbrew, su `sys.path` **no incluye** los paquetes de
> `apt` (`/usr/lib/python3/dist-packages`) y, por tanto, **no verá**
> `python3-gi` ni el resto de paquetes del sistema. Por eso los comandos de
> abajo usan explícitamente `/usr/bin/python3`.

### 2. Entorno Python y dependencias

**Camino recomendado:** ejecutar `make install-dev`. El Makefile crea `.venv`
con `--system-site-packages` solo si no existe, reutilizando `python3-gi` ya
instalado; después instala las dependencias y el paquete en modo editable.

```bash
# Crea .venv correctamente si no existe e instala runtime + desarrollo
make install-dev
```

Si `.venv` fue creado previamente con el `python3` de Linuxbrew/Homebrew,
elimínalo manualmente antes de recrearlo; no se borra automáticamente:

```bash
rm -rf .venv
make install-dev
```

**Alternativa PyPI (opcional):** si prefieres que `pip` compile PyGObject
desde PyPI, instala primero sus dependencias oficiales de compilación:

```bash
sudo apt install -y \
    libgirepository-2.0-dev gcc libcairo2-dev pkg-config python3-dev
```

Después crea el venv sin paquetes de sistema e instala con:

```bash
make USE_SYSTEM_PYGOBJECT=0 install-dev
```

Así `pip` compilará `PyGObject` en lugar de usar `python3-gi`. Esta alternativa
requiere que `.venv` todavía no exista, o que haya sido creado previamente con
`USE_SYSTEM_PYGOBJECT=0`; el Makefile nunca borra ni recrea un venv existente.

### 3. Verificar el entorno

```bash
make check-runtime
.venv/bin/openbuds doctor
```

Muestra las versiones detectadas del stack y si el entorno está soportado.

## Uso

### CLI

```bash
.venv/bin/openbuds doctor      # detecta y muestra el entorno del sistema
.venv/bin/openbuds config      # muestra la configuración efectiva
.venv/bin/openbuds version     # muestra la versión sin cargar config
.venv/bin/openbuds devices     # Fase 3: siguiente incremento sobre las consultas snapshot
.venv/bin/openbuds health      # futuro: Health Check (Fase 5)
.venv/bin/openbuds codec       # futuro: muestra el códec activo (Fase 3/4)
.venv/bin/openbuds bench       # futuro: benchmark de enlace (Fase 5)
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

**Baseline actual:** **177 tests** en verde + **3 skipped** (integración
BlueZ opt-in desactivada por defecto; 2026-08-09). El cliente D-Bus
(Incremento 1), el mapper de objetos y las consultas snapshot del repositorio
ya están cubiertos por la suite; las pruebas de señales (Incremento 2) se
añadirán en el incremento correspondiente y actualizarán este número.

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
| [0006](docs/ADR/0006-app-config-toml-xdg-atomic-write.md) | Configuración TOML con rutas XDG y escritura atómica |

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
