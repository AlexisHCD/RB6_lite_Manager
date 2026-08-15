# Caracterización física — Redmi Buds 6 Lite

> **Registro de evidencia empírica** con el dispositivo real conectado.
> Dos sesiones el **2026-08-11**:
>
> - **Sesión 1 (pasiva):** OpenBuds únicamente leyó; ninguna mutación de
>   OpenBuds (§1–§7).
> - **Sesión 2 (mutaciones controladas aprobadas):** verificación de solo
>   lectura primero y después mutaciones controladas bajo protocolo
>   previamente aprobado por el usuario (§8).
>
> Política de redacción (ambas sesiones): sin MAC, object paths, IDs runtime,
> payloads crudos, nombres de otros dispositivos ni logs AT vendor.

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

> La oferta de perfiles HSP/HFP es **runtime observada** del sistema (sesión 1);
> **no** es prueba funcional de HFP (la prueba funcional llegó en la sesión 2;
> ver §8).

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

Estado histórico al cierre de la **sesión 1 (pasiva)**. Los puntos resueltos en
las sesiones posteriores se marcan con **[sesión 2]** o **[sesión 3]** (detalles
en §6 y §9).

- [sesión 2] **HFP / micrófono** (Etapa 1, estado 4): en la sesión 1 solo se
  observó la oferta de perfiles HSP/HFP, sin prueba funcional.
- [sesión 2] **Desconexión/reconexión manual** como escenario de Etapa 1
  (estado 5).
- [sesión 3] **Desconectado estable** bajo el protocolo (Etapa 1, estado 1).
- [sesión 3] **Conectado sin reproducción dirigida al sink Bluetooth** (Etapa 1,
  estado 2); no equivale a silencio absoluto de todos los streams.
- **Suspensión/reanudación** de Ubuntu (estado 6): prueba ejecutada el
  2026-08-14; la sesión se recuperó, pero no hubo reconexión automática de los
  auriculares (ver §10).
- **Señales por cambio físico real**: la validación de señales/polling fue de
  **lifecycle** (sesión 1) y de suscripción correcta con hardware conectado
  (sesión 2); en esta sesión no se indujeron cambios durante `watch`.
- **RSSI positivo**: no disponible en esta sesión.
- **`api.bluez5.transport` con valor no vacío**: no observado.
- **AAC**: fuera del alcance aprobado; no probado.
- **Asociación robusta genérica** `Device1` ↔ nodos PipeWire: sin validar.

La Etapa 1 **no está completa**: los estados 1 y 2 (sesión 3), 3 (sesión 1),
4 y 5 (sesión 2) cuentan con evidencia; el estado 6 fue observado, pero no
superó el criterio de reconexión automática tras reanudar.

## 6. Sesión 3 (2026-08-13) — estados desconectado e idle

> **Método:** el usuario conectó manualmente los audífonos y autorizó una
> captura de solo lectura. No se reprodujo audio mediante OpenBuds ni se
> cambiaron perfiles, volumen, emparejamiento, configuración o servicios.
> No se indujo ninguna transición física durante `watch`.

### Estado 1 — emparejados y desconectados

- Antes de conectar: `openbuds devices` mostró el Redmi Buds 6 Lite como
  `desconectado / emparejado`.
- Tres muestras de `openbuds status`, separadas por aproximadamente 2 s,
  mantuvieron `Estado: emparejado` y todos los campos dependientes de conexión
  como `No disponible`.
- Resultado: **estable bajo el protocolo**.

### Estado 2 — conectados sin reproducción dirigida al dispositivo

- Pre-flight: servicio Bluetooth activo y adaptador sin bloqueo RF.
- Tres muestras de `openbuds status`, separadas por aproximadamente 2 s,
  mantuvieron `conectado`, batería agregada `100 %`, perfil `a2dp`, códec
  runtime `sbc`, un sink Bluetooth y ningún source Bluetooth.
- `openbuds health` terminó en `Estado global: OK`; la integración opt-in de
  solo lectura pasó completa.
