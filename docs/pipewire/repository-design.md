# Diseño — Incremento 1: `PipeWireRepository.list_bluetooth_audio_nodes`
> **Estado:** **IMPLEMENTADO Y VERIFICADO** (2026-08-10). Este documento nació como
> Documentation First (diseño antes de escribir código) y ahora refleja la
> **implementación verificada** del **Incremento 1** del repositorio PipeWire:
> `list_bluetooth_audio_nodes` compone `runner.dump()` (payload fresco) + parser
> puro en `pipewire_repository.py`. El contrato global `IAudioRepository` sigue
> **parcialmente implementado** — este incremento cubre solo el listado;
> `get_active_codec`/`get_default_audio_sink` **permanecen `NotImplementedError`**
> (§10). Gates reales en §8.3.
- **Etapa:** 2 (backend PipeWire de solo lectura) — repositorio base de
  inspección de audio PipeWire
- **Tipo:** diseño de implementación (no es un ADR)
- **Fecha:** 2026-08-10
- **Relacionados:** [ADR-0003 (inspección vía subprocess)](../ADR/0003-no-pipewire-python-binding.md), [ADR-0002 (WirePlumber 0.4)](../ADR/0002-wireplumber-0.4-lua-config-scope.md), [contrato del runner](pw-dump-runner-contract.md), [contrato del parser](pw-dump-parser-contract.md), [RESEARCH_LIMITS](../RESEARCH_LIMITS.md)
- **Dominio:** `AudioSubsystemError` + `PipeWireUnavailableError` / `PipeWireParseError` (`core/errors.py`) — ya existen; el repositorio **no** define excepciones nuevas.

