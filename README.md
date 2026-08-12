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

🔜 **Etapa 1 — Caracterización física pasiva en curso.** Primera evidencia
pasiva del Redmi Buds 6 Lite real (A2DP/SBC reproduciendo, 2026-08-11) en
[`docs/research/redmi-buds-6-lite-passive-characterization.md`](docs/research/redmi-buds-6-lite-passive-characterization.md).

El **backend base de BlueZ**, la base de **inspección PipeWire de solo lectura**,
la **CI** y la **licencia GPL-3.0-or-later** de la Etapa 0 están **completados** según el
roadmap ([`docs/ROADMAP.md`](docs/ROADMAP.md)).

El repositorio contiene la arquitectura por capas, los cimientos del dominio,
la configuración TOML, logging, detección del entorno y una CLI base funcional.

El **backend base de BlueZ** (acceso a BlueZ vía D-Bus, PyGObject/Gio) está
publicado por incrementos; se consumirá en el backend de sesión (Etapa 2), y la
validación física del dispositivo es de la Etapa 1. El **Incremento 1 — snapshot
`GetManagedObjects`** ya está implementado y verificado (`bluez/dbus_protocol.py` → `GioDBusProtocol` +
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
  (`bluez/device_change_diff.py`), y
- el **polling de respaldo** (extensión interna compatible
  `on_poll`/`poll_interval_ms`: validación pura `type int > 0` antes del
  worker/GIO, `GSource` de timeout monotónico en el worker tras `on_ready`,
  `SOURCE_CONTINUE`, un solo timer por repositorio con intervalo inyectable
  default 5000 ms, y `_handle_poll` compartiendo el **mismo pipeline
  `_refresh_and_dispatch`** que `_handle_signal` para capturar
  `Connected`/`Paired`/`Trusted` si `PropertiesChanged` no llega).

La validez proviene de fakes deterministas (sin GI), del spike genérico de
D-Bus y de la **integración real** en Python 3.12 / Gio: **lifecycle
A/B** (subscribe/unsubscribe/close + snapshot A/B + bus usable) y el
**polling de respaldo** (creación/destrucción inmediata del `GSource` con
`poll_interval_ms=60_000`, sin tick real); **no** se inducen señales, **no**
se afirma recepción real de eventos y **no** hay escrituras de hardware. Ver
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
conectado). **Pendientes del backend base BlueZ:** la **validación empírica de
propiedades runtime inciertas** (bloqueada: sin auriculares conectados ni nodos
Bluetooth); el **polling periódico de respaldo** para
`Connected`/`Paired`/`Trusted`
([RESEARCH_LIMITS §4](docs/RESEARCH_LIMITS.md#4-fiabilidad-de-señales-d-bus))
está **implementado y verificado (2026-08-10)** como extensión interna
compatible `on_poll`/`poll_interval_ms` (default 5000 ms inyectable y validado),
con `GSource` de timeout monotónico en el worker y **un solo timer por
repositorio**; la señal primaria y el poll comparten el **pipeline común
señal/poll** (`_refresh_and_dispatch`). El diseño y el código real están en
[`docs/bluez/signal-lifecycle-design.md`](docs/bluez/signal-lifecycle-design.md)
(§12) y [`docs/bluez/repository-design.md`](docs/bluez/repository-design.md)
(§12). La base Bluetooth de solo lectura está implementada; la validación
empírica del Redmi Buds 6 Lite se realizará en la Etapa 1, después de estabilizar
el runtime y presentar el protocolo pasivo para aprobación. Ver
[`docs/ROADMAP.md`](docs/ROADMAP.md), [`docs/cli/devices-command.md`](docs/cli/devices-command.md).
La aplicación completa aún no está terminada: controles de sesión, diagnóstico
y GUI se implementan en las etapas siguientes.

La base de inspección de audio incluye el **parser de
`pw-dump`** (`infrastructure/pipewire/pw_dump_parser.py`, ADR-0003) — está
**implementada y verificada (2026-08-10)**: función **pura**
(`payload: str` de `pw-dump` → `list[dict[str, str]]`, sin subprocess, sin
I/O), extrae nodos Bluetooth (`media.class` `Audio/Sink`/`Audio/Source`) por
prefijo `bluez_output.`/`bluez_input.` o `device.api=bluez5`, normaliza valores
escalares (`str` verbatim, `bool` lowercase, `int`/`float` `str`,
`null`/`list`/`dict` ignorados), añade `object.id` canónico, ordena por `id`
numérico y **preserva `bluez5.codec` / `api.bluez5.transport` verbatim sin
validar ni inferir**
([RESEARCH_LIMITS §2](docs/RESEARCH_LIMITS.md#2-propiedades-runtime-de-pipewire)).
Los errores estructurales (`JSONDecodeError` o root no-lista) se envuelven en
`PipeWireParseError(AudioSubsystemError)`. Está cubierto por **20 unit tests** y
una **integración real opt-in** (`OPENBUDS_RUN_INTEGRATION=1`, `pw-dump
--no-colors` que **no exige nodos conectados**; resultado local **0 nodos**; sin
MAC ni payload en logs). **Límites:** sin auriculares conectados no se valida el
caso positivo (códec/transporte reales); **no** se afirma el Redmi Buds 6 Lite
detectado ni códec verificado. Ver
[`docs/pipewire/pw-dump-parser-contract.md`](docs/pipewire/pw-dump-parser-contract.md).

El runner seguro `PwDumpRunner`
(`infrastructure/pipewire/pw_dump_runner.py`, ADR-0003) — está **implementada
y verificada (2026-08-10)**: ejecuta `pw-dump --no-colors` de forma aislada y
privada (`subprocess.run` con `capture_output`/`text`/`check=False`, `timeout`
default 5 s, **nunca `shell=True`**, sin argumentos de usuario), traduce
cualquier fallo (`OSError`/`TimeoutExpired`, `returncode != 0`, stdout no-`str`)
a `PipeWireUnavailableError(AudioSubsystemError)` con mensajes genéricos sin
paths, stdout/stderr ni MAC, y devuelve el payload JSON exacto como `str`
(incluido `""`) para el parser puro. `binary` y `timeout_seconds` se validan en
el constructor antes de ejecutar nada (`str` no vacío sin NUL; tipo exacto
`int`/`float` no-`bool`, `> 0` y **finito** — NaN/±inf rechazados, divergencia
aprobada); el `executor` es inyectable por Protocol (fakes en tests, default
real `subprocess.run`). Sin `shutil.which` (TOCTOU) y sin logging de
payload/stderr (privacidad). Cubierto por **29 unit tests** y una **integración
real opt-in** (`OPENBUDS_RUN_INTEGRATION=1`) que encadena `runner.dump()` →
`parse_bluetooth_audio_nodes` sin exigir nodos Bluetooth (resultado local **0
nodos**). Ver
[`docs/pipewire/pw-dump-runner-contract.md`](docs/pipewire/pw-dump-runner-contract.md).

El repositorio `PipeWireRepository`
(`infrastructure/pipewire/pipewire_repository.py`, ADR-0003) — está
**implementada y verificada (2026-08-10)** en su **Incremento 1**
(`list_bluetooth_audio_nodes`): es una **capa de composición** que ejecuta
`runner.dump()` **fresco en cada llamada** (sin cache, logs, subprocess propio
ni mutación) y entrega el payload al parser puro, devolviendo directamente su
`list[dict[str, str]]`. Usa el Protocol estructural `DumpRunner` (`dump() ->
str`) inyectable por constructor con condición **`is None`** (`None` →
`PwDumpRunner()`; un runner **falsy** inyectado se preserva). Los errores se
**propagan sin re-envolver** (`PipeWireUnavailableError` del runner,
`PipeWireParseError` del parser; misma instancia). El contrato global
`IAudioRepository` sigue **parcialmente implementado**:
`get_active_codec`/`get_default_audio_sink` **permanecen `NotImplementedError`**
— **no** se infiere ni afirma códec
([RESEARCH_LIMITS §2](docs/RESEARCH_LIMITS.md#2-propiedades-runtime-de-pipewire)).
Cubierto por **8 unit tests** con fakes (sin `pw-dump`/PipeWire/GI) y una
**integración real opt-in** (`tests/integration/test_pipewire_repository.py`,
`OPENBUDS_RUN_INTEGRATION=1`: solo `isinstance(result, list)` y elementos
`dict` con valores `str`, **sin assert de nodos ni payload/MAC**; resultado
local **0 nodos**, sin afirmación positiva de hardware). Ver
[`docs/pipewire/repository-design.md`](docs/pipewire/repository-design.md).

El incremento de solo lectura de `WpctlAdapter` (`status` e `inspect`, con
`set_profile`/`restart_service` en `NotImplementedError`) fue **validado,
aprobado y publicado**. Solo lectura: las mutaciones permanecen
deshabilitadas.

Ver el roadmap completo en [`docs/ROADMAP.md`](docs/ROADMAP.md).

## Requisitos del sistema

- **Ubuntu 24.04 LTS** (Noble Numbat)
- **BlueZ** ≥ 5.72
- **PipeWire** ≥ 1.0
- **WirePlumber** 0.4.x (Ubuntu 24.04 trae 0.4.17 — sintaxis de configuración Lua)
- **Python del sistema de Ubuntu 24.04:** `/usr/bin/python3` (3.12), necesario
  para reutilizar PyGObject/Gio de la distribución en las integraciones BlueZ.
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

Muestra las versiones detectadas del stack y tres categorías de diagnóstico:

- **Sistema soportado** — SO y stack (Ubuntu 24.04, BlueZ, PipeWire, WirePlumber
  Lua 0.4 y bus D-Bus del sistema).
- **Runtime aplicación** — el intérprete es `/usr/bin/python3` y puede importar
  PyGObject/Gio/GLib (un venv creado desde Linuxbrew/Homebrew no lo cumple).
- **Hardware Bluetooth** — adaptador disponible; es informativo.

La ausencia de adaptador **no** implica un sistema no soportado: `doctor` sale
con 0 cuando sistema y runtime están listos aunque no haya hardware; solo sale
con 1 si el sistema o el runtime son inválidos.

## Uso

### CLI

```bash
.venv/bin/openbuds doctor        # diagnostica sistema, runtime y hardware
.venv/bin/openbuds config        # muestra la configuración efectiva
.venv/bin/openbuds version       # muestra la versión sin cargar config
.venv/bin/openbuds devices       # lista dispositivos Bluetooth (backend base publicado): snapshot TSV
.venv/bin/openbuds devices --paired-only            # solo emparejados
.venv/bin/openbuds devices --adapter hci0           # solo el adaptador hci0 (o /org/bluez/hci0)
.venv/bin/openbuds status         # estado agregado de dispositivos emparejados (batería/RSSI/perfil/códec/sink/source observados; sin identificadores)
.venv/bin/openbuds watch          # observa en vivo cambios de estado de dispositivos emparejados (solo lectura; Ctrl+C para salir)
.venv/bin/openbuds connect|disconnect|music|mic [dispositivo]  # sesión: confirmación previa; mic advierte de degradación; perfil runtime no persistente
.venv/bin/openbuds health        # futuro: Health Check (Etapa 4)
.venv/bin/openbuds codec         # futuro: muestra el códec activo (Etapa 2, sujeto a evidencia de Etapa 1)
.venv/bin/openbuds bench         # futuro: benchmark de enlace (posterior)
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

La GUI se implementará después de la caracterización física y del backend de
sesión. El MVP será una sola ventana útil con estado, batería/RSSI opcionales,
perfil, códec observado, sink/source, modos Música/Micrófono y Diagnóstico. La
bandeja de GNOME y vistas avanzadas se añadirán después del MVP.

## Desarrollo

```bash
make lint       # ruff check + format check
make typecheck  # mypy
make test       # pytest (suite completa)
make test-quick # pytest solo tests unitarios
```

**CI:** el workflow [`.github/workflows/ci.yml`](.github/workflows/ci.yml) ejecuta
la suite de calidad en **Python 3.12** en push/PR a `main` y por invocación
manual (`workflow_dispatch`): Ruff check y format, mypy y unit tests
(`pytest tests/unit -m "not slow"`). No ejecuta integraciones reales ni toca
hardware o PyGObject/Gio: es una validación unitaria de los gates, no un
sustituto de la integración local con `/usr/bin/python3`.

Las pruebas unitarias se ejecutan en el venv de desarrollo. Las integraciones
BlueZ deben ejecutarse con un venv creado desde `/usr/bin/python3`, con acceso a
PyGObject/Gio, y requieren `OPENBUDS_RUN_INTEGRATION=1`. No se mantienen conteos
exactos en esta documentación: la salida de pytest es la fuente de verdad.

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

Licenciado bajo [GPL-3.0-or-later](LICENSE).