- `pw-dump` mostró el nodo Bluetooth `Audio/Sink` en estado `running` y un
  `Stream/Output/Audio` del sistema también en `running`. Ese stream no expuso
  un destino Bluetooth identificable en las propiedades observadas.
- Resultado: **conectado sin reproducción dirigida al sink Bluetooth**, no
  silencio absoluto del sistema. La aplicación no inició reproducción ni
  modificó el perfil.

### Validaciones de software durante la sesión

- Suite de integraciones opt-in, sin mutaciones: pasada completa.
- No se guardaron MAC, object paths, IDs runtime ni payloads crudos.

## 7. Sesiones adicionales y pendientes

La evidencia de los estados 1 y 2 (sesión 3), junto con el estado 3 (A2DP/SBC
reproduciendo), fue **suficiente** para
continuar el desarrollo de Etapa 2 — detección, estado agregado, asociación
sink y reporte de A2DP/SBC. La **sesión 2** validó además los estados 4 y 5 y
la Etapa 2 completa contra hardware real. La Etapa 1 **no está completa**:
el estado 6 fue observado, pero no superó el criterio de reconexión automática
tras reanudar.

Estas sesiones solo se harán cuando una capacidad avanzada las requiera (con
aprobación):

1. Repetición o diagnóstico de suspensión y reanudación de Ubuntu, después de
   revisar la falta de reconexión automática observada en §10.
2. Observación de señales ante cambios físicos reales.
3. RSSI positivo, si el sistema lo expone.
4. `api.bluez5.transport` con valor no vacío, si el sistema lo expone.

## 8. Fuentes oficiales

- BlueZ D-Bus Device API:
  <https://git.kernel.org/pub/scm/bluetooth/bluez.git/tree/doc/org.bluez.Device.rst>
- BlueZ Battery API:
  <https://git.kernel.org/pub/scm/bluetooth/bluez.git/tree/doc/org.bluez.Battery.rst>
- BlueZ MediaTransport API:
  <https://git.kernel.org/pub/scm/bluetooth/bluez.git/tree/doc/org.bluez.MediaTransport.rst>

> Las fuentes oficiales contextualizan las propiedades observadas; la evidencia
> local de este registro (sesiones 2026-08-11 y 2026-08-13) es el dato fechado
> que prevalece.

## 9. Sesión 2 (2026-08-11) — validación de Etapa 2 con mutaciones controladas

> **Método:** verificación de solo lectura y estado inicial primero; después,
> mutaciones controladas (`connect`/`disconnect`/`music`/`mic` de OpenBuds)
> ejecutadas **exclusivamente bajo protocolo previamente aprobado por el
> usuario**. Ninguna mutación se ejecutó sin aprobación. La suite de gates
> completa pasó en verde antes de la sesión. Política de redacción idéntica a
> la sesión 1.
>
> Distinción metodológica: **sesión 1 = pasiva** (solo lectura); **sesión 2 =
> mutaciones controladas aprobadas** (interfaces estándar BlueZ D-Bus y perfil
> runtime de PipeWire; sin comandos propietarios).

**Objetivo:** validar físicamente la Etapa 2 (status, watch,
connect/disconnect/music/mic) y completar los estados 4 (HFP/mic) y 5
(desconexión/reconexión) de Etapa 1.

**Estado inicial:** conectado (el usuario reconectó manualmente, sin cambios de
sistema); `Battery1` 100 %; perfil `a2dp-sink`; códec `sbc`; RSSI no disponible;
transport vacío; perfiles ofrecidos (`pw-cli EnumProfile`): `off`,
`headset-head-unit`, `a2dp-sink`, `headset-head-unit-cvsd`,
`headset-head-unit-msbc`.

### Resolución dinámica de objetos PipeWire (hallazgo)

Los ids de objeto de PipeWire **cambian entre sesiones**; no son estables. La
resolución dinámica por `pw-dump`/`pw-cli` fue **necesaria y funcionó** (nada
hardcodeado). No se documentan números concretos (política de redacción).

### Prueba 1 — Estado 5: desconexión/reconexión (`disconnect`/`connect`)

