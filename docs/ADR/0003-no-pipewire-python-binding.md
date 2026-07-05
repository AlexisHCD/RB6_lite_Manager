# ADR-0003: Sin binding Python de PipeWire — usar pw-dump/wpctl vía subprocess

- **Estado:** Aceptada
- **Fecha:** 2026-07-02
- **Fase:** 1

## Contexto

OpenBuds Manager necesita leer el estado del grafo de audio de PipeWire para:

- Identificar el códec Bluetooth activo (SBC, AAC, etc.).
- Listar los nodos de audio Bluetooth (sinks/sources).
- Leer propiedades como `device.profile`, `media.class`, `node.name`.

## Hallazgo

**No existe un binding Python oficial ni mantenido por el proyecto PipeWire.**

La API nativa es C (libpipewire), asíncrona y orientada a objetos. Las opciones
Python evaluadas:

| Opción | Estado | Veredicto |
|--------|--------|-----------|
| `pipewire_python` (pablodz) | Comunitario, **envuelve las CLI**, no es binding nativo | Insuficiente para inspección rica de propiedades Bluetooth |
| WirePlumber vía `gi.repository` (libwireplumber) | Teóricamente viable (GObject), pero **sin ejemplos ni soporte Python oficial** | No documentado; riesgoso |
| ctypes sobre libpipewire | Posible pero frágil (API C asíncrona, sin ABI estable) | Injustificable |

Fuente: [PipeWire API](https://docs.pipewire.org/page_api.html).

## Decisión

Usar **`pw-dump`** (salida JSON) y **`wpctl inspect <id>`** vía `subprocess` para
la inspección de solo lectura, y **`wpctl`** para acciones de control
(`set-default`, `set-profile`, `set-volume`).

- `pw-dump` vuelca **todo** el estado de PipeWire como un array JSON — ideal para
  parsing desde Python.
- `wpctl inspect <id>` muestra las propiedades detalladas de un objeto.
- `wpctl status` da un resumen legible de dispositivos y defaults.

Fuentes: [pw-dump(1)](https://docs.pipewire.org/page_man_pw-dump_1.html),
[pw-cli(1)](https://docs.pipewire.org/page_man_pw-cli_1.html).

## Justificación

1. **Fiabilidad:** las CLI son estables y documentadas oficialmente.
2. **Sin dependencias nativas:** evita el riesgo de un binding no mantenido.
3. **Suficiencia:** para **leer y optimizar** estado de audio Bluetooth, el
   parsing de `pw-dump` aporta toda la información disponible.
4. **Aislamiento:** los errores de parsing se contienen en
   `pipewire/pw_dump_parser.py`.

## Consecuencias

- **Positivas:** simple, fiable, sin dependencias frágiles.
- **Negativas:** overhead de subprocess (aceptable para inspección no frecuente);
  el parsing de JSON acoplado al esquema abierto de propiedades de PipeWire
  (se mitiga validando tipos en el parser).
- **Limitación documentada:** los nombres de propiedades runtime
  `api.bluez5.transport` y `bluez5.codec` **no están documentados formalmente**
  en pipewire.org (sí aparecen en salidas reales de `pw-dump`). Se validarán
  empíricamente en Fase 3/4. Ver [`RESEARCH_LIMITS.md`](../RESEARCH_LIMITS.md).

## Verificación local

```
pw-dump --version  →  Compiled with libpipewire 1.0.5
```

PipeWire 1.0.5 presente y `pw-dump` accesible en el entorno de desarrollo.
