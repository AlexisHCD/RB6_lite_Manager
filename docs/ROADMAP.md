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

## Fase 2 — Backend base

- [ ] Gestión de configuración (`core/config.py` + `persistence/app_config.py`)
- [ ] Logging estructurado (rotación, handler puente hacia la vista de Logs)
- [ ] CLI ampliada (subcomandos `devices`, `health`)
- [ ] Gestión de errores (jerarquía ya definida en Fase 1; integrar aquí)
- [ ] Detección de entorno completa (`system/environment_detector.py`)

## Fase 3 — Bluetooth

- [ ] Cliente D-Bus BlueZ (`bluez/dbus_client.py`) con PyGObject/Gio
- [ ] Mapeo de objetos D-Bus → modelos (`bluez/object_mapper.py`)
- [ ] Implementación de `IBluetoothRepository` (`bluez/bluez_repository.py`)
- [ ] Detección de adaptadores y dispositivos
- [ ] Suscripción a señales (InterfacesAdded/Removed, PropertiesChanged)
- [ ] Validación empírica de propiedades runtime inciertas

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
