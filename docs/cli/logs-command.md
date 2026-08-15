# Diseño técnico — CLI `logs` (logs del stack con redacción, Incremento 2 de Etapa 4)

- **Estado:** implementado en la **Etapa 4, Incremento 2** (cierre de Etapa 4);
  comando de **solo lectura**. Verificado real 2026-08-11 sin hardware:
  `openbuds logs --lines 5` mostró líneas reales de bluez, wireplumber y
  pipewire con las MAC y object paths redactados; sin identificadores reales
  en la salida.
- **Tipo:** diseño de implementación (**Documentation First; implementado y
  verificado** — el código y los tests cumplen lo aquí especificado).
- **Documentos relacionados:** [health](health-command.md),
  [status](status-command.md), [watch](watch-command.md),
  [devices](devices-command.md),
  [ADR-0004](../ADR/0004-clean-architecture-dependency-rule.md) y
  [AGENTS.md](../../AGENTS.md) §3/§5.

> **Alcance:** comando de **solo lectura** del journal de sistema y de
> usuario. No análisis automático, no escrituras, no servicios de journal
> propios.

## 1. Objetivo y salida

`openbuds logs [--service bluez|wireplumber|pipewire]... [--lines N]` imprime
por servicio `=== <servicio> ===` seguido de las líneas del journal (N entre 1
y 200, default 20; `--service` repetible; sin flag, usa los tres). Si un
servicio no está disponible se imprime `(no disponible: <error>)`. Exit **0**
si al menos un servicio está disponible; **1** si todos fallan.

```text
=== bluez ===
ago 11 10:00:01 <host> bluetoothd[PID]: <redacted> fd(41) ready
=== wireplumber ===
ago 11 10:00:02 <host> wireplumber[PID]: <bluetooth-sink>
=== pipewire ===
ago 11 10:00:03 <host> pipewire[PID]: <línea del journal sanitizada>
```

Las líneas reales se muestran con el mismo formato `-o short` de journalctl;
los identificadores se sustituyen por `<redacted>` (por ejemplo, en la
verificación real: `<bluetooth-sink>` en wireplumber y
`<redacted> fd(41) ready` en bluez).

## 2. Decisiones (registro del arquitecto)

1. **journalctl explícito:** `journalctl -u <unit> -n N --no-pager -o short`,
   sin colores ni paginación; cada intento con timeout.
2. **Unit real de BlueZ:** el daemon se llama **`bluetooth.service`**, no
   `bluez.service` (corrección real: `journalctl -u bluez` devuelve
   `-- No entries --` con exit 0); el reader mapea bluez→bluetooth.
3. **Fallback `--user`:** para wireplumber/pipewire (Ubuntu 24.04 los ejecuta
   como user), si el unit de sistema no existe, no produce líneas
   (`-- No entries --` o vacío) o falla, se reintenta con `--user`; para bluez
   **nunca** se reintenta como user.
4. **Redacción compartida:** `infrastructure/redaction.py` (usada también por
   health): MAC en todos los formatos (`:` `_` `.` espacio) y object paths
   `/org/bluez/...` → `<redacted>`; caracteres no imprimibles → `?`.
5. **Doble capa de sanitización:** el reader sanitiza cada línea (límite 300)
   y la CLI re-sanitiza en pantalla (`_sanitize_display_field`, límite 80).
6. **Exit 0/1** según haya al menos un servicio disponible.

## 3. Límites

- Depende de los permisos de journal del usuario: si el usuario no lee el
  journal de sistema, bluez mostrará `(no disponible: ...)`.
- Sin análisis automático de logs (solo volcado sanitizado).
- Los logs **no** están incluidos en `openbuds health` (subcomando aparte);
  `doctor` sigue siendo un comando separado. Sin cambios en
  health/status/watch/session/GUI.
