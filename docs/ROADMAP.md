# Roadmap de OpenBuds Manager

Las fases se desarrollan **secuencialmente**: cada una se completa y valida antes
de comenzar la siguiente. El progreso se marca con checkbox.

## Fase 1 — Planificación y Arquitectura ✅

- [x] Comprender el problema y los requisitos
- [x] Revisar documentación oficial (BlueZ, PipeWire, WirePlumber, D-Bus)
- [x] Definir la arquitectura (Clean Architecture por capas)
- [x] Definir módulos y árbol del proyecto
- [x] Documentar decisiones técnicas (ADRs)
- [x] Crear cimientos: modelos del dominio, contratos, core, esqueletos
- [x] Configurar tooling (ruff, mypy, pytest) y validar base (31 tests)

## Fase 2 — Backend base ✅

- [x] Gestión de configuración (`core/config.py` + `persistence/app_config.py`)
- [x] Logging estructurado (rotación, handler puente hacia la vista de Logs)
- [x] CLI base (`doctor`, `config`, `version`, bootstrap)
- [x] Gestión de errores (manejo uniforme de `OpenBudsError`)
- [x] Detección de entorno completa (`system/environment_detector.py`)

## Fase 3 — Bluetooth

- [x] CLI `devices` (`openbuds devices` sobre las consultas snapshot: `-p|--paired-only` y `-a|--adapter`; TSV en español con privacidad y sanitización; solo snapshot, sin señales; TDD + smoke real Python 3.12/Gio verificados)
- [x] Cliente D-Bus BlueZ — Incremento 1: snapshot `GetManagedObjects` (`bluez/dbus_protocol.py` + `bluez/dbus_client.py`, PyGObject/Gio; verificado con test de integración opt-in)
- [x] Cliente D-Bus BlueZ — Incremento 2: señales y lifecycle (`InterfacesAdded/Removed`, `PropertiesChanged`; suscripción, unsubscribe, cierre) — ✅ **completo (nivel bajo + dispatch del repositorio)**:
  - **Nivel bajo:** worker dedicado (`_SignalWorker`, GLib `MainContext`/`MainLoop` daemon), tres filtros exactos, `SignalEvent` (metadata, sin payload), suscripción/unsubscribe/close idempotentes con cero callbacks tras el unsubscribe, arranque perezoso/restart, **hook `on_ready` opcional** (corre en el hilo del worker tras instalar filtros y registrar el callback lógico, **antes** de que `subscribe` retorne; con rollback atómico si lanza), timeout y rollback atómico; TDD determinista (sin GI) + integración real de **lifecycle** en Python 3.12/Gio (25 ciclos subscribe/unsubscribe/close + snapshot fresco, sin cerrar el bus, sin inducir señales).
  - **Dispatch del repositorio:** `BlueZRepository.subscribe_device_changes` implementado, con **diff puro de snapshots** (`device_change_diff.py`: orden REMOVED→ADDED→UPDATED por `object_path`, `UPDATED` solo si `DeviceInfo` mapeado es desigual, sin eventos Battery/RSSI-only), init A→B en el worker vía `on_ready` (snapshot B cierra la carrera, sin replay de preexistente), cache de diff con refresh completo por señal, aislamiento de callbacks, suscriptores múltiples/tardíos/reentrantes, `Unsubscribe` idempotente con espera de in-flight, concurrencia de init, rollback de errores y sin cerrar cliente/bus. TDD determinista (`tests/unit/test_bluez_repository_signals.py`, `tests/unit/test_device_change_diff.py`) + integración real opt-in de **lifecycle A/B** (`tests/integration/test_bluez_repository_signals.py`: subscribe/unsubscribe + snapshot A/B + bus usable; **sin** señales inducidas, **sin** afirmar recepción real, **sin** escrituras). Contrato técnico en [signal-lifecycle-design](bluez/signal-lifecycle-design.md). El contrato de eventos del dominio ([ADR-0007](ADR/0007-device-change-event-contract.md): `DeviceChangeKind`/`DeviceChangeEvent`/`Unsubscribe`) está **implementado y probado**
