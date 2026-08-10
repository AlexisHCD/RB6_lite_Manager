# ADR-0007: Contrato de eventos de cambio de dispositivo (`DeviceChangeEvent`)

- **Estado:** Aceptada
- **Fecha:** 2026-08-09
- **Fase:** 3 (Bluetooth)

## Contexto

`IBluetoothRepository.subscribe_device_changes` se implementará en el
**Incremento 2** de señales de BlueZ (`InterfacesAdded`, `InterfacesRemoved`,
`PropertiesChanged`). El contrato actual del callback, definido en
`domain/interfaces/observer.py`:

```python
DeviceChangeCallback = Callable[[DeviceInfo, ConnectionState], None]
```

es insuficiente para ese incremento:

1. **No expresa el tipo de cambio.** Una aparición (`InterfacesAdded`), una
   actualización de propiedades (`PropertiesChanged`) y una desaparición
   (`InterfacesRemoved`) son tres acontecimientos distintos, pero el callback
   no permite distinguirlos: la UI no sabe si debe añadir, actualizar o quitar
   una fila, ni el logger si se trata de "nuevo", "cambiado" o "removido".
2. **El "estado anterior" es solo `ConnectionState`.** Los cambios de BlueZ
   entregan payloads parciales; para sincronizar estado incremental se necesita
   el `DeviceInfo` **completo** anterior, no solo su estado de conexión.
3. **El callback mezcla dos conceptos en una tupla posicional.** El par
   `(DeviceInfo, ConnectionState)` es opaco y propenso a confusiones de orden.
4. **No hay forma de desuscribirse.** `subscribe_device_changes` devuelve
   `None`; la GUI y los tests no pueden liberar la suscripción.

## Decisión

Sustituir el callback por un contrato tipado con **kind** explícito, un evento
inmutable y una devolución de desuscripción:

```python
from enum import StrEnum, unique

@unique
class DeviceChangeKind(StrEnum):
    ADDED = "added"      # nuevo objeto Device1 (InterfacesAdded)
    UPDATED = "updated"  # propiedades de Device1 cambiadas (PropertiesChanged)
    REMOVED = "removed"  # Device1 desaparece (InterfacesRemoved)

@dataclass(frozen=True, slots=True)
class DeviceChangeEvent:
    kind: DeviceChangeKind
    current: DeviceInfo | None
    previous: DeviceInfo | None
```

### Invariantes (validadas en construcción; violación → `ValueError`)

| `kind`    | `current`                    | `previous`                                                 |
|-----------|------------------------------|------------------------------------------------------------|
| `ADDED`   | requerido (no `None`)        | `None`                                                     |
| `UPDATED` | requerido                    | requerido y `current.object_path == previous.object_path` |
| `REMOVED` | `None`                       | requerido                                                  |

Cualquier otra combinación es inválida (p. ej. ambos `None`, `ADDED` con
`previous` no nulo, `REMOVED` con `current` no nulo, o `UPDATED` con object
paths distintos). El **`object_path`** de BlueZ es la clave de identidad del
dispositivo: el ciclo completo `ADDED → UPDATED → REMOVED` de un mismo
dispositivo comparte ese `object_path`.

### Tipos del contrato

```python
DeviceChangeCallback = Callable[[DeviceChangeEvent], None]  # re-define el alias actual
Unsubscribe = Callable[[], None]                            # devolución de suscripción
```

`IBluetoothRepository.subscribe_device_changes(callback) -> Unsubscribe`
devuelve un **`Unsubscribe` idempotente**: invocarlo dos veces no lanza
excepción ni repite la liberación. El alias `DeviceChangeCallback` se conserva
con la nueva firma para no propagar un renombrado a las capas que lo importan
hoy (`bluetooth_repo.py`, `bluez_repository.py`).

### Ubicación (implementada)

- `DeviceChangeKind` → `domain/enums.py` (junto a las demás enumeraciones).
- `DeviceChangeEvent` → `domain/models/device_change.py` (junto a `DeviceInfo`),
  exportado en `domain/models/__init__.py`.
- `DeviceChangeCallback` y `Unsubscribe` → `domain/interfaces/observer.py`.

