# Diseño técnico — CLI `fix` (auto-fix seguro del Health Check, posterior a Etapa 4)

- **Estado:** implementado en un **incremento posterior a la Etapa 4**; comando
  de **auto-reparación segura** del Health Check con mutaciones SEGURAS y
  confirmación explícita. Verificado real sin mutar: `fix no-existe --yes` →
  exit 1 «No hay auto-fix disponible ahora»; `fix start.audio --yes` → exit 1
  (sistema sano, el fix no aplica); `health` sin fixes visibles en sistema
  sano. **Ninguna mutación se ejecutó en pruebas**; el smoke de integración
  solo cubre rutas de no-disponible.
- **Tipo:** diseño de implementación (**Documentation First; implementado y
  verificado** — el código y los tests cumplen lo aquí especificado).
- **Documentos relacionados:** [health](health-command.md),
  [session](session-commands.md), [privacidad y seguridad](../../README.md#privacidad-y-seguridad) y [desarrollo y validación](../../README.md#desarrollo-y-validación).

> **Alcance:** mutaciones **seguras y reversibles** sobre Linux, **sin sudo** y
> solo tras **confirmación explícita** (`[s/N]` o `-y`). Nunca toca firmware,
> configuraciones del sistema ni unidades de sistema.

## 1. Objetivo y salida

`openbuds fix <id> [--yes]` ejecuta primero el Health Check; solo aplica los
`id` marcados como disponibles (`[fix: <id>]` al final de la línea del check
en `openbuds health`). Si el id no está disponible, no muta nada y sale 1:

```text
$ openbuds fix start.audio --yes
No hay auto-fix disponible ahora: start.audio
$ echo $?
1
```

Si está disponible, muestra la acción (label + mensaje del check +
descripción), pide confirmación, aplica el fix, re-ejecuta el Health Check y
muestra la verificación honesta (si el problema persiste, se muestra):

```text
$ openbuds fix <id>
Acción: <etiqueta del check> — <mensaje del check>
Descripción: <descripción de la reparación>
¿Aplicar <id>? [s/N]: s
<resultado de la reparación>
Verificación: <check_id> — <mensaje> (<evidencia>)
```

Exit **0** tras aplicar; **1** si el id no está disponible. `profile.a2dp` sin
dispositivo conectado → «requiere un dispositivo conectado» exit 1 (sin
mutar).

| id | cuándo se ofrece (check + condición) | acción exacta | reversibilidad |
|---|---|---|---|
| `start.audio` | `audio.sink_default` sin sink por defecto | `systemctl --user start pipewire wireplumber` (unidades de usuario, idempotente) | `systemctl --user stop` |
| `profile.a2dp` | `audio.profile` en WARNING (HFP activo) | `set_profile` a `a2dp-sink` (runtime, misma vía que `openbuds music`) | volver a HFP (`openbuds mic`) |

## 2. Decisiones (registro del arquitecto)

1. **Confirmación obligatoria:** ningún fix se ejecuta sin `[s/N]` o `-y`.
2. **Sin sudo:** solo unidades de usuario (`systemctl --user`); nunca
   unidades de sistema.
3. **Verificación post-fix honesta:** re-Health tras aplicar; si el problema
   persiste, se muestra sin ocultarlo.
4. **Errores sanitizados:** `ServiceError` con mensaje genérico sin paths ni
   identificadores.
5. **Ids estables:** `AutoFixId` en el dominio (`start.audio`, `profile.a2dp`).
6. **Disponibilidad desde el reporte:** un fix solo se ofrece si el Health
   Check lo marca (`auto_fix_available`); no se ofrecen fixes para problemas
   inexistentes.

## 3. Límites

- Sin auto-fix para `runtime.gio` (requiere recrear el venv manualmente),
  `hardware.adapter` (rfkill requiere sudo) ni reinicio de BlueZ (sudo).
- El benchmark permanece post-MVP y no tiene subcomando público.
