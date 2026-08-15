# Diseño técnico — CLI `status` (estado agregado, Incremento 1 de Etapa 2)

- **Estado:** implementado en la **Etapa 2, Incremento 1**; validado con la
  evidencia pasiva de la **Etapa 1** (A2DP/SBC reproduciendo, 2026-08-11). Sin
  hardware conectado la CLI reporta 0 emparejados o campos «No disponible».
- **Tipo:** diseño de implementación (**Documentation First; implementado y
  verificado** — el código y los tests cumplen lo aquí especificado).
- **Documentos relacionados:** [Diseño del comando `devices`](devices-command.md),
  [Diseño del repositorio PipeWire](../pipewire/repository-design.md),
  [Caracterización pasiva](../research/redmi-buds-6-lite-passive-characterization.md),
  [ADR-0004](../ADR/0004-clean-architecture-dependency-rule.md) y
  [alcance de la beta](../../README.md#alcance-de-la-beta) y [límites de investigación](../RESEARCH_LIMITS.md).

> **Alcance:** comando de **solo lectura**. No discovery, no connect, no señales
> ni main loop GLib: usa el snapshot de BlueZ (`list_devices`) y la inspección de
> PipeWire (`pw-dump` vía repositorio). No escribe en el dispositivo ni en el
> sistema.

## 1. Objetivo y salida

`openbuds status [-h] [-a|--adapter ADAPTER]` lista los dispositivos
**emparejados** y muestra un bloque por dispositivo, sin MAC ni object paths:

```text
Dispositivo: Redmi Buds 6 Lite
Estado: conectado
Batería: 100%
RSSI: -45 dBm
Perfil: a2dp
Códec: sbc (a2dp)
Sink: Disponible
Source: No disponible
```

Campos opcionales: `Batería` y `RSSI` solo si hay valor; `Perfil`/`Códec` solo
si el códec está **verificado**; `Sink`/`Source` con disponibilidad estable por
`media.class`, sin exponer `node.name`; cualquier ausencia se muestra como **«No disponible»**. Sin
dispositivos emparejados imprime solo `No se encontraron dispositivos
emparejados.` y sale con **exit 0**.

## 2. Decisiones (registro del arquitecto)

1. **Solo códec verificado:** `CodecInfo.verified` es condición para mostrar
   perfil/códec; nunca se inventa ni infiere (`off` → sin códec).
2. **Disponibilidad real:** batería/RSSI solo si existen (opcionales en el
   agregado); ausente = «No disponible».
3. **Redacción de identificadores:** nunca MAC ni object paths; los nombres de
   nodo se sanitizan y los patrones de dirección se redactan (`<redacted>`).
4. **Asociación por MAC normalizada:** `api.bluez5.address` → `node.name` →
   `device.name` (precedencia), con `normalize_address` para comparación
   privada (`node_mapper.py`, funciones puras).
5. **Contrato tipado:** `DeviceAggregate` + `BluetoothAudioNode` en vez de
   dicts; perfil/códec/transporte se conservan tal cual se observan
   (`to_domain_node`), sin inferir.

## 3. Límites

- HFP/micrófono y los casos de uso Connect/Disconnect/Música/Micrófono están
  implementados como operaciones runtime controladas y reversibles manualmente.
- El códec es **solo observado** (runtime); `configuration_hex` vacío y byte
  `None` en este incremento. Sin hardware: «No disponible».
