# Contrato técnico — Lifecycle de señales de BlueZ (Incremento 2)

> **Estado:** **parcialmente implementado y verificado (2026-08-09).**
>
> - ✅ **Worker y lifecycle de bajo nivel** (§2–§3: `_SignalWorker` +
>   `GioDBusProtocol.subscribe`/`unsubscribe`/`close` y la delegación en
>   `BlueZDBusClient`) **implementado y verificado**. Validez: fakes
>   deterministas (unit, sin GI/bus), el spike genérico de D-Bus con Gio del
>   2026-08-09 y la **integración real de lifecycle** (Python 3.12 / Gio, 25
>   ciclos subscribe/unsubscribe/close + snapshot fresco). **No se afirma
>   recepción de señales reales de BlueZ** (ver nota al pie).
> - ⏳ **Repositorio** (§4: registro, cache de diff y dispatch de
>   `DeviceChangeEvent`; invariantes 4–8 de §7) **pendiente de
>   implementación** — próximo incremento, que cerrará
>   `IBluetoothRepository`; `subscribe_device_changes` sigue lanzando
>   `NotImplementedError`.
>
> Este documento se redactó con metodología **Documentation First** antes de
> escribir código. La implementación de bajo nivel cumple el contrato (§2–§3);
> ante cualquier discrepancia con las fuentes oficiales o con el spike se
> detiene y se documenta (AGENTS.md §5).

- **Fase:** 3 (Bluetooth) — Incremento 2 de señales y lifecycle
- **Tipo:** contrato de implementación (no es un ADR)
- **Fecha del contrato:** 2026-08-09
- **Documentos relacionados:** [ADR-0007](../ADR/0007-device-change-event-contract.md),
  [Diseño del cliente GDBus](gio-dbus-client-design.md),
  [Diseño del repositorio BlueZ](repository-design.md),
  [Contrato del mapper](object-mapper-contract.md),
  [Interfaces D-Bus de BlueZ](dbus-interfaces.md)
- **Dependencias del dominio:** `DeviceChangeKind`/`DeviceChangeEvent`,
  `DeviceChangeCallback`/`Unsubscribe`, `IBluetoothRepository`, `BluetoothError`.

> **Validación real del lifecycle (2026-08-09, Python 3.12 / Gio sobre BlueZ):**
> el integration opt-in (`tests/integration/test_bluez_signal_lifecycle.py`)
> ejecutó **25 ciclos** de `subscribe` → `unsubscribe` → `close` (×2) contra el
> BlueZ del sistema y un **snapshot fresco** final: el **bus compartido siguió
> usable** (la conexión nunca se cierra) y **no se indujo ninguna señal ni
> escritura** (no enciende/apaga, no conecta/desconecta, no escribe). El spike
> previo (mismo día, `/usr/bin/python3` + Gio) validó el patrón de worker
> dedicado con `GLib.MainContext.new()` + `push_thread_default()` +
> `GLib.MainLoop`: subscribe/unsubscribe en el mismo worker con el callback en
> el hilo del worker, **cero callbacks después del `unsubscribe`**, y una sonda
> transitoria de `NameOwnerChanged` + `ListNames` verificó la conexión y se
> **eliminó** al terminar el spike.
>
> **No se afirma recepción de señales reales de BlueZ:** el integration solo
> valida subscribe/unsubscribe/close/snapshot; la entrega de `SignalEvent`
> (metadata correcta, orden de registro, aislamiento de errores) está cubierta
> por los **fakes deterministas** de los unit tests y por el spike genérico de
> D-Bus.

---

## 1. Alcance

**Implementa:** worker y lifecycle en `GioDBusProtocol`
(`subscribe`/`unsubscribe`/`close`), delegación en `BlueZDBusClient`, y el
dispatch de `DeviceChangeEvent` en `BlueZRepository` con cache de diff.

