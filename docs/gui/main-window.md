# Diseño técnico — Ventana principal PySide6 (GUI MVP, Incremento 2 de Etapa 3)

- **Estado:** implementado en la **Etapa 3, Incremento 2**. Conserva la
  ventana única y los 8 campos de estado del Incremento 1, y añade Health
  Check real de solo lectura dentro de la GUI. Funciona con estados reales y
  **sin audífonos** (smoke verificado con `QT_QPA_PLATFORM=offscreen` y
  repositorios reales): la ventana construye, refresca cada 2 s y el diálogo
  Health Check renderiza el `HealthReport` producido por el caso de uso.
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
- **Diagnóstico:** el botón abre un diálogo Health Check no bloqueante. El
  diálogo comienza con «Analizando...» y ejecuta el caso de uso en el
  `DeviceWorker`/`QThread`; no se limita a remitir a `openbuds doctor`.
- **Refresh no bloqueante:** `QTimer` de 2 s dispara `refresh` sobre un
  `DeviceWorker` en `QThread`; `closeEvent` detiene el timer y cierra el
  worker.
- **Estado del sistema:** barra de estado con errores **sanitizados** (sin
  MAC ni paths), «Actualizando...» durante operaciones y «Listo» en reposo.

Sin hardware: Conectar habilitado (emparejado y no conectado), los demás
controles deshabilitados; con audífonos conectados se habilitan
Desconectar/Música/Micrófono.

## 2. Diálogo Health Check

El botón Diagnóstico abre un diálogo no bloqueante que presenta el informe
real de `RunHealthCheckUseCase`. Mientras el worker está ocupado, el botón
Diagnóstico queda deshabilitado y vuelve a habilitarse al terminar o fallar.
Cerrar el diálogo no cancela ni muta la sesión: no conecta ni desconecta
dispositivos, no cambia perfiles, no reinicia servicios y no escribe
configuración.

El diálogo muestra, en el orden del `HealthReport`:

- estado global del informe;
- todos los checks, con severidad, identificador, etiqueta y mensaje;
- detalle cuando existe, evidencia y recomendaciones cuando existen;
- `[fix: id]` únicamente como texto informativo cuando el reporte indica que
  existe un auto-fix.

Usa texto plano, selección de texto y la redacción compartida de la
presentación. Los errores se sanitizan y no se exponen MAC, object paths ni
payloads crudos. La GUI no ejecuta auto-fixes: cualquier reparación permanece
separada en `openbuds fix` mediante la CLI y sus propias confirmaciones.

## 3. Decisiones (registro del arquitecto)

1. **Widgets → ViewModel → casos de uso:** la UI no toca D-Bus ni subprocess;
   la composición de repositorios vive **solo** en `build_default_view_model`
   (`ScanDevices`/`GetDeviceInfo`/`Connect`/`Disconnect`/`SetAudioProfile` y
   `RunHealthCheckUseCase(HealthCheckRepository(...))`). Health Check reutiliza
   los repositorios read-only de BlueZ/PipeWire.
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
7. **Health Check read-only en background:** el diálogo delega el informe a
   `RunHealthCheckUseCase` mediante `DeviceWorker`/`QThread`, sin bloquear la
   interfaz ni ejecutar auto-fixes. El contrato visual conserva el orden y la
   evidencia del `HealthReport`, con redacción compartida y errores sanitizados.

## 4. Límites

- El Health Check de la GUI es diagnóstico **read-only**. No cambia Bluetooth,
  PipeWire, servicios ni configuración, y no ejecuta auto-fixes. La ejecución
  de reparaciones sigue separada en `openbuds fix` desde la CLI.
- No se exponen MAC, object paths ni payloads crudos; el detalle disponible
  depende de la evidencia que entreguen los repositorios y el `HealthReport`.
- Bandeja GNOME y notificaciones **post-MVP**.
- Una sola ventana; sin vistas secundarias ni componentes L/R/estuche (no hay
  fuente identificable).
