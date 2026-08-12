# Diseño técnico — Ventana principal PySide6 (GUI MVP, Incremento 1 de Etapa 3)

- **Estado:** implementado en la **Etapa 3, Incremento 1**. Funciona con
  estados reales y **sin audífonos** (smoke verificado con
  `QT_QPA_PLATFORM=offscreen` y repositorios reales): ventana construye,
  refresca cada 2 s, muestra «Redmi Buds 6 Lite» / «emparejado» y «No
  disponible» en batería/RSSI/perfil/códec/sink/source. Gates Ruff/Mypy/
  diff-check OK; tests Qt con `importorskip` (se saltan en CI sin PySide6).
- **Tipo:** diseño de implementación (**Documentation First; implementado y
  verificado** — el código y los tests cumplen lo aquí especificado).
- **Documentos relacionados:** [Diseño del comando `status`](../cli/status-command.md),
  [diseño de comandos de sesión](../cli/session-commands.md),
  [ADR-0004](../ADR/0004-clean-architecture-dependency-rule.md) y
  [AGENTS.md](../../AGENTS.md) §3/§10.

> **Alcance:** una sola ventana PySide6 útil, sin vistas secundarias ni
> bandeja. `openbuds gui` la lanza con import lazy: error claro si falta
> PySide6 o no hay display utilizable.

## 1. Objetivo y descripción de la ventana

`openbuds gui` abre la **ventana única** de OpenBuds Manager:

- **Panel de estado** (8 campos en `QFormLayout`): Dispositivo, Estado,
  Batería, RSSI, Perfil, Códec, Sink y Source. Las ausencias se muestran como
  «No disponible»; nada se infiere.
- **Botones:** Conectar, Desconectar, Música (A2DP), Micrófono (HFP),
  Actualizar y Diagnóstico.
- **Confirmaciones:** toda mutación pide confirmación con `QMessageBox`
  (mismo contrato que la CLI). El micrófono **advierte de la degradación HFP
  antes** de confirmar (`prepare_mic_warning`); cancelar retira el aviso.
- **Diagnóstico informativo:** el botón muestra «Ejecuta `openbuds doctor` en
  la terminal», sin subprocess desde la UI; el diagnóstico real es Etapa 4.
- **Refresh no bloqueante:** `QTimer` de 2 s dispara `refresh` sobre un
  `DeviceWorker` en `QThread`; `closeEvent` detiene el timer y cierra el
  worker.
- **Estado del sistema:** barra de estado con errores **sanitizados** (sin
  MAC ni paths), «Actualizando...» durante operaciones y «Listo» en reposo.

Sin hardware: Conectar habilitado (emparejado y no conectado), los demás
controles deshabilitados; con audífonos conectados se habilitan
Desconectar/Música/Micrófono.

## 2. Decisiones (registro del arquitecto)

1. **Widgets → ViewModel → casos de uso:** la UI no toca D-Bus ni subprocess;
   la composición de repositorios vive **solo** en `build_default_view_model`
   (`ScanDevices`/`GetDeviceInfo`/`Connect`/`Disconnect`/`SetAudioProfile`).
2. **Formatter compartido CLI/GUI:** `presentation/formatting.py` provee
   `aggregate_fields`/`format_aggregate` y la redacción de MAC y
   `/org/bluez/...` (`REDACT_ADDRESS`); la CLI delega en él
   (`_ADDRESS = REDACT_ADDRESS` para compatibilidad), sin cambios de salida.
3. **Sin bloqueo de la UI:** `DeviceWorker` (QThread) ejecuta tareas y entrega
   resultados/errores vía señales; `busy` deshabilita los controles mientras
   hay operación en curso.
4. **Confirmación en la UI** (`QMessageBox`) igual que la CLI; el warning de
   degradación HFP se muestra **antes** de preguntar.
5. **Scaffolding legado eliminado:** se retiró `presentation/qt/views/`
   (10 archivos) y `tray_indicator.py` (bandeja post-MVP); queda una sola
   ventana sin vistas secundarias.
6. **Renombrado `connect_device`/`disconnect_device`:** colisión con
   `QObject.connect`/`disconnect` (antes exigía `type: ignore`); mypy ya no
   requiere excepción.

## 3. Límites

- **Diagnóstico real** completo es Etapa 4; el botón solo informa de
  `openbuds doctor`.
- Bandeja GNOME y notificaciones **post-MVP**.
- Una sola ventana; sin vistas secundarias ni componentes L/R/estuche (no hay
  fuente identificable).