- `openbuds disconnect` (org.bluez.Device1.Disconnect): exit 0; BlueZ
  `Connected=no`, `Paired=yes` (emparejamiento intacto); `openbuds status`
  reporta «emparejado» y batería/RSSI/perfil/códec/sink/source **«No
  disponible»** (correcto: no se inventan datos sin conexión).
- `openbuds connect` (org.bluez.Device1.Connect): exit 0; BlueZ
  `Connected=yes`; batería 100 %; `status` restaura perfil `a2dp` / códec
  `sbc`.

### Prueba 2 — Estado 4: micrófono HFP (`mic`/`music`)

- `openbuds mic`: exit 0; muestra la advertencia de degradación **antes** de
  aplicar; perfil HFP activo con códec **mSBC** (el caso de uso priorizó
  `headset-head-unit-msbc`, el códec HFP ofrecido de mayor calidad; PipeWire
  reporta en los nodos profile `headset-head-unit` + codec `msbc`); aparece el
  source Bluetooth; `status` → perfil `hfp`, códec `msbc (hfp)`, Source
  visible.
- `openbuds music`: exit 0; restaura perfil `a2dp-sink` + códec `sbc`; el
  source desaparece; `status` → `a2dp`/`sbc`, Source «No disponible».

### `watch` en esta sesión

La suscripción lifecycle ya estaba validada (sesión 1). Con hardware
conectado, `watch` **suscribe correctamente**; en esta sesión **no se
inducieron cambios durante `watch`**, por lo que **no** se afirma un evento
físico observado en vivo.

### Resultado y estado final

- Validación de Etapa 2 **completa**: `status` (Incremento 1), `watch`
  (Incremento 2) y `connect`/`disconnect`/`music`/`mic` (Incremento 3)
  probados contra hardware real con éxito.
- El dispositivo quedó en **A2DP** (estado óptimo); batería 100 % al cierre.
- RSSI y `api.bluez5.transport` siguen **no disponibles** — consistente con la
  sesión 1.
- Emparejamiento intacto durante toda la sesión: solo se mutó estado de
  conexión y perfil runtime, ambos reversibles.

## 10. Sesión 4 (2026-08-14) — suspensión y reanudación

> **Método:** prueba controlada con captura de solo lectura antes y después. No
> se cambiaron perfiles, volumen, emparejamiento ni configuración, y el usuario
> no intervino durante la espera. No se repitió el ciclo por protocolo.

- **Antes** (`2026-08-14T20:08:08-04:00`): Redmi Buds 6 Lite conectado,
  batería 100 %, RSSI no disponible, perfil `a2dp`, códec observado `sbc
  (a2dp)`, sink disponible y source no disponible; la GUI estaba activa y la
  gráfica actualizándose.
- La entrada de suspensión quedó registrada a las 20:10:00 y el retorno a las
  20:10:19 (aproximadamente 19 s).
- **Después:** la sesión se recuperó sin pantalla negra ni hard reset; la
  ventana siguió activa y respondía, la gráfica volvió y continuó actualizando,
  y, en esa versión de la GUI, el estado alternaba `Listo`/`Actualizando...`.
  El refresh periódico ahora se mantiene silencioso en segundo plano y deja
  `Listo` visible; los errores sanitizados y las acciones explícitas conservan
  su feedback.
- Los auriculares se desconectaron al suspender (comportamiento esperado), pero
  **no se reconectaron automáticamente** al reanudar. La consulta
  `openbuds devices --paired-only` terminó con exit 0 y mostró el dispositivo
  presente, confirmando que seguía emparejado en BlueZ pero desconectado. La lectura posterior de CLI también terminó con exit 0; batería, RSSI,
  perfil, códec, sink y source quedaron no disponibles.
- La consulta acotada de journal (system/user/kernel) terminó con exit 0 y mostró
  entrada/salida de suspensión y un error de E/S de BlueZ al retorno. También se
  observaron endpoints re-registrados; esto no se interpreta como capacidad de
  audio ni como reconexión exitosa.

**Resultado:** suspensión/reanudación de la sesión y la GUI recuperadas, pero el
criterio de reconexión automática no se cumplió. El estado 6 queda observado, no
aprobado como completo.
