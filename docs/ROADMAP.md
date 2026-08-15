# Roadmap de OpenBuds Manager

El roadmap prioriza una aplicación usable para Redmi Buds 6 Lite. Una etapa que
dependa del hardware queda como **implementación software completa; validación
física pendiente** hasta obtener evidencia real. No se infieren propiedades
ausentes ni se ejecutan acciones de hardware sin aprobación explícita.

## Etapa 0 — Estabilización inmediata (completada)

**Objetivo:** recuperar una base reproducible antes de añadir funciones.

- [x] Cerrar `WpctlAdapter`: validado, aprobado y publicado. Solo lectura,
  mutaciones deshabilitadas.
- [x] Ruff no presenta el fallo anunciado al inicio de esta revisión; volver a
  ejecutar todos los gates al cerrar el incremento local.
- [x] Recrear, en una tarea aprobada aparte, `.venv` con `/usr/bin/python3` y
  `--system-site-packages`; validar PyGObject/Gio. No usar Linuxbrew para BlueZ.
- [x] `openbuds doctor` distingue sistema soportado, runtime listo y hardware
  disponible; el runtime exige `base_prefix` `/usr` y PyGObject/Gio importables
  (Linuxbrew devuelve no listo). Verificado en Python 3.12.
- [x] Corregir rutas y afirmaciones obsoletas restantes: documentación
  normativa/técnica y metadatos fuente alineados con las etapas.
- [x] Añadir `LICENSE` GPL-3.0-or-later.
- [x] Diseñar CI básica para unit tests, Ruff y mypy: workflow GitHub Actions
  en push/PR a `main` y manual (`workflow_dispatch`), **Python 3.12**, gates
  unitarios (unit tests + Ruff check/format + mypy) sin hardware ni
  PyGObject/Gio; ver `.github/workflows/ci.yml`.
- WirePlumber permanece estrictamente en modo de solo lectura: no se habilitan
  mutaciones, y cualquier cambio futuro requiere la Etapa 5 (backup, rollback y
  aprobación explícita).

**Salida:** unit tests, Ruff y mypy pasan; `doctor` detecta un runtime inválido;
las integraciones de lectura pasan con Python 3.12/Gio; README y roadmap no
afirman capacidades no verificadas.

## Etapa 1 — Caracterización física pasiva

**Objetivo:** observar los Redmi Buds 6 Lite reales antes de detectar códec,
cambiar perfiles o cerrar la interfaz definitiva.

Estados de prueba, en este orden:

1. Emparejados y desconectados.
2. Conectados sin reproducir audio.
3. Reproduciendo música mediante A2DP.
4. Usando el micrófono mediante HFP.
5. Desconexión y reconexión manuales.
6. Suspensión y reanudación de Ubuntu.

En cada estado se observarán `Device1`, `Battery1` si aparece, RSSI,
`ServicesResolved`, nodos de `pw-dump`, `wpctl status`, `wpctl inspect`, perfiles
ofrecidos, propiedades de códec/transporte si existen, señales y polling.

**Estado de caracterización (2026-08-14):** registro **parcial**. Con
evidencia: estados 1 y 2 (sesión 3, solo lectura), estado 3 (sesión 1,
pasiva) y estados 4 y 5 (sesión 2, mutaciones controladas aprobadas). El
estado 6 se ejecutó en una prueba controlada, pero no superó el criterio de
reconexión automática tras reanudar.

- [x] Estado 3: **A2DP/SBC reproduciendo** — evidencia pasiva 2026-08-11
  (sesión 1): perfil `a2dp-sink`, códec runtime `sbc`, un único `Audio/Sink`,
  `Battery1` 100 %, perfiles ofrecidos por el sistema (incluida oferta HSP/HFP
  **sin prueba funcional**), 3 muestras estables; reconfirmado en la sesión 2
  (restauración A2DP/SBC tras `mic`). Ver
  [`docs/research/redmi-buds-6-lite-passive-characterization.md`](research/redmi-buds-6-lite-passive-characterization.md).
