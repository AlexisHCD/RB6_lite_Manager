# Contrato técnico — `object_mapper.py`

> **Estado:** **implementado y verificado** (2026-08-09). Este contrato se
> redactó con metodología **Documentation First** antes de escribir el código;
> la implementación de `object_mapper.py` cumple lo aquí especificado y se
> conserva como **documentación viva** (referencia normativa del módulo).
>
> Verificación:
>
> - Mapper **puro sin GI** (`map_adapter`, `map_device`, `map_battery`,
>   `map_rssi` → `AdapterInfo`/`DeviceInfo`/`BatteryLevel`/`RSSIReading`),
>   con validación estricta y defaults conservadores; sus unit tests corren sin
>   `python3-gi` y sin bus del sistema.
> - Test de integración opt-in (`OPENBUDS_RUN_INTEGRATION=1`) verificado en
>   **Python 3.12 / Gio** sobre un snapshot real de BlueZ (`GetManagedObjects`),
>   sin métodos mutadores ni exposición de la MAC.
> - Los gates ordinarios y la integración opt-in pasaron al cierre del
>   incremento (2026-08-10).

- **Ítem del roadmap:** separado del roadmap (ver §5 de
  [gio-dbus-client-design.md](gio-dbus-client-design.md))
- **Tipo:** contrato de implementación (no es un ADR)
- **Fecha del contrato:** 2026-08-09
- **Documentos relacionados:** [Interfaces D-Bus de BlueZ](dbus-interfaces.md),
  [Diseño del cliente GDBus](gio-dbus-client-design.md),
  [RESEARCH_LIMITS](../RESEARCH_LIMITS.md)
- **Dependencias del dominio:** `BluetoothError` (`core/errors.py`), modelos
  (`AdapterInfo`, `DeviceInfo`, `BatteryLevel`, `RSSIReading`) y enums
  (`AddressType`, `DeviceIcon`, `ConnectionState`).

