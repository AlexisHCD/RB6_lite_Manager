# Contrato técnico — runner de `pw-dump` (`PwDumpRunner`)

> **Estado:** **IMPLEMENTADO Y VERIFICADO** (2026-08-10). Contrato redactado con
> metodología **Documentation First** (docs primero, código después) y **cerrado**:
> `infrastructure/pipewire/pw_dump_runner.py` cumple la especificación salvo la
> **divergencia aprobada** del timeout (§4/§15): se exige además `math.isfinite`
> (`NaN`/`±inf` rechazados). Es el
> compañero de `pipewire/pw_dump_parser.py`
> ([contrato del parser](pw-dump-parser-contract.md), IMPLEMENTADO): el parser
> es la función **pura** que transforma el payload; el runner es quien
> **ejecuta** `pw-dump` y entrega ese payload (ADRs
> [0003](../ADR/0003-no-pipewire-python-binding.md) y
> [0002](../ADR/0002-wireplumber-0.4-lua-config-scope.md)).

- **Etapa:** 2 (backend PipeWire de solo lectura) — runner base de
  inspección de audio PipeWire
- **Tipo:** contrato de implementación (no es un ADR)
- **Fecha del contrato:** 2026-08-10
- **Estado:** ✅ IMPLEMENTADO Y VERIFICADO — `PwDumpRunner` implementado en
  `infrastructure/pipewire/pw_dump_runner.py`, cubierto por unit tests
  (`tests/unit/test_pw_dump_runner.py`, fakes sin `pw-dump`/PipeWire/GI) y una
  **integración real opt-in** (`tests/integration/test_pw_dump_runner.py`)
- **Documentos relacionados:** [ADR-0003 (pw-dump vía subprocess)](../ADR/0003-no-pipewire-python-binding.md),
  [ADR-0002 (WirePlumber 0.4)](../ADR/0002-wireplumber-0.4-lua-config-scope.md),
  [contrato del parser `pw-dump`](pw-dump-parser-contract.md),
  [RESEARCH_LIMITS](../RESEARCH_LIMITS.md)
- **Dependencias del dominio:** `PipeWireUnavailableError(AudioSubsystemError)`
  — **ya existe** en `core/errors.py` (línea 45) y es la única excepción que
  lanza el runner.