> ⚠️ **Regla de oro (AGENTS.md §5):** no se asume códec, transporte ni capacidad del dispositivo. `bluez5.codec` / `api.bluez5.transport` van verbatim desde el parser ([RESEARCH_LIMITS §2](../RESEARCH_LIMITS.md#2-propiedades-runtime-de-pipewire)) y **no se interpretan** en el repositorio.
---
## 1. Objetivo y delimitación
Orquestar la cadena **runner → parser** sin lógica propia: `list_bluetooth_audio_nodes()` ejecuta `runner.dump()` (payload fresco), lo entrega a `parse_bluetooth_audio_nodes(payload)` y devuelve directamente el `list[dict[str, str]]` resultante. El repositorio es una **capa de composición** (sin caching, logs, subprocess propio ni inferencia).
- Ubicación: `src/openbuds/infrastructure/pipewire/pipewire_repository.py` (capa **infrastructure**, junto a runner y parser; implementa `IAudioRepository` de `domain/interfaces/audio_repo.py`).
- **Subprocess solo en el runner** (ADR-0003); el repositorio nunca ejecuta procesos ni importa `subprocess`. Solo lectura (AGENTS.md §3).
- **Sin estado entre llamadas** (fresh payload, §4) y **sin mutación** del payload ni de los dicts del parser (no los transforma ni reordena).
## 2. Firma pública
```python
class PipeWireRepository(IAudioRepository):
    def __init__(self, runner: DumpRunner | None = None) -> None: ...
    def list_bluetooth_audio_nodes(self) -> list[dict[str, str]]: ...
    def get_active_codec(self, device_address: str) -> CodecInfo | None: ...  # NotImplemented
    def get_default_audio_sink(self) -> str | None: ...                        # NotImplemented
```
## 3. Protocolo `DumpRunner` (structural typing)
```python
from typing import Protocol
class DumpRunner(Protocol):
    """Mínimo contrato del runner inyectable: entregar el payload pw-dump."""
    def dump(self) -> str: ...
```
- `PwDumpRunner` es **estructuralmente compatible** (`dump() -> str` ya existe y está verificado). **No se modifica el runner ni el parser**; la inyección se añade solo en el repositorio.
- `DumpRunner` se define en el propio módulo del repositorio (cohesión).
- `list_bluetooth_audio_nodes` es el **único** consumidor de `runner.dump()` en este incremento.
## 4. Constructor y regla de inyección
```python
def __init__(self, runner: DumpRunner | None = None) -> None:
    self._runner = runner if runner is not None else PwDumpRunner()
```
Regla **crítica** — la condición es `is None`, **nunca** truthiness:
- `runner=None` (explícito u omitido) → default real `PwDumpRunner()` (producción: `pw-dump --no-colors`, timeout 5 s).
- Runner inyectado **falsy** (p. ej. `__bool__() -> False` o `__len__() == 0`) → **se preserva** y se usa tal cual. Un `or`/`or default` descartaría ese fake y rompería los tests con fakes falsy (§8.1).
- El ctor **no** valida el runner inyectado (compatibilidad por mypy; el contrato `dump() -> str` lo garantiza el Protocol).
## 5. `list_bluetooth_audio_nodes()` — comportamiento exacto
```python
def list_bluetooth_audio_nodes(self) -> list[dict[str, str]]:
    return parse_bluetooth_audio_nodes(self._runner.dump())
```
Invariantes:
1. **Llamada fresca:** `runner.dump()` se invoca en **cada** llamada. **Sin cache, sin memoización, sin payload almacenado** (estado entre llamadas = `None`).
2. **Forwarding por comportamiento:** el payload del runner se pasa tal cual (sin trim, sin validación previa) a `parse_bluetooth_audio_nodes`.
3. **Retorno directo:** se devuelve exactamente el `list[dict[str, str]]` del parser (dicts nuevos, ordenados por `object.id`; contrato del parser §7). Sin transformación, copia ni filtrado adicional.
4. **Sin logs:** no se loguea payload, nodos ni resultados.
5. **Sin subprocess directo:** la única ejecución de proceso ocurre dentro del runner inyectado (real o fake).
6. **Sin mutación:** ni del payload ni de los dicts de salida.
## 6. Propagación de errores (sin re-envolver)
`PipeWireUnavailableError` (runner) y `PipeWireParseError` (parser) se **propagan sin cambios**: el consumidor recibe la **misma instancia** (identidad preservada). Ambas son `AudioSubsystemError`; los callers capturan por subclase o por categoría.
- **No** hay `try/except` amplio, **no** re-traducción ni causas nuevas: JSON inválido / root no-lista → `PipeWireParseError` (idéntico); `pw-dump` no disponible, timeout, returncode ≠ 0, stdout no-`str` → `PipeWireUnavailableError` (idéntico).
- Excepciones de programación del runner/parser inyectados se propagan sin enmascarar (contrato del runner §7).
## 7. Privacidad
El repositorio **no** loguea, imprime ni expone la **MAC** ni el `node.name` (los dicts de salida pueden contenerlas, pero su emisión es responsabilidad de la **presentación**, que tratará la MAC como dato sensible). La privacidad de presentación se aborda en un incremento posterior.
## 8. Criterios de aceptación (TDD)
### 8.1 Unit — `tests/unit/test_pipewire_repository.py`
Fakes del runner (objetos ligeros con `dump()`); **sin** `pw-dump`, PipeWire ni GI.
| # | Caso | Resultado esperado |
|---|------|--------------------|
| 1 | fake que registra llamadas | `runner.dump()` invocado **exactamente una vez** por llamada, sin argumentos |
| 2 | fake devuelve payload con nodo `bluez_output.xx` | resultado = `parse_bluetooth_audio_nodes(payload)` (forwarding por comportamiento, no interceptando el payload) |
| 3 | dos llamadas consecutivas con fake contador | `dump()` se invoca **de nuevo** en cada llamada (fresh, sin cache) |
| 4 | fake devuelve `"[]"` | `[]` (lista vacía) |
| 5 | fake devuelve payload malformado (`"no json"`) | `PipeWireParseError` propagado **sin envolver** |
| 6 | fake lanza `PipeWireUnavailableError` | **misma instancia** propagada (identidad, sin re-envolver) |
| 7 | runner inyectado **falsy** (`__bool__`/`__len__` falsy) | se **preserva** en el ctor y se usa (no se sustituye por `PwDumpRunner()`) |
| 8 | `runner=None` explícito | `self._runner` es `PwDumpRunner` (se verifica el atributo sin invocar `dump()`, que requeriría `pw-dump` real) |
### 8.2 Integración real opt-in — `tests/integration/test_pipewire_repository.py`
Gated por `OPENBUDS_RUN_INTEGRATION=1` (`@pytest.mark.integration`).
1. `PipeWireRepository()` real (default `PwDumpRunner`, `--no-colors` implícito, timeout 5 s).
2. `result = repo.list_bluetooth_audio_nodes()`.
3. **Sin assert sobre nodos:** solo `isinstance(result, list)` y, si no está vacío, cada elemento es `dict` con valores `str`.
4. **Sin payload ni MAC:** no se loguea ni imprime el payload ni los nodos.
5. Resultado local esperado (sin dispositivos, 2026-08-10): `[]` (0 nodos Bluetooth). **No** se afirma detección de Redmi Buds 6 Lite ni códec positivo ([RESEARCH_LIMITS §2](../RESEARCH_LIMITS.md#2-propiedades-runtime-de-pipewire)).
6. Si `pw-dump` falta o PipeWire no responde, `dump()` lanza `PipeWireUnavailableError` y el test falla (diseño "la ejecución es la verdad", contrato del runner §11).
### 8.3 Gates del incremento (verificados 2026-08-10)
- `make lint` y `make typecheck` en verde; los gates ordinarios y la
  integración opt-in pasaron al cierre del incremento.
- **Unit tests** (`tests/unit/test_pipewire_repository.py`: fakes deterministas, sin `pw-dump`/PipeWire/GI) + **integración real opt-in** (`tests/integration/test_pipewire_repository.py`).
- Commit atómico único: `feat(pipewire): implement PipeWireRepository.list_bluetooth_audio_nodes`.
## 9. Fuera de alcance (Incremento 1)
- `get_active_codec` / `get_default_audio_sink` (**NotImplementedError**; §10).
- Inferencia/validación de códecs o transportes (verbatim del parser).
- Logging, caching, reintentos o política de retry del repositorio.
- Privacidad de presentación (MAC visible al usuario).
- Cualquier escritura sobre PipeWire/WirePlumber/dispositivo.
## 10. Métodos diferidos — documentación honesta
`get_active_codec(device_address) -> CodecInfo | None` y `get_default_audio_sink() -> str | None` **permanecen** con `NotImplementedError` en este incremento. No se implementan de forma parcial, **no se infiere códec** a partir de `bluez5.codec` (verbatim; semántica runtime no documentada formalmente) y no se afirma ningún códec. Se diseñarán en la Etapa 2 (backend de sesión); el caso positivo se validará empíricamente en la Etapa 1 (ADRs 0002/0003, RESEARCH_LIMITS §2).
## 11. Resumen de decisiones (registro del arquitecto)
1. Incremento 1 cubre **solo** `list_bluetooth_audio_nodes`; el contrato global `IAudioRepository` y los demás métodos quedan **pendientes**.
2. `DumpRunner` = Protocol estructural `dump() -> str`; `PwDumpRunner` ya es compatible (sin modificar runner ni parser).
3. Inyección por ctor con condición **`is None`**: `None` → `PwDumpRunner()`; un runner **falsy** inyectado se preserva.
4. Cuerpo mínimo de 2 líneas: `payload = runner.dump()` → `parse_bluetooth_audio_nodes(payload)` → retorno directo del `list[dict[str, str]]` del parser.
5. **Fresh call** en cada invocación: sin cache, estado, logs, subprocess propio ni mutación.
6. Errores propagados **sin re-envolver** (identidad): `PipeWireUnavailableError` del runner, `PipeWireParseError` del parser; sin `except` amplio.
7. Sin MAC en logs/salida del repositorio (privacidad de presentación diferida).
8. `get_active_codec` / `get_default_audio_sink` **NotImplemented**; sin inferencia de códec.
9. Unit tests con fakes (llamadas exactas, forwarding por comportamiento, fresh, `[]`, parse error, identidad de error del runner, runner falsy preservado, default `PwDumpRunner`); integración real opt-in `list`→`list`, **sin assert de nodos ni payload**; resultado local 0 nodos, sin afirmación positiva de hardware.
10. **Verificado (2026-08-10):** gates `make lint`/`make typecheck` en verde; los gates ordinarios y la integración opt-in pasaron al cierre del incremento. La implementación real es el retorno directo `parse_bluetooth_audio_nodes(self._runner.dump())` (§5) con ctor `runner if runner is not None else PwDumpRunner()` (§4). El contrato global `IAudioRepository` sigue **parcialmente implementado**.