> ⚠️ **Evidencia y no inferencia:** toda propiedad y tipo descritos aquí
> provienen de la documentación oficial de BlueZ, verificada el 2026-08-09
> (ver [Fuentes](#11-fuentes-oficiales-verificadas)). Ante cualquier
> discrepancia con el comportamiento real, se detiene la implementación y se
> documenta.

---

## 1. Objetivo

Traducir los **dicts nativos de propiedades D-Bus** de BlueZ (tal como los
produce el unpack de `GioDBusProtocol` — [gio-dbus-client-design §2.3](gio-dbus-client-design.md#23-unpack-de-gvariant--tipos-python))
en **dataclasses inmutables del dominio**. Es la frontera entre el mundo D-Bus
(arbitrario, heterogéneo) y el dominio (tipos puros y estables).

Este contrato se redactó con metodología **Documentation First**: se acordó
antes de escribir el código, de forma que la implementación pudiera verificarse
contra esta referencia sin ambigüedades. Tras su implementación y verificación
se conserva como documentación viva del módulo.

---

## 2. Delimitación: mapper puro, sin GI

- `object_mapper.py` es un módulo de **funciones puras**: entrada `dict` →
  salida modelo del dominio. **Sin efectos secundarios, sin I/O, sin bus, sin
  red.**
- **No importa `gi`** (ni PyGObject, ni Gio, ni GLib). El único módulo del
  paquete que toca GI es `dbus_protocol.py`
  ([gio-dbus-client-design §2.7](gio-dbus-client-design.md#27-inyección-de-backendprotocol-para-pruebas-sin-gi)).
- Consecuencia: **todos los unit tests del mapper corren sin `python3-gi` y sin
  bus del sistema.**
- El mapper **nunca** se aplica directamente a payloads parciales de
  `PropertiesChanged`. Siempre recibe **propiedades completas de una interfaz**,
  ya sea de un snapshot completo (`GetManagedObjects`) o de un **cache
  actualizado** por el repositorio. En el Incremento 2 el repositorio no
  fusiona payloads parciales: ante cada `SignalEvent` refresca un **snapshot
  completo** y diffs el cache contra él con el **diff puro de snapshots**
  (`device_change_diff.py`), de modo que el mapper solo recibe propiedades
  completas de interfaz ([signal-lifecycle-design §4](signal-lifecycle-design.md#4-repositorio-registro-cache-y-dispatch)).
- Consecuencia: la política de opcionales con default explícito (ver §4) es
  obligatoria y no una concesión, **no** porque el mapper tolere payloads
  parciales, sino porque BlueZ omite propiedades **opcionales** incluso en
  snapshots completos.

---

## 3. Firmas públicas

```python
from collections.abc import Mapping
from datetime import datetime

def map_adapter(object_path: str, props: Mapping[str, object]) -> AdapterInfo: ...
def map_device(object_path: str, props: Mapping[str, object]) -> DeviceInfo: ...
def map_battery(props: Mapping[str, object]) -> BatteryLevel: ...
def map_rssi(props: Mapping[str, object], *, timestamp: datetime | None = None) -> RSSIReading: ...
```

Notas de firma:

- **Entrada:** `Mapping[str, object]` (no `dict`). Acepta cualquier mapping de
  solo lectura; las propiedades siempre se acceden por nombre de clave.
- `object_path` **no** se lee de `props`: lo aporta el caller (clave del
  snapshot) porque es la identidad del objeto, no una propiedad de la interfaz.
- `map_battery` y `map_rssi` **no** reciben `object_path` (sus modelos no lo
  contienen).
- `map_rssi` es una función del contrato, implementada junto a `map_adapter`,
  `map_device` y `map_battery` en este ítem.
- `timestamp` es **inyectable** (keyword-only). Si es `None`, el mapper usa
  `datetime.now(UTC)` (tz-aware). Si se proporciona, en runtime debe ser un
  `datetime` **tz-aware con offset UTC (0)**: tipo erróneo, `datetime` naive o
  zona horaria distinta de UTC → `BluetoothError` (ver §4, regla 11). Un
  `datetime` inyectado que cumple UTC se **conserva exactamente** tal cual se
  recibió (sin normalización ni conversión).

---

## 4. Política de validación (reglas de oro)

Toda decisión de mapeo obedece estas reglas, en este orden:

1. **Propiedad requerida ausente** → `BluetoothError`.
2. **Propiedad requerida presente con tipo erróneo** → `BluetoothError`.
3. **Propiedad opcional ausente** → **default explícito** (tabla de §5).
   Nunca se inventa un valor de BlueZ que no llegó.
4. **Propiedad opcional presente con tipo erróneo** → `BluetoothError`
   (nunca se sustituye silenciosamente por el default).
5. **`bool` estricto:** los campos boolean exigen `type(v) is bool`. Un `int`
   (`0`/`1`) es un error. `bool` es subclase de `int` en Python: usar
   `isinstance(v, int)` aceptaría `True`; por eso se exige tipo exacto.
6. **`int` no acepta `bool`:** los campos enteros exigen
   `isinstance(v, int) and not isinstance(v, bool)`. D-Bus `b` (boolean) y
   `y`/`n` (byte/int16) son tipos distintos; tras el unpack son `bool` vs
   `int`. Aceptar `bool` como `int` mezclaría tipos y enmascararía fuentes
   corruptas.
7. **Enums:** valor ausente → `UNKNOWN`; valor `str` desconocido → `UNKNOWN`
   (sin error); valor presente no-`str` → `BluetoothError`.
8. **UUIDs:** ausente → `tuple()`; presente → secuencia completa de `str`
   (ver §6).
9. **Propiedades no mapeadas se ignoran** (p. ej. `Class`, `Appearance`,
   `Modalias`, `LegacyPairing`, `ManufacturerData` en Device1; `Class`, `Roles`,
   `Modalias` en Adapter1). Su presencia **nunca** produce error.
10. **Errores de invariante de los modelos** (`ValueError` de
    `__post_init__` en `BatteryLevel`/`RSSIReading`) se encadenan como
    `BluetoothError` con `from exc` (§7).
11. **`timestamp` de `map_rssi`:** si es `None` → `datetime.now(UTC)`
    (tz-aware). Si se proporciona debe ser `datetime` tz-aware con offset UTC
    (0): tipo erróneo, `naive` o zona no UTC → `BluetoothError`. El valor
    conforme se **conserva exactamente** (el mapper no re-ejecuta `now()` ni
    normaliza).

---

## 5. Tablas propiedad → campo

### 5.1 `Adapter1` → `AdapterInfo`

| Propiedad BlueZ | Tipo D-Bus | Campo dominio | Oficial (doc BlueZ) | Contrato | Default |
|-----------------|------------|---------------|----------------------|----------|---------|
| `Address` | string | `address` | siempre presente | **requerida** | — |
| `Name` | string | `name` | siempre presente | opcional | `""` |
| `Alias` | string | `alias` | siempre presente | opcional | `""` |
| `Powered` | boolean | `powered` | siempre presente | opcional | `False` |
| `Discoverable` | boolean | `discoverable` | siempre presente | opcional | `False` |
| `Pairable` | boolean | `pairable` | siempre presente | opcional | `False` |
| `Discovering` | boolean | `discovering` | siempre presente | opcional | `False` |
| `AddressType` | string | `address_type` | siempre presente | opcional | `AddressType.UNKNOWN` |

Solo `Address` es requerida: es la clave de identidad. Los booleanos se tratan
como opcionales con default `False`. Ese default es el **default conservador de
OpenBuds ante ausencia**, no necesariamente el default real de BlueZ ni una
afirmación del estado del dispositivo: una propiedad ausente puede no haber
llegado o no aplicarse, y el código no asume capacidades ni estados no
observados; las propiedades ausentes no se infieren.

### 5.2 `Device1` → `DeviceInfo`

| Propiedad BlueZ | Tipo D-Bus | Campo dominio | Oficial (doc BlueZ) | Contrato | Default |
|-----------------|------------|---------------|----------------------|----------|---------|
| `Address` | string | `address` | siempre presente | **requerida** | — |
| `Adapter` | object path | `adapter_path` | siempre presente | **requerida** | — |
| `Name` | string | `name` | **optional** | opcional | `""` |
| `Alias` | string | `alias` | siempre presente | opcional | `""` |
| `Icon` | string | `icon` | **optional** | opcional | `DeviceIcon.UNKNOWN` |
| `AddressType` | string | `address_type` | siempre presente | opcional | `AddressType.UNKNOWN` |
| `Paired` | boolean | `paired` | siempre presente | opcional | `False` |
| `Connected` | boolean | `connected` | siempre presente | opcional | `False` |
| (derivado) | — | `connection_state` | — | derivado de `connected` | `DISCONNECTED` |
| `Trusted` | boolean | `trusted` | siempre presente | opcional | `False` |
| `Blocked` | boolean | `blocked` | siempre presente | opcional | `False` |
| `ServicesResolved` | boolean | `services_resolved` | siempre presente | opcional | `False` |
| `UUIDs` | array{string} | `uuids` | **optional** | opcional | `()` |

`RSSI` y `TxPower` de `Device1` **no** se mapean aquí: pertenecen a `map_rssi`
(§5.4). Su presencia en `props` de `map_device` se ignora (regla 9).

### 5.3 `Battery1` → `BatteryLevel`

| Propiedad BlueZ | Tipo D-Bus | Campo dominio | Oficial | Contrato | Default |
|-----------------|------------|---------------|---------|----------|---------|
| `Percentage` | byte | `percentage` | única propiedad (readthedocs) | opcional | `None` |
| `Source` | string | `source` | kernel.org (`battery-api.txt`) | opcional | `""` |

`Percentage` es opcional con default `None` porque `Battery1` **no es
universal** ([RESEARCH_LIMITS §3](../RESEARCH_LIMITS.md#3-disponibilidad-de-batería)): el código debe
degradar con elegancia. Si está presente debe ser `int` (no `bool`) y estar en
`[0, 100]`.

### 5.4 `Device1.RSSI` / `Device1.TxPower` → `RSSIReading`

| Propiedad BlueZ | Tipo D-Bus | Campo dominio | Oficial | Contrato | Default |
|-----------------|------------|---------------|---------|----------|---------|
| `RSSI` | int16 | `rssi_dbm` | **optional** | opcional | `None` |
| `TxPower` | int16 | `tx_power_dbm` | **optional** | opcional | `None` |
| — (inyectado) | — | `timestamp` | — | inyectable | `datetime.now(UTC)` |

`timestamp` es la única entrada inyectada (no proviene de BlueZ). Política de
validación en §4 (regla 11) y nota de firma en §3.

---

## 6. Reglas específicas de mapeo

### 6.1 `Connected` → `ConnectionState`

`connection_state` se **deriva siempre** de `connected`:

- `connected is True` → `ConnectionState.CONNECTED`
- `connected is False` → `ConnectionState.DISCONNECTED`

`UNKNOWN` no se usa en este campo por parte del mapper (el modelo lo conserva
como default para construcciones manuales, pero el mapper siempre lo fija).

Cuando `connected` está ausente y cae al default `False`, el
`connection_state` resultante (`DISCONNECTED`) es el **derivado del default
conservador de OpenBuds**, no una afirmación del estado real del dispositivo.

### 6.2 UUIDs

- Ausente → `()`.
- Presente → debe ser una **secuencia completa de `str`**: contenedor de tipo
  `list`/`tuple` **no-`str`** (una cadena es en sí una secuencia de caracteres y
  pasaría un check ingenuo `isinstance(v, Sequence)`, así que `str`/`bytes` se
  rechazan explícitamente como contenedor) y **todos** sus elementos `str`. Si
  falta un elemento `str` → `BluetoothError`. Se convierte a `tuple[str, ...]`.
- Coherente con el unpack de BlueZ (`as` → `list[str]`,
  [gio-dbus-client-design §2.3](gio-dbus-client-design.md#23-unpack-de-gvariant--tipos-python)).

### 6.3 Enums desconocidos

`AddressType` y `DeviceIcon` se resuelven por nombre exacto del `StrEnum`.
Valor desconocido → `UNKNOWN` (política de tolerancia: BlueZ puede introducir
iconos nuevos; un icono desconocido no debe romper el mapeo).

### 6.4 No se mapea códec vendor

Este commit **no añade ningún mapeo de códec** (no existe `map_codec`, no se toca
`MediaTransport1`). Los bytes vendor (aptX/LDAC) **no están canonizados** y
nunca se asumen ([RESEARCH_LIMITS §1](../RESEARCH_LIMITS.md#1-bytes-de-códec-a2dp-vendor-specific)); incluso SBC/AAC
quedan fuera de este contrato (futuro ítem de la Etapa 1 vía
`MediaTransport1.Codec` + PipeWire).

---

## 7. Manejo de errores

- Todos los errores de validación y de invariante se reportan como
  `BluetoothError` (jerarquía en `core/errors.py`). **Nunca** escapan
  `ValueError`, `TypeError` ni excepciones de librerías a las capas de
  aplicación/presentación.
- **Convención de mensaje:** `"{Interfaz}.{Propiedad}: {motivo}"`, p. ej.:
  - Ausente requerida: `"Device1.Address: propiedad requerida ausente"`
  - Tipo erróneo: `"Device1.Name: se esperaba str, recibido int"`
  - Invariante: `"Battery1.Percentage fuera de rango [0, 100]: 101"`
- **Cadena de excepciones:** cuando el `__post_init__` del modelo lanza
  `ValueError` (rango de batería, signo de RSSI), el mapper lo envuelve con
  `raise BluetoothError(...) from exc` para conservar la causa original.
- Las propiedades no mapeadas **nunca** generan error (regla 9, §4).

---

## 8. Fuera de alcance (explícitamente excluido de este ítem)

- Mapeo de códecs / `MediaTransport1` / `MediaPlayer1` / `MediaControl1`
  (deprecated).
- Mapeo de propiedades no incluidas en el modelo (`Class`, `Appearance`,
  `Modalias`, `ManufacturerData`, `ServiceData`, `LegacyPairing`,
  `WakeAllowed`, `Roles`, `PairableTimeout`, `DiscoverableTimeout`, etc.).
- Resolución de perfiles de dispositivo, PipeWire/WirePlumber, `btmon`.
- Cualquier método mutador o escritura a BlueZ/dispositivo está fuera de alcance;
  el mapper es lectura pura por construcción (ver [privacidad y seguridad](../../README.md#privacidad-y-seguridad)).

---

## 9. Criterios TDD

Archivo de tests: **`tests/unit/test_object_mapper.py`** (patrón de
`tests/unit/test_models.py`). Todos corren **sin GI** y sin bus del sistema.

Proceso TDD seguido en la implementación (ya completado): **ciclos verticales
RED → GREEN por comportamiento**, uno por función, sin escribir los tests de
todas las funciones (38/41+) de una vez:

1. Por cada función, en este orden: `map_adapter`, `map_device`,
   `map_battery`, `map_rssi`:
   a. Escribir los tests de **esa** función contra este contrato → **RED**.
   b. Implementar el código mínimo de **esa** función → **GREEN**.
   c. Refactorizar si hace falta (seguir con la siguiente función).
2. Al terminar los cuatro ciclos, `make lint && make typecheck && make test`
   pasan ([desarrollo y validación](../../README.md#desarrollo-y-validación)).
3. Commit atómico `feat(bluetooth): implement pure D-Bus object mapper`.

### `map_adapter`

| # | Caso | Resultado esperado |
|---|------|--------------------|
| 1 | props completas válidas | todos los campos mapeados |
| 2 | solo `Address` | `name`/`alias` `""`, booleanos `False`, `address_type` `UNKNOWN` |
| 3 | `Address` ausente | `BluetoothError` |
| 4 | `Address` tipo `int` | `BluetoothError` |
| 5 | `Powered` = `1` (int) | `BluetoothError` (bool no acepta int) |
| 6 | `Powered` = `"yes"` | `BluetoothError` |
| 7 | `AddressType` = `"banana"` | `AddressType.UNKNOWN` |
| 8 | `AddressType` = `42` | `BluetoothError` |
| 9 | props extra (`Class`, `UUIDs`, `Modalias`) | se ignoran, sin error |

### `map_device`

| # | Caso | Resultado esperado |
|---|------|--------------------|
| 10 | props completas válidas | todos los campos mapeados |
| 11 | `Address` ausente | `BluetoothError` |
| 12 | `Adapter` ausente | `BluetoothError` |
| 13 | `Adapter` tipo `int` | `BluetoothError` |
| 14 | `Name`/`Alias` ausentes | `""` |
| 15 | `Icon` desconocido | `DeviceIcon.UNKNOWN` |
| 16 | `UUIDs` ausente | `()` |
| 17 | `UUIDs` lista de `str` | `tuple[str, ...]`; con un elemento no-`str` → `BluetoothError` |
| 18 | `UUIDs` = `"abcd"` (str suelto) | `BluetoothError` (contenedor no válido) |
| 19 | `Connected` ausente | `connected False`, `connection_state DISCONNECTED` |
| 20 | `Connected` = `True` | `connection_state CONNECTED` |
| 21 | `Connected` = `0` (int) | `BluetoothError` |
| 22 | `Paired` = `1` (int) | `BluetoothError` |
| 23 | `RSSI`/`TxPower`/`Class`/`Appearance` presentes | se ignoran, sin error (van a `map_rssi` / no mapeados) |

### `map_battery`

| # | Caso | Resultado esperado |
|---|------|--------------------|
| 24 | `Percentage` 80, `Source` `"GATT Battery Service"` | campos mapeados |
| 25 | props vacías | `percentage None`, `source ""` |
| 26 | `Percentage` = `True` | `BluetoothError` (int no acepta bool) |
| 27 | `Percentage` = `"80"` | `BluetoothError` |
| 28 | `Percentage` = `101` | `BluetoothError` (invariante encadenado) |
| 29 | `Percentage` = `-1` | `BluetoothError` |
| 30 | `Source` = `5` | `BluetoothError` |

### `map_rssi`

| # | Caso | Resultado esperado |
|---|------|--------------------|
| 31 | `RSSI` -67, `TxPower` 8, timestamp inyectado tz-aware UTC | se conserva exactamente el timestamp inyectado |
| 32 | props vacías | `rssi_dbm None`, `tx_power_dbm None`, timestamp ≈ `now(UTC)` tz-aware |
| 33 | `RSSI` = `True` | `BluetoothError` |
| 34 | `RSSI` = `"x"` | `BluetoothError` |
| 35 | `TxPower` = `True` | `BluetoothError` |
| 36 | `RSSI` = `10` (positivo) | `BluetoothError` (invariante encadenado) |
| 37 | `RSSI` ausente, `TxPower` presente | `rssi_dbm None`, `tx_power_dbm` seteado |
| 38 | timestamp por defecto (`None`) | `datetime` tz-aware en UTC |
| 39 | `timestamp` tipo erróneo (p. ej. `str`) | `BluetoothError` |
| 40 | `timestamp` naive (sin `tzinfo`) | `BluetoothError` |
| 41 | `timestamp` tz-aware con offset ≠ 0 (p. ej. `UTC+2`) | `BluetoothError` |
| 42 | `timestamp` tz-aware UTC conforme | se conserva exactamente (mismo valor e instante) |

### Invariantes encadenados

En los casos 28, 29, 36 el `BluetoothError` debe tener `__cause__` (`ValueError`)
no `None` (verificación de la cadena de excepciones, §7).

---

## 10. Integración real (solo lectura)

Test opt-in en **`tests/integration/`** (patrón de
`tests/integration/test_bluez_dbus_protocol.py`): marcado `@pytest.mark.integration`
y desactivado salvo `OPENBUDS_RUN_INTEGRATION=1`.

Procedimiento:

1. `snapshot = BlueZDBusClient().snapshot()` (solo `GetManagedObjects`, sin
   métodos mutadores).
2. Recorrer el snapshot; por cada objeto:
   - `org.bluez.Adapter1` → `map_adapter(object_path, props)`
   - `org.bluez.Device1` → `map_device(object_path, props)`
   - `org.bluez.Battery1` → `map_battery(props)`
   - `Device1` con `RSSI`/`TxPower` → `map_rssi(props)`
3. Afirmaciones: no lanza excepción sobre objetos reales; `address` y
   `adapter_path` no vacíos; `connection_state` coherente con `connected`;
   `uuids` es `tuple`.
4. **Privacidad:** no se loguea ni se aserta la MAC del dispositivo
   (coherente con [gio-dbus-client-design](gio-dbus-client-design.md), snapshot
   "sin exponer la MAC").

El mapper se ejercita **exclusivamente** con las propiedades completas de cada
interfaz del snapshot; no se le alimentan payloads parciales de
`PropertiesChanged` (ver §2) — el repositorio refresca un snapshot completo por
señal y diffs (Incremento 2, [signal-lifecycle-design §4](signal-lifecycle-design.md#4-repositorio-registro-cache-y-dispatch)).

El mapper es puro: la integración solo valida que los dicts reales de BlueZ
cumplen el contrato. La lectura nunca auto-arranca `bluetoothd` ni escribe nada.

**Verificación 2026-08-09:** el test opt-in pasó en Python 3.12 / Gio sobre el
snapshot real de BlueZ: todos los adaptadores/dispositivos/baterías del bus se
mapearon sin excepción, sin invocar ningún método mutador y sin loguear ni
exponer la MAC del dispositivo.

---

## 11. Fuentes oficiales verificadas

Verificadas (contenido consultado) el 2026-08-09:

| Tema | URL | Estado de verificación |
|------|-----|------------------------|
| BlueZ Device API (`Device1` props, marca `[optional]`) | https://bluez.readthedocs.io/en/latest/device-api/ | ✅ Accesible y consultado |
| BlueZ Adapter API (`Adapter1` props, defaults) | https://bluez.readthedocs.io/en/latest/adapter-api/ | ✅ Accesible y consultado |
| BlueZ Battery API (readthedocs) | https://bluez.readthedocs.io/en/latest/battery-api/ | ✅ Accesible; documenta `Percentage` |
| `battery-api.txt` (kernel.org) | https://git.kernel.org/pub/scm/bluetooth/bluez.git/tree/doc/battery-api.txt | ⚠️ Bloqueado por anti-bot (Anubis) en esta sesión; contenido ya verificado localmente (BlueZ 5.72) en [dbus-interfaces.md](dbus-interfaces.md) — incluye `Source` |
| `media-api.txt` (kernel.org) | https://git.kernel.org/pub/scm/bluetooth/bluez.git/tree/doc/media-api.txt | ⚠️ Idem (fuera de alcance de este contrato: códec) |
| D-Bus specification (ObjectManager/Properties, tipos) | https://dbus.freedesktop.org/doc/dbus-specification.html | Estándar de referencia |

Referencias internas: [Interfaces D-Bus de BlueZ](dbus-interfaces.md),
[Diseño del cliente GDBus](gio-dbus-client-design.md),
[RESEARCH_LIMITS](../RESEARCH_LIMITS.md#3-disponibilidad-de-batería),
[ADR-0001](../ADR/0001-decision-dbus-pygobject-gio.md).

---

## 12. Resumen de decisiones (registro del arquitecto)

1. `Mapping[str, object]` como tipo de entrada (no `dict`).
2. Requeridas: solo identidad (`Adapter1.Address`; `Device1.Address`,
   `Device1.Adapter`). Todo lo demás opcional con default explícito.
3. Defaults conservadores de OpenBuds ante ausencia (`""` Name/Alias, `False`
   bools, `()` UUIDs, `None` battery/RSSI/TxPower, `UNKNOWN` enums): **no** son
   necesariamente los defaults de BlueZ ni una afirmación del estado real.
4. `bool` estricto (tipo exacto) y `int` que rechaza `bool`.
5. `connection_state` derivado siempre de `connected` (el derivado de un
   default `False` es el default conservador, no estado real verificado).
6. UUIDs: secuencia completa de `str` o error; `str` suelto rechazado.
7. Invariantes de modelos encadenados en `BluetoothError` con `from`.
8. Sin códec vendor, sin GI, sin métodos mutadores.
9. El mapper **nunca** recibe payloads parciales de `PropertiesChanged`: solo
   propiedades completas de interfaz, de snapshot completo o del cache
   actualizado por el repositorio (Incremento 2 refresca un snapshot completo
   por señal y diffs; no fusiona `changed`/`invalidated`).
10. `timestamp`: `None` → `datetime.now(UTC)`; inyectado debe ser `datetime`
    tz-aware con offset UTC (0) y se conserva exactamente; tipo erróneo,
    `naive` o zona no UTC → `BluetoothError`.