> ⚠️ **Evidencia y no inferencia:** los flags y el comportamiento de
> `pw-dump` descritos aquí están verificados localmente (2026-08-10, PipeWire
> 1.0.5) y en las fuentes oficiales (ver [§12](#12-fuentes-oficiales)). Ante
> cualquier discrepancia con el comportamiento real se detiene la
> implementación y se documenta.

---

## 1. Objetivo

Ejecutar `pw-dump --no-colors` de forma **segura, aislada y testable** y
devolver su stdout (payload JSON completo) como `str` exacto para que lo
consuma el parser puro
[`parse_bluetooth_audio_nodes`](pw-dump-parser-contract.md) u otro consumidor.

El runner **no** parsea JSON, **no** filtra, **no** interpreta. Su única
responsabilidad es: **ejecutar de forma fiable y con privacidad**, y traducir
cualquier fallo de ejecución a `PipeWireUnavailableError(AudioSubsystemError)`.

---

## 2. Capa y delimitación

- Ubicación: `src/openbuds/infrastructure/pipewire/pw_dump_runner.py`
  (capa **infrastructure**, junto a `pw_dump_parser.py` y
  `pipewire_repository.py`).
- El runner **sí** ejecuta subprocess (a diferencia del parser, ADR-0003);
  eso es precisamente su frontera de responsabilidad.
- Es **solo lectura**: no modifica configuración, no muta el entorno
  (`os.environ`), no escribe sobre PipeWire/WirePlumber/dispositivo.
- Es **determinista y sin estado**: cada llamada a `dump()` ejecuta una vez,
  con los mismos parámetros, y no deja estado entre llamadas.

---

## 3. Firma pública

```python
class PwDumpRunner:
    def __init__(
        self,
        binary: str = "pw-dump",
        timeout_seconds: int | float = 5.0,
        executor: Executor | None = None,
    ) -> None: ...

    def dump(self) -> str: ...
```

Notas:

- `binary`: ruta o nombre del binario de `pw-dump`. **Configuración del
  operador**, nunca entrada de usuario (ver [§8](#8-seguridad-y-privacidad)).
- `timeout_seconds`: límite de tiempo de la ejecución (por defecto **5.0**).
- `executor`: callable inyectable para tests (ver [§5](#5-protocolo-del-executor)).
  `None` → se usa `subprocess.run` real (default de producción).
- `dump() -> str`: payload JSON exacto de `pw-dump` o
  `PipeWireUnavailableError`.

---

## 4. Constructor: validaciones (antes de ejecutar nada)

Toda validación ocurre **en el constructor** y **antes** de que exista o se
llame al executor. Parámetros inválidos → **`ValueError`** (error de
programación/configuración, no de runtime).

| Parámetro | Regla | Incumplimiento |
|-----------|-------|----------------|
| `binary` | debe ser `str` **no vacío** y **sin carácter NUL** (`"\x00"`) | `ValueError` |
| `timeout_seconds` | tipo **exacto** `int` **o** `float` (se excluye `bool` — `type(v) in (int, float)`), **`> 0`** y **finito** (`math.isfinite(float(v))`; `NaN` y `±inf` se rechazan — divergencia aprobada) | `ValueError` |
| `executor` | `None` o callable compatible con el Protocol ([§5](#5-protocolo-del-executor)) | — (no se valida en ctor; se usa tal cual) |

Detalles:

- `binary` con NUL se rechaza porque `subprocess` lanzaría `ValueError` en
  ejecución; se adelanta a ctor para fallar pronto, con mensaje determinista.
- `timeout_seconds=True` **se rechaza** (`bool` no es tiempo válido); `3.5`
  se acepta; `"5"` (str) y `None` se rechazan; `0` y `-1` se rechazan.
- **Divergencia aprobada (2026-08-10):** la implementación añade
  `math.isfinite(float(timeout_seconds))`, por lo que `NaN`, `float("inf")` y
  `float("-inf")` **se rechazan** con `ValueError` (un timeout no finito rompe
  la semántica de `subprocess.run(timeout=...)`). El contrato original solo
  exigía `> 0`; se cierra con esta regla más estricta, verificada por tests.
- El mensaje de `ValueError` es **genérico** (no replica el valor del binario
  ni ningún path potencialmente sensible).
- La validación del ctor **nunca** invoca al executor: los tests de
  "invalid ctor" deben poder correr con un executor que fallaría si se
  llamara.

---

## 5. Protocolo del executor (structural typing)

Para hacer el runner **testable sin subprocess reales**, el executor se define
como un **Protocol estructural** (PEP 544) y el resultado de ejecución como
otro Protocol. El default real (`subprocess.run`) debe ser **estructuralmente
compatible** con estos tipos (mypy lo verifica).

```python
from typing import Any, Protocol


class PwDumpResult(Protocol):
    """Resultado de ejecución: subconjunto estructural de CompletedProcess."""

    returncode: int
    stdout: Any
    stderr: Any


class Executor(Protocol):
    """Callable estructuralmente compatible con subprocess.run."""

    def __call__(self, argv: list[str], **kwargs: Any) -> PwDumpResult: ...
```

Decisiones de typing:

- `Executor.__call__` acepta `argv: list[str]` y `**kwargs: Any`; esto permite
  que `subprocess.run` (firma real `run(*popenargs, input=None,
  capture_output=False, timeout=None, check=False, ...)`) sea asignable al
  Protocol: `list[str]` es `Sequence[str]`, asignable al parámetro
  `popenargs: Sequence[str | bytes]` (covarianza de `Sequence`), y `kwargs:
  Any` no restringe el resto.
- `PwDumpResult.stdout`/`stderr` son `Any` porque `text=True` produce `str`,
  pero un fake de tests puede devolver `bytes` y el runner debe **detectar**
  ese caso en runtime (§7.4). `CompletedProcess[str]` es asignable a este
  Protocol.
- Un fake en unit tests solo necesita exponer los atributos `returncode`,
  `stdout`, `stderr` (objetos ligeros, sin herencia de `CompletedProcess`).
- `executor: Executor | None = None`; si `None`, el runner asigna
  `self._executor = subprocess.run`. La asignación pasa mypy por la
  compatibilidad estructural descrita.

---

## 6. `dump()`: ejecución del comando

La llamada al executor es **exacta y fija**:

```python
result = self._executor(
    [self._binary, "--no-colors"],
    capture_output=True,
    text=True,
    check=False,
    timeout=self._timeout_seconds,
)
```

Reglas invariables:

1. **`argv` es siempre la lista `[binary, "--no-colors"]`** — lista, nunca
   string. **Nunca `shell=True`.** No se añaden argumentos de usuario (no hay
   entrada de usuario en este módulo; ver §8).
2. **`capture_output=True`** → captura stdout y stderr.
3. **`text=True`** → el resultado llega como `str` (decodificado con la
   codificación locale del proceso, como hace `subprocess`; el runner **no**
   re-decodifica ni re-normaliza).
4. **`check=False`** → código de salida ≠ 0 **no** lanza `CalledProcessError`;
   el runner lo traduce él mismo (§7.3). Con `check=True` se perdería el
   control del mensaje y la privacidad (el error vendría con stdout/stderr).
5. **`timeout=timeout_seconds`** → si el proceso excede el límite,
   `subprocess.TimeoutExpired` se lanza y se traduce (§7.2).
6. **Sin `env=`**: se hereda el entorno del proceso, **sin mutarlo**. El
   runner nunca escribe en `os.environ`.
7. **Sin `cwd=`**, sin `stdin` (None por defecto), sin redirecciones extra.

**Sin precondición `shutil.which`:** el runner **no** comprueba la existencia
del binario antes de ejecutar. Hacerlo introduciría un **TOCTOU** (la
comprobación y la ejecución no son atómicas: el binario puede faltar justo
después de la comprobación, o aparecer justo después) y además es engañoso
(`which` encuentra el binario pero el daemon puede no responder). **La
ejecución es la verdad**: si el binario no existe, `subprocess.run` lanza
`FileNotFoundError` y el runner lo traduce a `PipeWireUnavailableError` (§7.1).

---

## 7. Mapeo de errores

`dump()` **nunca** deja escapar excepciones de la categoría subprocess a las
capas superiores: todo se traduce a `PipeWireUnavailableError` con
`__cause__` encadenado (`from exc`).

| # | Situación | Acción |
|---|-----------|--------|
| 7.1 | `FileNotFoundError` (binario ausente) **o** cualquier otro `OSError` (permisos, ENOENT, etc.) al ejecutar | `PipeWireUnavailableError` con `__cause__`. **Mensaje genérico sin paths sensibles**: no incluye el valor de `binary` ni rutas. |
| 7.2 | `subprocess.TimeoutExpired` (excede `timeout_seconds`) | `PipeWireUnavailableError` con `__cause__`. Mensaje genérico. |
| 7.3 | `result.returncode != 0` (aunque stdout/stderr existan) | `PipeWireUnavailableError` **sin incluir stdout ni stderr** en el mensaje (privacidad, §8). |
| 7.4 | `result.returncode == 0` pero `result.stdout` **no es `str`** (p. ej. bytes por un fake, o tipo raro) | `PipeWireUnavailableError` (stdout no textual; incoherencia de ejecución). |
| 7.5 | `returncode == 0` y `stdout` es `str` (incluida `""`) | **Retorna exactamente ese `str`**, sin trim, sin validación de contenido. `""` es legal aquí: el runner no parsea; será el parser quien lance `PipeWireParseError` (contrato §4 del parser). |

Reglas transversales:

- El **stderr nunca** se usa para construir mensajes ni se loguea (§8).
- El `stdout` (payload) **nunca** se loguea ni se incluye en excepciones
  (§8).
- Cualquier otra excepción del executor **no** prevista (excepción de
  programación, bug del fake, etc.) **se propaga sin enmascarar**: el runner
  solo traduce las categorías documentadas (7.1-7.4). No se ocultan bugs con
  un error genérico.
- El error lanzado es **siempre** `PipeWireUnavailableError`
  (`core/errors.py:45`, subclase de `AudioSubsystemError`), no su padre
  genérico.

---

## 8. Seguridad y privacidad

### Seguridad

- **Nunca `shell=True`.** `argv` es una lista de argumentos; no hay
  interpretación de shell, por lo que los meta-caracteres del binario (si
  algún día lo contuvieran) son inertes. No existe vector de "shell
  injection".
- **Sin argumentos de usuario.** El único argumento de ejecución es el flag
  fijo `--no-colors`. El runner no acepta ni reenvía argumentos arbitrarios.
- `binary` es **configuración del operador**, no entrada de usuario; su ruta
  se permite tal cual (p. ej. una ruta con espacios funciona correctamente
  porque se pasa como elemento de lista). Solo se rechaza el NUL (§4), que
  rompería la invocación de subprocess.
- **Sin mutación de entorno**: no se pasa `env=` y no se escribe
  `os.environ`.
- **Sin cambios de hardware/configuración**: ejecución de un dumper de solo
  lectura; no toca WirePlumber, no escribe archivos, no envía comandos al
  dispositivo (lectura pura; no modifica el sistema ni el dispositivo).
- **Acotado en el tiempo**: `timeout_seconds` (5 s por defecto) garantiza que
  un PipeWire colgado no bloquee al runner.
- **Sin TOCTOU**: no hay `shutil.which` previo (la existencia se valida por
  ejecución, §6).

### Privacidad

- El payload de `pw-dump` (que puede contener la **MAC** de dispositivos en
  `node.name`) **nunca** se loguea, imprime ni incrusta en excepciones.
- El `stderr` del proceso **nunca** se loguea ni se expone.
- Los mensajes de error son **genéricos**: no contienen paths, ni stdout, ni
  stderr, ni MAC.

---

## 9. Pseudocódigo de referencia

```
class PwDumpRunner:
    def __init__(binary="pw-dump", timeout_seconds=5.0, executor=None):
        if not isinstance(binary, str) or binary == "" or "\x00" in binary:
            raise ValueError("binary inválido")          # genérico, sin eco
        if type(timeout_seconds) not in (int, float) or timeout_seconds <= 0 \
                or not math.isfinite(float(timeout_seconds)):
            raise ValueError("timeout inválido")   # bool, NaN, inf → rechazado
        self._binary = binary
        self._timeout = timeout_seconds
        self._executor = subprocess.run if executor is None else executor

    def dump(self) -> str:
        try:
            result = self._executor(
                [self._binary, "--no-colors"],
                capture_output=True, text=True,
                check=False, timeout=self._timeout,
            )
        except FileNotFoundError as exc:                 # OSError incluido
            raise PipeWireUnavailableError("no se pudo ejecutar pw-dump") from exc
        except OSError as exc:
            raise PipeWireUnavailableError("no se pudo ejecutar pw-dump") from exc
        except subprocess.TimeoutExpired as exc:
            raise PipeWireUnavailableError("pw-dump excedió el tiempo límite") from exc

        if result.returncode != 0:
            raise PipeWireUnavailableError("pw-dump terminó con error")
        if not isinstance(result.stdout, str):
            raise PipeWireUnavailableError("salida de pw-dump no textual")
        return result.stdout                            # exacto; "" permitido
```

Notas sobre el pseudocódigo:

- El pseudocódigo refleja la **divergencia aprobada** del §4: además de
  `> 0`, la implementación exige `math.isfinite` (NaN/±inf → `ValueError`).
- `except (FileNotFoundError, OSError)` podría escribirse como una sola cláusula
  (`FileNotFoundError` es subclase de `OSError`); en el pseudocódigo se muestra
  separado solo para hacer explícito que ambas categorías caen en el mismo
  tratamiento. La implementación real usa una única cláusula
  `except (subprocess.TimeoutExpired, OSError)` (mismo efecto, un solo mensaje
  genérico `PipeWireUnavailableError`).
- El orden `returncode` → tipo de `stdout` → retorno garantiza que **nunca** se
  retorna `stdout` cuando `returncode != 0` ni cuando `stdout` no es `str`.
- `""` (vacío) se retorna: la decisión de qué hacer con un payload vacío es
  del parser (que lanza `PipeWireParseError`), no del runner.

---

## 10. Criterios de aceptación (unit tests TDD) — VERIFICADO

Archivo de tests: **`tests/unit/test_pw_dump_runner.py`** — unit tests
todos en verde (2026-08-10). Corren **sin** `pw-dump`, sin PipeWire y sin GI;
usan **fakes** del executor (objetos ligeros con
`returncode`/`stdout`/`stderr`, o lambdas que registran la llamada). Ningún
unit test toca el sistema real. La tabla de abajo son casos **implementados y
pasando**, no criterios pendientes.

### 10.1 Ejecución

| # | Caso | Resultado esperado |
|---|------|--------------------|
| 1 | `dump()` con fake que registra la llamada | argv exacto `[binary, "--no-colors"]` y kwargs exactos `{capture_output: True, text: True, check: False, timeout: timeout}` (un solo `_executor` invocado, una sola vez) |
| 2 | fake: `returncode=0`, stdout con Unicode exacto (acentos, emoji, `ñ`) | `dump()` retorna **exactamente** ese string, sin trim ni re-codificación |
| 3 | fake: `returncode=0`, `stdout=""` | `dump()` retorna `""` (no lanza; el parseo es responsabilidad del parser) |
| 4 | llamadas repetidas: `dump()` dos veces con fake que cuenta | el fake se invoca **de nuevo** en cada llamada (sin cache, sin estado entre llamadas) |
| 5 | `binary` configurable con espacios/ruta (p. ej. `"/opt/my tools/pw-dump"`) | se pasa como **un único elemento** de argv exacto (se permite; no se rechaza) |

### 10.2 Constructor (invalid ctor — antes que cualquier executor)

| # | Caso | Resultado esperado |
|---|------|--------------------|
| 6 | `binary=""` | `ValueError` |
| 7 | `binary="pw-dump\0x"` (contiene NUL) | `ValueError` |
| 8 | `binary` no-`str` (p. ej. `None`, `123`) | `ValueError` |
| 9 | `timeout_seconds=0`, `-1`, `float("nan")`, `float("inf")` o `float("-inf")` | `ValueError` (`math.isfinite`, divergencia aprobada §4) |
| 10 | `timeout_seconds=True` (bool) | `ValueError` (bool no es int/float válido) |
| 11 | `timeout_seconds="5"` (str) o `None` | `ValueError` (tipo no `int`/`float`) |
| 12 | `timeout_seconds=3.5` y `timeout_seconds=3` (int) | aceptado (no lanza) |
| 13 | todos los casos 6-12 | el executor **jamás** se invoca (fake que falla si se llama) |

### 10.3 Errores → `PipeWireUnavailableError`

| # | Caso | Resultado esperado |
|---|------|--------------------|
| 14 | fake ejecutor lanza `FileNotFoundError` | `PipeWireUnavailableError` con `__cause__`; el mensaje **no contiene** el valor de `binary` ni paths |
| 15 | fake ejecutor lanza `OSError` (p. ej. `PermissionError`) | `PipeWireUnavailableError` con `__cause__` |
| 16 | fake ejecutor lanza `subprocess.TimeoutExpired` | `PipeWireUnavailableError` con `__cause__` |
| 17 | fake: `returncode=7`, stdout/stderr con contenido | `PipeWireUnavailableError` **sin** stdout ni stderr en el mensaje |
| 18 | fake: `returncode=0`, `stdout=b"bytes"` (no-`str`) | `PipeWireUnavailableError` |
| 19 | error 7.x | la excepción es exactamente `PipeWireUnavailableError` (no `AudioSubsystemError` genérico) y `isinstance` de `AudioSubsystemError` |

### 10.4 Privacidad (secretos ausentes)

| # | Caso | Resultado esperado |
|---|------|--------------------|
| 20 | fake: `returncode=1` con `stderr="SECRETO_MAC:aa:bb:cc:dd:ee:ff"` | el texto secreto **no aparece** en el mensaje de la excepción (ni en logs — no hay logging en el runner) |
| 21 | fake: `returncode=0`, stdout con payload que incluye una MAC | `dump()` retorna el payload al caller pero el runner **no** lo loguea ni lo imprime; la excepción (si la hubiera) no lo contiene |

> El runner **no contiene ninguna llamada a logging** por diseño: ni payload,
> ni stderr, ni mensajes internos. Cualquier log de este tipo lo hace el
> caller con criterio propio (y tratando la MAC como dato sensible).

---

## 11. Integración real opt-in — IMPLEMENTADA Y VERIFICADA

Archivo: **`tests/integration/test_pw_dump_runner.py`**, gated por
`OPENBUDS_RUN_INTEGRATION=1` y auto-marcado `@pytest.mark.integration`
(conftest). Es **solo lectura** y **no exige dispositivos Bluetooth
conectados**. Verificada en verde (2026-08-10, Python 3.12).

Flujo real del test:

1. Instanciar `PwDumpRunner()` real (binario `pw-dump` por defecto,
   `timeout_seconds=5.0`, executor real `subprocess.run`).
2. `payload = runner.dump()` — el flag `--no-colors` lo inyecta el runner de
   forma **implícita**; el test nunca lo pasa.
3. `nodes = parse_bluetooth_audio_nodes(payload)` (parser del contrato
   [pw-dump-parser-contract](pw-dump-parser-contract.md)).
4. **Sin `assert` sobre nodos**: se valida solo la forma
   (`isinstance(payload, str)` y `isinstance(nodes, list)`); **no** se exige
   ningún nodo Bluetooth.
5. **Sin logging de salida**: el payload y el stderr no se loguean ni se
   imprimen.
6. `timeout` de ejecución: el por defecto (5.0 s).

La verificación local (2026-08-10) arroja **0 nodos Bluetooth** (sin
dispositivos conectados; RESEARCH_LIMITS §2), validando el pipeline
runner→parser end-to-end. El test **no** usa `shutil.which` ni pre-chequeos
TOCTOU y el skip se decide **solo** por el entorno
(`OPENBUDS_RUN_INTEGRATION != 1`): si en una ejecución opt-in `pw-dump`
falta o PipeWire no responde, `dump()` lanza `PipeWireUnavailableError` y el
test **falla**, coherente con el diseño "la ejecución es la verdad" (§6), que
exige un entorno PipeWire real para la integración.

Gates (2026-08-10): los gates ordinarios y la integración opt-in pasaron al
cierre del incremento; ruff y mypy en verde.

---

## 12. Fuentes oficiales

| Tema | URL | Estado |
|------|-----|--------|
| `pw-dump(1)` man page | https://docs.pipewire.org/page_man_pw-dump_1.html | Documenta `--no-colors`/`-N` (verificado localmente: PipeWire 1.0.5 lo acepta) |
| Python `subprocess` (documentación oficial) | https://docs.python.org/3/library/subprocess.html | Documenta `subprocess.run`, `capture_output`, `text`, `check`, `timeout`, `CompletedProcess`, `TimeoutExpired`; `shell=True` desaconsejado |
| ADR-0003 (inspección vía subprocess, sin binding) | [docs/ADR/0003](../ADR/0003-no-pipewire-python-binding.md) | Decisión de arquitectura de fondo |

Verificación local (2026-08-10): `pw-dump --help` muestra
`-N, --no-colors  disable color output` y `pw-dump --version` reporta
`Compiled with libpipewire 1.0.5`.

---

## 13. Contexto de versiones

- **Target de la app (ADR-0002):** WirePlumber **0.4** (Ubuntu 24.04 =
  0.4.17). El runner **no** depende de WirePlumber: solo ejecuta `pw-dump`.
- **Tolerancia de versión:** `--no-colors` es estable en la cadena actual de
  PipeWire (1.0.5) y existe desde versiones antiguas; si una versión futura lo
  eliminara, la ejecución fallaría con `returncode != 0` → `PipeWireUnavailableError`
  (degradación sin romper, revisando el contrato).
- **`text=True` y codificación:** la decodificación depende del locale del
  proceso (comportamiento estándar de `subprocess`). No se asume UTF-8
  explícito; el runner devuelve lo que `subprocess` devuelve (§6.3).

---

## 14. Fuera de alcance

- Parseo/interpretación del payload JSON (parser puro, ya implementado).
- Validación de códecs, transportes o perfiles Bluetooth.
- Cualquier escritura sobre PipeWire/WirePlumber/dispositivo (lectura pura;
  no modifica el sistema ni el dispositivo).
- Pre-chequeo de existencia del binario (`shutil.which`) — prohibido por
  TOCTOU (§6).
- Ejecución de otros binarios (`wpctl`, `pw-cli`, etc.) — cada uno tendrá su
  propio runner/adaptador si se necesita.

---

## 15. Resumen de decisiones (registro del arquitecto)

1. Clase `PwDumpRunner` en `infrastructure/pipewire/pw_dump_runner.py`,
   método público único `dump() -> str`; estado **IMPLEMENTADO Y VERIFICADO**
   (2026-08-10).
2. Ejecución única y fija:
   `executor([binary, "--no-colors"], capture_output=True, text=True,
   check=False, timeout=timeout_seconds)`. **Nunca `shell=True`, nunca
   argumentos de usuario.**
3. `check=False`: el runner traduce `returncode != 0` él mismo (mensaje sin
   stdout/stderr); con `check=True` se perdería la privacidad del mensaje.
4. `binary` = configuración del operador; se valida en ctor (no vacío, sin
   NUL); una ruta con espacios es legal (lista de argv). `timeout` = tipo
   exacto `int|float` no-`bool`, `> 0` **y finito** (`math.isfinite`;
   NaN/±inf rechazados — **divergencia aprobada**, §4); inválidos →
   `ValueError` **antes** de cualquier ejecución.
5. `executor` inyectable por Protocol estructural (`Executor` /
   `PwDumpResult` con `returncode`/`stdout`/`stderr`), compatible con
   `subprocess.run` para mypy; default real = `subprocess.run`.
6. Errores → `PipeWireUnavailableError(AudioSubsystemError)` con `__cause__`:
   `OSError` (incl. `FileNotFoundError`/`PermissionError`, mensaje genérico sin
   paths), `TimeoutExpired`, `returncode != 0` (sin stdout/stderr), `stdout`
   no-`str`. Otras excepciones se propagan sin enmascarar.
7. `returncode == 0` y `stdout` `str` → se retorna **exacto**, incluida `""`
   (el parser lanzará `PipeWireParseError` si el JSON es inválido).
8. Sin logging de payload ni stderr; sin mutación de `os.environ`; sin
   cambios de hardware/configuración; subprocess acotado por `timeout`.
9. **Sin `shutil.which`** (TOCTOU): la ejecución es la verdad.
10. Unit tests con fakes (sin `pw-dump`/PipeWire/GI) cubren argv/kwargs
    exactos, éxito Unicode, invalid ctor sin tocar executor (incl. NaN/±inf y
    `None` rechazados), mapeo de errores con privacidad, secretos ausentes,
    `""`, stdout no-`str`, ruta con espacios permitida, NUL rechazado y
    llamadas repetidas frescas.
11. Integración opt-in (`OPENBUDS_RUN_INTEGRATION=1`, timeout 5, sin logging)
    ejecuta `pw-dump` real → `dump()` → parser; `--no-colors` implícito en el
    runner; **sin assert de nodos**; skip solo por entorno, fallo si el
    `pw-dump` real falla. Verificada (2026-08-10): gates ordinarios e
    integración opt-in en verde (Python 3.12); ruff/mypy.