- [x] Mapeo de objetos D-Bus → modelos (`bluez/object_mapper.py`)
- [x] Implementación de `IBluetoothRepository` (`bluez/bluez_repository.py`) — ✅ **completo**: consultas snapshot (`list_adapters`/`list_devices`/`get_device`/`get_battery`/`get_rssi`, cliente inyectable + snapshot fresco; TDD e integración real solo lectura) **y** `subscribe_device_changes` con dispatch de `DeviceChangeEvent` (registro de suscriptores, cache de diff, cierre de carrera A→B vía `on_ready` en el worker, orden determinista REMOVED→ADDED→UPDATED y `Unsubscribe` idempotente; contrato en [signal-lifecycle-design §4](bluez/signal-lifecycle-design.md#4-repositorio-registro-cache-y-dispatch), eventos del dominio [ADR-0007](ADR/0007-device-change-event-contract.md) probados). Verificado con fakes deterministas + integración real de lifecycle A/B en Python 3.12/Gio
- [x] Detección de adaptadores y dispositivos — **implementación completa** (repo + mapper + CLI `devices` + señales) y **verificación real** (2026-08-10, sin auriculares conectados): adaptador detectado (`hci0`, `Powered=True`, `Discovering=False`, `Discoverable=False`) y **caso cero dispositivos** (`openbuds devices` → exit 0 con `No se encontraron dispositivos Bluetooth.`; snapshot con 0 `Device1`). **No** se afirma detección del Redmi Buds 6 Lite: no había hardware conectado; la detección del dispositivo real se valida cuando haya uno
- [ ] Validación empírica de propiedades runtime inciertas — **bloqueada**: los auriculares no están conectados y PipeWire reporta **0 nodos Bluetooth** (`pw-dump` exit 0, sin objetos ni property keys); requiere un dispositivo real conectado
- [ ] Polling periódico de respaldo para `Connected`/`Paired`/`Trusted` — recomendado por [RESEARCH_LIMITS §4](RESEARCH_LIMITS.md#4-fiabilidad-de-señales-d-bus); **no implementado** y **necesario antes de cerrar la Fase 3**. La señal primaria (refresh completo por señal + diff de snapshots) ya está implementada; el respaldo por polling queda como deuda explícita

## Fase 4 — Optimización

- [ ] Parser de `pw-dump` → nodos Bluetooth (`pipewire/pw_dump_parser.py`)
- [ ] Implementación de `IAudioRepository` (`pipewire/pipewire_repository.py`)
- [ ] Adaptador `wpctl` (`wireplumber/wpctl_adapter.py`)
- [ ] Editor seguro de config Lua 0.4 (`wireplumber/config_editor.py`)
- [ ] Gestión de backups (`wireplumber/backup_manager.py`)
- [ ] Implementación de `IConfigRepository` (`wireplumber/wireplumber_repository.py`)
- [ ] Caso de uso `ApplyOptimizationUseCase` con flujo seguro completo
- [ ] Validación de propiedades runtime de PipeWire (`bluez5.codec`, etc.)

## Fase 5 — Diagnóstico

- [ ] CLI `health`
- [ ] Implementación de `IDiagnosticsRepository`
- [ ] Health Check completo (BlueZ, PipeWire, WirePlumber, servicios, codecs, permisos)
- [ ] Generación de recomendaciones y auto-fix seguro
- [ ] Benchmark (RSSI, jitter, latencia, packet loss, retransmisiones)
- [ ] Historial de benchmarks (`persistence/benchmark_history.py`)
- [ ] Reportes

## Fase 6 — Interfaz gráfica

- [ ] PySide6: ventana principal con sidebar de 10 vistas
- [ ] Dashboard
- [ ] Vista de Dispositivo
- [ ] Vista de Audio
- [ ] Vista de Optimización
- [ ] Vista de Health Check
- [ ] Vista de Diagnóstico
- [ ] Vista de Benchmark
- [ ] Vista de Logs
- [ ] Vista de Configuración
- [ ] Vista de Laboratorio Experimental
- [ ] Notificaciones de escritorio
- [ ] AppIndicator (bandeja del sistema para GNOME)
- [ ] ViewModels (puente presentation → application)

## Fase 7 — Device Profiles

- [ ] Cargador de perfiles YAML → `DeviceProfile` (`device_profiles/loader.py`)
- [ ] Validación de perfiles
- [ ] Resolución de dispositivo → perfil (`match_device`)
- [ ] Validación empírica del perfil Redmi Buds 6 Lite (códecs, batería, RSSI)

## Fase 8 — Plugins

- [ ] Mecanismo de descubrimiento y carga de plugins
- [ ] Registro de perfiles vía plugins
- [ ] Hooks de diagnóstico extendibles

## Fase 9 — Ingeniería inversa (experimental)

> ⚠️ Solo cuando el proyecto sea completamente estable. Análisis **pasivo**
> exclusivamente. **Nunca** se envían comandos propietarios sin comprensión total.

- [ ] Captura de tráfico Bluetooth (`btmon`, solo lectura)
- [ ] Análisis del protocolo propietario de Xiaomi (passive)
- [ ] Estudio de comandos del fabricante (documentación, no envío)
- [ ] Implementación de funciones **solo** cuando se comprendan completamente
