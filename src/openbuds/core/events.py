"""Bus de eventos (pub/sub) para acoplamiento flojo entre capas.

Permite que los módulos reaccionen a eventos del dominio (dispositivo conectado,
códec cambiado, health check completado) sin conocerse directamente. La
infraestructura publica eventos; la presentación y la aplicación se suscriben.

Diseño simple en proceso (sin colas ni hilos): los callbacks se ejecutan
síncronamente en el hilo del publicador. Para el event loop de Qt se recomienda
que el callback republique a través de señales Qt (ver presentación).
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from threading import RLock
from typing import Any


@dataclass(frozen=True, slots=True)
class Event:
    """Evento base del bus.

    Los eventos concretos pueden heredar de esta clase para aportar tipado.
    Atributos:
        name: Nombre del evento (canónico, p. ej. "device.connected").
        payload: Datos arbitrarios del evento.
    """

    name: str
    payload: Any = None


# Tipo del callback: recibe un Event y no devuelve nada.
EventCallback = Callable[[Event], None]


class EventBus:
    """Bus de eventos en proceso, thread-safe (suscripción/publicación).

    Uso::

        bus = EventBus()
        bus.subscribe("device.connected", lambda e: print(e.payload))
        bus.publish(Event("device.connected", {"address": "AA:BB:..."}))
    """

    def __init__(self) -> None:
        self._subscribers: dict[str, list[EventCallback]] = defaultdict(list)
        self._lock = RLock()

    def subscribe(self, event_name: str, callback: EventCallback) -> None:
        """Registra ``callback`` para el evento ``event_name``."""
        with self._lock:
            self._subscribers[event_name].append(callback)

    def unsubscribe(self, event_name: str, callback: EventCallback) -> None:
        """Elimina un callback previamente registrado (si existe)."""
        with self._lock:
            subs = self._subscribers.get(event_name)
            if subs and callback in subs:
                subs.remove(callback)

    def publish(self, event: Event) -> None:
        """Publica un evento a todos los suscriptores.

        Los callbacks se ejecutan síncronamente en orden de suscripción.
        Una excepción en un callback se propaga (no se captura); esto hace
        visibles los bugs en los manejadores. Si se necesita aislamiento,
        el publicador puede envolver la llamada en try/except.
        """
        with self._lock:
            subs = list(self._subscribers.get(event.name, []))
        for callback in subs:
            callback(event)

    def clear(self) -> None:
        """Elimina todas las suscripciones (útil en tests)."""
        with self._lock:
            self._subscribers.clear()


# Instancia global compartida por la app. Inyectable para tests.
default_bus = EventBus()
