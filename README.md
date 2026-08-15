# OpenBuds Manager

Administrador de escritorio y CLI para auriculares Bluetooth en Linux. La
versión actual es **0.1.0 Beta** y está enfocada en **Redmi Buds 6 Lite**.

> Esta beta fue probada en un único entorno: Ubuntu 24.04 LTS, Python 3.12,
> BlueZ/PipeWire/WirePlumber de la distribución y Redmi Buds 6 Lite. El
> funcionamiento en otras distribuciones, versiones del stack o modelos no
> está garantizado.

## Alcance de la beta

OpenBuds Manager observa y administra el stack Bluetooth y de audio del
sistema mediante las APIs estándar de Linux. No es un driver ni una aplicación
oficial de Xiaomi.

Incluye:

- GUI PySide6 de una sola ventana con estado del dispositivo, batería/RSSI
  cuando el sistema los expone, perfil/códec solo cuando están verificados,
  estado de audio y diagnóstico.
- Conectar y desconectar dispositivos emparejados con confirmación explícita.
- Cambio runtime entre música (A2DP) y micrófono (HFP), si el perfil es
  ofrecido por el sistema. El cambio no se persiste en el dispositivo.
- CLI para listar dispositivos conocidos por BlueZ, consultar estado,
  observar cambios, ejecutar Health Check y leer logs sanitizados.
- Configuración propia TOML en las rutas XDG, backups y escritura atómica.
- Auto-fixes limitados y reversibles para problemas que el Health Check marque
  como disponibles.

No incluye firmware, OTA, comandos Bluetooth propietarios, escritura GATT,
modificación del hardware ni soporte genérico garantizado para otros modelos.
No modifica emparejamientos, `Trusted`, `Blocked` ni `Pairable`
automáticamente.

## Estado conocido y límites

La GUI continúa respondiendo mientras actualiza los datos en segundo plano. El
estado mostrado como «Listo» indica que no hay una acción explícita ni un
error que requiera feedback del usuario; el refresco periódico puede seguir
ejecutándose en segundo plano sin convertir cada ciclo en un mensaje visible.

La suspensión y reanudación se probaron con este resultado: la sesión de la
aplicación y la gráfica se recuperaron, pero los auriculares quedaron
emparejados y desconectados; **no hubo reconexión automática**. La conexión se
puede restablecer desde la GUI o con `openbuds connect`.

Otros límites importantes:

- Los campos ausentes del sistema aparecen como «No disponible»; no se
  inventan batería, códec, RSSI ni capacidades.
- El códec solo se muestra si fue observado de forma verificable. No se
  asume aptX, LDAC ni ninguna capacidad no expuesta por PipeWire.
- El cambio de perfil es runtime y se revierte manualmente con `music` o
  `mic`; no hay persistencia de perfiles ni benchmark de latencia/calidad.
- La bandeja y las notificaciones son opcionales y best-effort.
- Los auto-fixes no reinician BlueZ ni requieren `sudo`; solo se ofrecen cuando
  el diagnóstico los marca como disponibles.

La evidencia y las decisiones técnicas están resumidas en
[`docs/ROADMAP.md`](docs/ROADMAP.md), [`docs/RESEARCH_LIMITS.md`](docs/RESEARCH_LIMITS.md)
y la [caracterización pasiva](docs/research/redmi-buds-6-lite-passive-characterization.md).

## Requisitos

Entorno objetivo:

- Ubuntu 24.04 LTS (Noble Numbat).
- `/usr/bin/python3` de Ubuntu 24.04 (Python 3.12).
- BlueZ, PipeWire y WirePlumber disponibles y en ejecución según corresponda.
  Ubuntu 24.04 usa WirePlumber 0.4.x con configuración Lua.
- Adaptador Bluetooth integrado o USB.
- Un display para la GUI.

Las dependencias Python declaradas son PySide6 y PyGObject; las versiones de
desarrollo están en [`requirements-dev.txt`](requirements-dev.txt) y
[`pyproject.toml`](pyproject.toml). PyGObject puede reutilizar el paquete
`python3-gi` de Ubuntu mediante un entorno virtual con paquetes del sistema.

## Instalación reproducible en Ubuntu 24.04

Instala primero el stack y PyGObject de la distribución:

```bash
sudo apt update
sudo apt install -y \
  python3-gi python3-gi-cairo gir1.2-glib-2.0 gobject-introspection \
  bluez pipewire wireplumber
```

Clona el repositorio y prepara el entorno de desarrollo usando explícitamente
el Python de Ubuntu:

```bash
git clone https://github.com/AlexisHCD/RB6_lite_Manager.git
cd RB6_lite_Manager
make PYTHON=/usr/bin/python3 install-dev
make check-runtime
```

`make install-dev` crea `.venv` con `--system-site-packages`, instala las
dependencias declaradas y el paquete en modo editable. Para una instalación
sin herramientas de desarrollo usa `make PYTHON=/usr/bin/python3 install`.
El programa no necesita `sudo` para ejecutarse.

Si ya existe un `.venv`, el Makefile no lo recrea ni lo elimina. Comprueba que
pertenece a `/usr/bin/python3`; si no, crea un entorno nuevo siguiendo el
procedimiento anterior en una copia limpia del repositorio.

## Primeros pasos

Comprueba el sistema, el runtime y el adaptador:

```bash
.venv/bin/openbuds version
.venv/bin/openbuds doctor
.venv/bin/openbuds health
```

Lista los dispositivos conocidos por BlueZ y abre la GUI:

```bash
.venv/bin/openbuds devices --paired-only
.venv/bin/openbuds gui
```

