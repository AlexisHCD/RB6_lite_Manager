# Límites de la investigación (RESEARCH_LIMITS)

Este documento declara explícitamente las áreas donde la investigación técnica
**no pudo verificarse completamente** contra fuentes oficiales. El proyecto
sigue el principio de **nunca asumir** comportamientos no verificados: estos
puntos se validan empíricamente en sus etapas correspondientes antes de usarse
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
no como bytes. La identificación por byte se valida empíricamente en la Etapa 1
(caracterización física) y se consume en la Etapa 2.

Fuente: [media-api.txt](https://git.kernel.org/pub/scm/bluetooth/bluez.git/tree/doc/media-api.txt).

## 2. Propiedades runtime de PipeWire

**Estado:** no documentadas formalmente; el **parser de `pw-dump` las preserva
verbatim sin validar ni inferir (2026-08-10)**; el **caso positivo fue validado
empíricamente (2026-08-11)** para profile y codec; **`api.bluez5.transport` se
observó vacío/no utilizable** (no se validó un valor no vacío).

Los siguientes nombres de propiedades aparecen en **salidas reales de `pw-dump`**
(reportadas por la comunidad y confirmadas localmente), pero **no están
documentados** formalmente en pipewire.org ni en la documentación de WirePlumber:

- `api.bluez5.transport`
- `bluez5.codec` (como propiedad de nodo en runtime)

**Implicación:** no se asume su existencia ni su formato. El parser de
`pw-dump` (`pipewire/pw_dump_parser.py`,
[contrato](pipewire/pw-dump-parser-contract.md)) las **preserva verbatim**:
las pasa como `str` sin validar, sin inferir códec ni transporte y **sin
verificar** contra listas de códecs/transportes. **Validación 2026-08-11** con
el dispositivo conectado: el nodo `Audio/Sink` con perfil `a2dp-sink` expuso
`api.bluez5.codec=sbc`; `api.bluez5.transport` apareció **vacío/no utilizable**.
El valor de `bluez5.codec` coincide con los nombres de `bluez5.codecs` de
WirePlumber, pero la propiedad sigue sin documentación formal. El parser
continúa preservando verbatim, sin inferir códec ni transporte. Evidencia en
[`research/redmi-buds-6-lite-passive-characterization.md`](research/redmi-buds-6-lite-passive-characterization.md).

Las propiedades **sí documentadas** y seguras de usar son (de
[WirePlumber Bluetooth config 0.4](https://pipewire.pages.freedesktop.org/wireplumber/configuration/bluetooth.html)):

- `bluez5.codecs`, `bluez5.enable-sbc-xq`, `bluez5.a2dp.ldac.quality`,
  `bluez5.a2dp.aac.bitratemode`, `bluez5.auto-connect`, `bluez5.hfphsp-backend`,
  `bluez5.default.rate`, `bluez5.default.channels`.
- `device.profile` (valores: `a2dp-sink`, `headset-head-unit`).
- `device.name`, `node.name`, `media.class`.

## 3. Disponibilidad de batería

**Estado:** dependiente del dispositivo; **caso positivo validado (2026-08-11)**;
**batería por componente (L/R/estuche) no disponible** en la interfaz estándar.

La interfaz `org.bluez.Battery1` solo aparece si el dispositivo expone batería
vía:
- Servicio GATT Battery (UUID `0x180F`), o
- Comandos AT de HFP/AVRCP.

**Implicación:** no se asume que un dispositivo dado exponga batería. El código
debe tratar `Battery1` como opcional y degradar con elegancia (`BatteryLevel`
con `percentage=None`).

**Validación 2026-08-11:** con el Redmi Buds 6 Lite conectado se observó
`Battery1` con `Percentage=100` y `Source` vacío (no se documenta el mecanismo
GATT/AT subyacente). Sigue siendo opcional por dispositivo.

**Alcance (batería por componente y estuche):** `Battery1` define **solo**
`Percentage` (byte) y `Source` (opcional) en el object path `Device1`; la
interfaz **no define** identidad left/right/case. En la sesión 2026-08-11 se
observó **exactamente un** `Battery1` en el único `Device1` (`Percentage=100`,
`Source` vacío) y **ningún** objeto `Battery1` separado; por tanto **no** se
puede atribuir el valor a L/R/estuche ni afirmar si es el mínimo o un agregado.
La Xiaomi FAQ oficial KA-237699 describe que la notification shade muestra el
auricular con menor carga y que un teléfono Xiaomi puede mostrar batería de
auriculares y estuche (left/right pueden divergir en la app), pero **no publica**
protocolo ni UUID.

**Conclusión:** la batería por componente solo es posible como modelo
**degradable** (`aggregate_percentage` observado; `left`/`right`/`case`
opcionales `None`/No disponible). Obtener los tres exigiría que BlueZ/el
estándar los exponga en el futuro **o** investigar el protocolo Xiaomi
(actualmente **fuera de alcance/prohibido**: sin comandos propietarios o
desconocidos, sin reverse engineering activo, sin leer/escribir UUID vendor ni
emular Xiaomi Earbuds). **No** se asume que el agregado represente el menor,
aunque la notificación de Android pueda hacerlo según Xiaomi. `BatteryLevel` no
se modifica en este incremento; queda registrado como gap para un futuro
contrato tipado de batería de componentes.

Fuente: [battery-api.txt](https://git.kernel.org/pub/scm/bluetooth/bluez.git/tree/doc/battery-api.txt)
y [org.bluez.Battery.rst](https://github.com/bluez/bluez/blob/master/doc/org.bluez.Battery.rst).

## 4. Fiabilidad de señales D-Bus

**Estado:** señal primaria y **respaldo por polling implementados y verificados
(2026-08-10)**; con hardware conectado (2026-08-11) la validación fue de
**lifecycle A/B**, **no** de un evento físico real.

En ciertas situaciones, la señal `PropertiesChanged` de BlueZ puede no llegar.
Como respaldo, se implementó **polling periódico** de propiedades críticas
(`Connected`, `Paired`, `Trusted`) además de la suscripción a señales.

**Implicación:** el repositorio Bluetooth implementa la **señal primaria**
(`BlueZRepository.subscribe_device_changes`: refresh completo por señal + diff
de snapshots; ver [repository-design §6](bluez/repository-design.md#6-subscribe_device_changes--implementado-incremento-2))
**y el respaldo por polling** (extensión interna compatible
`on_poll`/`poll_interval_ms`, `GSource` de timeout monotónico en el worker, un
solo timer por repositorio y pipeline común señal/poll;
[signal-lifecycle-design §12](bluez/signal-lifecycle-design.md#12-polling-de-respaldo-implementado-y-verificado-2026-08-10)
y [repository-design §12](bluez/repository-design.md#12-polling-de-respaldo-del-repositorio-implementado-y-verificado-2026-08-10)).
La **validación de evento físico real sigue pendiente**: la caracterización
pasiva 2026-08-11 solo validó el **lifecycle A/B** (subscribe/unsubscribe/close
+ snapshot A/B) con `Connected=true` coincidente; no se indujeron cambios
físicos (sin desconexión/reconexión, sin encendido/apagado ni suspensión).
Todavía **no** se afirma que la señal o el poll capturen transiciones
`connected`→`disconnected` reales (Etapa 1, estados 4–6). Evidencia en
[`research/redmi-buds-6-lite-passive-characterization.md`](research/redmi-buds-6-lite-passive-characterization.md).

Fuente: discusiones de la comunidad; el mecanismo base está en la
[DBus specification](https://dbus.freedesktop.org/doc/dbus-specification.html).

## 5. Versión de librerías Python (2026)

**Estado:** rangos inferidos, no confirmados directamente.

Las versiones exactas más recientes de `python-sdbus` y `dbus-next` en 2026 se
inferieron de búsquedas (sdbus ~0.11.x, dbus-next 0.2.3) pero no se confirmaron
contra PyPI por timeouts. **No afectan a la decisión** (ADR-0001 usa
PyGObject/Gio, que es parte del stack GNOME y sí está verificada).

## 6. Perfil Redmi Buds 6 Lite

**Estado:** descriptivo con **evidencia runtime parcial (2026-08-11)**.

Los datos del perfil `redmi_buds_6_lite.yaml` (versión Bluetooth, códecs,
capacidades) provienen de **fuentes públicas no oficiales**. Cada campo no
verificado se marca con `verified: false`. El contrato y el YAML están
**bloqueados**: no se validarán en campo hasta aprobar la propuesta tipada del
contrato (ver el gate en [`ROADMAP.md`](ROADMAP.md)).

**Evidencia runtime observada (2026-08-11, pasiva):** perfil activo
`a2dp-sink` con códec `sbc` (un único nodo `Audio/Sink`, 2 canales / 44100 Hz);
perfiles ofrecidos por el sistema: `off`, HSP/HFP genérico, HSP/HFP CVSD,
HSP/HFP mSBC y A2DP Sink SBC. La oferta HSP/HFP es **runtime**, no prueba
funcional. Siguen pendientes: HFP/micrófono, desconectado estable, RSSI
positivo, `api.bluez5.transport` con valor y AAC (fuera del alcance aprobado).
Evidencia en
[`research/redmi-buds-6-lite-passive-characterization.md`](research/redmi-buds-6-lite-passive-characterization.md).

**Importante:** el proyecto **nunca** envía comandos al dispositivo para
"probar" funciones. La validación es **pasiva** (lectura de estado estándar).

---

## Principio rector

> Ante la incertidumbre, **detener** la implementación, **documentar** la
> limitación y **proponer un plan de investigación**, en lugar de asumir un
> comportamiento. Esta es una regla explícita del proyecto.
