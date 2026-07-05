# Decisiones técnicas (índice maestro)

Este documento indexa todas las decisiones arquitectónicas y técnicas importantes
del proyecto. Cada decisión se documenta como un **ADR** (Architecture Decision
Record) en [`ADR/`](ADR/).

## ADRs

| ID | Decisión | Estado | Fecha |
|----|----------|--------|-------|
| [0001](ADR/0001-decision-dbus-pygobject-gio.md) | Biblioteca D-Bus: PyGObject/Gio (GDBus) | Aceptada | 2026-07-02 |
| [0002](ADR/0002-wireplumber-0.4-lua-config-scope.md) | WirePlumber 0.4 Lua, scope `~/.config/`, backup/rollback | Aceptada | 2026-07-02 |
| [0003](ADR/0003-no-pipewire-python-binding.md) | Sin binding Python de PipeWire; usar pw-dump/wpctl | Aceptada | 2026-07-02 |
| [0004](ADR/0004-clean-architecture-dependency-rule.md) | Clean Architecture, regla de dependencias | Aceptada | 2026-07-02 |
| [0005](ADR/0005-device-profile-contract.md) | Contrato de perfiles de dispositivo | Aceptada | 2026-07-02 |

## Cómo añadir un nuevo ADR

1. Copia la plantilla inferior.
2. Numera secuencialmente (`0006-...`).
3. Indica contexto, decisión, justificación y consecuencias.
4. Actualiza esta tabla.

## Plantilla

```markdown
# ADR-NNNN: Título corto

- **Estado:** Propuesta / Aceptada / Obsoleta
- **Fecha:** YYYY-MM-DD
- **Fase:** N

## Contexto
(¿Qué problema se intenta resolver? ¿Qué restricciones hay?)

## Decisión
(¿Qué se decidió?)

## Justificación
(¿Por qué esta opción y no las alternativas?)

## Consecuencias
(¿Qué impacto tiene, positivo y negativo?)
```

## Restricciones del proyecto (no negociables)

Estas restricciones globales rigen todo el proyecto y se documentan aquí como
referencia permanente:

- **Nunca** modificar firmware, EEPROM ni NVRAM del dispositivo.
- **Nunca** enviar comandos Bluetooth desconocidos o propietarios sin
  comprensión total (Fase 9, análisis pasivo exclusivamente).
- **Nunca** aplicar ingeniería inversa directamente sobre el dispositivo.
- **Nunca** modificar hardware.
- **Nunca** eliminar configuraciones existentes del sistema sin backup.
- **Nunca** sobrescribir archivos sin crear backup previo.
- **Nunca** asumir soporte para un códec o capacidad del dispositivo.
- **Todo** cambio sobre el sistema Linux debe poder revertirse.