> **Estado (2026-08-09):** las dos primeras partes (worker + lifecycle y
> delegación del cliente, §2–§3) están **implementadas y verificadas**; el
> dispatch del repositorio (§4) sigue **pendiente** (próximo incremento).

**Fuera de alcance:** métodos mutadores (prohibidos por construcción), cierre de
la conexión compartida, polling de respaldo (RESEARCH_LIMITS §4 — ítem
separado), integración GLib/Qt (Fase 6), mapeo de payload parcial.

---

## 2. Capa baja: señales en `GioDBusProtocol`

> **Estado (2026-08-09):** **implementado y verificado** en
> `dbus_protocol.py` (`GioDBusProtocol` + `_SignalWorker`) y `dbus_client.py`
> (`BlueZDBusClient`), cubierto por `tests/unit/test_bluez_signal_protocol.py`
> (fakes, sin GI/bus) y el integration de lifecycle
> (`tests/integration/test_bluez_signal_lifecycle.py`).

### 2.1 `SignalEvent` — metadata inmutable, sin payload

```python
@dataclass(frozen=True, slots=True)
class SignalEvent:
    interface_name: str
    signal_name: str
    object_path: str
```

- **Sin payload:** el repositorio refresca un snapshot completo en cada señal;
  nunca se mapea un payload parcial (object-mapper-contract §2).
- Callback bajo nivel: `SignalCallback = Callable[[SignalEvent], None]`.

### 2.2 Contrato del protocolo

```python
class GioDBusProtocol(BlueZProtocol):
    def subscribe(self, callback: SignalCallback) -> int: ...  # id lógico
    def unsubscribe(self, sub_id: int) -> None: ...
    def close(self) -> None: ...            # idempotente; no cierra el bus
    def __enter__(self) -> "GioDBusProtocol": ...
    def __exit__(self, *exc) -> None: ...
```

- `sub_id` es un **id lógico propio** (contador monotónico); los `guint` de GIO
  quedan internos al worker.