La aplicación trabaja con dispositivos ya emparejados por el sistema. El
primer emparejamiento debe hacerse con las herramientas normales de Ubuntu.
OpenBuds no inicia discovery ni borra emparejamientos.

## CLI

Todos los comandos se pueden consultar con `--help`. Los nombres de
dispositivo se resuelven por alias/nombre; la salida no muestra MAC ni rutas
de objeto D-Bus.

```bash
# Entorno y configuración
.venv/bin/openbuds doctor
.venv/bin/openbuds config get
.venv/bin/openbuds config set <clave> <valor> --dry-run
.venv/bin/openbuds config backup
.venv/bin/openbuds config backups
.venv/bin/openbuds config restore <archivo.bak>

# Estado y observación (solo lectura)
.venv/bin/openbuds devices --paired-only
.venv/bin/openbuds devices --adapter hci0
.venv/bin/openbuds status
.venv/bin/openbuds watch                 # Ctrl+C para salir
.venv/bin/openbuds health
.venv/bin/openbuds logs --lines 20
.venv/bin/openbuds logs --service bluez --service pipewire --lines 50

# Sesión y perfiles runtime; siempre piden confirmación
.venv/bin/openbuds connect "Redmi Buds 6 Lite"
.venv/bin/openbuds disconnect "Redmi Buds 6 Lite"
.venv/bin/openbuds music "Redmi Buds 6 Lite"
.venv/bin/openbuds mic "Redmi Buds 6 Lite"

# Reparaciones disponibles solo cuando `health` las indica
.venv/bin/openbuds fix start.audio
.venv/bin/openbuds fix profile.a2dp
```

`connect`, `disconnect`, `music`, `mic` y `fix` modifican únicamente el estado
runtime permitido por las APIs del sistema y solicitan confirmación `[s/N]`.
`--yes` está disponible para automatización consciente. `mic` avisa que HFP
puede reducir la calidad de reproducción. Consulta los detalles en
[`docs/cli/session-commands.md`](docs/cli/session-commands.md) y
[`docs/cli/fix-command.md`](docs/cli/fix-command.md).

`health` es diagnóstico de solo lectura. `logs` lee el journal y redacta MAC,
rutas D-Bus y otros identificadores antes de imprimirlos. `devices`, `status`
y `watch` aplican la misma política de privacidad. Más información:
[`docs/cli/health-command.md`](docs/cli/health-command.md),
[`docs/cli/logs-command.md`](docs/cli/logs-command.md) y
[`docs/cli/status-command.md`](docs/cli/status-command.md).

## GUI

Ejecuta:

```bash
.venv/bin/openbuds gui
```

La ventana muestra el dispositivo y los datos que realmente puede observar el
stack. Incluye conectar, desconectar, música, micrófono y un botón de
diagnóstico. La captura y el Health Check se ejecutan sin bloquear la ventana;
los fallos parciales se presentan como datos no disponibles y la GUI intenta
seguir operativa. Consulta [`docs/gui/main-window.md`](docs/gui/main-window.md).

## Privacidad y seguridad

OpenBuds no envía comandos propietarios, no toca firmware y no escribe en el
hardware. Las lecturas de BlueZ/PipeWire son solo de observación, salvo las
acciones runtime confirmadas por el usuario.

La configuración de la aplicación se guarda bajo `~/.config/openbuds/`. Las
operaciones persistentes crean backup timestamped, escriben atómicamente,
verifican el resultado y hacen rollback si fallan. Los overrides de
WirePlumber, si se habilitan en el futuro, están limitados a
`~/.config/wireplumber/`; nunca se escribe en `/etc` o `/usr/share` y la app no
usa `sudo`. Consulta [`docs/ADR/0008-safe-persistence.md`](docs/ADR/0008-safe-persistence.md)
y [`docs/ADR/0002-wireplumber-0.4-lua-config-scope.md`](docs/ADR/0002-wireplumber-0.4-lua-config-scope.md).

## Troubleshooting seguro

Empieza siempre con comandos de lectura:

```bash
.venv/bin/openbuds doctor
.venv/bin/openbuds health
.venv/bin/openbuds logs --lines 50
.venv/bin/openbuds devices --paired-only
```

- Si falla `runtime.gio`, verifica `make check-runtime` y que el venv use
  `/usr/bin/python3` con `python3-gi` instalado.
- Si no aparece el auricular, comprueba primero el emparejamiento y el
  adaptador con las herramientas de Ubuntu; OpenBuds no hace discovery.
- Si falta el audio, revisa `health` y ejecuta un `fix` solo cuando el reporte
  muestre el ID como disponible.
- Si tras suspensión queda desconectado, usa `connect` o el botón Conectar;
  la beta no fuerza ni garantiza la reconexión automática; puedes usar el botón
  Conectar o `openbuds connect`, siempre con confirmación.
- Si un campo dice «No disponible», significa que no fue observable; no indica
  necesariamente un fallo del dispositivo.

No reinicies servicios ni cambies perfiles a ciegas. Las acciones de sesión y
los auto-fixes requieren confirmación y están documentados en
[`docs/cli/session-commands.md`](docs/cli/session-commands.md).

## Desarrollo y validación

Desde un entorno instalado con `install-dev`:

```bash
make lint
make typecheck
make test
make test-quick
```

Las integraciones reales están marcadas y pueden requerir el stack local:

```bash
OPENBUDS_RUN_INTEGRATION=1 .venv/bin/pytest tests/integration
```

La integración es de solo lectura salvo que una prueba indique explícitamente
lo contrario; no se debe ejecutar contra hardware sin revisar su alcance.
La arquitectura y las decisiones duraderas están en
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) y [`docs/ADR/`](docs/ADR/).

## Licencia

OpenBuds Manager se distribuye bajo [GPL-3.0-or-later](LICENSE).
