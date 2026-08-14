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
| [0006](ADR/0006-app-config-toml-xdg-atomic-write.md) | Configuración TOML con rutas XDG y escritura atómica | Aceptada | 2026-08-09 |
| [0007](ADR/0007-device-change-event-contract.md) | Contrato de eventos de cambio de dispositivo (`DeviceChangeEvent`) | Aceptada | 2026-08-09 |
| [0008](ADR/0008-safe-persistence.md) | Persistencia segura: backups, verificación y rollback | Aceptada | 2026-08-12 |
| [0009](ADR/0009-optional-qt-tray-and-gio-notifications.md) | Bandeja Qt opcional y notificaciones Gio | Aceptada | 2026-08-13 |

## Cómo añadir un nuevo ADR

1. Copia la plantilla inferior.
2. Numera secuencialmente (`0010-...`).
3. Indica contexto, decisión, justificación y consecuencias.
4. Actualiza esta tabla.

## Plantilla

```markdown
# ADR-NNNN: Título corto

- **Estado:** Propuesta / Aceptada / Obsoleta
- **Fecha:** YYYY-MM-DD
- **Etapa/Incremento:** N

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
- **Nunca** enviar comandos Bluetooth propietarios o desconocidos: están
  prohibidos de forma absoluta; el análisis pasivo no habilita el envío de
  comandos.
- **Nunca** aplicar ingeniería inversa directamente sobre el dispositivo.
- **Nunca** modificar hardware.
- **Nunca** eliminar configuraciones existentes del sistema sin backup.
- **Nunca** sobrescribir archivos sin crear backup previo.
- **Nunca** asumir soporte para un códec o capacidad del dispositivo.
- **Todo** cambio sobre el sistema Linux debe poder revertirse.
