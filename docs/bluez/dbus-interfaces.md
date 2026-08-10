# Interfaces D-Bus de BlueZ — referencia verificada

Referencia de las interfaces D-Bus de BlueZ usadas por OpenBuds Manager. Todos
los datos provienen de la documentación oficial de BlueZ y se verificaron contra
la instalación local (BlueZ 5.72 en Ubuntu 24.04).

> Servicio D-Bus: **`org.bluez`** · Bus: **system** · ObjectManager en raíz **`/`**

Fuentes principales:
- [device-api](https://bluez.readthedocs.io/en/latest/device-api/)
- [adapter-api](https://bluez.readthedocs.io/en/latest/adapter-api/)
- [battery-api.txt](https://git.kernel.org/pub/scm/bluetooth/bluez.git/tree/doc/battery-api.txt)
- [media-api.txt](https://git.kernel.org/pub/scm/bluetooth/bluez.git/tree/doc/media-api.txt)

## Interfaces y rutas de objeto

| Interfaz | Object path | Uso |
|----------|-------------|-----|
| `org.bluez.Adapter1` | `/org/bluez/hciX` | Un controlador local |
| `org.bluez.Device1` | `/org/bluez/hciX/dev_XX_XX_XX_XX_XX_XX` | Dispositivo remoto |
| `org.bluez.Battery1` | (debajo del dispositivo) | Solo si el dispositivo expone batería |
| `org.bluez.MediaTransport1` | `.../sepX/fdX` | Flujo de audio A2DP/SCO activo |
| `org.bluez.MediaPlayer1` | `.../playerX` | AVRCP: reproductor remoto |
| ~~`org.bluez.MediaControl1`~~ | — | **DEPRECATED.** No usar. |

## Propiedades de `Adapter1`

| Propiedad | Tipo | Acceso |
|-----------|------|--------|
| `Address` | string | readonly |
| `Name` | string | readonly |
| `Alias` | string | readwrite |
| `Class` | uint32 | readonly |
| `Powered` | boolean | readwrite |
| `Discoverable` | boolean | readwrite |
| `Pairable` | boolean | readwrite |
| `Discovering` | boolean | readonly |
| `UUIDs` | array{string} | readonly |
| `AddressType` | string | readonly |

## Propiedades de `Device1`

| Propiedad | Tipo | Acceso | Notas |
|-----------|------|--------|-------|
| `Address` | string | readonly | MAC del dispositivo |
| `AddressType` | string | readonly | `public` / `random` |
| `Name` | string | readonly | Puede no estar hasta resolver servicios |
| `Alias` | string | **readwrite** | |
| `Class` | uint32 | readonly | Codificación Major/Minor Service |
| `Appearance` | uint16 | readonly | |
| `Icon` | string | readonly | `audio-card`, `input-keyset`, ... |
| `Paired` | boolean | readonly | |
| `Connected` | boolean | readonly | |
| `Trusted` | boolean | readwrite | |
| `Blocked` | boolean | readwrite | |
| `RSSI` | int16 | readonly | Durante/después de descubrimiento |
| `TxPower` | int16 | readonly | |
| `UUIDs` | array{string} | readonly | Vacío hasta `ServicesResolved == true` |
| `ServicesResolved` | boolean | readonly | |
| `Adapter` | object path | readonly | |

## `Battery1`

```
Service     org.bluez
Interface   org.bluez.Battery1
Properties  byte    Percentage [readonly]   # 0-100
            string  Source     [readonly]   # "GATT Battery Service", "HFP", "AVRCP"
```

**Disponibilidad:** solo aparece si el dispositivo expone batería (GATT 0x180F
o AT commands de HFP/AVRCP). No es universal. Ver [RESEARCH_LIMITS.md](../RESEARCH_LIMITS.md#3).

## `MediaTransport1`

| Propiedad | Tipo | Notas |
|-----------|------|-------|
| `Device` | object path | |
| `UUID` | string | `0000110a-...` (A2DP), `0000111e-...` (HFP) |
| `Codec` | byte | **Identificador del códec activo.** SBC=0x00, AAC=0x02 |
| `Configuration` | array{byte} | Blob de config específica del códec |
| `State` | string | `idle` / `pending` / `active` |
| `Delay` | uint16 | |
| `Volume` | uint16 | readwrite |

> SBC es obligatorio en A2DP. AAC/aptX/LDAC solo aparecen si PipeWire/WirePlumber
> registra el endpoint correspondiente. Los bytes vendor (aptX/LDAC) no están
> canonizados — ver [RESEARCH_LIMITS.md](../RESEARCH_LIMITS.md#1).

## Señales estándar (freedesktop)

| Señal | Interfaz | Cuándo |
|-------|----------|-------|
| `InterfacesAdded(obj_path, dict)` | `ObjectManager` | Nuevo dispositivo/servicio |
| `InterfacesRemoved(obj_path, [iface])` | `ObjectManager` | Eliminación |
| `PropertiesChanged(iface, changed, invalidated)` | `Properties` | Cambio de cualquier propiedad |

## Mapeo en OpenBuds Manager

| Concepto del dominio | Fuente BlueZ |
|----------------------|--------------|
| `AdapterInfo` | `Adapter1` (propiedades) |
| `DeviceInfo` | `Device1` (propiedades) |
| `BatteryLevel` | `Battery1.Percentage` / `Battery1.Source` |
| `RSSIReading` | `Device1.RSSI` / `Device1.TxPower` |
| `CodecInfo` | `MediaTransport1.Codec` + PipeWire (`device.profile`) |
| Cambios de conexión | `PropertiesChanged` en `Device1.Connected` |

## Comandos CLI de verificación (solo lectura)

```bash
# Listar objetos gestionados por BlueZ
busctl tree org.bluez

# Batería de un dispositivo
dbus-send --system --dest=org.bluez --print-reply \
  /org/bluez/hci0/dev_XX_XX_XX_XX_XX_XX \
  org.freedesktop.DBus.Properties.Get \
  string:"org.bluez.Battery1" string:"Percentage"

# Inspección interactiva
bluetoothctl
> menu transport
> list
> show
```

## `btmon` (captura HCI pasiva)

`btmon` es el monitor de tráfico HCI (pasivo, solo lectura). Requiere
`CAP_NET_RAW` o root. Útil para auditar qué códec se negocia a bajo nivel.

- `btmon -w <file>` — guardar en btsnoop
- `btmon -A` — dump de tráfico A2DP
- `btmon -S` — dump SCO (HFP)

> **No confundir** con `bluetoothctl --monitor` (que activa el *Advertisement
> Monitor* de BlueZ para filtrar anuncios BLE por RSSI, no captura HCI).

Fuente: `btmon(1)`, `bluetoothctl(1)` — verificado en los binarios locales.
