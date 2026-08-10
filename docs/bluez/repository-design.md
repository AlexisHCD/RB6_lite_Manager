# Diseño técnico — Repositorio BlueZ (incremento de consultas snapshot)

Diseño del incremento de **consultas snapshot** de
`openbuds.infrastructure.bluez.bluez_repository` (`BlueZRepository`,
implementación de `IBluetoothRepository`): cada `list_*`/`get_*` toma un
snapshot fresco de BlueZ vía el cliente D-Bus inyectable con `snapshot()`, sin
cache, sin lifecycle y sin escritura.

- **Fase:** 3 (Bluetooth)
- **Tipo:** diseño de implementación (Documentation First; **implementado y
  verificado**)
- **Estado del checkbox roadmap:** el ítem global *"Implementación de
  `IBluetoothRepository`"* ([ROADMAP §Fase 3](../ROADMAP.md)) **NO se marca
  completo** en este incremento: `subscribe_device_changes` queda
  `NotImplementedError` hasta el Incremento 2 de señales (ver [§6](#6-subscribe_device_changes--notimplemented-incremento-2)).
- **Documentos relacionados:** [Interfaces D-Bus de BlueZ](dbus-interfaces.md),
  [Diseño del cliente GDBus](gio-dbus-client-design.md),
  [Contrato del mapper](object-mapper-contract.md), [ADR-0001](../ADR/0001-decision-dbus-pygobject-gio.md),
  [ADR-0004](../ADR/0004-clean-architecture-dependency-rule.md),
  [RESEARCH_LIMITS](../RESEARCH_LIMITS.md)
- **Dependencias del dominio:** `IBluetoothRepository`
  (`domain/interfaces/bluetooth_repo.py`), modelos (`AdapterInfo`,
  `DeviceInfo`, `BatteryLevel`, `RSSIReading`), `BluetoothError`
  (`core/errors.py`).

> ⚠️ **Regla de oro (AGENTS.md §5):** este diseño no asume comportamiento de
> BlueZ no verificado. El árbol de objetos y las interfaces se toman tal como
> los entrega `GetManagedObjects`; la disponibilidad de `Battery1` es opcional
> ([RESEARCH_LIMITS §3](../RESEARCH_LIMITS.md#3)) y las señales se difieren al
> Incremento 2.

> **Estado de implementación (2026-08-09):** este incremento está
> **implementado y verificado**. Las consultas snapshot de `BlueZRepository`
> (`list_adapters` / `list_devices` / `get_device` / `get_battery` /
> `get_rssi`) usan un **cliente estructural inyectable** (`SnapshotClient`,
> Protocol) y un **snapshot fresco por llamada**, sin cache, sin lifecycle y
> sin mutación. El TDD (§7) está **completado**: los unit tests de
> `bluez_repository.py` corren **sin GI ni bus del sistema**, y el test de
> integración opt-in (`tests/integration/test_bluez_repository.py`,
> `OPENBUDS_RUN_INTEGRATION=1`) pasó en **Python 3.12 / Gio** sobre BlueZ real
> (solo lectura). Suite total: **177 passed, 3 skipped** (las 3 omisiones son
> las integraciones opt-in, desactivadas por defecto).
> `subscribe_device_changes` **sigue lanzando `NotImplementedError`** hasta el
> Incremento 2, por lo que el checkbox global del roadmap **permanece `[ ]`**
> (ver §6).

---

## 1. Contexto y alcance

`BlueZRepository` es la implementación de infraestructura del contrato de solo
lectura `IBluetoothRepository`. Este incremento implementa las **consultas
puntuales** a partir del snapshot ya disponible:

- `list_adapters()` / `list_devices(adapter_path=None)` / `get_device(path)` /
  `get_battery(path)` / `get_rssi(path)`.
- **Queda fuera:** `subscribe_device_changes` (Incremento 2 de señales),
  cualquier cache persistente, cualquier lifecycle (`open`/`close`/`subscribe`)
  y cualquier método mutador de BlueZ.

El repositorio **orquesta**: pide snapshot al cliente, selecciona los objetos
de la interfaz relevante, los mapea con `object_mapper.py` (puro, sin GI) y
aplica las reglas de orden/filtro/None de este diseño. No toca GI ni D-Bus
directamente.

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
  infraestructura, no del dominio).

---

## 3. Contrato de métodos (resumen)

| Método | Snapshot fresco | Selección en el árbol | Mapeo | Orden / None |
|--------|-----------------|-----------------------|-------|--------------|
| `list_adapters()` | sí | solo objetos con `org.bluez.Adapter1` | `map_adapter(path, props)` | ordenado por `object_path` |
| `list_devices(adapter_path=None)` | sí | solo objetos con `org.bluez.Device1`; si `adapter_path`, filtro **exacto** `device.adapter_path == adapter_path` | `map_device(path, props)` | ordenado por `object_path` |
| `get_device(device_path)` | sí | objeto con `Device1` en `device_path` exacto | `map_device(path, props)` | `None` si ausente/sin `Device1` |
| `get_battery(device_path)` | sí | `Battery1` en `device_path`; si no, hijos con prefijo `device_path + "/"` en orden determinista | `map_battery(props)` | `None` si no existe ningún `Battery1` |
| `get_rssi(device_path)` | sí | `Device1` en `device_path` exacto | `map_rssi(props)` | `None` si no hay `Device1` ni hay `RSSI`/`TxPower` |
| `subscribe_device_changes(cb)` | — | — | — | `NotImplementedError` (§6) |

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

### 5.4 Sin lifecycle en este incremento

- No hay `open`/`close`/`subscribe`/`unsubscribe` en `BlueZRepository`. El
  ciclo de vida de señales y suscripciones es responsabilidad exclusiva del
  **Incremento 2** (ver [gio-dbus-client-design §2.4/§2.5](gio-dbus-client-design.md#24-señales-con-giodbusconnectionsignal_subscribe)).
- No se inventa aquí ningún estado incremental ni cache de señales.

---

## 6. `subscribe_device_changes` → NotImplemented (Incremento 2)

`subscribe_device_changes(callback)` **sigue lanzando `NotImplementedError`**:
las señales (`InterfacesAdded`/`InterfacesRemoved`/`PropertiesChanged`) y el
lifecycle del cliente D-Bus son del Incremento 2
([gio-dbus-client-design §4 — Incremento 2](gio-dbus-client-design.md#incremento-2--señales-y-lifecycle)).

**Por eso el checkbox global del roadmap no se marca completo:**
[ROADMAP §Fase 3](../ROADMAP.md) — *"Implementación de `IBluetoothRepository`"* —
**permanece `[ ]`** tras este incremento. El contrato `IBluetoothRepository`
solo se cumplirá en su totalidad cuando existan señales; este incremento
documenta y prueba explícitamente que la suscripción aún no está disponible.

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
| 26 | `subscribe_device_changes` | cualquier llamada | `NotImplementedError` (Incremento 2) |
| 27 | transversal | `client.snapshot()` lanza `BluetoothError` | se propaga idéntico (misma instancia, `__cause__` intacto) en todas las consultas |
| 28 | transversal | dos consultas seguidas | dos snapshots: el fake cuenta `snapshot()` por consulta (sin cache) |

---

## 8. Integración real (solo lectura) — verificada

Test opt-in en **`tests/integration/test_bluez_repository.py`** (patrón de
`tests/integration/test_bluez_dbus_protocol.py`): marcado
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

---

## 9. Ubicación en el árbol y enlace con el diseño del cliente

Coherente con [gio-dbus-client-design §5](gio-dbus-client-design.md#5-dependencia-y-ubicación-en-el-árbol):

```
src/openbuds/infrastructure/bluez/
├── dbus_protocol.py      # GioDBusProtocol (única importación de gi)   [Inc 1]
├── object_mapper.py      # dicts nativos → modelos (puro)              [implementado]
├── dbus_client.py        # BlueZDBusClient.snapshot()                  [Inc 1]
└── bluez_repository.py   # IBluetoothRepository sobre BlueZDBusClient  [implementado: consultas snapshot]
```

- `BlueZRepository` **no importa GI** y **no importa `dbus_protocol`** para
  nada más que el tipo `ManagedObjects`: delega el snapshot en el cliente
  inyectado y el mapeo en `object_mapper.py`.
- Cumple [ADR-0004](../ADR/0004-clean-architecture-dependency-rule.md):
  implementa el contrato del dominio (`IBluetoothRepository`) y no exporta
  lógica de negocio.

---

## 10. Fuentes oficiales e internas

Internas:
- `domain/interfaces/bluetooth_repo.py` (contrato), `object_mapper.py` +
  [object-mapper-contract.md](object-mapper-contract.md),
  `dbus_client.py` + [gio-dbus-client-design.md](gio-dbus-client-design.md),
  `dbus_protocol.py`, [dbus-interfaces.md](dbus-interfaces.md),
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
   `SnapshotClient`), default `BlueZDBusClient()`; tests con fake, sin GI/bus.
2. **Snapshot fresco por llamada, sin cache** a nivel de repositorio; sin
   lifecycle en este incremento.
3. `list_adapters`/`list_devices` mapean **solo** su interfaz y ordenan por
   `object_path`; filtro de adaptador **exacto**.
4. `get_device`/`get_rssi` por **ruta exacta**; `get_battery` primera en la
   misma ruta, luego hijos con prefijo en **orden determinista**; `None` si no
   hay.
5. `get_rssi`: `None` si no hay `Device1` o si faltan `RSSI` **y** `TxPower`.
6. `BluetoothError` (snapshot y mapper) **se propaga** sin re-envolver.
7. **No mutación**: única interacción con el bus es `GetManagedObjects`.
8. `subscribe_device_changes` **sigue `NotImplementedError`** hasta el
   Incremento 2; el checkbox global del roadmap **no se marca completo**.