- [x] Estado 1: **emparejados y desconectados**, estable bajo protocolo
  (sesión 3, 2026-08-13; tres muestras de `openbuds status` separadas por 2 s).
- [x] Estado 2: **conectados sin reproducción dirigida al dispositivo** (sesión
  3, 2026-08-13; tres muestras estables en A2DP/SBC, sin micrófono; el stream
  de sistema observado no expuso destino Bluetooth identificable, por lo que
  no se afirma silencio absoluto de todo el sistema).
- [x] Estado 4: **micrófono HFP — funcional**, validado 2026-08-11 (sesión 2,
  mutaciones controladas aprobadas): `openbuds mic` aplicó HFP con códec
  **mSBC** (el de mayor calidad de los ofrecidos) y source Bluetooth;
  `openbuds music` restauró A2DP/SBC.
- [x] Estado 5: **desconexión/reconexión manuales**, validado 2026-08-11
  (sesión 2): `openbuds disconnect`/`connect` (org.bluez.Device1) con
  emparejamiento intacto; sin conexión no se inventan datos («No disponible»).
- [ ] Estado 6: suspensión y reanudación de Ubuntu — prueba 2026-08-14:
  sesión y GUI recuperadas, pero los auriculares no se reconectaron
  automáticamente; `openbuds devices --paired-only` terminó con exit 0 y mostró
  el dispositivo presente, confirmando que seguía emparejado en BlueZ pero
  desconectado.

**La Etapa 1 no está completa:** el estado 6 fue observado, pero requiere
resolver o caracterizar la falta de reconexión automática para superar el
gate.
El estado 2 queda validado con la limitación indicada: se observó conexión
estable sin reproducción dirigida al sink Bluetooth, pero no se promete
silencio absoluto de todos los streams de PipeWire. El gate físico permanece
abierto: la prueba del estado 6 no cumplió la reconexión automática tras
reanudar y requiere diagnóstico o caracterización adicional, con gate.

**Gate físico:** antes de comenzar se presentará el protocolo exacto, comandos de
solo lectura y política de redacción; se esperará confirmación de que el usuario
conectó manualmente los audífonos mediante una interfaz estándar aprobada.
OpenBuds no llamará métodos mutadores, no cambiará perfiles/volumen, no
reiniciará servicios ni guardará MAC, object paths o payloads completos.

**Salida:** detección privada; conectado/desconectado estable; nodos y perfiles
reales conocidos; propiedades ausentes se muestran como «No disponible»; breve
registro de evidencia empírica.

## Etapa 2 — Backend funcional de control de sesión

**Objetivo:** entregar la rebanada dispositivo → estado agregado → perfil/códec
observado → casos de uso → CLI, sin configuración persistente.

- [x] Base BlueZ de solo lectura: snapshots, eventos y polling.
- [x] Base PipeWire de solo lectura: `pw-dump`, parser y listado de nodos.
- [x] `GetDeviceInfoUseCase` y estado agregado tipado (`DeviceAggregate` +
  `BluetoothAudioNode`).
- [x] Asociación segura `Device1`↔nodos PipeWire (MAC normalizada, precedencia
  `api.bluez5.address`→`node.name`→`device.name`).
- [x] Sink/source activos; códec solo con propiedades validadas (verified;
  `off`→sin códec; transport conservado).
- [x] CLI `openbuds status` (Incremento 1) y `openbuds watch` (Incremento 2)
  (ver [`docs/cli/status-command.md`](cli/status-command.md) y
  [`docs/cli/watch-command.md`](cli/watch-command.md)).
- [x] `PipeWireRepository.get_default_audio_sink` implementado (solo lectura,
  vía `wpctl inspect @DEFAULT_AUDIO_SINK@` con `WpctlInspector` inyectable;
  verificado real; el nombre dinámico no se expone en UI/CLI); consumo en
  `status`/Health posterior.
- [x] Batería agregada estándar (`Battery1`) en status; L/R/estuche solo si
  existe una fuente identificable (ya documentado en Etapa 1).
