# Diseño técnico — Repositorio BlueZ (consultas snapshot + suscripción de cambios)

Diseño de `openbuds.infrastructure.bluez.bluez_repository` (`BlueZRepository`,
implementación de `IBluetoothRepository`): las **consultas snapshot**
(`list_*`/`get_*`) toman un snapshot fresco de BlueZ vía el cliente D-Bus
inyectable con `snapshot()`, y **`subscribe_device_changes`** entrega
`DeviceChangeEvent` con cache de diff sobre el **diff puro de snapshots**
(`device_change_diff.py`), sin cache persistente, sin lifecycle propio de
escritura y sin mutación.

- **Fase:** 3 (Bluetooth)
- **Tipo:** diseño de implementación (Documentation First; **implementado y
  verificado**)
- **Estado del checkbox roadmap:** el ítem global *"Implementación de
  `IBluetoothRepository`"* ([ROADMAP §Fase 3](../ROADMAP.md)) está **marcado
  `[x]`**: el contrato completo (consultas snapshot + `subscribe_device_changes`)
  está implementado y verificado (ver [§6](#6-subscribe_device_changes--implementado-incremento-2)).
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
> ([RESEARCH_LIMITS §3](../RESEARCH_LIMITS.md#3)).

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
> inducidas ni escrituras). Suite total por defecto (Python 3.14): **276
> passed, 6 skipped**; con `OPENBUDS_RUN_INTEGRATION=1` en Python 3.12 / Gio:
> **282 passed**. Ruff y mypy en verde. El checkbox global del roadmap queda
> **`[x]`** (ver [§6](#6-subscribe_device_changes--implementado-incremento-2)).

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
  amplió con `subscribe(callback, on_ready=None)` / `unsubscribe(subscription_id)`
  (stream bajo nivel de `SignalEvent`), sin alterar las consultas snapshot; ver
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

**Por eso el checkbox global del roadmap se marca completo:**
[ROADMAP §Fase 3](../ROADMAP.md) — *"Implementación de `IBluetoothRepository`"* —
queda **`[x]`**: el contrato `IBluetoothRepository` se cumple en su totalidad
(consultas snapshot + suscripción con dispatch).

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
  [RESEARCH_LIMITS §3](../RESEARCH_LIMITS.md#3) (batería opcional) y §4
  (señales/polling → Incremento 2), [ROADMAP](../ROADMAP.md) §Fase 3.

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
   on_ready=None)` / `unsubscribe(subscription_id)`; default `BlueZDBusClient()`;
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
   errores; el checkbox global del roadmap queda **`[x]`**.
9. **Reentrancia:** `subscribe` reentrante durante A→B sin replay ni deadlock;
   **self-unsubscribe solo tras poseer el `Unsubscribe`** (en señales futuras);
   unsubscribe externo espera in-flight (salvo self).
10. **Diff puro** (`device_change_diff.py`): `REMOVED→ADDED→UPDATED` por
    `object_path`; `UPDATED` solo si el `DeviceInfo` mapeado es desigual; sin
    eventos Battery/RSSI-only; errores del mapper sin eventos parciales.
