# Contrato técnico — parser de `pw-dump` (`parse_bluetooth_audio_nodes`)

> **Estado:** **IMPLEMENTADO Y VERIFICADO** (2026-08-10). Contrato redactado con
> metodología **Documentation First**; la implementación cumple exactamente lo
> aquí especificado. `pipewire/pw_dump_parser.py` implementa
> `parse_bluetooth_audio_nodes` (ADRs [0003](../ADR/0003-no-pipewire-python-binding.md)
> y [0002](../ADR/0002-wireplumber-0.4-lua-config-scope.md)) con **20 unit tests
> TDD** en `tests/unit/test_pw_dump_parser.py` y una **integración real opt-in**
> `tests/integration/test_pw_dump_parser.py` (`pw-dump --no-colors`).
> **Verificación 2026-08-10:** 330 passed / 7 skipped por defecto y **337/337**
> con `OPENBUDS_RUN_INTEGRATION=1` (Python 3.12, `/tmp/openbuds-status-venv`);
> Ruff y mypy en verde.

- **Fase:** 4 (Optimización) — parser base de inspección de
  audio PipeWire
- **Tipo:** contrato de implementación (no es un ADR)
- **Fecha del contrato:** 2026-08-10
- **Documentos relacionados:** [ADR-0003 (pw-dump vía subprocess)](../ADR/0003-no-pipewire-python-binding.md),
  [ADR-0002 (WirePlumber 0.4)](../ADR/0002-wireplumber-0.4-lua-config-scope.md),
  [RESEARCH_LIMITS](../RESEARCH_LIMITS.md)
- **Dependencias del dominio:** `AudioSubsystemError` (`core/errors.py`); el
  error específico `PipeWireParseError(AudioSubsystemError)` **ya existe** en
  `core/errors.py` y es el que lanza el parser.

