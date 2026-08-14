# Diseño técnico — CLI `health` (Health Check etiquetado por evidencia, Incremento 1 de Etapa 4)

- **Estado:** implementado en la **Etapa 4, Incremento 1**; comando de **solo
  lectura**. Verificado real sin hardware: `Estado global: OK`; checks de
  sistema/runtime/hardware `observado`, 1 emparejado, «ninguno conectado»,
  perfil/códec/micrófono/batería «no disponible», sink por defecto real
  sanitizado y exit 0; sin MAC ni object paths.
- **Tipo:** diseño de implementación (**Documentation First; implementado y
  verificado** — el código y los tests cumplen lo aquí especificado).
- **Documentos relacionados:** [status](status-command.md),
  [watch](watch-command.md), [devices](devices-command.md),
  [ADR-0004](../ADR/0004-clean-architecture-dependency-rule.md) y
  [AGENTS.md](../../AGENTS.md) §3/§5.

> **Alcance:** comando de **solo lectura**: snapshot de BlueZ (dispositivos y
> batería), PipeWire (códec activo y sink por defecto) y detección del
> entorno. No discovery, no connect, no escrituras y **sin `auto_fix`**.

## 1. Objetivo y salida

`openbuds health` evalúa **14 checks estables en orden fijo** e imprime el
estado global, una línea por check con su etiqueta de evidencia y
`Recomendaciones:` si las hay, sin MAC ni object paths:

```text
Estado global: OK
[OK]       system.os — Sistema operativo: Ubuntu 24.04 soportado (observado)
[OK]       system.bluez — BlueZ: BlueZ disponible [5.72] (observado)
[OK]       system.pipewire — PipeWire: PipeWire disponible [1.0.5] (observado)
[OK]       system.wireplumber — WirePlumber: WirePlumber disponible [0.4.17 (lua-0.4)] (observado)
[OK]       system.dbus — Bus del sistema: bus del sistema disponible (observado)
[OK]       runtime.gio — Runtime PyGObject/Gio: runtime listo (base /usr) (observado)
[OK]       hardware.adapter — Adaptador Bluetooth: adaptador detectado (observado)
[OK]       device.paired — Dispositivos emparejados: 1 emparejados (observado)
[INFO]     device.connected — Dispositivo conectado: ninguno conectado (no disponible)
[INFO]     audio.profile — Perfil de audio activo: perfil no disponible (no disponible)
[INFO]     audio.codec — Códec activo: códec no disponible (no disponible)
[OK]       audio.sink_default — Sink por defecto del sistema: sink por defecto disponible [alsa_output.pci-0000_00_1f.3.analog-stereo] (observado)
[INFO]     audio.mic — Micrófono Bluetooth: micrófono no disponible (no disponible)
[INFO]     battery.aggregate — Batería (agregada): batería no disponible (no disponible)
```

Exit **0** si el estado global es OK o WARNING; **1** si ERROR o UNKNOWN. Los
14 `check_id` (orden fijo) y su semántica (evidencia default `observado`;
ausencias y fallos sin evaluar `no disponible`):

| check_id | etiqueta | semántica |
|---|---|---|
| `system.os` | Sistema operativo | OK Ubuntu 24.04 / ERROR no soportado |
| `system.bluez` | BlueZ | OK con versión / ERROR no disponible |
| `system.pipewire` | PipeWire | OK con versión / ERROR no disponible |
| `system.wireplumber` | WirePlumber | OK lua-0.4 / WARNING estilo no estándar / ERROR no disponible |
| `system.dbus` | Bus del sistema | OK disponible / ERROR no disponible |
| `runtime.gio` | Runtime PyGObject/Gio | OK runtime listo (base /usr) / ERROR no listo |
| `hardware.adapter` | Adaptador Bluetooth | OK detectado / WARNING ausente (política doctor) |
| `device.paired` | Dispositivos emparejados | OK N emparejados / INFO sin emparejados |
| `device.connected` | Dispositivo conectado | OK conectado / INFO ninguno conectado |
| `audio.profile` | Perfil de audio activo | OK A2DP / WARNING HFP / INFO no disponible |
| `audio.codec` | Códec activo | OK códec / WARNING no reconocido / INFO no disponible |
| `audio.sink_default` | Sink por defecto del sistema | OK con nombre sanitizado / INFO sin sink |
| `audio.mic` | Micrófono Bluetooth | OK sin micrófono / WARNING micrófono HFP / INFO no disponible |
| `battery.aggregate` | Batería (agregada) | INFO porcentaje / INFO no disponible |

## 2. Decisiones (registro del arquitecto)

1. **Evidencia por dato:** `EvidenceKind` en cada `CheckResult.evidence`
   (observado / inferido / no disponible / recomendación / acción segura
   disponible); nunca se infieren valores que no se observaron.
2. **Aislamiento por chequeo:** un check que lanza no rompe el reporte: ERROR
   «no se pudo evaluar» (no contado como evaluado); UNKNOWN solo si nada se
   pudo evaluar.
3. **Adaptador ausente = WARNING** (política doctor): la ausencia de hardware
   no invalida el resto; se sugiere verificar `rfkill`.
4. **HFP o micrófono activos = WARNING** + recomendación de `openbuds music`
   (restaura A2DP y calidad de reproducción).
5. **Sink por defecto opcional:** ausencia = INFO (no ERROR) + sugerencia de
   iniciar PipeWire/WirePlumber si el audio no funciona.
6. **Estado global:** ERROR > WARNING > OK; exit 0 (OK/WARNING) / 1
   (ERROR/UNKNOWN).
7. **Sanitización local:** MAC/object paths → `<redacted>`, imprimibles y
   máx. 80 caracteres; nunca MAC ni paths en la salida.
8. **Health no ejecuta auto-fix:** el informe puede indicar una acción segura
   disponible, pero `openbuds health` solo diagnostica; las reparaciones se
   ejecutan por separado mediante `openbuds fix` y su confirmación explícita.
9. **`doctor` vs `health`:** `doctor` = entorno (sistema, runtime, hardware);
   `health` = stack completo (entorno + dispositivo/audio/batería/sink).

## 3. Límites

- `openbuds health` no aplica auto-fixes; `openbuds fix` permanece separado y
  requiere confirmación explícita. Sin benchmark; sin jitter, latencia ni
  packet loss (no se prometen ni se estiman).
- `openbuds codec` sigue pendiente (milestone Etapa 2); `openbuds bench`
  pendiente (milestone posterior).
- La GUI ejecuta un Health Check real de solo lectura mediante
  `RunHealthCheckUseCase` en segundo plano y muestra el informe en un diálogo;
  `openbuds health` sigue siendo la interfaz CLI equivalente. La GUI no ejecuta
  auto-fixes.
- El volcado de logs/journal con redacción se difiere (pendiente parcial de
  Etapa 4); este incremento ya redacta identificadores en todos los mensajes.
