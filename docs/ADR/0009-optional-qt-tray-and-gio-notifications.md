# ADR-0009: Bandeja Qt opcional y notificaciones Gio

- **Estado:** Aceptada
- **Fecha:** 2026-08-13
- **Fase:** 3 (GUI MVP, slice post-MVP)

## Contexto

La GUI de Etapa 3 necesitaba un acceso opcional desde la bandeja y una
frontera pequeña para mostrar notificaciones de escritorio. El entorno puede no
ofrecer una bandeja usable y el servicio de notificaciones de la sesión puede
no estar disponible. Además, el contrato de eventos de cambio de dispositivo
ya existe, pero su callback se entrega en el contexto de señales de Gio y no se
debe tocar Qt desde ese callback ([ADR-0007](0007-device-change-event-contract.md)).

La solución debía conservar el alcance de seguridad del proyecto: no controlar
hardware automáticamente, no cambiar perfiles, servicios o configuración, y
no añadir dependencias específicas de GNOME.

## Decisión

Se acepta una implementación opcional y best-effort en `presentation`:

- La bandeja usa `PySide6.QtWidgets.QSystemTrayIcon`, `QMenu` y `QAction`.
  Antes de crearla se consulta `QSystemTrayIcon.isSystemTrayAvailable()`; si
  devuelve falso, el arranque continúa con la ventana sin bandeja. El menú
  ofrece **Abrir ventana**, **Actualizar**, **Diagnóstico** y **Salir**.
- Las acciones de bandeja delegan en `MainWindow`/ViewModel. No ejecutan
  mutaciones automáticas de Bluetooth, audio, perfiles, servicios ni
  configuración. El cierre sigue siendo un cierre normal de la aplicación y no
  oculta silenciosamente la ventana en un proceso residente.
- El icono concreto usa el icono estándar de volumen de Qt; no se añade un
  recurso binario ni una dependencia nueva. La limpieza oculta y separa la
  bandeja antes de cerrar el worker del ViewModel; es best-effort e idempotente.
- `DesktopNotifier` implementa `org.freedesktop.Notifications` sobre el bus de
  sesión mediante Gio/GDBus y `GLib.Variant`, con imports perezosos. Sanitiza
  los campos visibles y absorbe la ausencia del servicio o los fallos de la
  llamada con una advertencia genérica.
- No se añade una dependencia directa de Ayatana/AppIndicator ni se implementa
  manualmente `StatusNotifierItem`.
- Las notificaciones automáticas derivadas de `DeviceChangeEvent` quedan
  explícitamente diferidas. En este slice `MainWindow` no se suscribe a eventos
  de BlueZ y el refresco de 2 segundos no emite notificaciones. Requieren una
  decisión e incremento posterior para un puente explícito del ciclo de vida
  Qt/GLib y el *marshalling* seguro hacia el hilo de Qt.

La API `QSystemTrayIcon` documenta la disponibilidad del sistema y el ciclo de
vida del icono ([Qt for Python — QSystemTrayIcon](https://doc.qt.io/qtforpython-6/PySide6/QtWidgets/QSystemTrayIcon.html)). El adaptador sigue la interfaz de sesión y la llamada `Notify` descritas por la [Desktop Notifications Specification 1.3](https://specifications.freedesktop.org/notification/1.3/), sin asumir que exista un servidor disponible.

## Alternativas

### Ayatana/AppIndicator directo

No adoptado. Puede integrarse mejor con ciertos escritorios GNOME, pero añade
un proveedor y una dependencia específica de plataforma para una capacidad
opcional. No es necesario para el menú actual.

### `StatusNotifierItem` manual

No adoptado. Evita una dependencia adicional, pero obliga a mantener el
protocolo D-Bus, menús y ciclo de vida manualmente. Aumenta la superficie de
integración y el riesgo de errores sin aportar una necesidad del MVP.

### `QSystemTrayIcon`

Adoptado. Forma parte de PySide6, encaja con el ciclo de vida de la ventana y
permite degradar limpiamente cuando la bandeja no está disponible. Sus
limitaciones de integración se aceptan porque la bandeja es opcional.

## Consecuencias

### Positivas

- La ventana sigue funcionando en entornos sin bandeja.
- El menú reutiliza las mismas acciones y confirmaciones de la ventana.
- Las notificaciones usan un estándar de escritorio y no obligan a incorporar
  un proveedor de indicadores.
- Los fallos de integración se degradan a ausencia de bandeja o una advertencia
  genérica, sin exponer datos sensibles.

### Negativas y pendientes

- `QSystemTrayIcon` depende de lo que soporte el entorno de escritorio.
- El servidor de notificaciones es opcional y puede rechazar o no mostrar una
  notificación.
- Todavía no existe una ruta segura para convertir `DeviceChangeEvent` en una
  llamada Qt. Esa automatización queda fuera de este incremento y requiere
  diseño, validación de hilos y decisión explícita.

## Seguridad y lifecycle

La bandeja solo presenta acciones delegadas y no cambia por sí misma el estado
del sistema ni del dispositivo. El cierre de la ventana detiene el refresco,
cierra el diálogo de diagnóstico, libera la bandeja y después limpia el worker
del ViewModel. Repetir la limpieza no debe lanzar errores; los fallos de
desacoplar u ocultar el icono se tratan como best-effort.

El notificador no abre el bus al importar el módulo: crea el proxy solo al
primer uso. Sanitiza resumen y cuerpo antes de construir el `GVariant`, y no
registra la excepción cruda si el servicio no existe o falla.

## Verificación

La bandeja se verificó con fakes y Qt en modo `offscreen`: ausencia de bandeja
como no-op seguro, creación del menú y sus cuatro acciones, activación que abre
la ventana, icono estándar no nulo y limpieza idempotente incluso ante errores
de limpieza. El notificador se verificó con un proxy y una fábrica de variantes
falsos: creación perezosa, forma estándar de `Notify`, reutilización del proxy,
sanitización y absorción de fallos sin registrar datos crudos. Las pruebas no
requieren hardware Bluetooth ni D-Bus en vivo.

## Estado futuro

La emisión automática de notificaciones desde `DeviceChangeEvent` permanece
como una decisión e incremento posterior, pendiente de un puente explícito de
ciclo de vida Qt/GLib y de su verificación aislada.
