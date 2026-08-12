# Diseño técnico — CLI `watch` (eventos en vivo, Incremento 2 de Etapa 2)

- **Estado:** implementado en la **Etapa 2, Incremento 2**; **solo lectura**
  (reutiliza el backend de señales/polling BlueZ de la Etapa 0). Probado real:
  imprime el mensaje inicial y espera; sin hardware no llegan eventos (válido).
- **Tipo:** diseño de implementación (**Documentation First; implementado y
  verificado** — el código y los tests cumplen lo aquí especificado).
- **Documentos relacionados:** [Diseño del comando `status`](status-command.md),
  [señales y lifecycle BlueZ](../bluez/signal-lifecycle-design.md),
  [repositorio BlueZ](../bluez/repository-design.md),
  [ADR-0007](../ADR/0007-device-change-event-contract.md) y
  [AGENTS.md](../../AGENTS.md) §3/§5.

> **Alcance:** comando de **solo lectura**: suscribe callbacks (hilo worker,
> señal primaria + polling de respaldo), sin discovery, connect ni escrituras.

## 1. Objetivo y salida

`openbuds watch [-a|--adapter ADAPTER]` observa en vivo los cambios de los
dispositivos conocidos por BlueZ e imprime los eventos, sin MAC ni object paths:

```text
Observando cambios de dispositivos... (Ctrl+C para salir)
[apareció] Redmi Buds 6 Lite: emparejado
[cambio] Redmi Buds 6 Lite: conectado (conexión: emparejado → conectado)
[desapareció] Redmi Buds 6 Lite
Watch finalizado.
```

Eventos: `[apareció] <nombre>: <estado>` (ADDED), `[cambio] <nombre>: <estado>`
(UPDATED; añade `(conexión: <prev> → <nuevo>)` cuando cambia `connected`) y
`[desapareció] <nombre>` (REMOVED). `-a/--adapter` filtra por adaptador; Ctrl+C
finaliza con `unsubscribe()` idempotente en `finally` y **exit 0**.

## 2. Decisiones (registro del arquitecto)

1. **Suscripción delegada:** `WatchDevicesUseCase.subscribe(callback) ->
   Unsubscribe` delega en `subscribe_device_changes`; use case delgado.
2. **Filtro por adaptador en presentación:** el callback compara
   `adapter_path`; el caso de uso no filtra.
3. **Redacción de identificadores:** nunca MAC ni object paths; `_ADDRESS` se
   sustituye por `<redacted>` y el nombre se sanitiza (igual que `status`).
4. **Formato de eventos:** ADDED/UPDATED/REMOVED con sufijo de conexión solo si
   cambia `connected`; estados `conectado`/`emparejado`/`desconectado`.
5. **Ctrl+C seguro:** bucle de espera con `threading.Event`;
   `KeyboardInterrupt` capturado y `unsubscribe()` idempotente en `finally`.

## 3. Límites

- Sin hardware no llegan eventos (válido: la suscripción funciona, nada cambia).
- Solo eventos; **no** imprime estado agregado (para eso está `status`).
- `PipeWireRepository.get_default_audio_sink()` está implementado (vía `wpctl
  inspect @DEFAULT_AUDIO_SINK@`, parseando `node.name`; `None` sin WirePlumber)
  pero **aún no expuesto** en `status`/Health; se consumirá en incrementos
  posteriores.
- HFP/micrófono y los casos de uso Connect/Disconnect/Música/Micrófono **no**
  están implementados.
