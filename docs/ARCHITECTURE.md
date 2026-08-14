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
│   (PySide6 / Qt, bandeja opcional, notificaciones Gio)       │
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

| Caso de uso | Descripción | Estado |
|-------------|-------------|--------|
| `ScanDevicesUseCase` | Listar dispositivos Bluetooth | Implementado (backend base publicado); se consumirá en la Etapa 2 |
| `GetDeviceInfoUseCase` | Información agregada (dispositivo + batería + RSSI + códec) | Pendiente, Etapa 2 |
| `ApplyOptimizationUseCase` | Aplicar optimización con flujo seguro (backup → validate → apply → verify → rollback) | Pendiente, Etapa 5 |
| `RunHealthCheckUseCase` | Health Check completo del stack | Pendiente, Etapa 4 |
| `RunBenchmarkUseCase` | Benchmark de calidad de enlace | Posteriores |

### `infrastructure/` — Adaptadores externos

| Subpaquete | Tecnología | Implementa | Etapa |
|------------|------------|------------|-------|
| `bluez/` | D-Bus vía PyGObject/Gio | `IBluetoothRepository` | 2 |
| `pipewire/` | `pw-dump`/`wpctl` vía subprocess | `IAudioRepository` | 1/2 |
| `wireplumber/` | Edición segura de config Lua 0.4 | `IConfigRepository` | 5 |
| `system/` | Detección de entorno | (parte de `IDiagnosticsRepository`) | 0/4 |
| `persistence/` | Config de la app + historial | — | 0 / posteriores |

### `presentation/` — Interfaz

| Subpaquete | Contenido |
|------------|-----------|
| `qt/` | GUI MVP, ViewModels, `DeviceChangeBridge` y adaptador opcional `QSystemTrayIcon` (Etapa 3) |
| `notifications/` | Adaptador best-effort freedesktop mediante Gio/GDBus en el bus de sesión |

La UI **nunca** contiene lógica de negocio: delega en casos de uso.

### `core/` — Transversal

`errors.py` (jerarquía de excepciones), `result.py` (`Result[T, E]` funcional),
`events.py` (bus de eventos pub/sub), `config.py`, `logging_setup.py`.

## Flujo: añadir un nuevo dispositivo

El objetivo es que añadir soporte para un nuevo modelo **no** requiera tocar el
núcleo, pero hoy **no** basta con crear un YAML: el contrato `DeviceProfile` y el
archivo YAML son todavía incompatibles. El rediseño tipado del contrato
(diferenciando fuente, evidencia, fecha y nivel de verificación) está pendiente
de aprobación, y el flujo de incorporación se definirá después de aprobarlo y de
disponer de evidencia de la Etapa 1 (caracterización física). No se asume que el
loader actual cargue un perfil nuevo ni que el YAML declare capacidades
verificadas.

Ver [ADR-0005](ADR/0005-device-profile-contract.md) y el gate del contrato en
[`ROADMAP.md`](ROADMAP.md).

## Flujo: optimización segura

Toda escritura de configuración pasa por `ApplyOptimizationUseCase`, que
ejecuta estrictamente:

```
detect → backup → validate → apply → verify → (rollback si error)
```

Si **cualquier** paso falla, el sistema vuelve al estado anterior y lanza una
excepción del dominio. Nunca queda en estado intermedio.

## Coordinación de asincronía

- **D-Bus (BlueZ):** Gio/GDBus usa el `GMainLoop` de GLib. La composición de la
  GUI comparte un único `BlueZRepository` entre el ViewModel y
  `WatchDevicesUseCase`. `DeviceChangeBridge` recibe callbacks fuera del hilo
  de Qt, emite un sobre mínimo y usa `Qt.QueuedConnection` para ejecutar el
  filtrado y `DesktopNotifier` en el hilo Qt.
- **subprocess (PipeWire/WirePlumber):** llamadas síncronas y cortas; suficiente
  para inspección. No requiere event loop propio.
- **EventBus (`core/events.py`):** pub/sub en proceso, síncrono. Permite que la
  infraestructura publique eventos (dispositivo conectado, códec cambiado) sin
  acoplarse a la UI.

El lifecycle de la ventana cierra el puente de cambios de dispositivos antes
de limpiar el ViewModel. La suscripción, la desuscripción y la notificación son
best-effort: errores genéricos se absorben y la GUI continúa disponible. `Notify`
se llama síncronamente en Qt con timeout de 1 s; la creación perezosa del proxy
también es síncrona, por lo que puede existir una demora breve. Las
notificaciones solo representan ADDED, REMOVED y transiciones de conexión;
cambios aislados de RSSI o batería no generan avisos. El mecanismo es
read-only y session-only.

## Estado por etapas

Ver [`ROADMAP.md`](ROADMAP.md) para el detalle del progreso por etapas.