- [x] Casos de uso Connect, Disconnect, Música (A2DP) y Micrófono (HFP)
  (Incremento 3): CLI `connect`/`disconnect`/`music`/`mic` con confirmación
  previa (`-y` para scripting); perfil runtime vía `pw-cli`/`wpctl`
  (resolución dinámica, nada hardcodeado; los ids de objeto de PipeWire
  cambian entre sesiones y la resolución dinámica funcionó); **validación
  física completa contra hardware real el 2026-08-11** (ver
  [`docs/cli/session-commands.md`](cli/session-commands.md) y
  [`docs/research/redmi-buds-6-lite-passive-characterization.md`](research/redmi-buds-6-lite-passive-characterization.md)).

Connect/Disconnect usan las APIs oficiales BlueZ detrás de interfaces y con
fakes. La Etapa 2 queda así: **implementación software completa + validación
física completa (2026-08-11, sesión 2)** — `status`, `watch`,
`connect`/`disconnect`/`music`/`mic` probados contra hardware real; sesión con
verificación de solo lectura primero y mutaciones controladas ejecutadas solo
con aprobación (método, riesgos y reversibilidad mostrados antes de cada
mutación; emparejamiento intacto, cambios runtime reversibles). **Etapa 2
cerrada.**

**Salida:** estado completo por CLI; errores claros; A2DP/HFP solo si el sistema
los ofrece; ningún cambio persistente.

## Etapa 3 — Interfaz gráfica MVP

**Objetivo:** una ventana PySide6 útil antes de añadir vistas secundarias.

**Incremento 1 completado:** `openbuds gui` lanza la ventana única (import
lazy; error claro sin PySide6 o sin display). Smoke real verificado con
`QT_QPA_PLATFORM=offscreen` y repositorios reales sin hardware. Ver
[`docs/gui/main-window.md`](gui/main-window.md).

**Incremento 2 completado:** Health Check real integrado en la GUI. El botón
Diagnóstico abre un diálogo no bloqueante, muestra inicialmente «Analizando...»
y ejecuta `RunHealthCheckUseCase` mediante `DeviceWorker`/`QThread`. El diálogo
renderiza el `HealthReport` completo en orden, con estado global, severidad,
identificador, etiqueta, mensaje, detalle cuando existe, evidencia,
recomendaciones y `[fix: id]` solo como texto. La información se redacta y los
errores se sanitizan; no se exponen MAC, object paths ni payloads crudos.
La GUI permanece en modo diagnóstico read-only: no ejecuta auto-fixes, que
siguen separados en `openbuds fix` desde la CLI.

- [x] Nombre, estado, batería agregada estándar / RSSI opcionales, perfil,
  códec o «No disponible» (panel de 8 campos, `QFormLayout`); L/R/estuche solo
  si una fuente los identifica (sin fuente por ahora).
- [x] Sink/source y selector Música/Micrófono con aviso de pérdida de calidad
  (warning HFP antes de confirmar, igual que la CLI).
- [x] Botón Conectar/Desconectar, estado del sistema (barra con errores
  sanitizados) y acceso a Diagnóstico mediante Health Check real de solo
  lectura en un diálogo no bloqueante; el auto-fix permanece separado en
  `openbuds fix` CLI.
- [x] Health Check en GUI: `RunHealthCheckUseCase` inyectado por
  `build_default_view_model` con `HealthCheckRepository` y repositorios
  read-only de BlueZ/PipeWire; ejecución en `DeviceWorker`/`QThread`, checks en
  orden fijo y contenido redactado/seleccionable.
- [x] Paleta del sistema y accesibilidad (`accessibleName`, texto
  seleccionable).
- [x] Operaciones no bloqueantes: `DeviceWorker` (QThread) + `QTimer` 2 s;
  `busy` deshabilita controles.
- [x] Widgets → ViewModels → casos de uso; sin D-Bus/subprocess en la UI
  (composición solo en `build_default_view_model`; formatter compartido
  CLI/GUI con redacción).