- `signal_subscribe` **no es fallible**: no se espera `GLib.Error`
  ([gio-dbus-client-design §2.6](gio-dbus-client-design.md#26-traducción-de-gliberror--bluetootherror)).
- Conexión vía `proxy.get_connection()`; es **compartida** y **nunca se
  cierra** (§2.5 del diseño del cliente).
- **Factory de worker inyectable** (`WorkerFactory`, default `_SignalWorker`) con
  **arranque perezoso**: el worker se crea en la **primera** `subscribe` y se
  detiene/descarta en la última `unsubscribe` o en `close`; un `subscribe`
  posterior crea un worker **nuevo** (restart limpio).
- **Concurrencia del arranque:** varios `subscribe` simultáneos se serializan
  con un `threading.Event` compartido (`_worker_starting`); un `close`
  concurrente con el arranque **rechaza** la suscripción en curso con
  `BluetoothError` y descarta el worker sin dejar suscripciones huérfanas.

### 2.3 `BlueZDBusClient` delega

`BlueZDBusClient.subscribe(cb)` / `unsubscribe(sub_id)` / `close()` delegan en el
protocolo inyectado y entregan **`SignalEvent`** (stream bajo nivel). **No**
construye `DeviceChangeEvent`: ese mapeo vive en el repositorio (§4), dueño del
cache.

- `subscribe`/`unsubscribe`/`close` son **delegaciones puras** al proveedor
  inyectado (`SignalProvider`); el cliente añade el mecanismo `sub_id` lógico y
  un `__enter__`/`__exit__` (context manager) que garantiza `close()` incluso
  ante excepción.

---

## 3. Worker dedicado de señales

> **Estado (2026-08-09):** **implementado y verificado** como `_SignalWorker`
> (`dbus_protocol.py`), cubierto por `tests/unit/test_bluez_signal_worker.py`
> (fakes deterministas, sin GI/bus). La validez del patrón sobre D-Bus real se
> confirmó con el spike genérico (2026-08-09) y la integración real de
> **lifecycle** en Python 3.12 / Gio. **No se afirma recepción de señales
> reales de BlueZ** (ver §8).

- Hilo **daemon** que arranca en la **primera** `subscribe` y se detiene en la
  última `unsubscribe` o en `close`. Dentro del worker:
  `connection = proxy.get_connection()` (no se cierra),
  `ctx = GLib.MainContext.new()` + `ctx.push_thread_default()`,
  `loop = GLib.MainLoop(context=ctx)` + `loop.run()`.
- **Arranque sincronizado:** `start()` espera la señal *ready* del worker con
  timeout (`SIGNAL_OPERATION_TIMEOUT = 5.0 s`). Si la creación del
  contexto/loop falla en el hilo, el error queda capturado (`_startup_error`)
  y se re-lanza como `BluetoothError` desde `start()`; si se agota el timeout
  también se reporta `BluetoothError` sin dejar el worker medio vivo.
- **Tres suscripciones GIO exactas**, con `sender="org.bluez"` (well-known en el
  *match*), `object_path=None` y `Gio.DBusSignalFlags.NONE`:

  | Interfaz | Señal |
  |----------|-------|
  | `org.freedesktop.DBus.ObjectManager` | `InterfacesAdded` |
  | `org.freedesktop.DBus.ObjectManager` | `InterfacesRemoved` |
  | `org.freedesktop.DBus.Properties` | `PropertiesChanged` |

- En el callback **no se revalida sender** (D-Bus lo reescribe al nombre único;
  [gio-dbus-client-design §2.4](gio-dbus-client-design.md#24-señales-con-giodbusconnectionsignal_subscribe)):
  se valida que `object_path`/`interface_name`/`signal_name` sean `str` y que el
  par `(interface_name, signal_name)` sea exactamente uno de los tres suscritos,
  y se construye `SignalEvent`.
- **Serialización:** toda operación Gio (`subscribe`/`unsubscribe`/`stop`) se
  encola al contexto del worker con
  **`GLib.MainContext.invoke_full(priority, callback)`**, un callback de
  retorno `void`/`None` (ver
  [GLib.MainContext — GIO](https://docs.gtk.org/glib/struct.MainContext.html));
  si el llamador **ya es el worker**, se ejecuta **directo** (reentrancia).
  `unsubscribe` corre siempre en el **hilo del worker** → **cero callbacks tras
  el retorno** (doc oficial de `signal_unsubscribe`; ADR-0007 §Consecuencias).
  El llamador espera la ejecución con el mismo timeout; si se agota o la
  operación lanza, se reporta `BluetoothError`.
- **Rollback atómico del registro parcial:** los tres `signal_subscribe` se
  registran como **unidad**; si falla cualquiera de ellos, se **desuscriben
  los IDs ya registrados**, se detiene el worker y se lanza `BluetoothError`
  (sin fugas de suscripción GIO).
- **Reentrancia en callbacks:** un callback puede **darse de baja a sí mismo**
  (`unsubscribe` desde el hilo del worker, sin deadlock) y un **`subscribe`
  dentro de un callback se difiere** a la siguiente señal (la iteración actual
  no repite callbacks recién añadidos).
- **Última suscripción lógica:** desuscribe los tres IDs GIO, `loop.quit()` y
  `thread.join()` salvo `self`; `close` es **idempotente** (antes o después de
  que el hilo termine).
- Excepciones de los callbacks internos → **aisladas y logueadas**; nunca rompen
  el dispatch ni el worker.

---

## 4. Repositorio: registro, cache y dispatch

> **Estado (2026-08-09):** **pendiente de implementación** (próximo incremento
> del roadmap, que cerrará `IBluetoothRepository`). §4.1–§4.5 y las invariantes
> 4–8 de §7 siguen siendo el **contrato** que la implementación debe cumplir:
> `subscribe_device_changes` sigue lanzando `NotImplementedError` en
> `bluez_repository.py` ([repository-design §6](repository-design.md#6-subscribe_device_changes--notimplemented-incremento-2)).

### 4.1 Registro

- `subscribe_device_changes(callback) -> Unsubscribe`, con **id propio** por
  registro y **`Unsubscribe` idempotente** (dos invocaciones no lanzan ni
  repiten liberación).
- El **mismo callback puede registrarse dos veces** (dos suscripciones
  independientes).
- Suscriptores posteriores al primero reciben **solo eventos futuros** (sin
  replay del estado inicial ni del cache actual).

### 4.2 Cierre de carrera en el primer registro

1. **snapshot A** — estado antes de suscribir (bajo lock).
2. `subscribe` bajo nivel (el worker arranca).
3. **snapshot B** — bajo el mismo lock.
4. **diff A→B:** no se emiten eventos por el estado preexistente en A; sí por
   los cambios ocurridos **entre A y B** (carrera de suscripción).

### 4.3 Cache y refresh

- Cache completa `ManagedObjects` (path → interfaces → props) protegida por un
  lock.
- En cada `SignalEvent`: snapshot fresco completo → **diff `cache → nuevo`** →
  actualizar cache → emitir eventos.
- Nunca se mapea un payload parcial (`changed`/`invalidated`).
- Error de refresh (Bluetooth/mapper): **preserva la cache** y **no emite**
  eventos.

### 4.4 Orden determinista

- Orden de emisión: **REMOVED, ADDED, UPDATED**; dentro de cada grupo,
  `object_path` **lexicográfico**.
- `UPDATED` **solo** si el `DeviceInfo` mapeado es **desigual** (igualdad
  completa del dataclass).
- `Battery1`/RSSI **no generan evento** si `DeviceInfo` no cambia
  (ADR-0007 §Semántica).

### 4.5 Entrega y consultas

- Cada evento se entrega en **orden de registro** de los suscriptores,
  **fuera del lock**; un error del callback de usuario se **loguea y se
  continúa** con el siguiente suscriptor.
- `unsubscribe` invocado **desde dentro de un callback**: sin deadlock (la
  liberación se serializa al worker; el dispatcher no espera al llamador).
- Las consultas snapshot siguen **independientes** (snapshot fresco por llamada,
  [repository-design §5.1](repository-design.md#51-snapshot-fresco-por-llamada-sin-cache)),
  ajenas a la cache de señales.

---

## 5. Contrato de hilos

- El callback de usuario corre en el **hilo del worker** (contexto de señales;
  ADR-0007 §Semántica).
- La **UI nunca se toca desde el worker**: se **marshalear** a Qt (señal/slot o
  cola). Obligatorio en Fase 6.
- `subscribe`/`unsubscribe` desde **cualquier hilo**; se serializan al worker
  (§3).

---

## 6. Diagramas de secuencia (breves)

**Primer registro (cierre de carrera A→B):**

```
Repo             BlueZDBusClient      Worker (Gio)          bus BlueZ
  |--snapshot()--------->|======================>|   GetManagedObjects
  |  snapshot A (lock)   |                      |
  |--subscribe(ev)------>|--subscribe(ev)------>| new ctx+loop
  |                      |                      | 3x signal_subscribe
  |--snapshot()--------->|======================>|   GetManagedObjects
  |  snapshot B (lock)   |                      |
  |--diff A->B: solo cambios entre A y B (sin replay de preexistente)
  |<--return Unsubscribe idempotente
```

**Señal → refresh → dispatch:**

```
bus BlueZ                      Worker (Gio)                    Repo
   |--InterfacesAdded / Removed / PropertiesChanged-->|
   |  (callback worker)                               |
   |     |--SignalEvent(iface, signal, path)---------->|
   |     |--snapshot fresco (GetManagedObjects)------->|
   |     |--diff cache -> nuevo (lock)                |
   |     |--actualiza cache (lock)                    |
   |     |--emite REMOVED, ADDED, UPDATED (registro)  |
   |     |--error refresh -> preserva cache, sin emitir
```

**Unsubscribe / close:**

```
Llamador (cualquier hilo)         Worker (Gio)
   |--unsubscribe(sub_id)-------->| MainContext.invoke_full (o directo si worker)
   |  (serializado al worker)     | elimina suscripción lógica
   |                              | si última: 3x signal_unsubscribe
   |                              | loop.quit(); join (salvo self)
   |<--retorno (cero callbacks después)
   |--close() idempotente
```

---

## 7. Invariantes

> **Estado (2026-08-09):** las invariantes **1–3 (worker/lifecycle de bajo
> nivel) están verificadas** por los unit tests y el integration de lifecycle.
> Las invariantes **4–8 (repositorio/dispatch) siguen pendientes** de
> implementación (§4).

1. Cero callbacks de usuario después de que `unsubscribe` retorne; `Unsubscribe`
   y `close()` **idempotentes**.
2. La conexión del bus **nunca** se cierra desde el cliente ni el repositorio.
3. Sin fugas de suscripción GIO: los 3 IDs se liberan al salir del último
   `unsubscribe`/`close` (refcount > 0 mientras haya suscripciones).
4. Todo evento cumple las invariantes de `DeviceChangeEvent`
   ([ADR-0007 §Decisión](../ADR/0007-device-change-event-contract.md)).
5. Cache solo bajo lock; diff y emisión en orden determinista
   (REMOVED → ADDED → UPDATED, path lexicográfico).
6. Error de refresh → cache intacta y **cero eventos** en esa entrega.
7. Eventos fuera del lock, en orden de registro; un callback que lanza no
   afecta a los demás.
8. Snapshot A nunca emite; solo el diff A→B emite para el primer registro.

---

## 8. Estrategia de pruebas

| Nivel | Archivo | GI | Bus | Estado | Qué valida |
|-------|---------|----|-----|--------|------------|
| Unit worker (fakes deterministas) | `tests/unit/test_bluez_signal_worker.py` | No | No | ✅ implementado | `_SignalWorker`: hilo daemon + contexto/loop dedicados, arranque sincronizado y timeout/failure, los 3 filtros exactos en el hilo del worker, `SignalEvent` con metadata correcta, callbacks en orden de registro y en el hilo del worker, **aislamiento de errores** (un callback que lanza no bloquea al siguiente), unsubscribe no-último conserva el worker y último libera los 3 IDs GIO (en el hilo del worker), close idempotente (antes/después de parar), rollback atómico del registro parcial, startup timeout/failure, unsubscribe desde el propio callback (sin deadlock), subscribe reentrante diferido a la siguiente señal |
| Unit protocolo | `tests/unit/test_bluez_signal_protocol.py` | No | No | ✅ implementado | `GioDBusProtocol`: factory de worker **perezosa** (snapshot/close no la tocan), arranque único y delegación de IDs, restart limpio tras última baja, close idempotente **sin cerrar proxy/conexión**, suscripción tras close falla de inmediato, contexto manager, rechazo de suscripción concurrente con close (sin huérfanos), factory falsy usable |
| Unit dispatch repo (contrato §4) | `tests/unit/...` (futuro) | No | No | ⏳ pendiente | diff cache→nuevo, cierre de carrera A→B, orden determinista, `UPDATED` solo si `DeviceInfo` desigual, errores de refresh (preserva cache, sin emitir), doble registro del mismo callback, `Unsubscribe` idempotente, unsubscribe desde callback, suscriptores tardíos sin replay |
| Integración opt-in (`OPENBUDS_RUN_INTEGRATION=1`) | `tests/integration/test_bluez_signal_lifecycle.py` | Sí | Sí | ✅ lifecycle (no recepción real) | **solo** subscribe/unsubscribe/close/snapshot reales: 25 ciclos + snapshot fresco; bus compartido usable; sin cierre de conexión; **nunca provoca BlueZ ni induce señales** |

> **Nota de alcance de la validación:** la **entrega de señales** está validada
> con **fakes deterministas** (unit) y el spike genérico de D-Bus con Gio; el
> integration real **no** afirma recepción de señales reales de BlueZ (solo
> lifecycle).

- Baseline por defecto (Python 3.14, sin GI/bus): **234 passed, 5 skipped** (las
  5 omisiones son las integraciones opt-in). Con `OPENBUDS_RUN_INTEGRATION=1` en
  **Python 3.12 / Gio**: **239 passed**. Comando de commit:
  `make lint && make typecheck && make test` (AGENTS.md §13).

---

## 9. Consistencia con diseños previos (cross-references)

- **gio-dbus-client-design §2.4:** conexión vía `proxy.get_connection()`
  (decidido); tres filtros exactos (InterfacesAdded/InterfacesRemoved/
  PropertiesChanged) en lugar de dos suscripciones amplias.
- **gio-dbus-client-design §2.5:** sin `open()`; el worker arranca
  **perezosamente** en la primera suscripción; el resto del lifecycle se
  conserva (§2.5). **Implementado.**
- **gio-dbus-client-design §3:** el cliente expone el stream bajo nivel de
  `SignalEvent`; el mapeo a `DeviceChangeEvent` es del **repositorio**.
  **Implementado** (cliente).
- **repository-design §2:** `SnapshotClient` se amplía en el Incremento 2 con
  `subscribe`/`unsubscribe`/`close` para señales; las consultas snapshot no se
  alteran. **Implementado** (cliente/protocolo).
- **repository-design §6:** `subscribe_device_changes` dejará de lanzar
  `NotImplementedError` al implementarse la **parte del repositorio** de este
  contrato (§4, pendiente).

---

## 10. Riesgos de la integración Qt (Fase 6)

- **No existe puente automático GLib/Qt:** el worker itera su propio
  `GMainContext`; los callbacks no tocan Qt. Toda actualización de UI se
  marshalear a través de señal/slot o cola del hilo principal; el worker no
  debe bloquearse por trabajo de usuario (el mapeo/diff es ligero y ocurre en
  el worker).
- La estrategia concreta de integración GLib/Qt queda **pendiente de investigar
  y validar en Fase 6** ([gio-dbus-client-design §6](gio-dbus-client-design.md#6-requisitos-de-entorno)).
- Concurrencia: el objeto del repositorio usado desde Qt debe ser seguro (los
  métodos de snapshot son independientes; el dispatch ocurre en el worker).

---

## 11. Fuentes oficiales

| Tema | URL |
|------|-----|
| `Gio.DBusConnection.signal_subscribe` (main context, hilo del callback, reescritura de sender) | https://docs.gtk.org/gio/method.DBusConnection.signal_subscribe.html |
| `Gio.DBusConnection.signal_unsubscribe` (garantía de mismo hilo, sin drenaje obligatorio) | https://docs.gtk.org/gio/method.DBusConnection.signal_unsubscribe.html |
| `GLib.MainContext` (thread-default, wakeup, iteration) | https://docs.gtk.org/glib/struct.MainContext.html |
| `GLib.MainLoop` (context, run/quit) | https://docs.gtk.org/glib/struct.MainLoop.html |
| D-Bus spec — Standard Interfaces (ObjectManager, Properties) | https://dbus.freedesktop.org/doc/dbus-specification.html |
| BlueZ D-Bus (interfaces y señales) | https://bluez.readthedocs.io/en/latest/ |
| PyGObject (proyecto oficial) | https://pygobject.gnome.org/ |

Referencias internas: [ADR-0007](../ADR/0007-device-change-event-contract.md),
[gio-dbus-client-design §2.4/§2.5/§3/§4](gio-dbus-client-design.md),
[repository-design §2/§5/§6](repository-design.md),
[RESEARCH_LIMITS §4](../RESEARCH_LIMITS.md#4).
