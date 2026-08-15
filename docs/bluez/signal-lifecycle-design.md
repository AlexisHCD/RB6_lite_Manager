# Contrato técnico — Lifecycle de señales de BlueZ (Incremento 2)

> **Estado:** **implementado y verificado (2026-08-10).**
>
> - ✅ **Worker y lifecycle de bajo nivel** (§2–§3: `_SignalWorker` +
>   `GioDBusProtocol.subscribe`/`unsubscribe`/`close` y la delegación en
>   `BlueZDBusClient`) **implementado y verificado**, incluido el **hook
>   `on_ready` opcional** (§2.2.1: corre en el hilo del worker, después de
>   instalar los filtros GIO y registrar el callback lógico y **antes** de que
>   `subscribe` retorne; rollback atómico si lanza). Validez: fakes
>   deterministas (unit, sin GI/bus), el spike genérico de D-Bus con Gio del
>   2026-08-09 y la **integración real de lifecycle** (Python 3.12 / Gio, 25
>   ciclos subscribe/unsubscribe/close + snapshot fresco). **No se afirma
>   recepción de señales reales de BlueZ** (ver nota al pie).
> - ✅ **Repositorio** (§4: registro, cache de diff y dispatch de
>   `DeviceChangeEvent`) **implementado y verificado** con el **diff puro de
>   snapshots** (`device_change_diff.py`): init A→B en el worker vía `on_ready`
>   (snapshot B cierra la carrera), refresh completo por señal, orden
>   determinista `REMOVED→ADDED→UPDATED`, igualdad mapeada de `DeviceInfo`,
>   aislamiento de callbacks, suscriptores múltiples/tardíos/reentrantes,
>   `Unsubscribe` idempotente con espera de in-flight, concurrencia de init y
>   rollback de errores. Cubre por completo `IBluetoothRepository`
>   (`subscribe_device_changes` ya no lanza `NotImplementedError`). Validez:
>   fakes deterministas (`tests/unit/test_bluez_repository_signals.py`,
>   `tests/unit/test_device_change_diff.py`) + integración real opt-in de
>   **lifecycle A/B** (`tests/integration/test_bluez_repository_signals.py`).
> - ✅ **Polling de respaldo** (§12) **implementado y verificado (2026-08-10)**:
>   `on_poll`/`poll_interval_ms` en el nivel bajo
>   (`_validate_polling_options`: **validación pura antes de tocar el worker/
>   GIO** y además defensiva en el worker; `type(...) is int` exacto y `> 0`),
>   `GSource` de timeout **monotónico** con `set_callback` y `attach` al **mismo
>   `MainContext` del worker** **después** de `on_ready`, retorno
>   `SOURCE_CONTINUE` (la fuente nunca se auto-cancela), **error de poll aislado
>   y logueado**, **ownership lógico** por suscripción, `destroy()` **idempotente
>   en el hilo del worker** y **rollback create/set/attach**; el bus compartido
>   **nunca** se cierra. En el repositorio: **default
>   `POLL_INTERVAL_DEFAULT_MS = 5000` inyectable y validado en el constructor**,
>   **primer** `subscribe` bajo nivel único con `on_poll` (tardíos sin timers
>   extra), `_handle_signal` y `_handle_poll` comparten el **mismo pipeline
>   `_refresh_and_dispatch`** (detecta `Connected`/`Paired`/`Trusted`) y las
>   mismas garantías de cache/error/dispatch/unsubscribe. Validez: fakes
>   deterministas **sin `sleep`** (tick manual) + **integración real opt-in de
>   lifecycle create/destroy inmediato con `poll_interval_ms=60_000`** (sin
>   tick real, sin hardware, sin señales inducidas) y **bus compartido usable
>   con snapshot posterior**. Los gates ordinarios y la integración opt-in
>   pasaron al cierre del incremento (2026-08-10, Python 3.12 / Gio);
>   ruff/mypy en verde.
>
> **Corrección sobre el diseño previo (2026-08-10):** el *self-unsubscribe
> durante A→B* mediante el callable retornado es **imposible**: el
> `Unsubscribe` no existe hasta que `subscribe_device_changes` retorna, y
> `on_ready` corre dentro de esa llamada. Se eliminó esa promesa. Lo válido y
> probado: **`subscribe` reentrante durante A→B sin replay** (§4.6), self-
> unsubscribe **solo tras poseer el `Unsubscribe`** (en señales futuras) y
> unsubscribe externo con espera de in-flight.
>
> Este documento se redactó con metodología **Documentation First** antes de
> escribir código y ahora describe el **código real implementado**. Ante
> cualquier discrepancia con las fuentes oficiales o con el spike se detiene y
> se documenta y se detiene la implementación si la evidencia es insuficiente (ver [RESEARCH_LIMITS](../RESEARCH_LIMITS.md)).

- **Incremento:** 2 de señales y lifecycle (BlueZ)
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

> **Estado (2026-08-10):** las tres partes (worker + lifecycle, delegación del
> cliente y dispatch del repositorio, §2–§4) están **implementadas y
> verificadas**.