- [x] Bandeja opcional Qt (`QSystemTrayIcon`) con menú Abrir ventana,
  Actualizar, Diagnóstico y Salir; sin bandeja disponible, el arranque continúa
  con la ventana.
- [x] Adaptador de notificaciones freedesktop best-effort mediante Gio/GDBus
  en el bus de sesión, con sanitización y degradación segura si el servicio no
  está disponible.
- [x] Notificaciones automáticas de `DeviceChangeEvent`: `DeviceChangeBridge`
  con marshalling explícito mediante `Qt.QueuedConnection`, supresión segura
  de la tanda inicial, política ADDED/REMOVED y transición de conexión, textos
  sanitizados y degradación best-effort.

La bandeja, el adaptador de notificaciones y el puente automático son slices
post-MVP de la Etapa 3 completados. El puente es read-only y session-only: no
modifica Bluetooth, audio, perfiles, servicios ni configuración. Los fallos de
suscripción o notificación se absorben; `Notify` tiene timeout de 1 s y puede
retrasar brevemente Qt, pero no indefinidamente.

**Salida:** funciona con estados reales y sin audífonos; ausencias no rompen el
layout; operaciones en curso deshabilitan controles; errores sin datos
sensibles; la bandeja es opcional y las notificaciones directas y automáticas
son best-effort. El gate físico de la Etapa 1, incluida suspensión y
reanudación, no cambia.

## Etapa 4 — Health Check y diagnóstico (completada)

**Incremento 1 completado:** `openbuds health` implementado y verificado real
sin hardware (14 checks estables, `Estado global: OK`, exit 0, sin MAC ni
object paths). Ver [`docs/cli/health-command.md`](cli/health-command.md).

**Incremento 2 completado:** `openbuds logs` implementado y verificado real
sin hardware: líneas de los 3 servicios con MAC/object paths redactados. Ver
[`docs/cli/logs-command.md`](cli/logs-command.md).

**Incremento 3 completado (posterior a la Etapa 4):** **auto-fix seguro** —
`openbuds fix <id> [--yes]` repara problemas del Health Check con confirmación
explícita: `start.audio` (unidades de usuario pipewire+wireplumber vía
`systemctl --user`, sin sudo) y `profile.a2dp` (perfil A2DP runtime); ningún
fix se ejecuta sin confirmación (`[s/N]`/`-y`), verificación post-fix honesta
con re-Health y salida 1 sin mutar si el fix no aplica. Ver
[`docs/cli/fix-command.md`](cli/fix-command.md).

- [x] Runtime Python/Gio, BlueZ/D-Bus, PipeWire, WirePlumber y adaptador —
  checks `system.*`, `runtime.gio` y `hardware.adapter` (incremento 1).
- [x] Dispositivo, perfil, códec, sink/source, micrófono y configuración
  efectiva — checks `device.*`, `audio.*` y `battery.aggregate` (incluye
  `audio.sink_default`; incremento 1).
- [x] Logs relevantes con redacción de identificadores — **incremento 2
  completado:** `openbuds logs [--service bluez|wireplumber|pipewire]...
  [--lines N]` (1-200, default 20; `--service` repetible; sin flag, usa los
  tres); `journalctl -o short --no-pager`; unit real `bluetooth.service` (no
  `bluez.service`); fallback `--user` para wireplumber/pipewire cuando el
  unit de sistema no existe, no produce líneas o falla; redacción compartida
  (`infrastructure/redaction.py`, usada también por health) en doble capa con
  límites 300/80; exit 0 si al menos un servicio disponible, 1 si todos
  fallan; verificado real 2026-08-11 (`openbuds logs --lines 5` con líneas de
  los 3 servicios y MAC redactadas, sin identificadores reales).
- [x] Cada dato se etiqueta como **observado**, **inferido**, **no
  disponible**, **recomendación** o **acción segura disponible** —
  `EvidenceKind` en cada `CheckResult.evidence` (incremento 1).

No se prometen jitter, packet loss, retransmisiones o latencia exacta si el
sistema no los expone; toda estimación se etiqueta como tal (**cumplido** en
el incremento 1: el Health Check no promete ni estima esas métricas).

