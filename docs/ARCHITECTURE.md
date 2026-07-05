# Arquitectura de OpenBuds Manager

## Resumen

OpenBuds Manager sigue **Clean Architecture** (arquitectura limpia) con capas
separadas y dependencias **unidireccionales**. El objetivo es que el núcleo
del proyecto (el dominio) sea independiente de cualquier tecnología concreta
(BlueZ, PipeWire, Qt), de forma que:

- sea **testeable** sin hardware ni servicios del sistema;
- sea **extensible** a nuevos dispositivos sin tocar el núcleo;
- la **lógica de negocio** nunca se mezcle con la presentación ni con detalles técnicos.

## Regla de dependencias

```
┌─────────────────────────────────────────────────────────────┐
│                     presentation                             │
│   (PySide6 / Qt, notificaciones, tray indicator)            │
│                         │                                     │
│                         │ invoca casos de uso                │
│                         ▼                                     │
│                    application                                │
│   (casos de uso: ScanDevices, GetDeviceInfo, ... )          │
│                         │                                     │
│                         │ depende de contratos (interfaces)  │
│                         ▼                                     │
│                      domain ◄──────────────┐                 │
│   (modelos, enums, interfaces/ABCs)        │ implementa      │
│   ★ NO depende de nada externo ★           │ los contratos   │
│                                            │                 │
└────────────────────────────────────────────┤                 │
                                             │                 │
┌────────────────────────────────────────────┐                 │
│                  infrastructure            │                 │
│   (BlueZ/D-Bus, PipeWire, WirePlumber,     │                 │
│    detección del sistema, persistencia)    │                 │
└────────────────────────────────────────────┘                 │
```

**Invariante clave:** la flecha de dependencia solo apunta hacia el dominio.
`domain` no importa nada de `infrastructure` ni de `presentation`. La
infraestructura implementa los contratos definidos en el dominio; los casos de
uso los reciben por **inyección de dependencias**.

## Capas y responsabilidades

### `domain/` — Núcleo puro

| Submódulo | Contenido |
|-----------|-----------|
| `models/` | Dataclasses inmutables: `DeviceInfo`, `AdapterInfo`, `CodecInfo`, `BatteryLevel`, `RSSIReading`, `BenchmarkResult`, `HealthReport`, `SystemInfo` |
| `enums.py` | Enumeraciones estables: `BluetoothProfile`, `CodecType`, `ConnectionState`, `ProfileState`, `DeviceIcon`, `HealthStatus`, `CheckSeverity`, `AddressType` |
| `interfaces/` | Contratos (ABCs/Protocols): `IBluetoothRepository`, `IAudioRepository`, `IConfigRepository`, `IDiagnosticsRepository`, `IDeviceProfileRepository` |

### `application/` — Casos de uso

Cada caso de uso modela **una intención del usuario** y orquesta repositorios:

| Caso de uso | Descripción | Fase |
|-------------|-------------|------|
| `ScanDevicesUseCase` | Listar dispositivos Bluetooth | 3 |
| `GetDeviceInfoUseCase` | Información agregada (dispositivo + batería + RSSI + códec) | 3/4 |
| `ApplyOptimizationUseCase` | Aplicar optimización con flujo seguro (backup → validate → apply → verify → rollback) | 4 |
| `RunHealthCheckUseCase` | Health Check completo del stack | 5 |
| `RunBenchmarkUseCase` | Benchmark de calidad de enlace | 5 |

### `infrastructure/` — Adaptadores externos

| Subpaquete | Tecnología | Implementa | Fase |
|------------|------------|------------|------|
| `bluez/` | D-Bus vía PyGObject/Gio | `IBluetoothRepository` | 3 |
| `pipewire/` | `pw-dump`/`wpctl` vía subprocess | `IAudioRepository` | 3/4 |
| `wireplumber/` | Edición segura de config Lua 0.4 | `IConfigRepository` | 4 |
| `system/` | Detección de entorno | (parte de `IDiagnosticsRepository`) | 2/5 |
| `persistence/` | Config de la app + historial | — | 2/5 |

### `presentation/` — Interfaz

| Subpaquete | Contenido |
|------------|-----------|
| `qt/` | Ventana principal, 10 vistas, ViewModels, tray indicator |
| `notifications/` | Notificaciones de escritorio (freedesktop D-Bus) |

La UI **nunca** contiene lógica de negocio: delega en casos de uso.

### `core/` — Transversal

`errors.py` (jerarquía de excepciones), `result.py` (`Result[T, E]` funcional),
`events.py` (bus de eventos pub/sub), `config.py`, `logging_setup.py`.

## Flujo: añadir un nuevo dispositivo

Añadir soporte para un nuevo modelo de auriculares **no** requiere tocar el
núcleo. El proceso es:

1. Crear un archivo YAML en `src/openbuds/device_profiles/` describiendo el
   dispositivo (fabricante, modelo, códecs, capacidades, limitaciones).
2. (Opcional) Añadir heurísticas de resolución en `match_hints` del YAML.
3. El sistema cargará el perfil automáticamente vía `IDeviceProfileRepository`.

Ver [ADR-0005](ADR/0005-device-profile-contract.md).

## Flujo: optimización segura

Toda escritura de configuración pasa por `ApplyOptimizationUseCase`, que
ejecuta estrictamente:

```
detect → backup → validate → apply → verify → (rollback si error)
```

Si **cualquier** paso falla, el sistema vuelve al estado anterior y lanza una
excepción del dominio. Nunca queda en estado intermedio.

## Coordinación de asincronía

- **D-Bus (BlueZ):** Gio/GDBus usa el `GMainLoop` de GLib. En la app Qt, se
  puentea hacia el `QEventLoop` (mecanismo a definir en Fase 3/6).
- **subprocess (PipeWire/WirePlumber):** llamadas síncronas y cortas; suficiente
  para inspección. No requiere event loop propio.
- **EventBus (`core/events.py`):** pub/sub en proceso, síncrono. Permite que la
  infraestructura publique eventos (dispositivo conectado, códec cambiado) sin
  acoplarse a la UI.

## Estado por fase

Ver [`ROADMAP.md`](ROADMAP.md) para el detalle del progreso por fase.
