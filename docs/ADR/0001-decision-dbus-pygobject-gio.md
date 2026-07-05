# ADR-0001: Biblioteca de acceso a D-Bus — PyGObject/Gio (GDBus)

- **Estado:** Aceptada
- **Fecha:** 2026-07-02
- **Fase:** 1

## Contexto

OpenBuds Manager necesita comunicarse con BlueZ a través de D-Bus (bus del
sistema) para listar adaptadores y dispositivos, leer propiedades (conexión,
batería, RSSI, códec) y suscribirse a señales de cambio (`PropertiesChanged`,
`InterfacesAdded`, `InterfacesRemoved`).

La aplicación también usa PySide6/Qt para la GUI. Se necesita una biblioteca
D-Bus que sea robusta, mantenida y que integre bien con el event loop de Qt.

## Opciones consideradas

| Biblioteca | Backend | Estado (2026) | Notas |
|------------|---------|----------------|-------|
| **PyGObject / Gio (GDBus)** | libgio (GLib) | Mantenida, parte del stack GNOME | Asíncrona, robusta, integrable con Qt |
| python-sdbus | sd-bus (systemd) | Activamente mantenida (~0.11.x) | API async pythonica, pero usa asyncio (no Qt loop) |
| dbus-next | Python puro | Estancada (~0.2.3) | Sin dependencias nativas, pero desarrollo detenido |
| pydbus | PyGI/GDBus | **Abandonada** (último release 2016) | No usar |
| dbus-python | libdbus | Legada, deprecándose | Evitar para código nuevo |

Fuentes: [freedesktop.org DBusBindings](https://www.freedesktop.org/wiki/Software/DBusBindings/),
[python-sdbus](https://github.com/python-sdbus/python-sdbus).

## Decisión

Usar **PyGObject / Gio (GDBus)**.

## Justificación

1. **Mantenimiento y madurez:** es parte del stack GNOME, ampliamente usada y
   mantenida a largo plazo. No hay riesgo de abandono.
2. **Integración con Qt:** GDBus puede ejecutarse con su propio `GMainLoop` o
   puentearse hacia el `QEventLoop`. Aunque hay dos loops, es un patrón conocido
   y documentado.
3. **Soporte de señales:** las suscripciones a `PropertiesChanged` y
   `InterfacesAdded` son fiables y eficientes.
4. **Disponibilidad en Ubuntu 24.04:** PyGObject está en los repositorios
   oficiales (`python3-gi`, `gir1.2-glib-2.0`).

## Consecuencias

- **Positivas:** biblioteca robusta, bien documentada, con futuro garantizado.
- **Negativas:** PyGObject requiere paquetes de sistema (`libgirepository1.0-dev`)
  que no siempre se instalan limpiamente vía pip; se documenta la alternativa
  `apt` en el README. Hay que gestionar la convivencia de dos event loops
  (GLib + Qt) en la GUI — se aborda en Fase 3/6.

## Verificación

- `bluetoothctl --version` → 5.72 (BlueZ presente y accesible).
- El paquete `python3-gi` está disponible en Ubuntu 24.04.
