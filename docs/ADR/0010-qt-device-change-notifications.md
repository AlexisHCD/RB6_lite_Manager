# ADR-0010: Notificaciones Qt automáticas de cambios de dispositivos

- **Estado:** Aceptada
- **Fecha:** 2026-08-13
- **Etapa/Incremento:** 3 — GUI MVP

## Contexto

El dominio ya define `DeviceChangeEvent` y el repositorio puede observar
cambios de dispositivos. `WatchDevicesUseCase` expone ese contrato a la capa de
presentación y `DesktopNotifier` ofrece una notificación freedesktop
best-effort. Faltaba conectar ambos lados con marshalling al hilo Qt y un
timeout finito para no esperar indefinidamente en una notificación, sin exponer
identificadores privados ni hacer que un servicio de notificaciones
ausente afectara a la ventana.

La GUI también necesita cerrar la suscripción antes de liberar el ViewModel.
El origen puede entregar una tanda inicial durante `subscribe`, y esa tanda
describe el estado inicial de la sesión, no transiciones que deban avisarse al
usuario.

## Decisión

Se adopta `DeviceChangeBridge`, un `QObject` de presentación que recibe el
origen `WatchDevicesUseCase` y un `DesktopNotifier` inyectados.

- La señal `device_change_received` se conecta explícitamente con
  `Qt.QueuedConnection`; el callback del repositorio solo construye y emite un
  sobre `(event, is_initial)`. El filtrado y la llamada al notificador ocurren
  en el slot del hilo Qt.
- La tanda inicial se marca mientras la suscripción está en curso bajo un lock.
  Sus eventos se descartan; un evento posterior a la frontera de suscripción no
  se suprime aunque Qt aún no haya procesado la cola.
- `close()` es idempotente, desuscribe antes de la limpieza del ViewModel y no
  invoca la desuscripción mientras mantiene el lock. Las carreras entre cierre
  y suscripción liberan la suscripción una sola vez y descartan callbacks
  tardíos.
- La composición por defecto crea un único `BlueZRepository` compartido por
  las consultas de estado y por `WatchDevicesUseCase`; no se abre un segundo
  repositorio para las notificaciones.

La política de eventos significativos es deliberadamente estrecha:

- `ADDED` produce «Dispositivo detectado».
- `REMOVED` produce «Dispositivo desaparecido».
- `UPDATED` solo produce notificación cuando cambia `connected`.
- Cambios únicamente de RSSI, batería u otras propiedades no producen
  notificación.

Los mensajes se construyen con nombres y etiquetas sanitizados, sin MAC,
rutas de objeto, identificadores dinámicos, credenciales ni payloads crudos.
Los fallos al suscribirse, desuscribirse o mostrar una notificación se registran
con mensajes genéricos y degradan la función; no cierran la GUI. `Notify` usa
un timeout de 1 s, aunque la creación perezosa del proxy sigue siendo síncrona.

## Alternativas rechazadas

- Conectar directamente el callback del repositorio al notificador: podría
  ejecutar trabajo de presentación desde el worker de GLib y dejar la GUI
  expuesta a carreras de hilos.
- Usar la conexión automática de señales de Qt sin declarar el tipo: oculta la
  frontera de hilos y hace menos verificable el contrato.
- Notificar cada `UPDATED`: produciría ruido por RSSI o batería y no representa
  una transición significativa para la ventana.
- Crear otro `BlueZRepository` para observar eventos: duplicaría conexiones,
  cachés y lifecycle sin aportar información adicional.
- Hacer que una falla del servicio freedesktop sea fatal: contradice el
  carácter opcional del notificador y reduciría la disponibilidad de la GUI.

## Consecuencias

Las notificaciones automáticas quedan integradas en la sesión de la ventana,
con marshalling explícito a Qt, privacidad por diseño y degradación segura. La
limpieza tiene una frontera clara: primero se cierra el puente y luego el
ViewModel.

La cobertura incluye tests unitarios con fakes para marshalling entre hilos,
supresión de la tanda inicial, frontera de suscripción, política ADDED/
REMOVED/UPDATED, sanitización, fallos del notificador, suscripción bloqueada,
cierre idempotente y carreras de lifecycle. El smoke de la GUI y la
integración disponible se ejecutan sin hardware; no se afirma haber probado
transiciones reales del dispositivo, suspensión o reanudación.

Esta es una funcionalidad de software read-only y session-only: no cambia
Bluetooth, audio, perfiles, servicios ni configuración persistente. No requiere
validación de hardware para cerrar este slice; la validación física de la
caracterización y su gate de suspensión permanecen independientes.
