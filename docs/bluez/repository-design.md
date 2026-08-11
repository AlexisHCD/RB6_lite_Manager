# Diseño técnico — Repositorio BlueZ (consultas snapshot + suscripción de cambios)

Diseño de `openbuds.infrastructure.bluez.bluez_repository` (`BlueZRepository`,
implementación de `IBluetoothRepository`): las **consultas snapshot**
(`list_*`/`get_*`) toman un snapshot fresco de BlueZ vía el cliente D-Bus
inyectable con `snapshot()`, y **`subscribe_device_changes`** entrega
`DeviceChangeEvent` con cache de diff sobre el **diff puro de snapshots**
(`device_change_diff.py`), sin cache persistente, sin lifecycle propio de
escritura y sin mutación.

- **Tipo:** diseño de implementación (Documentation First; **implementado y
  verificado**)
- **Estado del roadmap:** el contrato completo (consultas snapshot +
  `subscribe_device_changes`) está **implementado y verificado** como parte del
  backend base de BlueZ publicado; se consumirá en la Etapa 2. La validación
  física del dispositivo es de la Etapa 1 (ver [§6](#6-subscribe_device_changes--implementado-incremento-2)).
- **Documentos relacionados:** [Interfaces D-Bus de BlueZ](dbus-interfaces.md),
  [Diseño del cliente GDBus](gio-dbus-client-design.md),
  [Contrato del mapper](object-mapper-contract.md), [ADR-0001](../ADR/0001-decision-dbus-pygobject-gio.md),
  [ADR-0004](../ADR/0004-clean-architecture-dependency-rule.md),
  [ADR-0007](../ADR/0007-device-change-event-contract.md),
  [RESEARCH_LIMITS](../RESEARCH_LIMITS.md)
- **Dependencias del dominio:** `IBluetoothRepository`
  (`domain/interfaces/bluetooth_repo.py`), modelos (`AdapterInfo`,
  `DeviceInfo`, `BatteryLevel`, `RSSIReading`, `DeviceChangeEvent`),
  `BluetoothError` (`core/errors.py`).

> ⚠️ **Regla de oro (AGENTS.md §5):** este diseño no asume comportamiento de
> BlueZ no verificado. El árbol de objetos y las interfaces se toman tal como
> los entrega `GetManagedObjects`; la disponibilidad de `Battery1` es opcional
> ([RESEARCH_LIMITS §3](../RESEARCH_LIMITS.md#3-disponibilidad-de-batería)).

> **Estado de implementación (2026-08-10):** este incremento está
> **implementado y verificado**. Las consultas snapshot de `BlueZRepository`
> (`list_adapters` / `list_devices` / `get_device` / `get_battery` /
> `get_rssi`) usan un **cliente estructural inyectable** (`SnapshotClient`,
> Protocol) y un **snapshot fresco por llamada**, sin cache, sin lifecycle y
> sin mutación. **`subscribe_device_changes` está implementado** con el
> **diff puro de snapshots** (`device_change_diff.py`): init A→B en el worker
> vía `on_ready`, cache de diff, refresh completo por señal, orden determinista
> `REMOVED→ADDED→UPDATED`, aislamiento de callbacks, suscriptores
> múltiples/tardíos/reentrantes, `Unsubscribe` idempotente con espera de
> in-flight y rollback de errores (ver [§6](#6-subscribe_device_changes--implementado-incremento-2)).
> El TDD (§7) está **completado**: los unit tests de `bluez_repository.py`
> (`tests/unit/test_bluez_repository.py`), del diff puro
> (`tests/unit/test_device_change_diff.py`) y del dispatch
> (`tests/unit/test_bluez_repository_signals.py`) corren **sin GI ni bus del
> sistema**, y los tests de integración opt-in
> (`tests/integration/test_bluez_repository.py`, `tests/integration/test_bluez_repository_signals.py`,
> `OPENBUDS_RUN_INTEGRATION=1`) pasaron en **Python 3.12 / Gio** sobre BlueZ
> real (solo lectura; el de señales solo **lifecycle A/B**, sin señales
> inducidas ni escrituras). Los gates ordinarios y la integración opt-in
> pasaron al cierre del incremento (2026-08-10); Ruff y mypy en verde. El
> backend base de BlueZ queda publicado; se consumirá en la Etapa 2, con
> validación física pendiente en la Etapa 1 (ver
> [§6](#6-subscribe_device_changes--implementado-incremento-2)).
>
> **Alcance de lo "completo":** el contrato **`IBluetoothRepository`** (consultas
> snapshot + `subscribe_device_changes`) está **completo**. La **resiliencia por
> polling** recomendada en [RESEARCH_LIMITS §4](../RESEARCH_LIMITS.md#4-fiabilidad-de-señales-d-bus)
> está **implementada y verificada (2026-08-10)** como extensión **interna
> compatible** (no cambia `IBluetoothRepository`; [ROADMAP](../ROADMAP.md)
> marcado `[x]`). El diseño (Documentation First) está en
> [§12](#12-polling-de-respaldo-del-repositorio-implementado-y-verificado-2026-08-10)
> y en [signal-lifecycle-design §12](signal-lifecycle-design.md#12-polling-de-respaldo-implementado-y-verificado-2026-08-10).
> Hoy no hay auriculares conectados ni nodos Bluetooth (`pw-dump` con 0 objetos)
> para validar el flujo real contra hardware.

---

## 1. Contexto y alcance

`BlueZRepository` es la implementación de infraestructura del contrato de solo
lectura `IBluetoothRepository`. Este diseño implementa las **consultas
puntuales** a partir del snapshot ya disponible:

- `list_adapters()` / `list_devices(adapter_path=None)` / `get_device(path)` /
  `get_battery(path)` / `get_rssi(path)`.
- **`subscribe_device_changes(callback) -> Unsubscribe`** (Incremento 2,
  [§6](#6-subscribe_device_changes--implementado-incremento-2)).
- **Queda fuera:** cache persistente, cualquier lifecycle propio de escritura
  y cualquier método mutador de BlueZ.

El repositorio **orquesta**: pide snapshot al cliente, selecciona los objetos
de la interfaz relevante, los mapea con `object_mapper.py` (puro, sin GI),
difflos con `device_change_diff.py` (puro, sin GI) y aplica las reglas de
orden/filtro/None de este diseño. No toca GI ni D-Bus directamente.

---

## 2. Inyección del cliente snapshot (cliente estructural/protocolo)

`BlueZRepository` recibe un cliente **estructural** (Protocol) que solo expone
`snapshot()`, lo que permite testear sin GI y sin bus del sistema (patrón de
[gio-dbus-client-design §2.7](gio-dbus-client-design.md#27-inyección-de-backendprotocol-para-pruebas-sin-gi)).

```python
class SnapshotClient(Protocol):
    def snapshot(self) -> ManagedObjects: ...

class BlueZRepository(IBluetoothRepository):
    def __init__(self, client: SnapshotClient | None = None) -> None:
        self._client = client if client is not None else BlueZDBusClient()
```

- `ManagedObjects = dict[str, dict[str, dict[str, object]]]` (`dbus_protocol.py`).
- `BlueZDBusClient` (`dbus_client.py`) ya satisface el Protocol estructuralmente
  (`snapshot()` delega en `GioDBusProtocol` / proveedor inyectado).
- En producción el default construye `BlueZDBusClient()` (GI real); en tests se
  inyecta un `FakeSnapshotClient` con snapshots guionados.
- **El Protocol vive en `bluez_repository.py`** (contrato interno de
  infraestructura, no del dominio). Para el **Incremento 2** este Protocol se
  amplió con `subscribe(callback, on_ready=None, on_poll=None,
  poll_interval_ms=None)` / `unsubscribe(subscription_id)`
  (stream bajo nivel de `SignalEvent`; `on_poll`/`poll_interval_ms` son la
  extensión interna del polling de respaldo, §12), sin alterar las consultas
  snapshot; ver
  [signal-lifecycle-design §4](signal-lifecycle-design.md#4-repositorio-registro-cache-y-dispatch).

---

## 3. Contrato de métodos (resumen)

| Método | Snapshot fresco | Selección en el árbol | Mapeo | Orden / None |
|--------|-----------------|-----------------------|-------|--------------|
| `list_adapters()` | sí | solo objetos con `org.bluez.Adapter1` | `map_adapter(path, props)` | ordenado por `object_path` |
| `list_devices(adapter_path=None)` | sí | solo objetos con `org.bluez.Device1`; si `adapter_path`, filtro **exacto** `device.adapter_path == adapter_path` | `map_device(path, props)` | ordenado por `object_path` |
| `get_device(device_path)` | sí | objeto con `Device1` en `device_path` exacto | `map_device(path, props)` | `None` si ausente/sin `Device1` |
| `get_battery(device_path)` | sí | `Battery1` en `device_path`; si no, hijos con prefijo `device_path + "/"` en orden determinista | `map_battery(props)` | `None` si no existe ningún `Battery1` |
| `get_rssi(device_path)` | sí | `Device1` en `device_path` exacto | `map_rssi(props)` | `None` si no hay `Device1` ni hay `RSSI`/`TxPower` |
| `subscribe_device_changes(cb)` | — | — | — | `-> Unsubscribe` (§6) |

Todas las consultas **propagan `BluetoothError`** tal cual (snapshot o mapper),
sin envolverlas de nuevo ni tragarlas (§5.2).

---

## 4. Semántica de cada consulta

### 4.1 `list_adapters() -> list[AdapterInfo]`

1. `snapshot = self._client.snapshot()` (fresco).
2. Para cada `(object_path, interfaces)` con `org.bluez.Adapter1` en
   `interfaces` → `map_adapter(object_path, interfaces[IFACE_ADAPTER1])`.
3. Solo se mapean objetos con `Adapter1` (los `Device1`/`Battery1`/`Media*`
   del snapshot se ignoran aquí).
4. Resultado ordenado por `object_path` (orden lexicográfico de `str`,
   determinista).

### 4.2 `list_devices(adapter_path: str | None = None) -> list[DeviceInfo]`

1. `snapshot` fresco.
2. Solo objetos con `org.bluez.Device1` → `map_device(object_path, props)`.
3. Si `adapter_path` es `None` → todos los adaptadores. Si no → filtro
   **exacto** `device.adapter_path == adapter_path` (equivalencia de la
   propiedad `Adapter`; rutas que solo comparten prefijo, p. ej. `/org/bluez/hci01`
   vs `/org/bluez/hci0`, se excluyen).
4. Resultado ordenado por `object_path`.

### 4.3 `get_device(device_path: str) -> DeviceInfo | None`

1. `snapshot` fresco.
2. Si `device_path` no está en el snapshot o su objeto no tiene `Device1` →
   `None`.
3. Si no → `map_device(device_path, props)`.

### 4.4 `get_battery(device_path: str) -> BatteryLevel | None`

1. `snapshot` fresco.
2. **Primero** el objeto en `device_path` exacto: si tiene
   `org.bluez.Battery1` → `map_battery(props)`.
3. **Después** los hijos: objetos cuyo `object_path` empieza por
   `device_path + "/"`, recorridos en **orden determinista** (orden
   lexicográfico de `object_path`); el primer hijo con `Battery1` gana.
4. Si nada de lo anterior existe → `None`.

> No se asume dónde coloca BlueZ el `Battery1` (misma ruta o subobjeto): la
> búsqueda cubre ambos casos sin presuponer la topología.

### 4.5 `get_rssi(device_path: str) -> RSSIReading | None`

1. `snapshot` fresco.
2. Si `device_path` no tiene `org.bluez.Device1` → `None`.
3. Si el objeto tiene `Device1` pero **ni** `RSSI` **ni** `TxPower` en sus
   propiedades → `None` (no se llama a `map_rssi`).
4. Si hay al menos `RSSI` o `TxPower` → `map_rssi(props)` (con
   `timestamp=datetime.now(UTC)` por defecto, conservado de `object_mapper.py`).

---

## 5. Principios transversales

### 5.1 Snapshot fresco por llamada, sin cache

- Cada `list_*`/`get_*` llama a `self._client.snapshot()`: **un snapshot por
  llamada**, siempre el estado actual del bus.
- **No existe cache a nivel de repositorio** (ni se decide, ni se especula):
  el `GDBusProxy` de GIO mantiene su propio cache interno de propiedades por
  mecanismo de GIO, pero el repositorio no lo explota ni lo emula, y **no hay**
  cache de snapshots entre llamadas.
- Consecuencia de test: dos llamadas consecutivas ven dos snapshots
  independientes; el fake cliente cuenta llamadas y no se reutiliza estado.

### 5.2 Los `BluetoothError` se propagan

- `BluetoothError` procedente de `snapshot()` (bus no disponible, firma
  inválida — `dbus_protocol.py`) y de los mappers (propiedad requerida ausente,
  tipo erróneo, invariante — `object_mapper.py`) **se propaga tal cual** a la
  capa de aplicación: no se captura para devolver `None` ni se re-envuelve en
  otra excepción. El `__cause__` original se conserva.
- Los fallos esperados del límite BlueZ/mapeo pertenecen a la jerarquía
  `OpenBudsError`. El repositorio no captura `Exception` de forma genérica:
  un error de programación inesperado permanece visible y no se disfraza como
  indisponibilidad Bluetooth.

### 5.3 No mutación

- El repositorio es **solo lectura por construcción**: la única interacción con
  el bus es `snapshot()` (`GetManagedObjects`), y la única salida son modelos
  inmutables del dominio. No existe ningún método que invoque un miembro
  mutador de BlueZ (`Adapter1.Powered`, `Device1.Connect`, `Battery1.*`, etc.).
- Regla de revisión: cualquier llamada mutadora en este incremento es **fuera
  de alcance** y debe rechazarse ([filosofía AGENTS.md §3]).

### 5.4 No mutación de señales ni escritura

- Las consultas snapshot son **independientes** de la cache de señales
  (snapshot fresco por llamada, [§5.1](#51-snapshot-fresco-por-llamada-sin-cache)).
- La suscripción (`subscribe_device_changes`) es **recepción pura**: solo
  `GetManagedObjects` (snapshots A/B/C) y las tres señales estándar
  (`InterfacesAdded`/`InterfacesRemoved`/`PropertiesChanged`); **nunca** emite
  señales, no invoca métodos mutadores y **no cierra** el cliente ni la
  conexión D-Bus compartida.

---

## 6. `subscribe_device_changes` → implementado (Incremento 2)

`subscribe_device_changes(callback) -> Unsubscribe` está **implementado y
verificado** en `bluez_repository.py`. Se apoya en el **nivel bajo de señales**
del Incremento 2 (`GioDBusProtocol` + `_SignalWorker`: worker dedicado, tres
filtros exactos, `SignalEvent`, lifecycle `subscribe`/`unsubscribe`/`close`
idempotente y hook `on_ready`
([gio-dbus-client-design §4 — Incremento 2](gio-dbus-client-design.md#incremento-2--señales-y-lifecycle),
[signal-lifecycle-design §2/§3](signal-lifecycle-design.md#2-capa-baja-señales-en-giodbusprotocol))
y en el **diff puro de snapshots** (`device_change_diff.py`). El contrato
técnico completo (código real, invariantes y tests) está en
[signal-lifecycle-design §4](signal-lifecycle-design.md#4-repositorio-registro-cache-y-dispatch).

**Por eso el backend base de BlueZ se considera completo:** el contrato
`IBluetoothRepository` se cumple en su totalidad (consultas snapshot +
suscripción con dispatch) y queda **publicado; se consumirá en la Etapa 2**;
la validación física del dispositivo queda para la Etapa 1. La **resiliencia por polling**
de [RESEARCH_LIMITS §4](../RESEARCH_LIMITS.md#4-fiabilidad-de-señales-d-bus) es
**externa al contrato** y está **implementada y verificada** (extensión interna,
sin cambiar la interfaz; [§12](#12-polling-de-respaldo-del-repositorio-implementado-y-verificado-2026-08-10)
y [ROADMAP](../ROADMAP.md)).

### 6.1 Implementación del dispatch (`subscribe_device_changes`)

> **Estado (2026-08-10):** **implementado y verificado.** La API `on_ready` es
> **infraestructura interna** y **no modifica el contrato del dominio**
> ([ADR-0007](../ADR/0007-device-change-event-contract.md)).

La contradicción del diseño original (snapshot B + diff + primer dispatch en el
hilo del llamador, vs callbacks de usuario entregados **en el hilo del worker**
apenas el worker registra filtros y callback) se resuelve moviendo el init del
repositorio al hook `on_ready` del bajo nivel
([signal-lifecycle-design §2.2.1](signal-lifecycle-design.md#221-on_ready-hook-de-init-en-el-worker)),
que corre **en el worker, antes de que `subscribe` retorne**. Las señales que
lleguen durante el init se serializan en el mismo `MainContext` y se procesan
después: **B cierra la carrera**. Código real (estructura de sincronización:
una `threading.Condition` sobre `RLock`; `_subscribers` es un `dict[int,
_Subscriber]`) y reentrancia en
[signal-lifecycle-design §4.6/§4.7](signal-lifecycle-design.md#46-api-on_ready-del-primer-registro);
aquí se documenta la parte específica del repositorio.

**Reglas del repositorio (implementadas y verificadas):**

1. **Primer suscriptor** inicia el pipeline: snapshot A (bajo lock) →
   `subscribe(cb, on_ready=init)` → en `on_ready` (worker): snapshot B, diff
   A→B (solo cambios entre A y B, sin replay de preexistente), actualizar
   cache, primer dispatch (fuera del lock).
2. **Segundo suscriptor concurrente** espera al init y se registra **sin
   replay** (solo futuros). Si el init falló, recibe el mismo `BluetoothError`.
3. **Suscriptor reentrante** (desde un callback, en el worker): se registra
   **sin replay y sin esperarse a sí mismo** (sin deadlock).
4. **Suscriptor tardío** (post-init): solo eventos futuros, nunca replay
   (un único `subscribe` bajo nivel con fan-out en orden de registro).
5. **`on_ready` falla:** rollback bajo nivel (callback lógico + IDs GIO, worker
   limpio si última) + **estado parcial revocado** (`_abort_initialization`:
   cache/suscriptores del init) + `BluetoothError` propagado; **cero eventos**.
6. **Cero llamadas de usuario bajo lock:** el dispatch (init y refresh) corre
   siempre fuera del lock; el lock solo protege cache, estado de init y lista
   de suscriptores.
7. **Reentrancia de `Unsubscribe`:** **self-unsubscribe solo es posible tras
   poseer el `Unsubscribe`** (desde un callback de señal posterior): `active=false`
   (no recibe ni el resto de la entrega en curso ni eventos futuros) y, si es el
   último, se libera el `subscribe` bajo nivel y la cache. **Durante A→B no
   aplica** (el callable aún no existe; lo válido ahí es `subscribe` reentrante
   sin replay). El unsubscribe **externo** espera callbacks in-flight del
   suscriptor (**salvo self**) ⇒ **cero callbacks tras el retorno**; idempotente.
8. **Refresh fallido (señal):** cache previa intacta y **cero eventos** en esa
   entrega; la siguiente señal diffs contra la cache preservada.
9. **El repositorio nunca cierra el cliente:** no llama `close()` y no cierra
   la conexión D-Bus compartida.
10. **Orden determinista:** `REMOVED→ADDED→UPDATED`, dentro de cada grupo por
    `object_path` lexicográfico; `UPDATED` solo si el `DeviceInfo` mapeado es
    desigual; cambios solo de `Battery1`/`RSSI`/`TxPower`/props no mapeadas no
    emiten evento.

### 6.2 Esquema de la implementación (código real en `bluez_repository.py`)

```python
def subscribe_device_changes(self, callback: DeviceChangeCallback) -> Unsubscribe:
    current_thread_id = threading.get_ident()
    with self._condition:
        while self._initializing and self._initializing_thread_id != current_thread_id:
            self._condition.wait()                       # segundo concurrente espera init
        subscriber_id = self._add_subscriber(callback)   # registro inmediato
        if self._low_subscription_id is not None:        # ya suscrito: solo futuros
            return self._make_unsubscribe(subscriber_id)
        if self._initializing:                           # reentrante desde callback
            self._initializing_subscriber_ids.add(subscriber_id)
            return self._make_unsubscribe(subscriber_id)
        self._initializing = True                        # primer suscriptor inicia el pipeline
        self._initializing_thread_id = current_thread_id
        self._initializing_subscriber_ids = {subscriber_id}

    try:
        snapshot_a = self._client.snapshot()             # A: antes de instalar filtros
        low_subscription_id = self._client.subscribe(
            self._handle_signal,
            on_ready=lambda: self._finish_initialization(snapshot_a),  # worker, antes del retorno
            on_poll=self._handle_poll,                   # polling de respaldo (§12)
            poll_interval_ms=self._poll_interval_ms,
        )
    except Exception:
        self._abort_initialization()                     # revoca cache/init y notifica
        raise
    with self._condition:
        self._low_subscription_id = low_subscription_id  # sub_id ya disponible
        self._initializing = False
        self._initializing_thread_id = None
        self._initializing_subscriber_ids.clear()
        self._condition.notify_all()
        should_unsubscribe = not self._subscribers       # todos se dieron de baja durante A→B
        if should_unsubscribe:
            self._low_subscription_id = None
            self._cache = None
    if should_unsubscribe:
        self._client.unsubscribe(low_subscription_id)    # sin suscriptores: libera el bajo nivel
    return self._make_unsubscribe(subscriber_id)

def _finish_initialization(self, snapshot_a: ManagedObjects) -> None:
    with self._condition:
        if not self._initializing:
            return
        self._initializing_thread_id = threading.get_ident()
    snapshot_b = self._client.snapshot()                 # B: post-filtros (cierra carrera)
    events = diff_device_snapshots(snapshot_a, snapshot_b)
    with self._condition:
        self._cache = snapshot_b
        recipients = tuple(self._subscribers.values())
    self._dispatch(events, recipients)                   # fuera del lock, en el worker
```

`_finish_initialization` es el `on_ready`; corre **en el hilo del worker**,
dentro de la operación de `subscribe` serializada por el `MainContext`. El
`Unsubscribe` se construye por suscriptor (`_make_unsubscribe` → `_unsubscribe`:
`active=false`, espera de in-flight salvo self, liberación del bajo nivel si es
el último). `_handle_signal` refresca un **snapshot completo por señal** y diffs
la cache contra él (sin mapeo de payloads parciales); `_dispatch` entrega en
orden de registro, fuera del lock, con aislamiento de excepciones.

### 6.3 Casos de prueba concretos (implementados, fakes deterministas sin GI/bus)

> Archivos reales: `tests/unit/test_bluez_repository_signals.py` (dispatch) y
> `tests/unit/test_device_change_diff.py` (diff puro). Todos **implementados y
> en verde**.

| # | Caso | Verificación esperada (real) |
|---|------|------------------------------|
| 1 | Primer registro: init completo | A antes del `subscribe` bajo nivel; `on_ready` en el hilo worker y **antes** del retorno; diff A→B; cache a B; snapshots iguales → cero eventos. |
| 2 | Señal durante el init | No se entrega hasta que `on_ready` termina (cache ya en B). |
| 3 | Diff A→B | Solo cambios entre A y B; preexistente en A sin eventos. |
| 4 | `on_ready` falla (snapshot B) | Rollback bajo nivel + estado revocado + `BluetoothError`; cero eventos; retry como primer suscriptor. |
| 5 | `subscribe` bajo nivel falla | Estado limpio + `BluetoothError`; retry funciona. |
| 6 | Snapshot A falla | No se suscribe a bajo nivel; retry funciona. |
| 7 | Segundo concurrente (init ok / init fallido) | Espera al init; sin replay; solo futuros; si falló recibe el mismo error. |
| 8 | Reentrante desde callback | Sin replay y sin deadlock (probado también con `on_ready_in_worker_thread`). |
| 9 | Self-unsubscribe desde callback de señal | `active=false`; sin deadlock; ni eventos futuros ni del resto de la entrega; al ser último libera el bajo nivel. *(Durante A→B no aplica.)* |
| 10 | Unsubscribe externo con in-flight | Retorna solo al terminar el callback en curso; cero callbacks posteriores; idempotente. |
| 11 | Unsubscribe externo sin in-flight + nuevo ciclo | Retorno inmediato; idempotente; nuevo ciclo con `sub_id` y cache nuevos. |
| 12 | Reentrancia `subscribe`/`unsubscribe` desde callback | Sin deadlock del lock del repo. |
| 13 | Refresh fallido (señal) | Cache previa intacta, cero eventos; siguiente señal diffs contra la cache preservada. |
| 14 | Doble registro del mismo callback | Dos suscripciones independientes, entrega en orden de registro; baja de una no afecta a la otra. |
| — | Orden determinista / UPDATED condicional | `REMOVED→ADDED→UPDATED` por `object_path`; `UPDATED` solo si `DeviceInfo` desigual. |
| — | Sin eventos Battery/RSSI-only | Cambios solo en `Battery1`/`RSSI`/`TxPower`/props no mapeadas → cero eventos. |
| — | El repositorio nunca cierra el cliente | `client.close_calls == 0`. |

---

## 7. Criterios TDD (completados)

Archivo de tests: **`tests/unit/test_bluez_repository.py`** (patrón de
`tests/unit/test_bluez_dbus_protocol.py`). **Todos corren sin GI y sin bus**:
`FakeSnapshotClient` guionado, sin `gi`, sin bus del sistema. Todos los casos
de la tabla están **implementados y en verde** (algunos casos parametrizados
se agrupan en una misma función de test, manteniendo la cobertura de cada
fila).

> Regla transversal probada en cada método: **snapshot fresco por llamada**
> (el fake cuenta llamadas; cada consulta incrementa el contador y dos
> consultas seguidas no comparten estado) y **`BluetoothError` se propaga** con
> su `__cause__` intacto.

| # | Método | Caso | Resultado esperado |
|---|--------|------|--------------------|
| 1 | `list_adapters` | snapshot con un `Adapter1` | `[AdapterInfo]` con campos mapeados |
| 2 | `list_adapters` | snapshot con adapter + device + battery | solo los `Adapter1`, sin colaterales |
| 3 | `list_adapters` | dos adaptadores (`hci0`, `hci1`) | ordenados por `object_path` |
| 4 | `list_adapters` | snapshot vacío | `[]` |
| 5 | `list_adapters` | `Adapter1.Address` ausente | `BluetoothError` propagado |
| 6 | `list_devices` | varios `Device1` + otros objetos | solo `Device1`, ordenados |
| 7 | `list_devices` | `adapter_path=None` | todos los adaptadores |
| 8 | `list_devices` | `adapter_path="/org/bluez/hci0"` | solo dispositivos con `adapter_path` **exacto** |
| 9 | `list_devices` | `adapter_path="/org/bluez/hci0"` y ruta `/org/bluez/hci01/...` | `hci01` se excluye (no prefijo) |
| 10 | `list_devices` | filtro sin coincidencias | `[]` |
| 11 | `list_devices` | `Device1.Adapter` ausente | `BluetoothError` propagado |
| 12 | `get_device` | `device_path` exacto con `Device1` | `DeviceInfo` mapeado |
| 13 | `get_device` | `device_path` presente sin `Device1` | `None` |
| 14 | `get_device` | `device_path` ausente | `None` |
| 15 | `get_battery` | `Battery1` en la misma `device_path` | `BatteryLevel` mapeado |
| 16 | `get_battery` | `Battery1` solo en un hijo `device_path + "/battery0"` | se encuentra por hijos |
| 17 | `get_battery` | varios hijos con `Battery1` | gana el primero en orden determinista |
| 18 | `get_battery` | sin `Battery1` en ninguna parte | `None` |
| 19 | `get_battery` | `Percentage` fuera de rango (101) | `BluetoothError` propagado |
| 20 | `get_rssi` | `Device1` con `RSSI` | `RSSIReading` con `rssi_dbm`, timestamp tz-aware UTC |
| 21 | `get_rssi` | `Device1` con solo `TxPower` | `rssi_dbm None`, `tx_power_dbm` seteado |
| 22 | `get_rssi` | `Device1` presente, ni `RSSI` ni `TxPower` | `None` |
| 23 | `get_rssi` | ruta presente sin `Device1` | `None` |
| 24 | `get_rssi` | ruta ausente | `None` |
| 25 | `get_rssi` | `RSSI` positivo (10) | `BluetoothError` propagado |
| 26 | `subscribe_device_changes` | sin suscriptores previos (primer registro) | init A→B en `on_ready` (worker), sin replay de preexistente; `Unsubscribe` retornado (Incremento 2; cubierto a fondo en `tests/unit/test_bluez_repository_signals.py`) |
| 27 | transversal | `client.snapshot()` lanza `BluetoothError` | se propaga idéntico (misma instancia, `__cause__` intacto) en todas las consultas |
| 28 | transversal | dos consultas seguidas | dos snapshots: el fake cuenta `snapshot()` por consulta (sin cache) |

---

## 8. Integración real (solo lectura) — verificada

**Consultas snapshot.** Test opt-in en **`tests/integration/test_bluez_repository.py`**
(patrón de `tests/integration/test_bluez_dbus_protocol.py`): marcado
`@pytest.mark.integration`, desactivado salvo `OPENBUDS_RUN_INTEGRATION=1`.
**Verificado en Python 3.12 / Gio sobre BlueZ real** (Ubuntu, PyGObject):
consulta de adaptadores y dispositivos reales, batería/RSSI sin excepciones y
sin invocar ningún método mutador.

Procedimiento verificado:

1. `repo = BlueZRepository()` (default → `BlueZDBusClient()` → `GioDBusProtocol`
   real).
2. `adapters = repo.list_adapters()`: no vacío, ordenado, `address` no vacío.
3. `devices = repo.list_devices()`: por cada uno, `address` y `adapter_path` no
   vacíos; `repo.list_devices(adapter_path)` devuelve solo los del adaptador
   dado.
4. `repo.get_device(d.object_path)` para cada `d` real → `DeviceInfo` coherente.
5. `repo.get_battery(d.object_path)` / `repo.get_rssi(d.object_path)` sobre
   dispositivos reales: **sin excepción**; batería `None` o en `[0, 100]`; RSSI
   `None` o `RSSIReading`.
6. **Privacidad:** no se loguea ni se aserta la MAC del dispositivo.
7. La lectura **no auto-arranca** `bluetoothd` (flags `DO_NOT_AUTO_START` /
   `NO_AUTO_START`, [gio-dbus-client-design §2.1/§2.2](gio-dbus-client-design.md#21-giodbusproxynew_for_bus_sync-sobre-el-bus-del-sistema))
   y **no invoca ningún método mutador**.

**Lifecycle A/B del repositorio.** Test opt-in en
**`tests/integration/test_bluez_repository_signals.py`** (Python 3.12 / Gio):
`repo.subscribe_device_changes(events.append)` real → los eventos del diff A→B
cumplen las **invariantes del dominio** (validación sin exponer MAC) →
`unsubscribe()` **idempotente** (dos llamadas) → `repo.list_devices()` sigue
usable. El bus compartido permanece usable. **No** se inducen señales, **no**
se afirma recepción real de eventos y **no** hay escrituras de hardware.

---

## 9. Ubicación en el árbol y enlace con el diseño del cliente

Coherente con [gio-dbus-client-design §5](gio-dbus-client-design.md#5-dependencia-y-ubicación-en-el-árbol):

```
src/openbuds/infrastructure/bluez/
├── dbus_protocol.py      # GioDBusProtocol (única importación de gi)   [Inc 1 + Inc 2 bajo nivel]
├── object_mapper.py      # dicts nativos → modelos (puro)              [implementado]
├── device_change_diff.py # diff puro de snapshots Device1 → eventos    [implementado]
├── dbus_client.py        # BlueZDBusClient (snapshot + señales)        [Inc 1 + Inc 2 bajo nivel]
└── bluez_repository.py   # IBluetoothRepository completo               [implementado: consultas + subscribe_device_changes]
```

- `BlueZRepository` **no importa GI** y **no importa `dbus_protocol`** para
  nada más que el tipo `ManagedObjects`: delega el snapshot y las señales en el
  cliente inyectado, el mapeo en `object_mapper.py` y el diff en
  `device_change_diff.py`.
- Cumple [ADR-0004](../ADR/0004-clean-architecture-dependency-rule.md):
  implementa el contrato del dominio (`IBluetoothRepository`) y no exporta
  lógica de negocio.

---

## 10. Fuentes oficiales e internas

Internas:
- `domain/interfaces/bluetooth_repo.py` (contrato), `object_mapper.py` +
  [object-mapper-contract.md](object-mapper-contract.md),
  `device_change_diff.py` + [signal-lifecycle-design.md](signal-lifecycle-design.md) §4,
  `dbus_client.py` + [gio-dbus-client-design.md](gio-dbus-client-design.md),
  `dbus_protocol.py`, [dbus-interfaces.md](dbus-interfaces.md),
  [ADR-0007](../ADR/0007-device-change-event-contract.md),
  [RESEARCH_LIMITS §3](../RESEARCH_LIMITS.md#3-disponibilidad-de-batería) (batería
  opcional) y [§4](../RESEARCH_LIMITS.md#4-fiabilidad-de-señales-d-bus)
  (señal primaria y **polling de respaldo implementados** —
  [§12](#12-polling-de-respaldo-del-repositorio-implementado-y-verificado-2026-08-10)
  y [signal-lifecycle-design §12](signal-lifecycle-design.md#12-polling-de-respaldo-implementado-y-verificado-2026-08-10)),
  [ROADMAP](../ROADMAP.md).

Oficiales (verificadas en [gio-dbus-client-design §8](gio-dbus-client-design.md#8-fuentes-oficiales-verificadas)
y [object-mapper-contract §11](object-mapper-contract.md#11-fuentes-oficiales-verificadas)):

| Tema | URL |
|------|-----|
| D-Bus spec — `org.freedesktop.DBus.ObjectManager` (`GetManagedObjects`, `a{oa{sa{sv}}}`) | https://dbus.freedesktop.org/doc/dbus-specification.html |
| BlueZ Device API (`Device1` props) | https://bluez.readthedocs.io/en/latest/device-api/ |
| BlueZ Adapter API (`Adapter1` props) | https://bluez.readthedocs.io/en/latest/adapter-api/ |
| BlueZ Battery API (`Battery1`) | https://bluez.readthedocs.io/en/latest/battery-api/ |

---

## 11. Resumen de decisiones (registro del arquitecto)

1. **Cliente estructural inyectable con `snapshot()`** (Protocol
   `SnapshotClient`), ampliado en el Incremento 2 con `subscribe(callback,
   on_ready=None, on_poll=None, poll_interval_ms=None)` /
   `unsubscribe(subscription_id)`; default `BlueZDBusClient()`;
   tests con fake, sin GI/bus.
2. **Snapshot fresco por llamada, sin cache** a nivel de consultas; la única
   cache es la de señales del dispatch (`subscribe_device_changes`).
3. `list_adapters`/`list_devices` mapean **solo** su interfaz y ordenan por
   `object_path`; filtro de adaptador **exacto**.
4. `get_device`/`get_rssi` por **ruta exacta**; `get_battery` primera en la
   misma ruta, luego hijos con prefijo en **orden determinista**; `None` si no
   hay.
5. `get_rssi`: `None` si no hay `Device1` o si faltan `RSSI` **y** `TxPower`.
6. `BluetoothError` (snapshot y mapper) **se propaga** sin re-envolver.
7. **No mutación**: la única interacción con el bus es `GetManagedObjects` +
   las tres señales estándar; el repositorio **nunca cierra** el cliente ni la
   conexión.
8. `subscribe_device_changes` **implementado** (Incremento 2): init A→B en el
   worker vía `on_ready`, diff puro de snapshots, orden determinista, cache de
   señales, `Unsubscribe` idempotente con espera de in-flight y rollback de
   errores; el backend base de BlueZ queda publicado; se consumirá en la Etapa 2,
   con validación física pendiente en la Etapa 1.
9. **Reentrancia:** `subscribe` reentrante durante A→B sin replay ni deadlock;
   **self-unsubscribe solo tras poseer el `Unsubscribe`** (en señales futuras);
   unsubscribe externo espera in-flight (salvo self).
10. **Diff puro** (`device_change_diff.py`): `REMOVED→ADDED→UPDATED` por
    `object_path`; `UPDATED` solo si el `DeviceInfo` mapeado es desigual; sin
    eventos Battery/RSSI-only; errores del mapper sin eventos parciales.
11. **Polling de respaldo** ([§12](#12-polling-de-respaldo-del-repositorio-implementado-y-verificado-2026-08-10)):
    **implementado y verificado (2026-08-10).** Extensión interna
    compatible hacia atrás de `subscribe` (`on_poll`/`poll_interval_ms`, default
    `POLL_INTERVAL_DEFAULT_MS = 5000` inyectable y validado en el constructor);
    **un solo timer por
    repositorio** (primer suscriptor); `_handle_poll` comparte el **mismo
    pipeline** snapshot/diff/cache/dispatch que `_handle_signal` (`_refresh_and_dispatch`);
    **no cambia** `IBluetoothRepository` ni el contrato del dominio.

---

## 12. Polling de respaldo del repositorio (implementado y verificado 2026-08-10)

> **Estado:** **implementado y verificado (2026-08-10).** Documentación First
> aprobada del respaldo por polling del repositorio, ahora **código real** en
> `bluez_repository.py` (`subscribe_device_changes` pasa `on_poll`/
> `poll_interval_ms`; `_handle_poll` → `_refresh_and_dispatch`). El detalle de
> bajo nivel (timer en el worker, ownership de la fuente, acceptance, pruebas y
> fuentes) está en
> [signal-lifecycle-design §12](signal-lifecycle-design.md#12-polling-de-respaldo-implementado-y-verificado-2026-08-10);
> aquí se documenta **la parte específica del repositorio**.

### 12.1 Reglas del repositorio (implementadas)

1. **Un solo timer por repositorio.** Solo el **primer** subscribe de bajo nivel
   pasa `on_poll=self._handle_poll` y `poll_interval_ms`; los **suscriptores
   tardíos NO crean timers extra** (una única suscripción de bajo nivel y un
   único `GSource` por repositorio; el poll hace fan-out a todos los suscriptores
   registrados, igual que una señal).
2. **Intervalo inyectable y validado.** Constante `POLL_INTERVAL_DEFAULT_MS = 5000`
   (default) e **inyección en el constructor** `BlueZRepository(client=None,
   poll_interval_ms=...)`, con **validación estricta** (`type(...) is int` exacto
   y `> 0` ⇒ `ValueError` antes de usar el cliente) para que los tests disparen
   ticks sin depender del tiempo real.
3. **Pipeline común (DRY).** `_handle_poll` usa **exactamente el mismo pipeline**
   que `_handle_signal` ante un `SignalEvent`: snapshot fresco completo → diff
   `cache → nuevo` → actualizar cache → dispatch en orden, fuera del lock. Se
   **refactoriza el código común** en un único método interno
   (`_refresh_and_dispatch`); señal y poll **nunca** tienen dos caminos
   divergentes.
4. **Captura de `Connected`/`Paired`/`Trusted`.** Si `PropertiesChanged` no
   llegó, el poll detecta cualquier cambio observable de `DeviceInfo` (incluido
   `Connected`) y emite los mismos `DeviceChangeEvent` que la señal
   ([ADR-0007](../ADR/0007-device-change-event-contract.md)). Un poll sin cambios
   emite **cero eventos** (diff vacío).
5. **`unsubscribe` a cero callbacks.** Hereda la serialización del worker (cero
   ticks tras el retorno) y la semántica `active`/in-flight del repositorio
   (§4.6): el **self-unsubscribe** desde un evento futuro (señal o poll) destruye
   la fuente de forma **reentrante** con seguridad (`destroy()` idempotente,
   serializado al worker, sin esperar al propio hilo).
6. **Sin cierre de cliente.** El repositorio **nunca** llama `close()` (regla 9
   de §6.1); la destrucción de la fuente es responsabilidad del bajo nivel
   (`unsubscribe`/`close`).
7. **Contrato del dominio intacto.** Es infraestructura interna; **no cambia**
   `IBluetoothRepository`, `DeviceChangeCallback` ni `Unsubscribe`.

### 12.2 Código real (equivalente al diseño aprobado)

```python
# __init__: intervalo inyectable y validado (type int exacto > 0)
def __init__(self, client: SnapshotClient | None = None,
             poll_interval_ms: int = POLL_INTERVAL_DEFAULT_MS) -> None:
    if type(poll_interval_ms) is not int or poll_interval_ms <= 0:
        raise ValueError("poll_interval_ms debe ser un entero positivo")
    self._client = client if client is not None else BlueZDBusClient()
    self._poll_interval_ms = poll_interval_ms

# primer suscriptor: único subscribe de bajo nivel, con polling
sub_id = self._client.subscribe(
    self._handle_signal,
    on_ready=lambda: self._finish_initialization(snapshot_a),
    on_poll=self._handle_poll,
    poll_interval_ms=self._poll_interval_ms,
)

def _handle_signal(self, event: SignalEvent) -> None:
    self._refresh_and_dispatch()      # MISMO pipeline que el poll (refactor común)

def _handle_poll(self) -> None:
    self._refresh_and_dispatch()      # snapshot completo + diff + cache + dispatch
```

### 12.3 Casos de prueba implementados (fakes deterministas sin GI/bus)

| # | Caso | Verificación esperada (real) |
|---|------|------------------------------|
| 1 | Primer suscriptor con polling | `on_poll=self._handle_poll` y `poll_interval_ms` pasados al bajo nivel (verificado en el fake cliente). |
| 2 | Un solo timer | el segundo/tardíos suscriptores no vuelven a llamar `subscribe` ni crean fuentes; fan-out del poll a todos. |
| 3 | Poll == señal | `_handle_poll` dispara el mismo snapshot/diff/cache/dispatch que `_handle_signal` (assert del pipeline compartido). |
| 4 | Poll sin cambios | snapshot idéntico → **cero eventos** (diff vacío). |
| 5 | Poll captura `Connected`/`Paired`/`Trusted` | si la señal se perdió, un cambio de `Connected`/`Paired`/`Trusted` entre cache y poll genera `UPDATED`. |
| 6 | Intervalo inyectable y default | `poll_interval_ms` del constructor (p. ej. `1234`) llega exacto al fake cliente; default `5000`; inválido (`0`, `-1`, `"1234"`, `True`) → `ValueError` antes de usar el cliente. |
| 7 | `unsubscribe` a cero callbacks | tras el retorno del `Unsubscribe`, los ticks del poll no entregan callbacks (serialización + `active`/in-flight). |
| 8 | Self-unsubscribe reentrante | desde un callback de señal/poll: destruye la fuente con seguridad, sin deadlock ni eventos futuros. |
| 9 | El repo nunca cierra el cliente | `client.close_calls == 0` incluso con polling activo. |
| 10 | Poll falla (snapshot/mapper) | cache preservada, cero eventos en esa entrega; el siguiente poll diffs contra la cache preservada. |
| 11 | Último unsubscribe cancela el poll | fuente destruida y nuevo ciclo crea un `subscribe` y cache nuevos. |
| 12 | Integración real (opt-in) | **solo lifecycle create/destroy**: subscribe con polling → unsubscribe/close reales; **no** se espera 5 s ni se afirma ningún tick real. |

### 12.4 Riesgos y límites

- Coste de un `GetManagedObjects` completo por tick mientras haya suscriptores;
  5000 ms por defecto es conservador y ajustable.
- **Validación empírica pendiente (hardware):** hoy 0 dispositivos conectados; no
  se asume que el poll vea `Connected` real si BlueZ tampoco lo refleja en el
  snapshot.
- Es redundancia de la señal, no sustituto: el primer poll tras una señal sin
  cambios emite cero eventos.
- Detalle de riesgo bajo nivel (fuente nunca se auto-destruye, rollback de
  create/set/attach) en [signal-lifecycle-design §12.9](signal-lifecycle-design.md#129-riesgos-y-límites).
