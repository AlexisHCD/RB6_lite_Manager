# Diseño — `WpctlAdapter` (wpctl), Incremento 1: solo lectura

> **Estado honesto:** incremento de solo lectura **validado, aprobado y publicado**.

## Propósito

`openbuds.infrastructure.wireplumber.wpctl_adapter` (`WpctlAdapter`) ejecuta
consultas seguras y frescas contra la CLI `wpctl` (WirePlumber Control), como
homólogo de `PwDumpRunner` ([contrato](../pipewire/pw-dump-runner-contract.md)).
Relacionados: [ADR-0002](../ADR/0002-wireplumber-0.4-lua-config-scope.md) y
[ADR-0003](../ADR/0003-no-pipewire-python-binding.md).

## API pública

- `__init__(binary="wpctl", timeout_seconds=5.0, executor=None)` — `binary` `str`
  no vacío sin NUL, `timeout` `int`/`float` exacto `> 0` finito; `executor`
  callable inyectable (`None` → `subprocess.run`, preservando callables falsy).
- `status() -> str` — devuelve exactamente el stdout de `wpctl status`.
- `inspect(object_id: int | str) -> str` — stdout exacto de `wpctl inspect`.
  Target admitido: **ID entero no negativo** o el alias exacto
  **`@DEFAULT_AUDIO_SINK@`**; cualquier otro valor → `ValueError` antes del
  executor.
- `set_profile()`/`restart_service()` — siguen `NotImplementedError` (sin
  mutaciones).

## Frontera de seguridad

- `argv` como lista `[binary, *args]`; **nunca `shell=True`**, sin argumentos de
  usuario, sin `shutil.which` previo (TOCTOU), sin `env`/`cwd`.
- Ejecución acotada por `timeout`; llamadas frescas sin caché.
- Sin logging del stdout (puede contener MAC); errores genéricos sin paths,
  binario, stdout ni stderr.
- Ninguna mutación: lectura pura; no modifica el sistema ni el dispositivo.

## Comportamiento de errores (público)

Solo `OSError` y `subprocess.TimeoutExpired` se envuelven en
`WirePlumberUnavailableError(AudioSubsystemError)` con `raise ... from error`
(`__cause__`). Si `returncode != 0` o el `stdout` no es `str`, se lanza
`WirePlumberUnavailableError` genérico **sin causa**. Las excepciones inesperadas
se propagan sin enmascarar. Validaciones de constructor/`inspect` → `ValueError`.

## Integración opt-in (estrictamente de lectura)

`tests/integration/test_wpctl_adapter.py`, gated por `OPENBUDS_RUN_INTEGRATION=1`
y `@pytest.mark.integration`: `status()` → `str`; `inspect("@DEFAULT_AUDIO_SINK@")`
→ `str` con clave `node.name` (nunca su valor). Sin `print`/logging de salidas.

## Fuentes oficiales esenciales

- `wpctl(1)`: <https://pipewire.pages.freedesktop.org/wireplumber/tools/wpctl.html>
- `subprocess`: <https://docs.python.org/3/library/subprocess.html>

## Límites (fuera de alcance)

- No hay parser de la salida (claves, códecs, perfiles) en este incremento.
- No perfiles/códec, no volumen, no reinicio ni configuración
  (`set_profile`/`restart_service` no implementados).
- Verificado con WirePlumber 0.4.17 (Ubuntu 24.04); publicado como solo
  lectura.