Ninguno depende de GI ni de capas externas (cumple
[ADR-0004](0004-clean-architecture-dependency-rule.md)).

### Semántica de ejecución

- **Cero callbacks después de `unsubscribe` en el mismo hilo/contexto.** La
  documentación de GIO (`signal_unsubscribe`) garantiza que, llamada desde el
  mismo hilo que `subscribe`, el callback no se invoca después de que retorne.
  Una implementación con worker propio **debe serializar** `subscribe` y
  `unsubscribe` en el mismo hilo para conservar esa garantía.
- **Los callbacks se ejecutan en el hilo/contexto de las señales** (el
  `GMainContext` que itera el dispatch). La **UI debe marshalear** al hilo de
  Qt (señal/slot o cola); **nunca** se toca Qt desde el callback.
- **Los eventos se emiten solo cuando cambia `DeviceInfo`.** `Battery1` y RSSI
  no forman parte de `DeviceInfo` (se consultan por snapshot con `get_battery`
  / `get_rssi`) y **no** disparan este callback por sí solos; solo un cambio de
  `Device1` observable que altere un campo de `DeviceInfo` lo dispara.
- **Las excepciones de los callbacks se aíslan y se loguean.** Un handler que
  lanza no debe interrumpir la entrega al resto de suscriptores ni romper el
  dispatch de GIO.

## Justificación

1. **Semántica explícita y verificable:** el `kind` permite reaccionar
   correctamente (añadir/actualizar/quitar) y las invariantes hacen que el
   evento sea comprobable por construcción.
2. **Diff real con `previous`:** el `DeviceInfo` anterior completo habilita la
   sincronización de estado incremental y los diffs, necesario porque
   `PropertiesChanged` entrega payloads parciales.
3. **`Unsubscribe` como valor de primera clase:** el contrato del dominio queda
   independiente de los identificadores internos de GIO; el llamador guarda el
   callable y lo invoca cuando quiere; la idempotencia protege contra dobles
   limpiezas.
