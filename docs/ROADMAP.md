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
  normativa/técnica y metadatos fuente alineados con las etapas; `MASTER_DOC`
  etiquetado como histórico.
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

**Estado de caracterización (2026-08-11):** registro **parcial**. Solo el estado
3 cuenta con evidencia pasiva; los estados 1, 2, 4, 5 y 6 siguen pendientes.

- [x] Estado 3 (parcial): **A2DP/SBC reproduciendo** — evidencia pasiva
  2026-08-11: perfil `a2dp-sink`, códec runtime `sbc`, un único `Audio/Sink`,
  `Battery1` 100 %, perfiles ofrecidos por el sistema (incluida oferta HSP/HFP
  **sin prueba funcional**), 3 muestras estables. Ver
  [`docs/research/redmi-buds-6-lite-passive-characterization.md`](research/redmi-buds-6-lite-passive-characterization.md).
- [ ] Estado 1: emparejados y desconectados (estable bajo protocolo).
- [ ] Estado 2: conectados sin reproducir (idle formal).
- [ ] Estado 4: micrófono mediante HFP (funcional).
- [ ] Estado 5: desconexión y reconexión manuales.
- [ ] Estado 6: suspensión y reanudación de Ubuntu.

**La Etapa 1 no está completa:** el gate físico se mantiene para las sesiones
restantes (protocolo pasivo y política de redacción aprobados antes de cada una).
La evidencia del estado 3 habilita el trabajo de backend SBC/A2DP de la Etapa 2
**sin repetir la conexión**; los estados restantes se validarán cuando su
funcionalidad consumidora los requiera, con gate.

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
- [x] CLI `openbuds status` (ver
  [`docs/cli/status-command.md`](cli/status-command.md)); `watch` sigue [ ]
  (incremento posterior).
- [x] Batería agregada estándar (`Battery1`) en status; L/R/estuche solo si
  existe una fuente identificable (ya documentado en Etapa 1).
- [ ] Casos de uso Connect, Disconnect, Música (A2DP) y Micrófono (HFP) — sin
  cambios.

No se hardcodean índices ni nombres de perfiles. Connect/Disconnect usarán APIs
oficiales BlueZ detrás de interfaces y con fakes. Antes de una prueba real se
mostrarán método/comando, riesgos y reversibilidad, y se esperará aprobación.

**Salida:** estado completo por CLI; errores claros; A2DP/HFP solo si el sistema
los ofrece; ningún cambio persistente.

## Etapa 3 — Interfaz gráfica MVP

**Objetivo:** una ventana PySide6 útil antes de añadir vistas secundarias.

- Nombre, estado, batería agregada estándar / RSSI opcionales, perfil, códec o
  «No disponible»; L/R/estuche solo si una fuente los identifica.
- Sink/source y selector Música/Micrófono con aviso de pérdida de calidad.
- Botón Conectar/Desconectar, estado del sistema y acceso a Diagnóstico.
- Paleta del sistema, accesibilidad y operaciones no bloqueantes.
- Widgets → ViewModels → casos de uso; sin D-Bus/subprocess en la UI.
- Bandeja GNOME y notificaciones después del MVP.

**Salida:** funciona con estados reales y sin audífonos; ausencias no rompen el
layout; operaciones en curso deshabilitan controles; errores sin datos sensibles.

## Etapa 4 — Health Check y diagnóstico

- Runtime Python/Gio, BlueZ/D-Bus, PipeWire, WirePlumber y adaptador.
- Dispositivo, perfil, códec, sink/source, micrófono y configuración efectiva.
- Logs relevantes con redacción de identificadores.
- Cada dato se etiqueta como **observado**, **inferido**, **no disponible**,
  **recomendación** o **acción segura disponible**.

No se prometen jitter, packet loss, retransmisiones o latencia exacta si el
sistema no los expone; toda estimación se etiqueta como tal.

## Etapa 5 — Optimización persistente y rollback

No comienza hasta que las etapas anteriores funcionen con hardware real.

1. Dry-run.
2. Validación del entorno y ruta confinada.
3. Lectura de configuración existente y backup.
4. Validación sintáctica y escritura atómica.
5. Recarga o reinicio previamente aprobado.
6. Verificación y rollback automático si falla.
7. Verificación del rollback.

La lógica se prueba primero en directorios temporales, nunca usando los
audífonos para ensayar backup o rollback. Solo se escribe bajo
`~/.config/wireplumber/`; nunca globalmente ni con `sudo`.

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