**Etapa 4 cerrada:** incrementos 1 y 2 completados — Health Check con
evidencia etiquetada y logs redactados, ambos verificados reales sin hardware.

**Diferido/post-MVP (no forma parte del cierre de Etapa 4):** **benchmark de
enlace**. No tiene subcomando público y no se marca como completado. El **auto-fix
seguro** dejó de estar diferido: quedó **implementado** en el incremento
posterior a la Etapa 4 (`openbuds fix` con `start.audio` y `profile.a2dp`;
confirmación explícita y verificación, sin sudo ni unidades de sistema).

**Salida:** informe CLI de solo lectura con los 14 checks en orden fijo y
cada dato etiquetado por evidencia; exit 0/1 según el estado global; volcado
de logs por servicio con identificadores redactados.

## Etapa 5 — Optimización persistente y rollback

**Incremento 1 completado (2026-08-12) — persistencia segura de configuración.**

> **Nota de cierre:** se marca la **implementación completa**; la **validación
> física de overrides WirePlumber reales queda diferida** porque aún no existe
> ninguna configuración de WirePlumber modificable por la app (ninguna función
> escribe overrides hoy). Lo validado es la capa de persistencia aislada y
> reversible, con smoke real de la CLI sobre XDG temporales (config del usuario
> no tocada). Ver [ADR-0008](ADR/0008-safe-persistence.md).

- [x] Dry-run: `config set <clave> <valor> --dry-run` renderiza el TOML
  resultante sin escribir nada.
- [x] Validación del entorno y ruta confinada: config TOML de la app bajo
  `~/.config/openbuds/` y overrides WirePlumber bajo `~/.config/wireplumber/`
  (solo XDG, nunca root); `WirePlumberConfigEditor` rechaza rutas absolutas,
  traversal (`..`), backslashes/drives de Windows y NUL.
- [x] Lectura de configuración existente y backup: backup timestamped previo
  automático antes de reemplazar (config de la app y overrides) y backup
  manual (`config backup`).
- [x] Validación sintáctica y escritura atómica: temp + fsync + `os.replace`
  (ya existente desde ADR-0006, ahora siempre precedida de backup).
- [x] Verificación y rollback automático si falla: verificación post-escritura
  con `load_config` (TOML) y lectura de contenido (overrides); rollback
  automático restaurando el backup (salvo `auto_rollback=False`); sin archivo
  previo → `backup_path` vacío y error claro.
- [x] Verificación del rollback: `config restore <archivo.bak>` pre-valida el
  TOML del backup, lo instala atómicamente y verifica el resultado.

**Salida del incremento:** `AppConfigStore.save` devuelve el backup creado
(`Path | None`); el contrato `IConfigRepository` queda implementado por
`WirePlumberConfigEditor`; `apply_optimization.py` **no se tocó** (stub
histórico: el flujo de seguridad que documenta ya está materializado por las
primitivas de este incremento).

La lógica se prueba primero en directorios temporales, nunca usando los
audífonos para ensayar backup o rollback. Solo se escribe bajo
`~/.config/wireplumber/` y `~/.config/openbuds/`; nunca globalmente ni con
`sudo`.

## Etapas posteriores

- Historial y benchmark limitados a métricas observables.
- Otros modelos solo cuando exista una necesidad real; no crear plugins antes.
- Ingeniería inversa exclusivamente pasiva si el producto estable la justifica.
- Funciones propietarias, OTA y firmware permanecen fuera de alcance.

## Gate del contrato Device Profiles

Antes de implementar el loader se presentará una propuesta breve para reconciliar
`DeviceProfile` y el YAML. Debe tipar identificación, códecs, perfiles,
capacidades, fuente, evidencia, fecha y seguridad decisional, diferenciando
`standard_guaranteed`, `vendor_claimed`, `runtime_observed`,
`hardware_verified` y `unknown`. No se modificará el esquema ni el YAML sin
aprobación; OTA se eliminará de las funciones experimentales en ese incremento.