4. **Seguridad de hilos respaldada por la documentación oficial de GIO** para
   el caso de mismo hilo ([gio-dbus-client-design §2.5](../bluez/gio-dbus-client-design.md#25-lifecycle-y-unsubscribe)),
   con responsabilidad explícita del worker de preservarla.
5. **Aislamiento de fallos:** un handler defectuoso degrada solo su propia
   suscripción y queda visible en logs.

## Alternativas rechazadas

- **Añadir el `ConnectionState` anterior como segundo parámetro:** el problema
  es que falta el `DeviceInfo` completo previo y el tipo de cambio; duplicar
  `ConnectionState` no los aporta.
- **`DeviceInfo` centinela para ADDED/REMOVED** (dispositivo "fantasma"):
  recurso implícito y frágil; oculta la semántica tras una convención no
  verificable.
- **Sin `unsubscribe`** (registro vitalicio): imposible de gestionar en la GUI y
  en los tests; rompe el lifecycle del cliente
  ([gio-dbus-client-design §2.5](../bluez/gio-dbus-client-design.md#25-lifecycle-y-unsubscribe)).
- **Solo `EventBus`** (publicar el `Event` genérico de `core/events.py`):
  pierde el tipado del contrato y obliga a inspeccionar `payload`; no sustituye
  al callback del repositorio. Puede coexistir como canal complementario en
  capas superiores, no como reemplazo.

## Consecuencias

- **Positivas:** contrato expresivo y validado, unsubscribe idempotente,
  aislamiento de excepciones, base sólida para la UI reactiva (add/update/remove)
  y para el dispatch del Incremento 2.
- **Negativas:** el dispatch debe refrescar el `DeviceInfo` completo y construir
  eventos que cumplan las invariantes; la UI debe marshalear al hilo de Qt;
  Battery/RSSI quedan fuera de este canal (se consumen por snapshot).
- **Migración:** el alias `DeviceChangeCallback` se conservó en `observer.py`
  con la nueva firma y `bluez_repository.py` lo implementa; el cambio se aplicó
  sin tocar otras capas. No hubo consumidores activos con la firma antigua
  (`DeviceChangeCallback` de dos parámetros).

## Verificación (contrato, lifecycle de bajo nivel y dispatch implementados)

El **contrato del dominio** está **implementado y probado** sin GI ni bus del
sistema (suite por defecto: **276 passed, 6 skipped**; suite completa en
Python 3.12/Gio con `OPENBUDS_RUN_INTEGRATION=1`: **282 passed**, 2026-08-10;
ruff/mypy en verde):

- `DeviceChangeKind` con valores únicos (`@unique`), cubierto en
  `tests/unit/test_enums.py`.
- Invariantes de `DeviceChangeEvent`: cada fila válida de la tabla se
  construye y cada combinación inválida lanza `ValueError`, además de ser
  `frozen` + `slots` (`tests/unit/test_device_change.py`).
- Alias del contrato: `DeviceChangeCallback` re-definido con la nueva firma y
  `Unsubscribe` nuevo, ambos verificados (`test_device_change.py`).
- El **diff puro de snapshots** que produce los eventos (`device_change_diff.py`):
  orden `REMOVED→ADDED→UPDATED` por `object_path`, `UPDATED` solo si el
  `DeviceInfo` mapeado es desigual (igualdad completa del dataclass), **sin**
  eventos por cambios solo de `Battery1`/`RSSI`/`TxPower`, errores del mapper
  propagados sin resultados parciales y snapshots no mutados
  (`tests/unit/test_device_change_diff.py`).

El **Incremento 2 está completo y verificado**, incluyendo el **dispatch del
repositorio**:

- `BlueZRepository.subscribe_device_changes` **implementado**: init A→B con
  snapshot B en el worker vía `on_ready` (antes de que `subscribe` retorne; B
  cierra la carrera), cache de diff, refresh completo por señal, dispatch en
  orden de registro fuera del lock, aislamiento de excepciones, suscriptores
  múltiples/tardíos/reentrantes, `Unsubscribe` idempotente con espera de
  callbacks in-flight, concurrencia de init y rollback de errores
  (`tests/unit/test_bluez_repository_signals.py`, fakes sin GI/bus).
- **Reentrancia probada:** `subscribe` reentrante durante A→B (desde un
  callback de `on_ready` o de señal) se registra **sin replay y sin deadlock**;
  self-unsubscribe **solo es posible una vez que el llamador posee el
  `Unsubscribe`** (desde un callback de señal posterior, sin deadlock y sin
  eventos futuros) — durante A→B el callable aún no existe porque
  `subscribe_device_changes` no ha retornado, así que esa vía no aplica.
  El unsubscribe **externo** espera cualquier callback in-flight de su
  suscriptor (salvo self) y garantiza cero callbacks tras el retorno.
- Integración real opt-in (**`tests/integration/test_bluez_repository_signals.py`**,
  Python 3.12/Gio): **solo lifecycle A/B** — subscribe_device_changes +
  unsubscribe (idempotente) + snapshot A/B + `list_devices`; el bus compartido
  sigue usable. **No** se inducen señales, **no** se afirma recepción real de
  eventos ni escrituras de hardware.
- **Sin cierre de bus/cliente:** el repositorio nunca llama `close()` ni
  cierra la conexión D-Bus compartida (verificado en tests).

## Fuentes oficiales

| Tema | URL |
|------|-----|
| Gio.DBusConnection.signal_subscribe (main context, hilo del callback) | https://docs.gtk.org/gio/method.DBusConnection.signal_subscribe.html |
| Gio.DBusConnection.signal_unsubscribe (garantía de mismo hilo) | https://docs.gtk.org/gio/method.DBusConnection.signal_unsubscribe.html |
| GLib.MainContext (thread-default, iteración del loop) | https://docs.gtk.org/glib/struct.MainContext.html |
| D-Bus spec — ObjectManager / Properties (señales de BlueZ) | https://dbus.freedesktop.org/doc/dbus-specification.html |
| typing — `Callable` (contrato de callbacks) | https://docs.python.org/3/library/typing.html |

Internas: [gio-dbus-client-design §2.4/§2.5 y §3](../bluez/gio-dbus-client-design.md),
[repository-design §6](../bluez/repository-design.md),
[ADR-0001](0001-decision-dbus-pygobject-gio.md).
