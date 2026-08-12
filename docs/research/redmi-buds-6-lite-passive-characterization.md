# Caracterización física pasiva — Redmi Buds 6 Lite

> **Registro de evidencia empírica** con el dispositivo real conectado.
> Método **pasivo**: OpenBuds únicamente leyó; ninguna mutación de OpenBuds.
> Fecha: **2026-08-11**.
> Política de redacción: sin MAC, object paths, IDs runtime, payloads crudos,
> nombres de otros dispositivos ni logs AT vendor.

## 1. Alcance

- Observación pasiva del estado estándar (BlueZ D-Bus, PipeWire/WirePlumber)
  con el Redmi Buds 6 Lite **conectado y reproduciendo audio A2DP**.
- Alcance de códec aprobado: **SBC**. El sistema no ofreció AAC en esta sesión;
  no se probó ni cambió nada. Xiaomi declara AAC públicamente, pero la
  investigación AAC queda **fuera del alcance** de esta caracterización.
- No se evalúa calidad subjetiva: no se afirma que SBC sea mejor ni peor.
- Sin mutaciones de OpenBuds: sin cambio de perfil, sin volumen, sin
  disconnect/reconnect durante la caracterización, sin reinicios, sin
  configuración y sin comandos propietarios.
- La conexión fue **manual y previa**, autorizada explícitamente por el usuario
  mediante `bluetoothctl` estándar (no GNOME); la caracterización documentada
  es exclusivamente pasiva.

## 2. Entorno

| Componente | Detalle |
|------------|---------|
| SO | Ubuntu 24.04 (Noble Numbat) |
| Kernel | 6.17.0-22-generic |
| BlueZ | 5.72 |
| PipeWire | 1.0.5 |
| WirePlumber | 0.4.17 (configuración Lua) |
| Runtime | Python 3.12.3 con PyGObject/Gio |

## 3. Observado

### BlueZ (`Device1`)

- Dispositivo encontrado: `found` sí.
- `Connected=true`, `Paired=true`, `Trusted=true`, `Blocked=false`.
- `ServicesResolved=false` en la lectura puntual.
- 12 UUIDs de servicio presentes (no enumerados por política de redacción).
- `Battery1` disponible: **100 %**; `Source` vacío / no disponible.
- RSSI: **no disponible**.

### Batería por componente y estuche