> ⚠️ **Regla de oro (AGENTS.md §5):** las claves y tipos descritos aquí se basan
> en la salida real de `pw-dump` verificada localmente (ver [§10](#10-evidencia-verificada))
> y en las fuentes oficiales de PipeWire/WirePlumber (ver
> [§11](#11-fuentes-oficiales)). Ante cualquier discrepancia con el
> comportamiento real se detiene la implementación y se documenta.

---

## 1. Objetivo

Extraer, de la salida JSON de `pw-dump`, la lista de **nodos de audio
Bluetooth** (sinks/sources) como **dicts planos normalizados**
`list[dict[str, str]]`, listos para consumo por el dominio (códec activo,
transporte, etc.). Es la frontera entre el volcado JSON de PipeWire (esquema
abierto, tipos heterogéneos) y las capas de aplicación/dominio.

El parser **nunca** ejecuta subprocesses (ADR-0003): es una **función pura** que
recibe el payload de `pw-dump` ya obtenido por el caller (`PwDumpRunner` u
otro). El runner es quien ejecuta `pw-dump`; el parser solo transforma.

---

## 2. Delimitación: función pura, sin I/O

- `parse_bluetooth_audio_nodes(payload: str) -> list[dict[str, str]]` es una
  función **pura**: entrada `str` (el JSON emitido por `pw-dump`) → salida
  `list[dict[str, str]]`.
- **Sin efectos secundarios, sin subprocess, sin red, sin I/O de archivos, sin
  dependencias de PipeWire/GI.** Toda la lógica opera sobre el JSON decodificado
  en memoria.
- Consecuencia: **todos los unit tests corren sin `pw-dump` instalado y sin un
  PipeWire en ejecución.**

---

## 3. Firma pública

```python
def parse_bluetooth_audio_nodes(payload: str) -> list[dict[str, str]]: ...
```

Notas:

- **Entrada:** `str` — el texto JSON completo que produce `pw-dump` (el propio
  runner lo captura de stdout; el parser **no** lo ejecuta).
- **Salida:** `list[dict[str, str]]` — cada dict es un nodo de audio Bluetooth
  normalizado (ver [§6](#6-normalización-de-propiedades-escalares)). Orden
  estable y determinista (ver [§5](#5-orden-y-condiciones)).

---

## 4. Validación de estructura (JSON root)

- El payload debe decodificar como JSON **válido** y el root debe ser una
  **lista** (array). `pw-dump` emite siempre `[ ... ]`.
- Cualquier fallo de `json.loads` o un root que **no** sea `list` → se lanza el
  error específico `PipeWireParseError(AudioSubsystemError)` (ya existente en
  `core/errors.py`, subclase de `AudioSubsystemError`). Mensaje
  descriptivo que incluya el contexto del fallo (p. ej. `json.JSONDecodeError`
  encadenado con `from exc`).
- **Nunca** escapan `json.JSONDecodeError`, `ValueError` ni `TypeError` a las
  capas de aplicación/presentación: todo se envuelve en `PipeWireParseError`.

---

## 5. Entradas válidas e inválidas

El root es una lista de objetos; cada objeto tiene la forma típica de un objeto
de `pw-dump` (`{ "id", "type", "version", "permissions", "info": { "props": {
... } } }`). El parser itera la lista y, por cada entrada, aplica la política de
ignorado/validación:

### 5.1 Entradas ignoradas (malformed/unrelated)

Se **ignoran silenciosamente** (nunca error, nunca se incluyen en la salida):

- Entrada que **no es** un `dict` (p. ej. `None`, `str`, `int`, `list`).
- Objeto con `type` **distinto** de `"PipeWire:Interface:Node"` (Clients,
  Devices, Ports, Links, Modules, Metadata, Factory, Profiler, Core, etc.).
- `type` presente pero **no-`str`**, o `type` ausente.
- Nodo sin `info.props` (o `info` ausente / `info` no-`dict` / `props`
  no-`dict`).
- Nodo cuya `media.class` no sea exactamente `"Audio/Sink"` ni
  `"Audio/Source"` (p. ej. `"Audio/Duplex"`, `"Midi/Bridge"`, `"Video/Sink"`,
  ausente, no-`str`). *Nota: los nodos Bluetooth puros de hoy son `Audio/Sink`
  (altavoz A2DP) y `Audio/Source` (micrófono HFP/HSP); otros `media.class`
  quedan fuera del contrato.*
- Nodo que **no** cumple la condición de Bluetooth (§5.2).
- Nodo con `node.name` no-`str` **o** `id` inválido (regla 5.3): un objeto que
  en todo lo demás es un nodo, pero no supera validación estricta, se ignora
  como entrada corrupta.

> **Regla general:** el parser es **tolerante ante entradas no relevantes o
> malformadas** en el array (política «ignore, don't fail»). Un solo objeto raro
> entre cientos nunca rompe el parseo. Solo el root no-lista o JSON inválido
> producen error (§4).

### 5.2 Condición de Bluetooth

Un nodo es **de audio Bluetooth** si y solo si cumple **al menos una** de:

1. `node.name` (de `info.props`) comienza exactamente por **`bluez_output.`**
   o **`bluez_input.`** (prefijos reales de WirePlumber: `bluez_output.<addr>` /
   `bluez_input.<addr>`).
2. `device.api` (de `info.props`) es exactamente **`bluez5`**. La clave común
   `device.api` está documentada por PipeWire; el valor `bluez5` se trata como
   marcador runtime de respaldo y se validará con hardware real.

Si cumple (1) **o** (2) → candidato; se incluye siempre que `media.class` y
`id` superen la validación. Si no cumple ninguna → se ignora.

### 5.3 Validación estricta de `id` y `node.name`

Para un nodo candidato, la **única** validación estricta (fuera de la política
de ignorado) es:

- **`id`:** debe ser **`int` exacto** (`type(v) is int`, es decir que **no** sea
  `bool` — `bool` es subclase de `int`) y **`>= 0`**. `id` ausente, `bool`,
  `float`, `str` o negativo → entrada **ignorada** (malformada).
- **`node.name`:** para computar la condición (1) se exige `str`; si no lo es,
  la condición (1) falla y la entrada se evalúa solo por (2).

`media.class` ya se validó en §5.1 (si no es `Audio/Sink`/`Audio/Source` la
entrada se ignoró antes).

---

## 6. Normalización de propiedades escalares

El dict resultante por nodo es **plano** (todas las claves a nivel top) y con
**valores `str`**. Se aplica sobre `info.props`:

| Tipo original del valor | Normalización |
|-------------------------|---------------|
| `str` | se conserva **exactamente** (sin trim, sin case-normalize, sin unicode-parse) |
| `bool` | `"true"` / `"false"` (lowercase) |
| `int` / `float` | `str(v)` (representación decimal de Python) |
| `null` / `list` / `dict` | **se ignora** la clave (no se incluye en la salida) |

Reglas:

1. Cada clave de `info.props` con valor escalar admitido se emite tal cual (la
   clave ya es `str`; si una clave no fuera `str`, se **ignora**).
2. Los valores `list`/`dict`/`null` **nunca** se serializan (p. ej. no se hace
   `json.dumps` ni `str(list)`); la clave simplemente no aparece.
3. `bool` se normaliza explícitamente a lowercase (`true`/`false`) para no
   depender de la representación de Python (`True`/`False`).

### 6.1 `object.id` — decisión explícita sobre el ID canónico

- El parser **añade siempre** la clave top-level **`object.id`** al dict de
  salida, con el valor del `id` top-level del objeto `pw-dump`
  (canónico del grafo).
- **Decisión explícita:** si `info.props` contuviera también un `id` (colisión),
  **gana el `id` top-level canónico** — se sobrescribe con él. No se mezclan:
  el `object.id` de salida es, por contrato, el `id` numérico del objeto del
  grafo PipeWire (equivalente al `id` de `wpctl status`), nunca un `id` de
  `props`.
- Esto evita inconsistencia entre consumidores que usan `id` como clave del
  objeto.

### 6.2 Claves Bluetooth preservadas verbatim

- `bluez5.codec` y `api.bluez5.transport` se **preservan verbatim** si aparecen
  en `info.props` (se pasan como `str` sin validar, sin inferir códec ni
  transporte, **sin verificar** contra listas de códecs ni transportes).
- **No** se deriva, valida ni verifica ningún valor de estas claves: su
  semántica se documenta como incierta en
  [RESEARCH_LIMITS §2](../RESEARCH_LIMITS.md#2-propiedades-runtime-de-pipewire)
  (propiedades runtime no documentadas formalmente). El parser es agnóstico.

---

## 7. Orden, duplicados y no-mutación

- **Orden:** los dicts de salida se ordenan por **`id` numérico ascendente** y,
  para ids iguales, por **`node.name`** ascendente (orden lexicográfico
  estable).
- **Duplicados:** si el payload contiene **varias entradas con el mismo `id`**
  (repetición legal en `pw-dump`, p. ej. nodos que aparecen dos veces), **se
  preservan todas** — no se deduplica. Cada una genera su propio dict. El orden
  de los duplicados con igual `id`+`node.name` es **estable** (se conserva el
  orden de aparición relativo, tal como produce `sorted` con claves estables).
- **No-mutación:** la función **nunca** muta el payload de entrada ni ningún
  objeto del JSON decodificado. Construye dicts nuevos.

---

## 8. Pseudocódigo de referencia

```
def parse_bluetooth_audio_nodes(payload: str) -> list[dict[str, str]]:
    try:
        root = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise PipeWireParseError(...) from exc
    if not isinstance(root, list):
        raise PipeWireParseError("root JSON no es lista")

    results = []
    for obj in root:
        if not isinstance(obj, dict):
            continue                       # ignorado
        if obj.get("type") != "PipeWire:Interface:Node":
            continue                       # no es nodo / unrelated

        info = obj.get("info")
        if not isinstance(info, dict):
            continue                       # sin info → ignorado
        props = info.get("props")
        if not isinstance(props, dict):
            continue                       # sin props → ignorado

        media_class = props.get("media.class")
        if media_class not in ("Audio/Sink", "Audio/Source"):
            continue                       # media.class no soportado

        node_name = props.get("node.name")
        node_name_ok = isinstance(node_name, str)
        is_bluez_name = node_name_ok and (
            node_name.startswith("bluez_output.")
            or node_name.startswith("bluez_input.")
        )
        device_api = props.get("device.api")
        if not (is_bluez_name or device_api == "bluez5"):
            continue                       # no es Bluetooth

        obj_id = obj.get("id")
        if type(obj_id) is not int or obj_id < 0:
            continue                       # id malformado → ignorado

        flat = {"object.id": str(obj_id)}
        for key, value in props.items():
            if not isinstance(key, str):
                continue
            if isinstance(value, str):
                flat[key] = value
            elif isinstance(value, bool):
                flat[key] = "true" if value else "false"
            elif isinstance(value, (int, float)):
                flat[key] = str(value)
            else:
                continue                   # null/list/dict → ignorado

        results.append(flat)

    results.sort(key=lambda d: (int(d["object.id"]), d.get("node.name", "")))
    return results
```

> Nota: en `bluez5.codec` / `api.bluez5.transport` no hay ningún `if` de
> validación: pasan por la rama genérica `str` del loop (verbatim, §6.2).

---

## 9. Criterios de aceptación (tests TDD)

Archivo de tests: **`tests/unit/test_pw_dump_parser.py`** — **20 unit tests**
(casos 1-32 agrupados y parametrizados). Corren **sin**
`pw-dump`, sin PipeWire y sin GI.

### 9.1 Estructura y errores

| # | Caso | Resultado esperado |
|---|------|--------------------|
| 1 | payload JSON inválido (`"no json"`) | `PipeWireParseError` con `__cause__` (`JSONDecodeError`) |
| 2 | root JSON **objeto** (`{...}`) | `PipeWireParseError` (root no lista) |
| 3 | root JSON `"[]"` (lista vacía) | `[]` |
| 4 | root lista con entradas no-dict (`None`, `"x"`, `42`, `[1]`) | `[]` (ignoradas) |
| 5 | lista con objetos de otros tipos (Client, Device, Port, Link, Module, Metadata) | `[]` (ignorados) |
| 6 | root `null` / `"true"` / `123` (JSON válido, no lista) | `PipeWireParseError` |

### 9.2 Filtrado Bluetooth / media.class / id

| # | Caso | Resultado esperado |
|---|------|--------------------|
| 7 | nodo `Audio/Sink` con `node.name="bluez_output.xx"` | incluido |
| 8 | nodo `Audio/Source` con `node.name="bluez_input.xx"` | incluido |
| 9 | nodo con `device.api="bluez5"` y `media.class="Audio/Sink"` | incluido (sin prefijo bluez) |
| 10 | nodo `Audio/Sink` sin `node.name` ni `device.api="bluez5"` | ignorado |
| 11 | nodo `bluez_output.xx` con `media.class="Audio/Duplex"` | ignorado |
| 12 | nodo `bluez_output.xx` con `media.class` ausente | ignorado |
| 13 | nodo `bluez_output.xx` con `node.name` no-`str` (int) | evaluado solo por `device.api`; sin él → ignorado |
| 14 | `media.class="Audio/Sink"` pero `id` ausente | ignorado |
| 15 | `id = True` (bool) | ignorado (id no acepta bool) |
| 16 | `id = -1` | ignorado |
| 17 | `id = "12"` (str) | ignorado |
| 18 | `id = 3.0` (float) | ignorado |
| 19 | `info` ausente / no-dict / `props` no-dict | ignorado |

### 9.3 Normalización

| # | Caso | Resultado esperado |
|---|------|--------------------|
| 20 | `str` en props | conservado exacto (con espacios, mayúsculas) |
| 21 | `bool True` / `bool False` | `"true"` / `"false"` |
| 22 | `int 48000` / `float 1.5` | `"48000"` / `"1.5"` |
| 23 | props con `null`, `list`, `dict` | esas claves **no** aparecen en la salida |
| 24 | clave no-`str` en props | clave ignorada |
| 25 | props vacías | dict de salida solo con `object.id` |
| 26 | colisión `props["id"]` ≠ `id` top-level | `object.id` = **id top-level canónico** (gana el top) |
| 27 | `bluez5.codec` / `api.bluez5.transport` presentes | preservados verbatim, sin validar/inferir |

### 9.4 Orden, duplicados, no-mutación

| # | Caso | Resultado esperado |
|---|------|--------------------|
| 28 | varios nodos desordenados | salida ordenada por `id` numérico ascendente |
| 29 | dos nodos con igual `id` | orden secundario por `node.name` ascendente |
| 30 | entradas duplicadas con el mismo `id` | **ambas** preservadas (no dedup) |
| 31 | payload con un nodo válido | el objeto JSON decodificado de entrada no se muta (comparar deepcopy) |
| 32 | `object.id` en salida es `str` | todos los valores del dict son `str` (invariante `list[dict[str,str]]`) |

**Verificación de calidad (2026-08-10):** `make lint` y `make typecheck`
(Ruff y mypy en verde) y `make test` → **330 passed / 7 skipped** por defecto;
con `OPENBUDS_RUN_INTEGRATION=1` en **Python 3.12** (`/tmp/openbuds-status-venv`)
→ **337/337**. Commit atómico
`feat(pipewire): implement pure pw-dump bluetooth audio node parser`.

---

## 10. Evidencia verificada

### 10.1 Verificación local (2026-08-10, sin auriculares conectados)

Verificado localmente con el `pw-dump` del entorno de desarrollo:

```
pw-dump --version            →  Compiled with libpipewire 1.0.5
root JSON                    →  lista (array)          ✅ (contrato §4)
total objetos en root        →  125                    ✅
nodos (PipeWire:Interface:Node) → 16                  ✅
nodos Bluetooth (bluez_output/bluez_input o device.api=bluez5) → 0  ✅
```

- El root es **lista** de 125 objetos: 11 Clients, 1 Core, 2 Devices, 13
  Factories, 14 Links, 3 Metadata, 14 Modules, **16 Nodes**, 50 Ports, 1
  Profiler.
- Los 16 nodos **no** tienen prefijo `bluez_*` ni `device.api=bluez5`
  (p. ej. `Dummy-Driver`, `Freewheel-Driver`, `Midi-Bridge` con `media.class`
  `Midi/Bridge`) → la salida esperada del parser hoy es `[]`.

### 10.2 Verificación de integración real (opt-in) y cierre

- **20 unit tests TDD** (`tests/unit/test_pw_dump_parser.py`) pasan **sin**
  `pw-dump`, sin PipeWire y sin GI (casos 1-32 de §9).
- **Integración real opt-in** `tests/integration/test_pw_dump_parser.py` (gated
  por `OPENBUDS_RUN_INTEGRATION=1`, `@pytest.mark.integration`): ejecuta
  **`pw-dump --no-colors`** real y parsea su stdout con el parser. **No exige
  nodos Bluetooth conectados** (solo valida forma de la salida); el **resultado
  local es `[]` (0 nodos Bluetooth)**. **No captura ni expone MAC ni payload:**
  el payload no se loguea y la MAC solo se usa como condición de filtrado
  (`startswith`), nunca en logs ni en la salida.
- **Gates al cierre (2026-08-10):** `make test` → **330 passed / 7 skipped**
  por defecto; con `OPENBUDS_RUN_INTEGRATION=1` en **Python 3.12**
  (`/tmp/openbuds-status-venv`) → **337/337**. Ruff y mypy en verde
  (`make lint`, `make typecheck`).
- **Implicación de verificación:** al no haber nodos Bluetooth reales, la
  validación empírica del caso positivo (códec/transporte) sigue **pendiente**
  hasta disponer de un dispositivo conectado
  ([RESEARCH_LIMITS §2](../RESEARCH_LIMITS.md#2-propiedades-runtime-de-pipewire)).
  **No** se afirma Redmi Buds 6 Lite detectado ni códec verificado.

---

## 11. Fuentes oficiales

| Tema | URL | Estado |
|------|-----|--------|
| `pw-dump(1)` man page | https://docs.pipewire.org/page_man_pw-dump_1.html | Referencia oficial del formato de salida |
| Propiedades de objetos PipeWire (`pipewire-props(7)`) | https://docs.pipewire.org/page_man_pipewire-props_7.html | Documenta `media.class`, `node.name`, `device.api` |
| WirePlumber Bluetooth configuration (actual) | https://pipewire.pages.freedesktop.org/wireplumber/daemon/configuration/bluetooth.html | Documenta los patrones de nodos `bluez_output.*`/`bluez_input.*`; no canoniza aquí el valor runtime `device.api=bluez5` |

## 12. Contexto de versiones

- **Target de la app (ADR-0002):** WirePlumber **0.4** (Ubuntu 24.04 =
  0.4.17, sintaxis Lua). El contrato **no** depende de la versión de
  WirePlumber: solo lee `info.props` que emite el PipeWire del sistema.
- **Tolerancia de versión:** el parser es **agnóstico a la versión de
  PipeWire/WirePlumber**. Valida por prefijos/valores exactos
  (`bluez_output.`/`bluez_input.`, `bluez5`, `Audio/Sink`, `Audio/Source`) que
  son estables en la cadena actual de PipeWire; si un PipeWire futuro cambiara
  estos nombres, el parser degrada a `[]` (sin romper) y se revisa el contrato.
- **ADR-0003:** el parser **no** ejecuta `pw-dump`; solo procesa el payload. La
  ejecución queda en el runner del módulo de inspección.

## 13. Privacidad

- El parser **no** loguea, imprime ni expone la **MAC** de los dispositivos.
  El `node.name` de Bluetooth (`bluez_output.<MAC>` / `bluez_input.<MAC>`) solo
  se usa como **condición de filtrado** (`startswith`); **nunca** se incluye en
  logs ni en la salida de diagnóstico como dato legible por defecto.
- La salida es `list[dict[str, str]]` de propiedades técnicas; si un consumer
  la loguea, debe tratar la MAC como dato sensible (coherente con el resto de
  contratos de lectura del proyecto).

## 14. Fuera de alcance

- Ejecución de `pw-dump`/`wpctl` (runner, ADR-0003).
- Validación de códecs (`bluez5.codec`), transportes
  (`api.bluez5.transport`) ni resolución de perfiles Bluetooth.
- `media.class` distintos de `Audio/Sink`/`Audio/Source` (p. ej.
  `Audio/Duplex`).
- Cualquier escritura sobre PipeWire/WirePlumber/dispositivo (filosofía
  AGENTS.md §3; lectura pura).

## 15. Resumen de decisiones (registro del arquitecto)

1. Función pura `parse_bluetooth_audio_nodes(payload: str) -> list[dict[str, str]]`,
   sin subprocess (ADR-0003).
2. JSON root debe ser lista; si no → `PipeWireParseError(AudioSubsystemError)`
   (ya existe en `core/errors.py`, subclase de `AudioSubsystemError`),
   `JSONDecodeError` encadenado con `from`.
3. Política «ignore, don't fail»: entradas no relevantes o malformadas se
   ignoran silenciosamente; solo root no-lista/JSON inválido fallan.
4. Nodo válido exige: `type == "PipeWire:Interface:Node"`, `info.props` dict,
   `media.class in ("Audio/Sink", "Audio/Source")`, `id` int exacto no-`bool`
   `>= 0`.
5. Bluetooth iff `node.name` prefijo `bluez_output.`/`bluez_input.` **o**
   `device.api == "bluez5"`.
6. Normalización escalar: `str` verbatim, `bool` lowercase, `int`/`float`
   `str`, `null`/`list`/`dict` → clave ignorada.
7. `object.id` añadido siempre; ante colisión **gana el `id` top-level
   canónico**.
8. `bluez5.codec` / `api.bluez5.transport` verbatim, sin inferir ni verificar
   ([RESEARCH_LIMITS §2](../RESEARCH_LIMITS.md#2-propiedades-runtime-de-pipewire)).
9. Orden por `id` numérico luego `node.name`; **no** se deduplican ids
   repetidos; no se muta la entrada.
10. Tolerante a la versión de PipeWire/WirePlumber (target 0.4, ADR-0002);
    degrada a `[]` ante cambios de nomenclatura.
11. Privacidad: la MAC nunca se loguea ni se expone.
