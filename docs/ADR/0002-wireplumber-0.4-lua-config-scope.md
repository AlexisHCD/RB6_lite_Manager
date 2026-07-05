# ADR-0002: WirePlumber 0.4 (Lua) — scope por usuario y política de backup/rollback

- **Estado:** Aceptada
- **Fecha:** 2026-07-02
- **Fase:** 1

## Contexto

El módulo de optimización (Fase 4) necesita editar la configuración de
WirePlumber para ajustar códecs, calidad SBC-XQ, perfiles Bluetooth, etc.
WirePlumber es el *session manager* de PipeWire y decide el ruteo y las policies.

### Hallazgo crítico de versiones

**Ubuntu 24.04 (Noble) incluye WirePlumber 0.4.17**, que usa el sistema de
configuración **Lua** (directorios `.lua.d/` con archivos como
`bluetooth.lua.d/50-bluez-config.lua`).

La versión **0.5.x** (más reciente, pero **no** la de Ubuntu 24.04) cambió
completamente el formato a `.conf.d/*.conf` y deprecó los scripts Lua.

Fuente: [packages.ubuntu.com/noble/wireplumber](https://packages.ubuntu.com/noble/wireplumber),
[Migrating configuration from 0.4](https://pipewire.pages.freedesktop.org/wireplumber/daemon/configuration/migration.html).

Usar la sintaxis 0.5 en Ubuntu 24.04 **rompería** la aplicación.

## Decisión

1. **Sintaxis:** usar exclusivamente la sintaxis **WirePlumber 0.4 (Lua)** para
   los overrides generados por la app. Bloque `bluez_monitor.properties` y
   `bluez_monitor.rules` en archivos `bluetooth.lua.d/*.lua`.

2. **Scope:** escribir **solo** en `~/.config/wireplumber/` (override por
   usuario). **Nunca** en `/usr/share/wireplumber/` (se sobrescribe al
   actualizar) ni en `/etc/wireplumber/` (requiere root y afecta a todos).

3. **Política de backup/rollback obligatoria:** todo cambio sigue el flujo
   `detect → backup → validate → apply → verify → rollback si error`. Si el
   backup falla, **no se aplica el cambio**.

4. **Recarga:** tras editar archivos estáticos, reiniciar el servicio de usuario
   (`systemctl --user restart wireplumber`). No existe `wpctl reload` genérico.

## Justificación

- **Seguridad (prioridad máxima del proyecto):** el scope por usuario no requiere
  root y no afecta a otros usuarios ni se pierde en actualizaciones del sistema.
- **Reversibilidad:** cada cambio va precedido de un backup timestamped; el
  rollback restaura el estado exacto anterior.
- **Corrección técnica:** la sintaxis 0.4 es la que funciona en el SO objetivo.

## Propiedades reales de WirePlumber 0.4 (verificadas)

Bloque `bluez_monitor.properties` en `bluetooth.lua.d/50-bluez-config.lua`:

```lua
bluez_monitor.properties = {
  ["bluez5.enable-sbc-xq"] = true,
  ["bluez5.enable-msbc"] = true,
  ["bluez5.codecs"] = "[ sbc sbc_xq aac ldac aptx aptx_hd ]",
  ["bluez5.default.rate"] = 48000,
  ["bluez5.default.channels"] = 2,
}
```

Reglas por dispositivo (bloque `bluez_monitor.rules`):

```lua
bluez_monitor.rules = {
  {
    matches = {
      { "device.name", "matches", "bluez_card.*" },
    },
    apply_properties = {
      ["bluez5.auto-connect"] = "[ hfp_hf hsp_hs a2dp_sink ]",
    },
  },
}
```

Fuente: [Bluetooth configuration — WirePlumber 0.4](https://pipewire.pages.freedesktop.org/wireplumber/configuration/bluetooth.html).

## Consecuencias

- **Positivas:** modificaciones seguras, reversibles y sin privilegios.
- **Negativas:** la app queda ligada a la sintaxis 0.4; si el usuario actualiza
  a WirePlumber 0.5 manualmente, los overrides dejarían de funcionar. Se
  detectará esto en `system/environment_detector.py` (campo
  `wireplumber_config_style`) y se advertirá al usuario.

## Detección dinámica

`environment_detector.detect()` resuelve el estilo de configuración desde la
versión de WirePlumber (`< 0.5` → `lua-0.4`; `>= 0.5` → `conf-0.5`) y lo expone
en `SystemInfo.wireplumber_config_style`. El módulo de optimización debe
verificar este campo antes de generar cualquier override.
