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
(`bluez/object_mapper.py`, puro y sin GI), las **consultas snapshot del
repositorio** (`bluez/bluez_repository.py`:
`list_adapters`/`list_devices`/`get_device`/`get_battery`/`get_rssi`, con
cliente D-Bus inyectable y snapshot fresco por llamada) y la **CLI `devices`**
(ver abajo); la integración real solo lectura se verificó en **Python 3.12 /
Gio**. El **Incremento 2 — señales y lifecycle** está **completo**:
- El **nivel bajo** (`GioDBusProtocol` + `_SignalWorker`: worker dedicado GLib
  `MainContext`/`MainLoop` daemon, tres filtros exactos
  `InterfacesAdded`/`InterfacesRemoved`/`PropertiesChanged`, `SignalEvent` sin
  payload, suscripción/unsubscribe/close idempotentes, arranque perezoso, hook
  **`on_ready`** opcional que corre en el hilo del worker antes de que
  `subscribe` retorne, timeout y rollback atómico, sin cerrar la conexión
  compartida) y
- el **dispatch del repositorio** (`BlueZRepository.subscribe_device_changes`:
  init A→B con snapshot B en el worker vía `on_ready`, cache de diff,
  refresh completo por señal, orden determinista `REMOVED→ADDED→UPDATED`,
  igualdad mapeada de `DeviceInfo` sin eventos Battery/RSSI-only, aislamiento
  de callbacks, suscriptores múltiples/tardíos/reentrantes, `Unsubscribe`
  idempotente con espera de in-flight, concurrencia de init y rollback de
  errores), sobre el **diff puro de snapshots**
  (`bluez/device_change_diff.py`).

La validez proviene de fakes deterministas (sin GI), del spike genérico de
D-Bus y de la **integración real** en Python 3.12 / Gio: solo **lifecycle
A/B** (subscribe/unsubscribe/close + snapshot A/B + bus usable); **no** se
inducen señales, **no** se afirma recepción real de eventos y **no** hay
escrituras de hardware. Ver
[`docs/bluez/signal-lifecycle-design.md`](docs/bluez/signal-lifecycle-design.md)
y [`docs/bluez/repository-design.md`](docs/bluez/repository-design.md). El
**contrato completo de `IBluetoothRepository`** queda así **cerrado** (checkbox
del roadmap marcado), incluido el contrato de eventos
([ADR-0007](docs/ADR/0007-device-change-event-contract.md):
`DeviceChangeKind`, `DeviceChangeEvent` y `Unsubscribe`), probado con fakes y
integración. La **detección de adaptadores y dispositivos** está **completa**
(implementación + verificación real). **Verificación real 2026-08-10** (sin
auriculares conectados): `doctor` exit 0 (Ubuntu 24.04, BlueZ 5.72, PipeWire
1.0.5, WirePlumber 0.4.17 Lua, bus/adaptador/config sí); adaptador detectado
(`hci0`, `Powered=True`, `Discovering=False`, `Discoverable=False`); **caso
cero dispositivos**: `openbuds devices` exit 0 con `No se encontraron
dispositivos Bluetooth.` y `pw-dump` con **0 nodos Bluetooth** (sin property
keys). **No** se afirma detección del Redmi Buds 6 Lite (no había hardware
conectado). **Pendientes de la Fase 3:** la **validación empírica de
propiedades runtime inciertas** (bloqueada: sin auriculares conectados ni nodos
Bluetooth) y el **polling periódico de respaldo** para
`Connected`/`Paired`/`Trusted`
([RESEARCH_LIMITS §4](docs/RESEARCH_LIMITS.md#4-fiabilidad-de-señales-d-bus)),
**no implementado** y necesario antes de cerrar la Fase 3 (ver
[`docs/ROADMAP.md`](docs/ROADMAP.md), [`docs/cli/devices-command.md`](docs/cli/devices-command.md)).
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
.venv/bin/openbuds doctor        # detecta y muestra el entorno del sistema
.venv/bin/openbuds config        # muestra la configuración efectiva
.venv/bin/openbuds version       # muestra la versión sin cargar config
.venv/bin/openbuds devices       # lista dispositivos Bluetooth (Fase 3): snapshot TSV
.venv/bin/openbuds devices --paired-only            # solo emparejados
.venv/bin/openbuds devices --adapter hci0           # solo el adaptador hci0 (o /org/bluez/hci0)
.venv/bin/openbuds health        # futuro: Health Check (Fase 5)
.venv/bin/openbuds codec         # futuro: muestra el códec activo (Fase 3/4)
.venv/bin/openbuds bench         # futuro: benchmark de enlace (Fase 5)
```

`openbuds devices` lista el snapshot de los dispositivos **conocidos** por
BlueZ (solo lectura: sin discovery, sin conexión y sin señales) en TSV en
español:

```text
NOMBRE	CONEXIÓN	EMPAREJAMIENTO	ADAPTADOR
Redmi Buds 6 Lite	conectado	emparejado	hci0
```

La salida es **privada por diseño**: nunca incluye MAC ni rutas de objeto D-Bus
(`/org/bluez/.../dev_`), los nombres sin `alias`/`name` se muestran como
`Dispositivo sin nombre`, y los campos de texto se sanitizan (caracteres de
control → `?`, máx. 80 caracteres). Un valor de adaptador inválido sale con
código 2 antes de tocar el bus; un error de lectura de BlueZ sale con 1 y el
mensaje en stderr. Detalles en
[`docs/cli/devices-command.md`](docs/cli/devices-command.md).

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

**Baseline actual por defecto (Python 3.14):** **276 tests** en verde +
**6 skipped** (las 6 integraciones BlueZ opt-in desactivadas por defecto;
2026-08-10); con `OPENBUDS_RUN_INTEGRATION=1` en **Python 3.12 / Gio**:
**282 passed**. Ruff y mypy en verde. El cliente D-Bus (Incremento 1), el
mapper de objetos, el **worker y lifecycle de señales de bajo nivel** y el
**dispatch del repositorio** (Incremento 2 completo), el **diff puro de
snapshots** (`device_change_diff.py`), el contrato de eventos de cambio de
dispositivo ([ADR-0007](docs/ADR/0007-device-change-event-contract.md)), las
consultas snapshot del repositorio y la CLI `devices` ya están cubiertos por la
suite (`tests/unit/test_device_change_diff.py`,
`tests/unit/test_bluez_repository_signals.py`,
`tests/integration/test_bluez_repository_signals.py`).

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