**Fuera de alcance:** métodos mutadores (prohibidos por construcción), cierre de
la conexión compartida, integración GLib/Qt (Etapa 3) y mapeo de payload parcial.
El **polling de respaldo** está **implementado y verificado** en
[§12](#12-polling-de-respaldo-implementado-y-verificado-2026-08-10)
([RESEARCH_LIMITS §4](../RESEARCH_LIMITS.md#4-fiabilidad-de-señales-d-bus)) como
extensión interna compatible; **no** forma parte del contrato del dominio.

---

## 2. Capa baja: señales en `GioDBusProtocol`

> **Estado (2026-08-10):** **implementado y verificado** en
> `dbus_protocol.py` (`GioDBusProtocol` + `_SignalWorker`) y `dbus_client.py`
> (`BlueZDBusClient`), cubierto por `tests/unit/test_bluez_signal_protocol.py`
> (fakes, sin GI/bus) y el integration de lifecycle
> (`tests/integration/test_bluez_signal_lifecycle.py`). Incluye el hook
> **`on_ready`** (§2.2.1).

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

### 2.2.1 `on_ready`: hook de init en el worker

> **Estado (2026-08-10):** **implementado y verificado.** El contrato de §2.2
> (`subscribe(callback) -> int`) no cambia: `on_ready` es una **extensión
> opcional compatible hacia atrás** (default `None`).

```python
class GioDBusProtocol(BlueZProtocol):
    def subscribe(
        self,
        callback: SignalCallback,
        on_ready: Callable[[], None] | None = None,
    ) -> int: ...  # id lógico
```

- `on_ready` es un **callable sin argumentos o `None`** (`ReadyCallback =
  Callable[[], None]`); también está en el worker (`SignalWorker.subscribe`),
  en el protocolo interno (`SignalProvider.subscribe`), en
  `BlueZDBusClient.subscribe` y en el `SnapshotClient` del repositorio.
- **Dónde y cuándo (implementación real en `_SignalWorker._subscribe`):** se
  ejecuta **en el hilo del worker**, **después** de registrar los tres filtros
  GIO (`_register_bus_signals`) y **después** de registrar el callback lógico,
  y **antes** de que `subscribe` retorne al llamador.
- **Serialización con las señales:** `on_ready` corre dentro de la operación de
  `subscribe` encolada en el `MainContext` del worker; las señales que lleguen
  durante el init quedan **encoladas en el mismo contexto** y se procesan
  **después** de que `on_ready` termine. Por tanto `on_ready` ve el estado
  post-filtros sin que ningún `SignalEvent` se haya entregado todavía: el init
  del repositorio y el dispatch de señales quedan **totalmente ordenados**.
- **Fallos (implementación real):** si `on_ready` lanza, el worker **revierte**
  el registro lógico recién añadido (`self._subscriptions.pop(subscription_id)`),
  detiene el worker si era la última suscripción (`_stop_on_worker`) y **re-lanza
  la excepción** al llamador (el protocolo la envuelve como `BluetoothError`
  con su `__cause__`).
- **Reentrancia:** `on_ready` corre en el worker; **no debe esperar
  operaciones del hilo llamador** ni esperarse a sí mismo (sería deadlock). El
  repositorio la usa solo para snapshot + diff + cache + dispatch, todo
  autocontenido.
- **`None` (default)** ⇒ comportamiento de §2.2, sin hook.

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

> **Estado (2026-08-10):** **implementado y verificado** como `_SignalWorker`
> (`dbus_protocol.py`), cubierto por `tests/unit/test_bluez_signal_worker.py`
> (fakes deterministas, sin GI/bus). Incluye la ejecución serializada del hook
> **`on_ready`** (§2.2.1) dentro de la operación de `subscribe`. La validez del
> patrón sobre D-Bus real se confirmó con el spike genérico (2026-08-09) y la
> integración real de **lifecycle** en Python 3.12 / Gio. **No se afirma
> recepción de señales reales de BlueZ** (ver §8).

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

> **Estado (2026-08-10):** **implementado y verificado** en `bluez_repository.py`
> (`BlueZRepository.subscribe_device_changes`) sobre el **diff puro de
> snapshots** (`device_change_diff.py`). §4.1–§4.5 y las invariantes 4–15 de §7
> describen el **comportamiento real**, cubierto por
> `tests/unit/test_bluez_repository_signals.py` y
> `tests/unit/test_device_change_diff.py` (fakes deterministas, sin GI/bus) más
> la **integración real de lifecycle A/B**
> (`tests/integration/test_bluez_repository_signals.py`, Python 3.12/Gio;
> solo subscribe/unsubscribe + snapshot A/B + bus usable, sin señales inducidas
> ni escrituras). `IBluetoothRepository` queda **completo** (el checkbox del
> roadmap se marca `[x]`).

### 4.1 Registro

- `subscribe_device_changes(callback) -> Unsubscribe`, con **id propio** por
  registro y **`Unsubscribe` idempotente** (dos invocaciones no lanzan ni
  repiten liberación).
- El **mismo callback puede registrarse dos veces** (dos suscripciones
  independientes).
- Suscriptores posteriores al primero reciben **solo eventos futuros** (sin
  replay del estado inicial ni del cache actual).

### 4.2 Cierre de carrera en el primer registro

> **Estado (2026-08-10): implementado.** El flujo usa el hook `on_ready` de
> bajo nivel (§2.2.1) para que el init corra **en el worker** antes de que
> `subscribe` retorne. Detalle, pseudocódigo ya implementado y casos de prueba
> en §4.6/§4.7.

1. **snapshot A** — estado antes de suscribir, bajo el lock del repositorio
   (hilo del llamador de `subscribe_device_changes`).
2. `subscribe(callback_lógico, on_ready=init)` de bajo nivel (el worker arranca,
   instala los tres filtros GIO y registra el callback lógico).
3. **En el worker, dentro de `subscribe`, antes de que retorne:** `on_ready`
   ejecuta el init del repositorio:
   a. **snapshot B** — estado post-filtros (**cierra la carrera**).
   b. **diff A→B** — no se emiten eventos por el estado preexistente en A; sí
      por los cambios ocurridos **entre A y B** (carrera de suscripción).
   c. **actualizar cache** a B.
   d. **primer dispatch** al primer suscriptor (fuera del lock).
4. `subscribe` retorna; en adelante cada `SignalEvent` → refresh → dispatch a
   todos los suscriptores.

- Las señales llegadas entre la instalación de filtros y el fin de `on_ready`
  se **serializan en el mismo `MainContext`** y se procesan **después** de que
  `on_ready` termine (la cache ya está en B): **B cierra la carrera**.
- **Fallo de `on_ready` (snapshot B / mapper / diff):** rollback completo —
  callback lógico + IDs GIO liberados (worker limpio si era la última
  suscripción lógica), **estado parcial revocado** (cache y subscriber init) y
  `BluetoothError` propagado a `subscribe_device_changes`. **Cero eventos** en
  ese registro.

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

### 4.6 API `on_ready` del primer registro

> **Estado (2026-08-10):** **implementado y verificado** en
> `bluez_repository.py`. La API `on_ready` es **infraestructura interna**: no
> altera `IBluetoothRepository` ni el contrato `DeviceChangeCallback` del
> dominio ([ADR-0007](../ADR/0007-device-change-event-contract.md)).

**Contradicción que resuelve.** El diseño original hacía `subscribe` → retorno →
snapshot B + diff + primer dispatch **en el hilo del llamador**, pero los
callbacks de usuario corren **en el hilo del worker** (§5) y comienzan a
entregarse en cuanto el worker instala filtros y registra el callback lógico:
quedaba una ventana en la que señales en curso podían disparar dispatch contra
un cache aún sin init (sin B, sin diff A→B). `on_ready` elimina la ventana: el
init del repositorio corre **en el worker**, dentro de la operación de
`subscribe` serializada por el `MainContext`, y **antes del retorno**.

**Implementación real en `bluez_repository.py`** (estructura de sincronización:
una `threading.Condition` sobre `RLock`; `_subscribers` es un `dict[int,
_Subscriber]`):

1. `subscribe_device_changes` toma el `_condition`; si otro hilo está
   inicializando (**`_initializing`**) y no es este hilo, **espera** en la
   condición hasta que el init termine. Luego **registra el suscriptor**
   (`_add_subscriber`) y, si ya existe suscripción de bajo nivel
   (`_low_subscription_id`) o el init está en curso, retorna ya el
   `Unsubscribe` (solo futuros, sin replay).
2. **Primer suscriptor:** marca `_initializing`, toma **snapshot A** (bajo
   lock, antes de instalar filtros) y llama
   `self._client.subscribe(self._handle_signal, on_ready=...)`.
3. **`on_ready` (`_finish_initialization`) corre en el hilo del worker, dentro
   de `subscribe`, antes del retorno:** toma **snapshot B** (post-filtros →
   **cierra la carrera**), hace `diff_device_snapshots(A, B)` (solo cambios
   entre A y B; el estado preexistente en A **no emite**), actualiza `_cache` a
   B y hace el **primer dispatch** con una copia de los suscriptores (fuera del
   lock).
4. Al retornar `subscribe` con el `sub_id`, el repositorio guarda
   `_low_subscription_id`, limpia `_initializing`, notifica a los segundos
   concurrentes y devuelve `self._make_unsubscribe(subscriber_id)`. **No existe
   `_flush_pending_releases`**: el self-unsubscribe durante A→B es imposible
   porque el `Unsubscribe` aún no se ha devuelto (ver reentrancia abajo).

**Fallos de init.** Si `on_ready` lanza (snapshot B / mapper / diff), el bajo
nivel revierte (callback lógico + IDs GIO + worker limpio si era la última
suscripción lógica) y propaga `BluetoothError`; el repositorio ejecuta
`_abort_initialization` (**revoca el estado parcial**: `_cache`, suscriptores
del init en curso) y notifica a los segundos concurrentes (reciben el mismo
error, no quedan colgados; un registro posterior puede reiniciar como primer
suscriptor). **Cero eventos** entregados por el registro fallido.

**Semántica de suscriptores.**

- **Primer suscriptor:** dispara el init (A → on_ready/B → diff → cache → primer
  dispatch) y recibe los eventos del diff A→B.
- **Segundo concurrente:** espera a que el init termine (condición), luego se
  registra **sin replay** (solo eventos futuros). Si el init falló, recibe el
  error.
- **Reentrante desde callback** (worker): se registra **sin replay** y **sin
  esperarse a sí mismo** (esperar bloquearía al worker; la detección usa el
  `threading.get_ident()` del hilo que inicializa).
- **Suscriptor tardío** (post-init): solo eventos futuros; nunca replay del
  estado inicial ni del cache (invariante 8).

**Reentrancia de `Unsubscribe`.**

- **`subscribe` reentrante durante A→B** (un callback de `on_ready` o de señal
  llama a `subscribe_device_changes`): se registra **sin replay** (no recibe ni
  el diff actual ni el resto de la entrega en curso) y **sin deadlock**; recibe
  los eventos de señales futuras. Verificado por
  `test_worker_on_ready_reentrant_subscriber_does_not_deadlock_or_replay` y
  `test_reentrant_subscriber_from_callback_does_not_receive_current_event_but_gets_future`.
- **Self-unsubscribe es solo posible después de poseer el `Unsubscribe`** (que
  `subscribe_device_changes` haya retornado), p. ej. **desde un callback de
  señal posterior**: `active=false` (no se le entregan más eventos, ni siquiera
  el resto de la entrega en curso) y, si es el último suscriptor, se libera la
  suscripción de bajo nivel y se descarta la cache. Sin deadlock (la espera de
  in-flight se salta al propio hilo). Durante A→B **no** puede ocurrir, porque
  el callable aún no existe; por eso no hay release pendiente.
- **Unsubscribe externo** (otro hilo): `active=false` + `client.unsubscribe(sub_id)`
  (cero callbacks futuros por el contrato del worker) y **espera a que termine
  cualquier callback in-flight de ese suscriptor** (contador/condición de
  dispatch) **salvo si el propio hilo es el del callback** (self). Garantía:
  **cero callbacks de ese suscriptor después de que `Unsubscribe` retorne**.
- `Unsubscribe` **idempotente**: la segunda invocación no lanza ni repite release.

**Cero llamadas de usuario bajo lock.** Los callbacks (dispatch en `on_ready` y
en refresh) se invocan **siempre fuera del lock** del repositorio: el lock solo
protege cache, estado de init y lista de suscriptores. El snapshot/diff se
computa bajo lock, pero la entrega se hace con una copia de la lista y fuera del
lock.

**Fallos de refresh (señal).** Si el snapshot fresco o el mapper fallan durante
un `SignalEvent`: se **preserva la cache anterior** y se **emiten cero eventos**
en esa entrega (invariante 6, sin cambios).

---

### 4.7 Casos de prueba concretos del dispatch (implementados)

> Archivos reales: `tests/unit/test_bluez_repository_signals.py` (dispatch,
> fakes deterministas sin GI/bus) y `tests/unit/test_device_change_diff.py`
> (diff puro). Todos **implementados y en verde**; la columna "Verificación
> esperada" describe el comportamiento real verificado.

| # | Caso | Verificación esperada (real) |
|---|------|------------------------------|
| 1 | Primer registro: init completo | A tomado antes del `subscribe` bajo nivel; `on_ready` corre **antes** de que `subscribe` retorne; diff A→B calculado; cache actualizada a B. |
| 2 | Señales durante el init | `on_ready` bloqueado → se procesa después (cache ya en B); los eventos del init no se pierden. |
| 3 | Diff A→B | Solo emite cambios entre A y B; el estado preexistente en A no emite (igualdad → cero eventos). |
| 4 | Init fallido (snapshot B lanza) | Rollback bajo nivel (callback lógico + IDs GIO + worker si último), estado repo revocado (cache/init), `BluetoothError` propagado, **cero eventos**. |
| 5 | Init fallido + segundo concurrente | El segundo `subscribe_device_changes` espera y recibe el mismo error (no queda colgado); un registro posterior reinicia como primer suscriptor. |
| 6 | Segundo concurrente tras init ok | Espera al init; se registra sin replay; solo recibe eventos futuros. |
| 7 | Suscriptor tardío | Sin replay del estado inicial ni del cache; solo futuros (un único `subscribe` bajo nivel que hace fan-out). |
| 8 | Reentrante desde callback (worker) | Se registra **sin replay y sin bloquear al worker** (sin deadlock); recibe eventos de señales futuras (probado también con `on_ready_in_worker_thread`). |
| 9 | Self-unsubscribe desde un callback de señal (tras poseer el `Unsubscribe`) | `active=false` (no recibe ni el resto de la entrega en curso ni eventos futuros); al ser el último se libera el `subscribe` bajo nivel; sin deadlock. *(Self-unsubscribe durante A→B: no aplica — el callable aún no existe.)* |
| 10 | Unsubscribe externo con callback in-flight | El `Unsubscribe` retorna solo cuando el callback en curso termina; **cero callbacks posteriores**. |
| 11 | Unsubscribe externo sin in-flight | Retorno inmediato; cero callbacks posteriores; idempotente (segunda llamada no-op); un nuevo ciclo usa un `sub_id` nuevo y cache limpia. |
| 12 | Reentrancia de `subscribe`/`unsubscribe` desde un callback | Sin deadlock del lock del repo (probado explícitamente). |
| 13 | Refresh fallido (señal) | Snapshot/mapper falla → cache anterior intacta, **cero eventos** en esa entrega; la siguiente señal diffs contra la cache preservada. |
| 14 | Doble registro del mismo callback | Dos suscripciones independientes; se entrega a ambas en orden de registro; dar de baja una no afecta a la otra. |
| — | Orden determinista y `UPDATED` condicional | `REMOVED→ADDED→UPDATED` por `object_path`; `UPDATED` solo si `DeviceInfo` mapeado es desigual. |
| — | Sin eventos Battery/RSSI-only | Cambios solo en `Battery1`/`RSSI`/`TxPower` o props no mapeadas no emiten evento. |
| — | El repositorio nunca cierra el cliente | `close()` del cliente no se invoca nunca (`client.close_calls == 0`). |

---

## 5. Contrato de hilos

- El callback de usuario corre en el **hilo del worker** (contexto de señales;
  ADR-0007 §Semántica).
- La **UI nunca se toca desde el worker**: se **marshalear** a Qt (señal/slot o
  cola). Obligatorio en la Etapa 3.
- `subscribe`/`unsubscribe` desde **cualquier hilo**; se serializan al worker
  (§3).

---

## 6. Diagramas de secuencia (breves)

**Primer registro (cierre de carrera A→B, implementado §4.6):**

```
Llamador/repo           BlueZDBusClient         Worker (Gio)             bus BlueZ
   |--snapshot()----------->|==========================>|   GetManagedObjects
   |  snapshot A (lock)     |                          |
   |--subscribe(cb,on_ready)-->|--subscribe(cb,on_ready)-->| new ctx+loop
   |                         |                          | 3x signal_subscribe + registra cb
   |                         |   on_ready() [worker]    |
   |                         |--snapshot()======================>|  GetManagedObjects
   |                         |  snapshot B (cierra carrera)
   |                         |  diff A->B (lock) -> cache -> primer dispatch (fuera del lock)
   |<--retorno (sub_id)------|<--retorno
   |  (self-unsubscribe durante A->B: no aplica — el Unsubscribe aún no existe)
```

> Las señales llegadas durante el init (entre la instalación de filtros y el fin
> de `on_ready`) se **encolan en el mismo `MainContext`** y se procesan
> **después** de `on_ready`: la cache ya está en B, por lo que **B cierra la
> carrera**.

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

> **Estado (2026-08-10):** las invariantes **1–15** están **verificadas** por
> los unit tests (fakes deterministas, sin GI/bus) y las integraciones reales
> opt-in de lifecycle (worker A/B + repositorio A/B, Python 3.12/Gio). La 13
> describe el self-unsubscribe válido (desde un callback de señal, tras poseer
> el `Unsubscribe`); durante A→B no aplica porque el callable aún no existe
> (§4.6). El **polling de respaldo** ([§12](#12-polling-de-respaldo-implementado-y-verificado-2026-08-10))
> está **implementado y verificado** y reutiliza estas invariantes (mismo
> pipeline `_refresh_and_dispatch`, cache, `active`/in-flight y serialización
> del worker).

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
9. El init del primer registro corre en **`on_ready`, en el hilo del worker,
   antes de que `subscribe` retorne** y antes de cualquier `SignalEvent`; **B
   cierra la carrera** (las señales del init se serializan en el mismo
   `MainContext` y se procesan después).
10. Si el init falla (`on_ready`/snapshot B/mapper/diff): **rollback completo**
    de la suscripción lógica/GIO (worker limpio si era la última), estado
    parcial del repositorio **revocado** (cache/init) y `BluetoothError`
    propagado; **cero eventos** entregados.
11. Suscriptores posteriores al primero: **solo eventos futuros, sin replay**;
    el segundo concurrente **espera al init**; el reentrante desde callback se
    registra **sin replay y sin esperarse a sí mismo** (sin deadlock).
12. **Cero llamadas de usuario bajo el lock** del repositorio (cache, init y
    lista de suscriptores sí; el dispatch nunca).
13. **Self-unsubscribe desde un callback de señal** (tras poseer el
    `Unsubscribe`): `active=false` → no recibe ni el resto de la entrega en
    curso ni eventos futuros; sin deadlock; si es el último suscriptor se libera
    el `subscribe` bajo nivel y la cache. **Durante A→B no aplica** (el callable
    aún no existe; lo válido ahí es `subscribe` reentrante sin replay).
14. **Unsubscribe externo espera** cualquier callback in-flight de su
    suscriptor (**salvo self**) para garantizar **cero callbacks tras el
    retorno**; `Unsubscribe` idempotente.
15. Fallo de snapshot/mapper en refresh (señal): **preserva la cache previa** y
    **emite cero eventos** en esa entrega.

---

## 8. Estrategia de pruebas

| Nivel | Archivo | GI | Bus | Estado | Qué valida |
|-------|---------|----|-----|--------|------------|
| Unit worker (fakes deterministas) | `tests/unit/test_bluez_signal_worker.py` | No | No | ✅ implementado | `_SignalWorker`: hilo daemon + contexto/loop dedicados, arranque sincronizado y timeout/failure, los 3 filtros exactos en el hilo del worker, `SignalEvent` con metadata correcta, callbacks en orden de registro y en el hilo del worker, **aislamiento de errores** (un callback que lanza no bloquea al siguiente), unsubscribe no-último conserva el worker y último libera los 3 IDs GIO (en el hilo del worker), close idempotente (antes/después de parar), rollback atómico del registro parcial, startup timeout/failure, unsubscribe desde el propio callback (sin deadlock), subscribe reentrante diferido a la siguiente señal |
| Unit protocolo | `tests/unit/test_bluez_signal_protocol.py` | No | No | ✅ implementado | `GioDBusProtocol`: factory de worker **perezosa** (snapshot/close no la tocan), arranque único y delegación de IDs, restart limpio tras última baja, close idempotente **sin cerrar proxy/conexión**, suscripción tras close falla de inmediato, contexto manager, rechazo de suscripción concurrente con close (sin huérfanos), factory falsy usable; **`on_ready`** opcional (propagación al worker, rollback si lanza); **`on_poll`/`poll_interval_ms`** reenviados con el intervalo exacto al worker y **`ValueError` antes de crear el worker** si el par es inválido |
| Unit diff puro | `tests/unit/test_device_change_diff.py` | No | No | ✅ implementado | `diff_device_snapshots`: snapshots iguales → `()`; `REMOVED`/`ADDED`/`UPDATED` con `current`/`previous` correctos; orden agrupado `REMOVED→ADDED→UPDATED` por `object_path`; `UPDATED` solo si `DeviceInfo` mapeado es desigual; **sin eventos** por cambios solo de `Battery1`/`RSSI`/`TxPower`/props no mapeadas; alta/baja de `Device1` detectada aunque la ruta conserve otra interfaz; errores del mapper propagados sin eventos parciales; snapshots no mutados |
| Unit dispatch repo | `tests/unit/test_bluez_repository_signals.py` | No | No | ✅ implementado | init vía `on_ready` en worker (snapshot A→B, diff, cache y primer dispatch **antes** del retorno de `subscribe`; `on_ready` en hilo worker con `on_ready_in_worker_thread`); diff A→B sin replay de preexistente; init fallido (snapshot B / subscribe bajo nivel: rollback + estado revocado + `BluetoothError`, cero eventos, retry como primer suscriptor); segundo concurrente espera init (y error si falló); suscriptor tardío sin replay (un único subscribe bajo nivel con fan-out en orden); reentrante desde callback sin deadlock ni replay; **self-unsubscribe** desde callback de señal sin deadlock ni eventos futuros; unsubscribe externo espera in-flight (cero callbacks tras retorno) e idempotente; reentrancia `subscribe`/`unsubscribe` desde callback sin deadlock del lock; refresh fallido (snapshot/mapper) preserva cache sin emitir; doble registro del mismo callback independiente; orden determinista y `UPDATED` solo si `DeviceInfo` desigual; **sin eventos Battery/RSSI-only**; **el repo nunca cierra el cliente**; **polling**: default 5000 ms en el primer subscribe de bajo nivel, intervalo inyectado exacto, inválido rechazado antes de usar el cliente, tardíos sin timers extra, poll captura `Connected`/`Paired`/`Trusted`, poll == señal (mismo `_refresh_and_dispatch`), cache/error/self-unsubscribe/external-unsubscribe idénticos a señal, último unsubscribe cancela el poll y el nuevo ciclo crea fuente nueva |
| Integración opt-in (`OPENBUDS_RUN_INTEGRATION=1`) | `tests/integration/test_bluez_signal_lifecycle.py` | Sí | Sí | ✅ lifecycle + polling (no recepción real) | **solo** subscribe/unsubscribe/close/snapshot reales: 25 ciclos + snapshot fresco; **creación/destrucción inmediata del `GSource` de polling con `poll_interval_ms=60_000`** (no tick real, no espera el intervalo); bus compartido usable; sin cierre de conexión; **nunca provoca BlueZ ni induce señales** |
| Integración opt-in (`OPENBUDS_RUN_INTEGRATION=1`) | `tests/integration/test_bluez_repository_signals.py` | Sí | Sí | ✅ lifecycle A/B (no recepción real) | `subscribe_device_changes` real + unsubscribe idempotente + snapshot A/B (eventos con invariantes del dominio) + `list_devices` post-cierre; bus compartido usable; **sin** señales inducidas, **sin** afirmar recepción real, **sin** escrituras de hardware |

> **Nota de alcance de la validación:** la **entrega de señales** está validada
> con **fakes deterministas** (unit) y el spike genérico de D-Bus con Gio; el
> integration real **no** afirma recepción de señales reales de BlueZ (solo
> lifecycle).

- Los gates ordinarios y la integración opt-in pasaron al cierre del incremento
  (2026-08-10; ruff/mypy en verde). Comando de commit:
  `make lint && make typecheck && make test` ([desarrollo y validación](../../README.md#desarrollo-y-validación)).

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
- **repository-design §6:** `subscribe_device_changes` ya **no lanza
  `NotImplementedError`**: la **parte del repositorio** de este contrato (§4)
  está **implementada y verificada** ([repository-design §6](repository-design.md#6-subscribe_device_changes--implementado-incremento-2)).

---

## 10. Riesgos de la integración Qt (Etapa 3)

- **Puente GLib/Qt implementado:**
  `src/openbuds/presentation/qt/device_change_bridge.py` recibe los eventos;
  los callbacks del repositorio no tocan Qt y `Qt.QueuedConnection` realiza el
  *marshal* hacia el hilo de Qt. El worker itera su propio `GMainContext` y no
  debe bloquearse por trabajo de usuario (el mapeo/diff es ligero y ocurre en
  el worker).
- El lifecycle del puente está validado por tests, incluidos el cierre
  idempotente, la desuscripción y las carreras relevantes; la cobertura no
  afirma transiciones reales del dispositivo, suspensión o reanudación.
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
[RESEARCH_LIMITS §4](../RESEARCH_LIMITS.md#4-fiabilidad-de-señales-d-bus).

> Las fuentes de `GLib.timeout_source_new`/`GSource` (tiempo monotónico, attach,
> destroy, set_callback, `SOURCE_CONTINUE`) del **polling de respaldo
> implementado** están verificadas en [§12.10](#1210-fuentes-oficiales-verificadas).

---

## 12. Polling de respaldo: implementado y verificado (2026-08-10)

> **Estado:** **implementado y verificado (2026-08-10).** Este §12 se redactó con
> metodología **Documentation First aprobada** y ahora describe el **código real
> implementado** en `dbus_protocol.py`, `dbus_client.py` y `bluez_repository.py`.
> Es un **respaldo por polling** periódico que mitiga la posible pérdida de
> `PropertiesChanged`
> ([RESEARCH_LIMITS §4](../RESEARCH_LIMITS.md#4-fiabilidad-de-señales-d-bus)).
> Los contratos implementados de §2–§4 y las invariantes 1–15 de §7 **no
> cambian**: esta extensión es **compatible hacia atrás** y **no modifica**
> `IBluetoothRepository` ni el contrato del dominio
> ([ADR-0007](../ADR/0007-device-change-event-contract.md)). Validez: fakes
> deterministas (tick manual, sin `sleep`) + integración real opt-in de
> **lifecycle create/destroy inmediato** (sin tick real).

### 12.1 Objetivo

La señal primaria (refresh completo por señal + diff de snapshots) puede fallar
si `PropertiesChanged` no llega (casos documentados en
[RESEARCH_LIMITS §4](../RESEARCH_LIMITS.md#4-fiabilidad-de-señales-d-bus)). El
polling de respaldo es una **red de seguridad redundante**: un timer periódico
dispara el **mismo pipeline snapshot → diff → cache → dispatch** que la señal, de
modo que un cambio en `Connected`/`Paired`/`Trusted` perdido por la señal queda
capturado en el siguiente tick. Es **redundancia, no reemplazo**: el primer poll
tras una señal sin cambios emite **cero eventos** (el diff es vacío).

### 12.2 Extensión compatible de la API de bajo nivel

El `subscribe` de bajo nivel (§2.2) **ganó** dos parámetros opcionales
(extensión **compatible hacia atrás**; la firma actual
`subscribe(callback, on_ready=None)` sigue siendo válida):

```python
class GioDBusProtocol(BlueZProtocol):
    def subscribe(
        self,
        signal_callback: SignalCallback,
        on_ready: Callable[[], None] | None = None,
        on_poll: Callable[[], None] | None = None,
        poll_interval_ms: int | None = None,
    ) -> int: ...  # id lógico
```

Contrato del par `on_poll`/`poll_interval_ms` (**implementado** en
`_validate_polling_options`, validación pura antes de tocar el worker/GIO y
además defensiva en el worker):

- `on_poll` (`Callable[[], None] | None`): callback periódico que corre **en el
  hilo del worker** (§3).
- Si `on_poll` está presente, `poll_interval_ms` es **obligatorio y `> 0`**
  (milisegundos). Si `on_poll` es `None`, `poll_interval_ms` debe ser `None`.
  Cualquier otra combinación → `ValueError` **antes** de tocar GIO.
- La comprobación de `poll_interval_ms` exige **`type(...) is int`** exacto
  (`0`, negativos, `float` y `bool` se rechazan).
- `on_poll=None` **y** `poll_interval_ms=None` ⇒ **sin polling** (comportamiento
  actual idéntico).
- La extensión se propaga por la misma cadena interna que `on_ready` (§2.2.1):
  `_SignalWorker.subscribe`, `SignalProvider.subscribe`, `BlueZDBusClient.subscribe`
  y el `SnapshotClient` del repositorio, con la misma firma ampliada.

### 12.3 Timer en el worker (`_SignalWorker`)

**Implementado en `_SignalWorker._subscribe`** (tras `on_ready`, dentro de la
misma operación de `subscribe` encolada en el `MainContext` del worker,
**después** de que `on_ready` termine —el init del repositorio corre primero— y
**antes** de que `subscribe` retorne):

1. `source = GLib.timeout_source_new(poll_interval_ms)` — intervalo en ms; el
   `GSource` de timeout usa **tiempo monotónico** y se rearma automáticamente
   mientras el callback retorne `G_SOURCE_CONTINUE`
   ([§12.10](#1210-fuentes-oficiales-verificadas)).
2. `source.set_callback(wrapper)` — `wrapper()` llama a `on_poll()`, captura y
   **loguea cualquier excepción** (aislamiento, §3) y retorna siempre
   `GLib.SOURCE_CONTINUE` (la fuente **nunca se auto-cancela**).
3. `source.attach(ctx)` — se adjunta al **`GLib.MainContext` dedicado del
   worker** (el mismo que itera el `MainLoop`, §3). `attach` devuelve un id
   `guint > 0`; si devuelve `0`, la fuente no quedó adjunta ⇒ error.

Consecuencias (**verificadas**):

- El poll corre **en el hilo del worker**, **serializado** con las señales y con
  las operaciones `subscribe`/`unsubscribe` en el mismo `MainContext` (mismo
  modelo que `on_ready`, §2.2.1).
- El primer tick ocurre `poll_interval_ms` después del registro: **no es
  inmediato**; el init del repositorio ya ha corrido en `on_ready`.
- **Error de poll:** se loguea y se continúa (retorna `SOURCE_CONTINUE`); un
  `on_poll` que lanza **no** destruye la fuente ni el worker.

### 12.4 Ciclo de vida de la fuente (ownership)

**Implementado** (ownership **lógico** por suscripción, `_SubscriptionState.poll_source`):

- La fuente se **retiene por suscripción lógica** (`subscription_id → GSource`),
  igual que los IDs GIO.
- **`unsubscribe(sub_id)`:** destruye la fuente **exactamente una vez**
  (`source.destroy()`) **antes** de liberar el callback lógico / IDs GIO / worker.
  Sin polling no hay fuente que destruir.
- **`close()` / rollback:** destruyen **todas** las fuentes retenidas; **nunca**
  se llama `connection.close()` (el bus es compartido, §2.5 / invariante 2).
- **Crear/set/attach falla** (§12.3): rollback completo — destruir la fuente recién
  creada, liberar el callback lógico y los IDs GIO ya registrados, worker limpio
  si era la última suscripción — y `BluetoothError` al llamador (**sin fuentes
  huérfanas**).
- `GSource.destroy` es **idempotente** y **thread-safe** según la doc oficial
  ([§12.10](#1210-fuentes-oficiales-verificadas)); aun así el `unsubscribe` se
  serializa al worker como hoy (§3) y el destroy corre **en el hilo del worker**.

### 12.5 Lado repositorio (`BlueZRepository`)

**Implementado en `bluez_repository.py`:**

- El **primer** subscribe de bajo nivel pasa `on_poll=self._handle_poll` y
  `poll_interval_ms`; el repositorio usa la constante
  **`POLL_INTERVAL_DEFAULT_MS = 5000`** (default) e **inyecta el intervalo en el
  constructor** (`BlueZRepository(client=None, poll_interval_ms=...)`, con
  **validación en el constructor**: `type(...) is int` exacto y `> 0` ⇒
  `ValueError` antes de usar el cliente) para que los tests no dependan del
  tiempo real.
- `_handle_poll` usa **exactamente el mismo pipeline** que `_handle_signal` ante
  un `SignalEvent`: ambos llaman al **mismo método interno
  `_refresh_and_dispatch`** (snapshot fresco completo → diff `cache → nuevo` →
  actualizar cache → dispatch en orden, fuera del lock). Señal y poll comparten
  **una sola implementación** (DRY), nunca dos caminos divergentes.
- El poll captura `Connected`/`Paired`/`Trusted` si `PropertiesChanged` se
  perdió: al ser un snapshot completo con diff, cualquier cambio observable de
  `DeviceInfo` (incluido `Connected`) produce los mismos eventos que la señal.
- **Un solo timer por repositorio:** los **suscriptores tardíos NO crean timers
  extra** — hay una única suscripción de bajo nivel y un único `GSource`; el poll
  hace fan-out a todos los suscriptores registrados (igual que una señal).
- **`unsubscribe` a cero callbacks:** hereda la serialización del worker (cero
  ticks tras el retorno) + la semántica `active`/in-flight del repositorio
  (§4.6). El **self-unsubscribe** desde un evento futuro (señal o poll) destruye
  la fuente de forma **reentrante** con seguridad (`destroy()` idempotente,
  serializado en el worker, sin esperar al propio hilo).
- `close()` del repositorio no aplica: el repositorio **nunca** cierra el cliente
  (invariante 2 / §4.7); la destrucción de la fuente es responsabilidad del bajo
  nivel (`unsubscribe`/`close`).

### 12.6 Criterios de aceptación

> **Estado (2026-08-10): todos los criterios verificados** por fakes deterministas
> (sin GI/bus) y la integración real opt-in de lifecycle create/destroy.

| # | Criterio | Verificación esperada |
|---|----------|----------------------|
| 1 | Compatibilidad de firma | `subscribe(cb)` y `subscribe(cb, on_ready=...)` siguen funcionando; el default sin polling es idéntico al comportamiento actual. |
| 2 | Validación del par `on_poll`/`poll_interval_ms` | `on_poll` exige `poll_interval_ms > 0` y `type(...) is int` exacto; ambos presentes o ambos `None`; combinación inválida → `ValueError` antes de tocar GIO. |
| 3 | Orden en el worker | filtros GIO → callback lógico → `on_ready` → `timeout_source_new`/`set_callback`/`attach` → retorno de `subscribe`. |
| 4 | Poll en el hilo del worker y serializado | fake `GSource` valida attach al contexto del worker + ticks manuales (sin sleep) en el hilo del worker. |
| 5 | Retorno `SOURCE_CONTINUE` | cada tick verificado contra la fuente fake; la fuente nunca se auto-cancela. |
| 6 | Error de poll aislado | `on_poll` lanza → log, se continúa, fuente viva, sin eventos corruptos ni destrucción. |
| 7 | Ownership de la fuente | `unsubscribe` destruye la fuente exactamente una vez antes de remover; `close`/rollback destruyen todas. |
| 8 | Fallo create/set/attach | rollback lógico/GIO completo + `BluetoothError`; cero fuentes huérfanas. |
| 9 | Sin polling | `on_poll=None` → ningún `GSource`; `attach` nunca se llama. |
| 10 | Un solo timer por repositorio | el primer suscriptor crea la única suscripción de bajo nivel; los tardíos no añaden fuentes. |
| 11 | Pipeline común | `_handle_poll` == `_handle_signal` (mismo `_refresh_and_dispatch`); captura `Connected`/`Paired`/`Trusted`. |
| 12 | Cero callbacks tras `unsubscribe` | serialización worker + `active`/in-flight del repositorio; self-unsubscribe reentrante seguro. |
| 13 | Nunca se cierra el bus | close/rollback destruyen fuentes pero `connection.close()` no se invoca. |
| 14 | Tests deterministas | fakes con tick manual (sin sleep); integración real solo lifecycle create/destroy con `poll_interval_ms=60_000` (sin tick real). |
| 15 | Calidad | `make lint && make typecheck && make test` en verde ([desarrollo y validación](../../README.md#desarrollo-y-validación)); los gates ordinarios y la integración opt-in pasaron al cierre del incremento. |

### 12.7 Pseudocódigo

> **Estado (2026-08-10):** los tres fragmentos corresponden al **código real
> implementado** en `dbus_protocol.py` (`_SignalWorker._subscribe`,
> `_unsubscribe`, `_stop_on_worker`, `_destroy_poll_source`) y en
> `bluez_repository.py` (`subscribe_device_changes`, `_handle_signal`,
> `_handle_poll`, `_refresh_and_dispatch`); el dict `_poll_sources` real es el
> campo `poll_source` de `_SubscriptionState` retenido por `subscription_id`.

**Worker — dentro de la operación de `subscribe`, tras `on_ready`:**

```python
if on_poll is not None:
    source = GLib.timeout_source_new(poll_interval_ms)  # monotonic
    def wrapper() -> int:
        try:
            on_poll()
        except Exception:
            log.exception("poll failed; continuing")
        return GLib.SOURCE_CONTINUE                      # nunca se auto-cancela
    source.set_callback(wrapper)
    gid = source.attach(self._ctx)                       # contexto dedicado del worker
    if gid == 0:
        # rollback: destruir source + callback lógico + IDs GIO -> BluetoothError
        raise BluetoothError("failed to attach poll source")
    self._poll_sources[subscription_id] = source
```

**`unsubscribe(sub_id)` (serializado al worker) y `close()`/rollback:**

```python
source = self._poll_sources.pop(subscription_id, None)
if source is not None:
    source.destroy()                                     # exactamente una vez; idempotente/thread-safe
# ... continúa la liberación actual (callback lógico, IDs GIO, worker si última)

# close() / rollback:
for source in self._poll_sources.values():
    source.destroy()
self._poll_sources.clear()
# NUNCA connection.close(): el bus es compartido (invariante 2)
```

**Repositorio — primer suscriptor (único subscribe de bajo nivel):**

```python
sub_id = self._client.subscribe(
    self._handle_signal,
    on_ready=lambda: self._finish_initialization(snapshot_a),
    on_poll=self._handle_poll,
    poll_interval_ms=self._poll_interval_ms,   # default POLL_INTERVAL_DEFAULT_MS = 5000; inyectable en __init__
)

def _handle_signal(self, event: SignalEvent) -> None:
    self._refresh_and_dispatch()               # MISMO pipeline que el poll (refactor común)

def _handle_poll(self) -> None:
    self._refresh_and_dispatch()               # snapshot completo + diff + cache + dispatch
```

### 12.8 Estrategia de pruebas

> **Estado (2026-08-10): implementado y en verde.** Los archivos listados ya
> existen y contienen los tests de polling.

| Nivel | Archivo | GI | Bus | Qué valida |
|-------|---------|----|-----|------------|
| Unit worker | `tests/unit/test_bluez_signal_worker.py` | No | No | fake `GSource`: creación tras `on_ready`, `set_callback` recibe el wrapper, `attach` al contexto del worker con id > 0, **ticks manuales disparados sin sleep**, retorno `SOURCE_CONTINUE` en cada tick, error de poll aislado y continuado, `destroy` exactamente una vez, destrucción en `close`/rollback, fallo create/set/attach → rollback lógico/GIO + `BluetoothError`, sin polling → sin `attach`, validación estricta del par (`ValueError`). |
| Unit protocolo | `tests/unit/test_bluez_signal_protocol.py` | No | No | firma compatible; validación del par `on_poll`/`poll_interval_ms` (`ValueError` antes de crear el worker); propagación exacta del intervalo al worker; no cierra el worker existente en inválido. |
| Unit repositorio | `tests/unit/test_bluez_repository_signals.py` | No | No | default 5000 ms en el primer subscribe; intervalo inyectado exacto; inválido rechazado antes de usar el cliente; un solo subscribe/timer por repositorio; tardíos sin timers extra; `_handle_poll` == `_handle_signal` (mismo `_refresh_and_dispatch`); captura de `Connected`/`Paired`/`Trusted` vía diff si se perdió la señal; cero eventos si el snapshot no cambió; cache preservada si el poll falla; self-unsubscribe/external-unsubscribe idénticos a señal; último unsubscribe cancela el poll y el nuevo ciclo crea fuente nueva. |
| Integración opt-in | `tests/integration/test_bluez_signal_lifecycle.py` | Sí | Sí | **solo lifecycle create/destroy** reales: subscribe con `on_poll`/`poll_interval_ms=60_000` → unsubscribe/close inmediatos; **no** se espera el intervalo y **no** se afirma ningún tick real; bus compartido usable con snapshot posterior. |

> **Nota determinismo:** los fakes **disparan el tick manualmente** contra la
> fuente fake — **nunca** `sleep`. La integración real **no espera el intervalo**
> ni afirma que el timer real haya disparado (evita acoplar los tests al tiempo).

### 12.9 Riesgos y límites

- **Redundancia, no reemplazo:** el polling no corrige una señal perdida *a
  tiempo*; solo la compensa en el siguiente tick. El primer poll tras una señal
  sin cambios emite cero eventos (diff vacío).
- **Coste por tick:** un `GetManagedObjects` completo por intervalo mientras
  haya suscriptores. 5000 ms es conservador y ajustable por inyección; intervalos
  cortos aumentan la carga del bus.
- **Validación empírica pendiente:** no se asume que el poll vea `Connected` real
  si BlueZ tampoco lo refleja en el snapshot; hoy no hay dispositivos conectados
  (0 objetos, [RESEARCH_LIMITS §4](../RESEARCH_LIMITS.md#4-fiabilidad-de-señales-d-bus)).
- **La fuente nunca se auto-destruye** (`SOURCE_CONTINUE`): la destrucción es
  exclusiva del lifecycle (`unsubscribe`/`close`/rollback).
- **Contrato del dominio intacto:** es infraestructura interna; no cambia
  `IBluetoothRepository` ni [ADR-0007](../ADR/0007-device-change-event-contract.md).
- **Etapa 3 (Qt):** el poll corre en el worker (GLib), nunca en Qt; se
  marshaleará igual que las señales (contrato de hilos, §5).

### 12.10 Fuentes oficiales verificadas

Verificadas el 2026-08-10 para este diseño (implementado el mismo día):

| Tema | URL |
|------|-----|
| `GLib.timeout_source_new` (intervalo ms; tiempo monotónico; rearmado con `SOURCE_CONTINUE`; **requiere `attach`**) | https://docs.gtk.org/glib/func.timeout_source_new.html |
| `GSource.attach` (adjunta a un `GMainContext`; devuelve id > 0) | https://docs.gtk.org/glib/method.Source.attach.html |
| `GSource.destroy` (idempotente, thread-safe) | https://docs.gtk.org/glib/method.Source.destroy.html |
| `GSource.set_callback` | https://docs.gtk.org/glib/method.Source.set_callback.html |
| `G_SOURCE_CONTINUE` (mantener la fuente activa) | https://docs.gtk.org/glib/const.SOURCE_CONTINUE.html |
