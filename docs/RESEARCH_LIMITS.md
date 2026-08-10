# Límites de la investigación (RESEARCH_LIMITS)

Este documento declara explícitamente las áreas donde la investigación técnica
**no pudo verificarse completamente** contra fuentes oficiales. El proyecto
sigue el principio de **nunca asumir** comportamientos no verificados: estos
puntos se validan empíricamente en sus fases correspondientes antes de usarse
para decisiones de optimización o para interactuar con hardware.

## 1. Bytes de códec A2DP vendor-specific

**Estado:** parcialmente verificado.

| Códec | Byte A2DP | Verificado |
|-------|-----------|------------|
| SBC | 0x00 | ✅ Sí — estándar A2DP obligatorio |
| AAC | 0x02 | ✅ Sí — A2DP v1.3 |
| aptX | (vendor) | ❌ No canonizado en el estándar |
| aptX HD | (vendor) | ❌ No canonizado |
| LDAC | (vendor) | ❌ No canonizado |

**Implicación:** los códecs aptX/LDAC dependen de endpoints registrados por
PipeWire/WirePlumber (no por BlueZ). Su byte numérico no está definido
canónicamente en `doc/media-api.txt`. El enum `CodecType` los incluye como
identificadores de **nombre** (coinciden con `bluez5.codecs` de WirePlumber 0.4),
no como bytes. La identificación por byte se valida empíricamente en Fase 3/4.

Fuente: [media-api.txt](https://git.kernel.org/pub/scm/bluetooth/bluez.git/tree/doc/media-api.txt).

## 2. Propiedades runtime de PipeWire

**Estado:** no documentadas formalmente.

Los siguientes nombres de propiedades aparecen en **salidas reales de `pw-dump`**
(reportadas por la comunidad), pero **no están documentados** formalmente en
pipewire.org ni en la documentación de WirePlumber:

- `api.bluez5.transport`
- `bluez5.codec` (como propiedad de nodo en runtime)

**Implicación:** no se asume su existencia ni su formato. Se validan
empíricamente en Fase 3/4 inspeccionando `pw-dump` con un dispositivo conectado.

Las propiedades **sí documentadas** y seguras de usar son (de
[WirePlumber Bluetooth config 0.4](https://pipewire.pages.freedesktop.org/wireplumber/configuration/bluetooth.html)):

- `bluez5.codecs`, `bluez5.enable-sbc-xq`, `bluez5.a2dp.ldac.quality`,
  `bluez5.a2dp.aac.bitratemode`, `bluez5.auto-connect`, `bluez5.hfphsp-backend`,
  `bluez5.default.rate`, `bluez5.default.channels`.
- `device.profile` (valores: `a2dp-sink`, `headset-head-unit`).
- `device.name`, `node.name`, `media.class`.

## 3. Disponibilidad de batería

**Estado:** dependiente del dispositivo.

La interfaz `org.bluez.Battery1` solo aparece si el dispositivo expone batería
vía:
- Servicio GATT Battery (UUID `0x180F`), o
- Comandos AT de HFP/AVRCP.

**Implicación:** no se asume que un dispositivo dado exponga batería. El código
debe tratar `Battery1` como opcional y degradar con elegancia (`BatteryLevel`
con `percentage=None`).

Fuente: [battery-api.txt](https://git.kernel.org/pub/scm/bluetooth/bluez.git/tree/doc/battery-api.txt).

## 4. Fiabilidad de señales D-Bus

**Estado:** mayoritariamente fiable, con respaldo recomendado.

En ciertas situaciones, la señal `PropertiesChanged` de BlueZ puede no llegar.
Como respaldo, se recomienda **polling periódico** de propiedades críticas
(`Connected`, `Paired`, `Trusted`) además de la suscripción a señales.

**Implicación:** el repositorio Bluetooth implementa suscripción a señales
(primario) + polling periódico (respaldo) en Fase 3.

Fuente: discusiones de la comunidad; el mecanismo base está en la
[DBus specification](https://dbus.freedesktop.org/doc/dbus-specification.html).

## 5. Versión de librerías Python (2026)

**Estado:** rangos inferidos, no confirmados directamente.

Las versiones exactas más recientes de `python-sdbus` y `dbus-next` en 2026 se
inferieron de búsquedas (sdbus ~0.11.x, dbus-next 0.2.3) pero no se confirmaron
contra PyPI por timeouts. **No afectan a la decisión** (ADR-0001 usa
PyGObject/Gio, que es parte del stack GNOME y sí está verificada).

## 6. Perfil Redmi Buds 6 Lite

**Estado:** descriptivo, no verificado empíricamente.

Los datos del perfil `redmi_buds_6_lite.yaml` (versión Bluetooth, códecs,
capacidades) provienen de **fuentes públicas no oficiales**. Cada campo no
verificado se marca con `verified: false`. Se validan empíricamente en Fase 7
conectando un dispositivo real y observando BlueZ/PipeWire.

**Importante:** el proyecto **nunca** envía comandos al dispositivo para
"probar" funciones. La validación es **pasiva** (lectura de estado estándar).

---

## Principio rector

> Ante la incertidumbre, **detener** la implementación, **documentar** la
> limitación y **proponer un plan de investigación**, en lugar de asumir un
> comportamiento. Esta es una regla explícita del proyecto.