- **Agregado (BlueZ):** `Battery1` ofrece **solo** `Percentage` (byte) y
  `Source` opcional en el object path `Device1`; la interfaz **no define**
  identidad left/right/case (fuente oficial:
  <https://github.com/bluez/bluez/blob/master/doc/org.bluez.Battery.rst>).
- **Observación local (BlueZ 5.72):** exactamente **1** `Battery1` en el único
  `Device1` del dispositivo: `Percentage=100`, `Source` vacío; `Device1.Sets`
  sin valor y **sin** objetos `Battery1` separados. **No es posible** atribuir
  el 100 % a L/R/estuche ni afirmar si es el mínimo o un agregado.
- **Fuente documental (Xiaomi FAQ oficial KA-237699):** la notification shade
  muestra la batería del auricular con **menor carga**; el teléfono Xiaomi puede
  mostrar batería de auriculares **y estuche**; left/right pueden **divergir**
  en la app. La FAQ describe el comportamiento de tapa/caja pero **no publica**
  protocolo ni UUID.
- **Conclusión:** función posible **solo como modelo degradable**:
  `aggregate_percentage` observado; `left`/`right`/`case` opcionales
  (`None`/No disponible). Obtener los tres exigiría que BlueZ/el estándar los
  exponga en el futuro **o** investigar el protocolo Xiaomi; esto último es
  actualmente **fuera de alcance/prohibido** (sin comandos propietarios o
  desconocidos, sin reverse engineering activo; no se leen/escriben UUID vendor
  ni se emula Xiaomi Earbuds).
- **Gap/decisión futura:** no se implementa aún ni se cambia `BatteryLevel`;
  queda registrado para un futuro contrato tipado de batería por componente.
  **No** se asume que el `Battery1` agregado representa el menor, aunque la
  notificación de Android pueda hacerlo según Xiaomi.

### PipeWire / audio

- **Exactamente un nodo** del dispositivo: `Audio/Sink`.
- Perfil activo: `a2dp-sink`.
- Propiedad runtime `api.bluez5.codec=sbc`.
- Propiedad runtime `api.bluez5.transport`: vacía / no utilizable.
- Sink `RUNNING`, formato `s16le`, **2 canales**, **44100 Hz**.
- Sin source Bluetooth / micrófono activo.

### Perfiles ofrecidos (`pactl`)

- `off`
- HSP/HFP genérico
- HSP/HFP CVSD
- HSP/HFP mSBC
- `A2DP Sink` (SBC) **activo**

> La oferta de perfiles HSP/HFP es **runtime observada** del sistema; **no** es
> prueba funcional de HFP.

### Estabilidad

- 3 muestras separadas por 2 s: estables (`connected=true`, 1 sink,
  A2DP/SBC).

## 4. Validaciones

### Integraciones opt-in

Todas las integraciones opt-in existentes pasaron (2026-08-11), con el
dispositivo conectado. Lista funcional:

- snapshot / protocolo BlueZ (D-Bus)
- mapper (objetos D-Bus → modelos)
- consultas del repositorio
- señales
- lifecycle / bus compartido
- CLI privacy (`openbuds devices`)
- `pw-dump` runner / parser / repository
- `wpctl` status / inspect

> Se registra la lista funcional y la fecha; **no** se mantiene un conteo como
> baseline permanente.

### CLI

- `openbuds devices`: mostró el dispositivo objetivo como
  `conectado / emparejado`, sin MAC ni object path.
- `openbuds doctor`: sistema / runtime / hardware **OK**.

## 5. Límites (no probado / pendiente)

- **Desconectado estable** bajo el protocolo (Etapa 1, estado 1).
- **Conectado idle formal** sin reproducir (Etapa 1, estado 2).
- **HFP / micrófono** (Etapa 1, estado 4): solo se observó la oferta de
  perfiles HSP/HFP; sin prueba funcional.
- **Señales por cambio físico real**: la validación de señales/polling fue de
  **lifecycle**, no de un evento físico.
- **Desconexión/reconexión manual** como escenario de Etapa 1 (estado 5).
- **Suspensión/reanudación** de Ubuntu (estado 6).
- **RSSI positivo**: no disponible en esta sesión.
- **`api.bluez5.transport` con valor no vacío**: no observado.
- **AAC**: fuera del alcance aprobado; no probado.
- **Asociación robusta genérica** `Device1` ↔ nodos PipeWire: sin validar.

La Etapa 1 **no está completa**: solo el estado 3 (A2DP/SBC reproduciendo)
cuenta con evidencia parcial.

## 6. Sesiones adicionales (diferidas)

La evidencia del estado 3 (A2DP/SBC reproduciendo) es **suficiente** para
continuar el desarrollo de Etapa 2 — detección, estado agregado, asociación
sink y reporte de A2DP/SBC — **sin reconectar** el dispositivo. La Etapa 1
**no está completa**: los estados restantes siguen **pendientes / diferidos**.

Estas sesiones se difieren y solo se harán cuando una capacidad avanzada las
requiera (con aprobación y método pasivo): HFP/mic, transiciones/señales,
suspensión, etc.

1. Emparejados y desconectados (estado estable bajo protocolo).
2. Conectados sin reproducir (idle formal).
3. Micrófono HFP (validación funcional; requiere escenario aprobado).
4. Desconexión y reconexión manuales.
5. Suspensión y reanudación de Ubuntu.
6. Observación de señales ante cambios físicos reales.
7. RSSI positivo, si el sistema lo expone.
8. `api.bluez5.transport` con valor no vacío, si el sistema lo expone.

## 7. Fuentes oficiales

- BlueZ D-Bus Device API:
  <https://git.kernel.org/pub/scm/bluetooth/bluez.git/tree/doc/org.bluez.Device.rst>
- BlueZ Battery API:
  <https://git.kernel.org/pub/scm/bluetooth/bluez.git/tree/doc/org.bluez.Battery.rst>
- BlueZ MediaTransport API:
  <https://git.kernel.org/pub/scm/bluetooth/bluez.git/tree/doc/org.bluez.MediaTransport.rst>

> Las fuentes oficiales contextualizan las propiedades observadas; la evidencia
> local de este registro (2026-08-11) es el dato fechado que prevalece.
