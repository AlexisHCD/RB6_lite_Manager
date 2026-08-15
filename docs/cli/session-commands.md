# Diseño técnico — CLI de sesión: `connect`/`disconnect`/`music`/`mic` (Incremento 3 de Etapa 2)

- **Estado:** implementado en la **Etapa 2, Incremento 3**; mutaciones de
  sesión **controladas** (runtime, no persistentes). Verificado real **sin
  hardware**: `list_profiles` devuelve `()` o perfiles existentes; parser
  contra `pw-cli` real; ninguna mutación ejecutada en pruebas. Gates: 478
  unit / 490 integración opt-in (solo lectura); Ruff/Mypy/diff-check OK.
- **Tipo:** diseño de implementación (**Documentation First; implementado y
  verificado** — el código y los tests cumplen lo aquí especificado).
- **Documentos relacionados:** [Diseño del comando `status`](status-command.md)
  y [watch](watch-command.md); [diseño de `WpctlAdapter`](../wireplumber/wpctl-adapter-design.md);
  [ADR-0004](../ADR/0004-clean-architecture-dependency-rule.md) y
  [privacidad y seguridad](../../README.md#privacidad-y-seguridad) y [alcance de la beta](../../README.md#alcance-de-la-beta).

> **Alcance:** mutaciones de sesión: conectar/desconectar y perfil de audio
> **runtime** (no persistente). Solo con **confirmación explícita** (o `-y`).

## 1. Objetivo y salida

`openbuds connect <dispositivo>` y `disconnect <dispositivo>` (dispositivo
**obligatorio**) usan las APIs oficiales `org.bluez.Device1.Connect/Disconnect`
(Gio). `music [dispositivo]` y `mic [dispositivo]` (dispositivo **opcional**:
si se omite, el primer conectado; si ninguno → «ningún dispositivo conectado»)
cambian el perfil runtime: música → `a2dp-sink`; micrófono → HFP (prioridad
`headset-head-unit-msbc`, fallback `headset-head-unit`); perfil no ofrecido →
`ProfileUnavailableError` («perfil no ofrecido»).

```text
¿Conectar Redmi Buds 6 Lite? [s/N]: s
Conectado: Redmi Buds 6 Lite
Recomendación: openbuds music para A2DP
```

Respuesta negativa → `Cancelado.` con **exit 0**; sin TTY → **exit 1**:
`Error: confirmación requerida; usa --yes en modo no interactivo`.

```text
Advertencia: activar el micrófono Bluetooth (HFP) puede reducir la calidad de
reproducción.
¿Activar Micrófono (HFP) en Redmi Buds 6 Lite? [s/N]: s
Perfil HFP aplicado a Redmi Buds 6 Lite
```

Resolución por **alias/nombre exacto** case-insensitive (match parcial único;
ambiguo → error; `disconnect`/`music`/`mic` exigen dispositivo conectado).

## 2. Decisiones (registro del arquitecto)

1. **APIs oficiales BlueZ:** `Device1.Connect/Disconnect` detrás del contrato
   ampliado `IBluetoothRepository.connect/disconnect` (aprobado, con fakes);
   solo mutan el estado de conexión, **nunca** el emparejamiento.
2. **Solo perfiles ofrecidos:** resolución dinámica, nada hardcodeado — id de
   objeto desde `pw-dump` (bluez5 por MAC normalizada), índice desde
   `pw-cli enum-params <id> EnumProfile` (parser dual: árbol 1.0.x y formato
   compacto `index:`/`name:`) y `wpctl set-profile <id> <índice>`.
3. **Confirmación [s/N]:** toda mutación pide confirmación salvo `-y/--yes`
   (scripting); respuesta negativa = cancelación silenciosa con exit 0.
4. **Contrato ampliado:** `IAudioControlRepository` y `ProfileUnavailableError`;
   `WpctlAdapter.set_profile` habilitado **solo runtime**; persistente y
   reinicio bloqueados hasta la Etapa 5.
5. **Errores sin datos sensibles** (sin MAC ni paths); advertencia de
   degradación en `mic` impresa antes de confirmar.

## 3. Límites

- Prueba real con hardware requiere **aprobación previa** (método, riesgos y
  reversibilidad); en la validación real no se ejecutó mutación.
- **Sin rollback automático** de perfil: el cambio runtime se revierte
  manualmente con `music`/`mic`.
- HFP solo si el sistema ofrece el perfil; `a2dp-sink` usa el mismo mecanismo
  de índice ofrecido (validado al aplicar). El emparejamiento permanece
  intacto: nunca se borra.
