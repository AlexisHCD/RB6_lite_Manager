# Diseño técnico — Cliente GDBus para BlueZ (PyGObject/Gio)

Diseño de `openbuds.infrastructure.bluez.dbus_client` (`BlueZDBusClient`), el
cliente de bajo nivel que accede a BlueZ vía D-Bus usando **PyGObject/Gio
(GDBus)** según [ADR-0001](../ADR/0001-decision-dbus-pygobject-gio.md).

- **Fase:** 3 (Bluetooth)
- **Tipo:** diseño de implementación (no es un ADR)
- **Documento relacionado:** [Interfaces D-Bus de BlueZ](dbus-interfaces.md)
- **Dependencias del dominio:** `BluetoothError` (`core/errors.py`),
  `IBluetoothRepository` (`domain/interfaces/bluetooth_repo.py`), modelos del
  dominio (`DeviceInfo`, `AdapterInfo`, `BatteryLevel`, `RSSIReading`).

> ⚠️ **Regla de oro (AGENTS.md §5):** todo lo descrito aquí proviene de la
> documentación oficial (GNOME GIO/GLib, freedesktop.org, BlueZ). Los enlaces
> se listan en [Fuentes](#8-fuentes-oficiales-verificadas) y se verificaron el
> 2026-08-09. Ante cualquier discrepancia con el comportamiento real, se
> detiene la implementación y se documenta.

> **Estado de implementación (2026-08-09):** el **Incremento 1 — snapshot** de
> este diseño está **implementado y verificado**, y el **mapper de objetos**
> (`object_mapper.py`, ítem separado del roadmap) también:
>
> - `GioDBusProtocol` (`dbus_protocol.py`) construye el proxy con
>   `DO_NOT_AUTO_START` y llama a `GetManagedObjects` con `NO_AUTO_START`,
>   timeout finito `DBUS_CALL_TIMEOUT_MS = 5000`, valida la firma exacta
>   `(a{oa{sa{sv}}})` y envuelve `GLib.Error` → `BluetoothError` (§2.1, §2.2,
>   §2.6).
> - `BlueZDBusClient.snapshot()` (`dbus_client.py`) delega en un proveedor
>   inyectable; la carga de GI es **diferida** (solo se importa `gi` al
>   construir `GioDBusProtocol`), de modo que los unit tests corren **sin GI**
>   y sin bus del sistema (§2.7).
> - `object_mapper.py` está **implementado y verificado** contra su
>   [contrato](object-mapper-contract.md): mapper puro sin GI
>   (`map_adapter`/`map_device`/`map_battery`/`map_rssi`), validación estricta
>   y defaults conservadores.
> - Tests de integración opt-in (`OPENBUDS_RUN_INTEGRATION=1`) verificados en
>   Ubuntu, Python 3.12.3, PyGObject 3.48.2, con BlueZ disponible: lectura real
>   de `GetManagedObjects` coherente y mapeo de todos los objetos reales del
>   bus, **sin métodos mutadores** y sin exponer la MAC del dispositivo.
> - Suite actual: **177 passed, 3 skipped** (las 3 omisiones son las
>   integraciones opt-in, desactivadas por defecto). Las **consultas snapshot
>   del repositorio** (`bluez_repository.py`: `list_adapters`/`list_devices`/
>   `get_device`/`get_battery`/`get_rssi`, cliente inyectable + snapshot
>   fresco) están **implementadas y verificadas**
>   ([repository-design.md](repository-design.md)), incluida la integración
>   real solo lectura en **Python 3.12 / Gio**. El **repositorio completo**
>   sigue pendiente: `subscribe_device_changes` lanza `NotImplementedError`
>   hasta el **Incremento 2 de señales** (por eso el checkbox global del
>   roadmap permanece `[ ]`). También siguen pendientes las **señales/
>   lifecycle (Incremento 2)**, la **detección completa de
>   adaptadores/dispositivos** y la **CLI `devices`**.

---

## 1. Contexto y alcance

OpenBuds Manager necesita:

1. Obtener un **snapshot** del estado Bluetooth: lista de adaptadores,
   dispositivos, batería, RSSI, transporte de media activo.
2. **Suscribirse a cambios** en vivo: nuevos objetos
   (`InterfacesAdded`/`InterfacesRemoved`) y cambios de propiedades
   (`PropertiesChanged`).

El servicio D-Bus es **`org.bluez`** en el **bus del sistema**, gestionado por
el daemon `bluetoothd`. El ObjectManager de BlueZ vive en el object path raíz
**`/`** e implementa `org.freedesktop.DBus.ObjectManager`
([referencia dbus-interfaces.md](dbus-interfaces.md), [bluez doc](https://bluez.readthedocs.io/en/latest/)).
`MediaControl1` está **deprecated** y no se usa.

**Restricción absoluta de este componente (solo lectura):** el cliente nunca
invoca métodos que escriban en el dispositivo ni en BlueZ. Las únicas
interacciones son:

- `GetManagedObjects` (lectura del árbol de objetos).
- Suscripción a señales estándar (recepción, nunca emisión).
- Lectura vía `org.freedesktop.DBus.Properties.GetAll`/`Get` (si el snapshot
  lo requiere en lugar de cache).

La **filosofía del proyecto** (AGENTS.md §3) prohíbe escribir dentro del
dispositivo Bluetooth. Este diseño la cumple por construcción: no hay ningún
método mutador en el contrato del cliente.

---

## 2. Decisiones de diseño clave

### 2.1 `Gio.DBusProxy.new_for_bus_sync` sobre el bus del sistema

Se crea un proxy síncrono para el **ObjectManager** de BlueZ:

```
Gio.DBusProxy.new_for_bus_sync(
    Gio.BusType.SYSTEM,
    Gio.DBusProxyFlags.DO_NOT_AUTO_START,   # no auto-arrancar bluetoothd
    None,                                    # interface_info: confiar en la introspección remota
    "org.bluez",                             # well-known name
    "/",                                     # object path raíz (ObjectManager)
    "org.freedesktop.DBus.ObjectManager",
    None,                                    # cancellable
)
```

Justificación ([Gio.DBusProxy — GNOME Python API](https://api.pygobject.gnome.org/Gio-2.0/class-DBusProxy.html),
[new_for_bus_sync — GIO](https://docs.gtk.org/gio/ctor.DBusProxy.new_for_bus_sync.html)):

- `new_for_bus_sync` se conecta al bus del sistema **sincrónicamente** y deja
  el proxy listo antes de devolver el control: encaja con el snapshot inicial.
- BlueZ es un servicio **persistente** (daemon `bluetoothd`), no un servicio
  stateless: usar `GDBusProxy` es correcto. (Para servicios stateless la doc
  de GIO recomienda llamadas directas, pero ese no es el caso.)
- `DBusProxyFlags.DO_NOT_AUTO_START`: la lectura del snapshot **nunca** debe
  activar `bluetoothd`. La disponibilidad de BlueZ la comprueba el **environment
  detector** antes de llamar al cliente; si el daemon no está activo se reporta
  `BluetoothError` sin intentar auto-arrancarlo.
- `interface_info=None`: no se inventa un `Gio.DBusInterfaceInfo`; el proxy se
  construye confiando en la introspección remota del objeto.
- El proxy se construye **una sola vez** por instancia del cliente y se
  reutiliza para el snapshot y (en Incremento 2) para refrescos puntuales.
- El `GDBusProxy` cachea propiedades y expone `g-properties-changed`, pero en
  este diseño las señales se gestionan con `signal_subscribe` sobre la
  conexión (ver §2.4): el proxy es el medio para **métodos**, no la fuente de
  señales.

**Detalle de trazabilidad:** `DBusProxy.new_for_bus_sync` es la única vía
documentada por GIO para crear un proxy *para un bus* de forma síncrona
("Like g_dbus_proxy_new_sync() but takes a GBusType instead of a
GDBusConnection").

### 2.2 `GetManagedObjects` sin parámetros, flags NO_AUTO_START, timeout finito

Invocación del método:

```
reply = proxy.call_sync(
    "GetManagedObjects",               # método de org.freedesktop.DBus.ObjectManager
    None,                              # parámetros: None = sin parámetros (la API permite NULL)
    Gio.DBusCallFlags.NO_AUTO_START,   # no auto-arrancar bluetoothd
    5000,                              # timeout FINITO en ms (nunca -1/G_MAXINT)
    None,                              # cancellable
)
```

Racional ([call_sync](https://docs.gtk.org/gio/method.DBusProxy.call_sync.html),
[DBusCallFlags](https://docs.gtk.org/gio/flags.DBusCallFlags.html)):

- **Sin parámetros:** la especificación de D-Bus define `GetManagedObjects()`
  sin argumentos y con retorno `a{oa{sa{sv}}}` (sección *Standard Interfaces →
  org.freedesktop.DBus.ObjectManager*). `call_sync` acepta **`None`** en
  `parameters` (equivale a sin parámetros), verificado contra la
  implementación real.
- **`DBusCallFlags.NO_AUTO_START`:** la lectura del snapshot no debe
  auto-activar `bluetoothd`. La disponibilidad del daemon se comprueba antes
  con el **environment detector**; si no está disponible, se reporta
  `BluetoothError` sin intentar arrancarlo.
- **Timeout finito (5000 ms):** GIO usa `-1` para el timeout por defecto del
  proxy y `G_MAXINT` para "infinito". Se exige explícitamente un valor finito
  para que un daemon colgado no bloquee el CLI o la GUI. El valor se expone
  como constante (`DBUS_CALL_TIMEOUT_MS = 5000`) para ajuste centralizado.
- **Cancellable:** `None` en el snapshot; se permite inyectar uno en entornos
  con ciclo de vida controlado (GUI).

El retorno verificado es un `GLib.Variant` con firma `(a{oa{sa{sv}}})` (tupla
de un elemento; ver §2.3).

### 2.3 Unpack de GVariant → tipos Python

PyGObject expone `GLib.Variant.unpack()` que convierte valores GVariant a
tipos Python nativos. BlueZ usa exclusivamente tipos canónicos del D-Bus:

| D-Bus (GVariant) | Firma | Python resultante |
|-------------------|-------|-------------------|
| STRING / OBJECT_PATH | `s` / `o` | `str` |
| BOOLEAN | `b` | `bool` |
| BYTE | `y` | `int` |
| INT16 / UINT16 / INT32 / UINT32 / INT64 / UINT64 | `n` `q` `i` `u` `x` `t` | `int` |
| DOUBLE | `d` | `float` |
| ARRAY de STRING | `as` | `list[str]` |
| ARRAY de BYTE | `ay` | `list[int]` |
| DICT `{sv}` | `a{sv}` | `dict[str, Any]` |

Uso previsto (resultado real verificado):

```
reply.get_type_string() == "(a{oa{sa{sv}}})"   # firma verificada empíricamente
snapshot = reply.unpack()[0]                   # unpack() devuelve una tupla de longitud 1
# snapshot: dict[str, dict[str, dict[str, object]]]
#   object_path -> { "org.bluez.Device1": { "Address": "AA:BB:...", ... }, ... }
```

En la prueba real, las propiedades llegan **ya como tipos Python nativos**
(`str`, `bool`, `int`, `float`, listas y dicts) tras el unpack, sin necesidad
de conversión manual; la tabla anterior documenta el mapeo esperado por tipo.

Reglas de mapeo concretas para este proyecto (ver tablas de propiedades en
[dbus-interfaces.md](dbus-interfaces.md)):

- `Device1.RSSI` (int16) → `int`. Puede estar ausente → `None`.
- `MediaTransport1.Codec` (byte) → `int`. SBC=0x00, AAC=0x02 son canonizados;
  los vendor no se asumen (ver [RESEARCH_LIMITS](../RESEARCH_LIMITS.md#1)).
- `Device1.UUIDs` (`as`) → `tuple[str, ...]` al mapear al dominio.
- `Adapter` (object path) → `str` (se usa como clave de relación).

**Separación de responsabilidades:** el *unpack* del `GLib.Variant` (que sí
toca GI) vive aislado en una función pequeña del módulo Gio; la **traducción
de dicts nativos → modelos del dominio** la hace
`bluez/object_mapper.py` como funciones puras sobre `dict` (testeable sin
GI). Esto es un prerrequisito de la inyección de backend (§2.7).

### 2.4 Señales con `Gio.DBusConnection.signal_subscribe`

Para el Incremento 2, el cliente obtiene su conexión (vía `Gio.bus_get_sync`
o `proxy.get_connection()`) y suscribe:

```
connection.signal_subscribe(
    "org.bluez",                       # sender (well-known name)
    "org.freedesktop.DBus.ObjectManager",  # interface_name (InterfacesAdded/Removed)
    None,                              # member: None = todas las señales de la interfaz
    None,                              # object_path: None = todos
    None,                              # arg0
    Gio.DBusSignalFlags.NONE,          # flags de matching
    _on_om_signal,                     # callback
)
```

Y una segunda suscripción para `org.freedesktop.DBus.Properties` /
`PropertiesChanged`. La firma del callback es
`(connection, sender_name, object_path, interface_name, signal_name, parameters)`
— el `parameters` es un `GLib.Variant` que se unpackea con las reglas de §2.3.

**Obligación de GLib main context** (punto no negociable). La documentación de
[signal_subscribe](https://docs.gtk.org/gio/method.DBusConnection.signal_subscribe.html)
es explícita:

> "callback will be invoked in the thread-default main context
> (`g_main_context_push_thread_default()`) of the thread you are calling this
> method from."

Consecuencias de diseño:

- Las suscripciones **no entregan callbacks hasta que un `GMainContext` está
  siendo iterado** (`GLib.MainLoop.run()`, `GLib.MainContext.iteration()`, o
  el event loop de Qt si se integra como fuente).
- En CLI (Incremento 2) se itera el loop el tiempo que dure la sesión de
  monitoreo. Para Fase 3 basta un `GMainContext` **dedicado** o **iterado
  explícitamente** por el hilo que llama a `subscribe`. La integración
  GLib/Qt concreta queda **pendiente de investigar y validar para la Fase 6**:
  no se asume ningún puente automático entre event loops.
- El código de test que quiera *ver* señales debe hacer avanzar el context
  (p.ej. `GLib.MainContext.default().iteration(False)` con límites) — nunca
  un `sleep` a ciegas.
- La conexión de GIO es segura para hilos, pero los callbacks se ejecutan en
  el hilo del main context; el mapeo de señales a eventos del dominio debe
  ser libre de races o delegar a la cola del hilo principal.

Manejo de nombres: D-Bus reescribe el sender al **nombre único** del emisor
(`:1.XX`) en el callback; no debe filtrarse por well-known name dentro del
callback (ver nota de la doc oficial de `signal_subscribe`). Para BlueZ con
un único daemon es seguro simplemente no filtrar por sender y validar por
`interface_name` + `signal_name`.

### 2.5 Lifecycle y unsubscribe

El contrato del cliente expone un ciclo de vida explícito:

- `open()` / constructor → conexión + snapshot.
- `subscribe(callback)` → devuelve `SubscriptionId`.
- `unsubscribe(subscription_id)` → libera la suscripción.
- `close()` → libera suscripciones y referencias propias (no cierra el bus);
  idempotente.

Detalles técnicos ([signal_unsubscribe](https://docs.gtk.org/gio/method.DBusConnection.signal_unsubscribe.html)):

- `signal_subscribe` devuelve un identificador `guint` **no cero**. Según su
  documentación no es una llamada fallible: no se incluye entre las llamadas
  GIO que lanzan `GLib.Error` (§2.6). El ID se almacena por suscripción y se
  usa en `signal_unsubscribe(id)`.
- **Garantía de la doc (mismo hilo):** si `unsubscribe` se llama desde el mismo
  hilo que hizo `subscribe`, el callback no se invocará después de que
  `unsubscribe` retorne. No hay obligación documental de **drenar** el
  `GMainContext` posterior: como `user_data` y `DestroyNotify` serán `None`,
  no queda recurso de usuario pendiente que liberar.
- **El cliente NO es dueño de la conexión ni del bus.** La conexión se obtiene
  de `Gio.bus_get_sync`/`proxy.get_connection()` y puede compartirse con otros
  componentes; `close()` **no** llama a `connection.close()`/`close_sync()`.
  `close()` solo hace `signal_unsubscribe` de los IDs propios y libera las
  referencias propias; debe ser **idempotente** (cerrar dos veces no lanza
  excepción ni re-intenta unsubscribes ya realizados).
- El cliente se implementa como **context manager** (`__enter__`/`__exit__`)
  para garantizar `close()` incluso ante excepción.

### 2.6 Traducción de `GLib.Error` → `BluetoothError`

Todas las llamadas GIO fallibles (`new_for_bus_sync`, `call_sync`) lanzan
`GLib.Error` en PyGObject. `signal_subscribe` no se incluye: según su
documentación no es una llamada fallible (devuelve un ID no cero, ver §2.5).
Los errores se envuelven de forma centralizada en la jerarquía del dominio
(AGENTS.md §13:

```
def _to_bluetooth_error(err: GLib.Error, context: str) -> BluetoothError:
    domain = err.domain                    # e.g. "g-io-error-quark"
    code = err.code                        # G_IO_ERROR_CLOSED, G_DBUS_ERROR_* ...
    message = err.message
    return BluetoothError(f"{context}: {message}")  # con __cause__ = err
```

Reglas:

- Se mantiene el `GLib.Error` original como `__cause__` (cadena de
  excepciones) para diagnóstico.
- Errores conocidos se traducen a subclases cuando aportan semántica: bus
  no disponible o daemon caído → `BluetoothError` genérica (no inventar
  subclases sin necesidad); objeto no encontrado (Nombre desconocido) →
  `DeviceNotFoundError`/`AdapterNotFoundError` ya existentes en
  `core/errors.py`.
- La traducción es **únicamente hacia `BluetoothError`** (subclase de
  `OpenBudsError`); nunca se deja escapar un `GLib.Error` a las capas de
  aplicación/presentación.
- La doc oficial de GLib ([error-reporting](https://docs.gtk.org/glib/error-reporting.html))
  define el contrato de `GError` (domain/code/message): es la base del
  mapeo.

### 2.7 Inyección de backend/protocol para pruebas sin GI

El módulo Gio no se importa de forma global: se aísla tras una pequeña
abstracción de protocolo. Objetivo: **todos los unit tests corren sin
`python3-gi` y sin bus del sistema**.

```
class BlueZProtocol(Protocol):      # contrato interno (infrastructure)
    def snapshot(self) -> dict[str, dict[str, dict[str, object]]]: ...
    def subscribe(self, cb) -> int: ...
    def unsubscribe(self, sub_id: int) -> None: ...
    def close(self) -> None: ...

class GioDBusProtocol(BlueZProtocol):   # implementación real (usa GI)
    ...

class FakeDBusProtocol(BlueZProtocol):  # implementación de prueba (sin GI)
    ...
```

`BlueZDBusClient` recibe el protocolo por **inyección** (`__init__`); por
defecto construye `GioDBusProtocol` solo cuando se usa en producción, y los
tests pasan `FakeDBusProtocol`.

Capas resultantes (todas dentro de `infrastructure/bluez/`):

1. **`dbus_protocol.py`** — solo el adaptador Gio: construir proxy, `call_sync`
   `GetManagedObjects`, `signal_subscribe`, lifecycle. **Único archivo que
   importa `gi`.** Recibe el snapshot en dicts nativos.
2. **`object_mapper.py`** — funciones puras: `dict nativo → DeviceInfo /
   AdapterInfo / BatteryLevel / RSSIReading`. Sin GI.
3. **`dbus_client.py`** — orquesta: protocolo + mapper + errores + observador
   (`DeviceChangeCallback`). Sin GI.

De esta forma `object_mapper.py` y `dbus_client.py` se testean en CI sin
dependencia de GI; `GioDBusProtocol` se cubre con tests de integración
marcados (ver §7) que requieren bus del sistema.

### 2.8 Ninguna escritura al dispositivo

- El contrato del protocolo solo expone `snapshot()`, `subscribe()`,
  `unsubscribe()`, `close()`. **No existe** método de invocación arbitraria
  expuesto al resto del sistema.
- El repositorio `IBluetoothRepository` ya declara ser **solo lectura**
  (ver docstring en `domain/interfaces/bluetooth_repo.py`).
- Ni `GetManagedObjects`, ni las señales suscritas, ni `Properties.GetAll`
  modifican el stack ni el dispositivo: son operaciones de lectura pura.
- Regla de revisión de código: cualquier método que llame a un miembro
  **mutador** de BlueZ (`Adapter1.Powered`, `Device1.Connect`, etc.) está
  **fuera de alcance** de este diseño y debe rechazarse.

---

## 3. Interfaz del cliente (resumen)

```
class BlueZDBusClient:
    def __init__(self, protocol: BlueZProtocol | None = None) -> None: ...

    def snapshot(self) -> ManagedObjectsSnapshot:   # dicts nativos (sin mapeo a modelos)
    def list_adapters(self) -> list[AdapterInfo]
    def list_devices(self, adapter_path: str | None = None) -> list[DeviceInfo]
    def get_device(self, device_path: str) -> DeviceInfo | None
    def get_battery(self, device_path: str) -> BatteryLevel | None
    def get_rssi(self, device_path: str) -> RSSIReading | None

    def subscribe_device_changes(self, cb: DeviceChangeCallback) -> int
    def unsubscribe_device_changes(self, sub_id: int) -> None

    def close(self) -> None  # idempotente; libera suscripciones y referencias propias (no cierra el bus)
    def __enter__(self) -> "BlueZDBusClient"
    def __exit__(self, *exc) -> None
```

`subscribe_device_changes` mapea las señales a `DeviceChangeCallback`
(`DeviceInfo, ConnectionState`), manteniendo el contrato del dominio intacto.

---

## 4. Incrementos de implementación

### Incremento 1 — Snapshot (GetManagedObjects)

**Alcance:**
- `GioDBusProtocol`: `new_for_bus_sync` + `call_sync("GetManagedObjects", …)`
  con `DBusCallFlags.NO_AUTO_START` y timeout finito (§2.1, §2.2).
- `unpack()` → `snapshot = reply.unpack()[0]` (dicts nativos; §2.3).
- Traducción `GLib.Error` → `BluetoothError` (§2.6).
- `BlueZDBusClient.snapshot()` con protocolo inyectable (§2.7).
- **Sin señales** y **sin `object_mapper`** en este incremento: el mapeo de
  dicts nativos → modelos del dominio es un ítem/commit **separado** del
  roadmap (`bluez/object_mapper.py`), no forma parte de los criterios de este
  incremento.

**Criterios de aceptación (Incremento 1):**
- `pytest` unitario pasa **sin GI** (FakeDBusProtocol) cubriendo
  `GioDBusProtocol`/snapshot con respuestas de ejemplo.
- En la máquina real (Ubuntu 24.04 + BlueZ), el test de integración marcado
  obtiene una respuesta `GetManagedObjects` con
  `get_type_string() == "(a{oa{sa{sv}}})"` y un snapshot coherente con
  `busctl tree org.bluez` (comandos solo lectura de
  [dbus-interfaces.md](dbus-interfaces.md)).
- La lectura **no auto-arranca** `bluetoothd`: con el daemon detenido se
  produce `BluetoothError` (tras la comprobación del environment detector),
  no `GLib.Error` ni cuelgues.
- No se invoca ningún método mutador (revisión de git diff).

### Incremento 2 — Señales y lifecycle

**Alcance:**
- `signal_subscribe` para `ObjectManager` (InterfacesAdded/Removed) y
  `Properties` (PropertiesChanged) (§2.4).
- Dispatch a `DeviceChangeCallback` manteniendo estado incremental
  (los eventos traen payloads parciales; se refrescan con el snapshot de la
  propiedad y se notifica `DeviceInfo` completo).
- `unsubscribe` + `close()` idempotentes, sin cerrar la conexión compartida
  (§2.5).
- CLI de monitoreo (o vista de Logs/dashboard en Fase 6) que itere el
  `GMainContext` para entregar señales.
- Respaldo por polling periódico de propiedades críticas según
  [RESEARCH_LIMITS §4](../RESEARCH_LIMITS.md#4).

**Criterios de aceptación (Incremento 2):**
- Conectar/desconectar un dispositivo (p.ej. `bluetoothctl power on` /
  encendido físico) dispara el callback con el `DeviceInfo` correcto, sin
  bloqueos ni pérdida de callbacks.
- `unsubscribe`/`close` idempotentes; sin excepción al cerrar dos veces y sin
  callbacks posteriores al unsubscribe.
- Tests unitarios de dispatch con señales fabricadas (sin GI).
- Se documenta empíricamente la fiabilidad de `PropertiesChanged` para
  `Device1.Connected` en el entorno objetivo.

---

## 5. Dependencia y ubicación en el árbol

```
src/openbuds/infrastructure/bluez/
├── dbus_protocol.py      # [INC 1] GioDBusProtocol (única importación de gi)
├── object_mapper.py      # [implementado] dicts nativos → modelos (puro)
├── dbus_client.py        # [INC 1+2] BlueZDBusClient (protocolo + errores + observador; usa object_mapper)
└── bluez_repository.py   # [consultas implementadas] IBluetoothRepository sobre BlueZDBusClient (señales → Inc 2)
```

> El contrato técnico (Documentation First) del mapper está en
> [object-mapper-contract.md](object-mapper-contract.md): firmas, política de
> validación, tablas propiedad→campo y criterios TDD. El ítem está
> **implementado y verificado** y el contrato se conserva como documentación
> viva.

`bluez_repository.py` empezó como esqueleto en Fase 1; sus **consultas
snapshot** ya están **implementadas y verificadas** (cliente inyectable,
snapshot fresco por llamada; ver [repository-design.md](repository-design.md)).
La suscripción a cambios (`subscribe_device_changes`) se completará en el
Incremento 2 y cerrará el contrato `IBluetoothRepository`.

---

## 6. Requisitos de entorno

- Ubuntu 24.04: `python3-gi`, `gir1.2-glib-2.0`, `libgirepository-2.0-dev`
  (ver README, sección Instalación).
- BlueZ ≥ 5.72. El environment detector comprueba la disponibilidad de
  `bluetoothd` antes del snapshot; el cliente nunca lo auto-arranca.
- Para el incremento de señales: un `GMainContext` iterando (dedicado o
  explícitamente iterado por el hilo que suscribe).
- La integración GLib/Qt concreta queda **pendiente de investigar y validar
  para la Fase 6**; no se asume ningún puente automático entre event loops.

---

## 7. Estrategia de pruebas

| Nivel | Requiere GI | Requiere bus del sistema | Cobertura |
|-------|-------------|--------------------------|-----------|
| Unit (mapper) | No | No | Traducción dicts → modelos, valores ausentes, tipos raros |
| Unit (cliente) | No | No | Orquestación con `FakeDBusProtocol`, traducción de errores, lifecycle |
| Unit (dispatch señales) | No | No | Fabricar `parameters` GVariant-like (dicts) → `DeviceChangeCallback` |
| Integración (marcados) | Sí | Sí | `GetManagedObjects` real, señales reales con un dispositivo |
| E2E / manual | Sí | Sí | `openbuds devices`, monitoreo con conexión/desconexión real |

- Los tests de integración se marcan (p.ej. `@pytest.mark.integration` /
  `@pytest.mark.slow`) y no forman parte del baseline por defecto, siguiendo
  el patrón del Makefile (`make test-quick` = solo unit).
- El baseline actual del proyecto es de **177 tests** en verde + **3 skipped**
  (las integraciones BlueZ opt-in desactivadas por defecto; 2026-08-09); las
  pruebas del mapper, del cliente y de las consultas del repositorio de este
  diseño ya forman parte del suite y el resto de incrementos se añaden sin
  romperlo.
- Verificación manual complementaria (solo lectura):
  `busctl tree org.bluez`, `busctl introspect org.bluez /`, `dbus-send
  --system --dest=org.bluez --print-reply / org.freedesktop.DBus.ObjectManager.GetManagedObjects`.
- Comando del equipo: `make lint && make typecheck && make test` antes de
  cada commit (AGENTS.md §13).

---

## 8. Fuentes oficiales verificadas

Verificadas (contenido consultado) el 2026-08-09:

| Tema | URL |
|------|-----|
| Gio.DBusProxy (new_for_bus_sync, call_sync, cache de propiedades) | https://docs.gtk.org/gio/class.DBusProxy.html |
| Gio.DBusProxy.call_sync (parámetros, flags, timeout, retorno GVariant) | https://docs.gtk.org/gio/method.DBusProxy.call_sync.html |
| Gio.DBusConnection.signal_subscribe (main context obligatorio, firma callback, nombres únicos) | https://docs.gtk.org/gio/method.DBusConnection.signal_subscribe.html |
| Gio.DBusConnection.signal_unsubscribe (garantía de mismo hilo, sin drenaje obligatorio) | https://docs.gtk.org/gio/method.DBusConnection.signal_unsubscribe.html |
| Gio.DBusConnection (class: call_sync, close, is_closed) | https://docs.gtk.org/gio/class.DBusConnection.html |
| Gio.DBusCallFlags (NONE / NO_AUTO_START / ALLOW_INTERACTIVE_AUTHORIZATION) | https://docs.gtk.org/gio/flags.DBusCallFlags.html |
| GLib.MainContext (thread-default, iteration, main loop) | https://docs.gtk.org/glib/struct.MainContext.html |
| GLib.Variant (unpack/get_*, tipos) | https://docs.gtk.org/glib/struct.Variant.html |
| GLib error-reporting (GError domain/code/message) | https://docs.gtk.org/glib/error-reporting.html |
| D-Bus specification — Standard Interfaces (ObjectManager, Properties) | https://dbus.freedesktop.org/doc/dbus-specification.html |
| GNOME Python API — `Gio.DBusProxy` | https://api.pygobject.gnome.org/Gio-2.0/class-DBusProxy.html |
| GNOME Python API — `GLib.Variant.unpack` | https://api.pygobject.gnome.org/GLib-2.0/structure-Variant.html |
| PyGObject (proyecto oficial) | https://pygobject.gnome.org/ |
| BlueZ — documentación D-Bus (adapter, device, battery, media) | https://bluez.readthedocs.io/en/latest/ |

Referencias internas: [ADR-0001](../ADR/0001-decision-dbus-pygobject-gio.md),
[Interfaces D-Bus de BlueZ](dbus-interfaces.md),
[RESEARCH_LIMITS](../RESEARCH_LIMITS.md).

---

## 9. Riesgos y límites conocidos

- **Fiabilidad de `PropertiesChanged`:** puede no llegar en ciertos flujos;
  se respalda con polling periódico (RESEARCH_LIMITS §4).
- **`Battery1` no es universal:** se trata como opcional
  (RESEARCH_LIMITS §3).
- **Códecs vendor (aptX/LDAC):** bytes no canonizados; nunca se asumen
  (RESEARCH_LIMITS §1).
- **Integración GLib/Qt en la GUI:** estrategia **pendiente de investigar y
  validar** en la Fase 6; no se asume ningún puente automático entre event
  loops. En Fase 3 se usa un `GMainContext` dedicado o iterado explícitamente;
  en CLI el `GMainLoop` es suficiente.
- **Disponibilidad de BlueZ:** el snapshot no auto-arranca `bluetoothd`; si el
  daemon no está disponible, el environment detector lo detecta y el cliente
  reporta `BluetoothError` sin intentar arrancarlo.
- **Timeout:** el valor de 5000 ms es una decisión de ingeniería razonable,
  no una constante del protocolo; se valida empíricamente en la máquina real.
