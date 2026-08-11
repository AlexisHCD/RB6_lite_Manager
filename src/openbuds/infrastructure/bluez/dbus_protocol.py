"""Protocolo de snapshot de BlueZ mediante el proxy síncrono de Gio."""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol, cast

from openbuds.core.errors import BluetoothError

type ManagedObjects = dict[str, dict[str, dict[str, object]]]
type GILoader = Callable[[], tuple[Any, Any]]
type SignalCallback = Callable[[SignalEvent], None]
type ReadyCallback = Callable[[], None]
DBUS_CALL_TIMEOUT_MS = 5000
SIGNAL_OPERATION_TIMEOUT = 5.0
_EXPECTED_SIGNATURE = "(a{oa{sa{sv}}})"
_LOGGER = logging.getLogger(__name__)


def _validate_polling_options(
    on_poll: Callable[[], None] | None,
    poll_interval_ms: int | None,
) -> None:
    """Validate the optional polling callback and interval pair."""
    if (on_poll is None) != (poll_interval_ms is None):
        raise ValueError("on_poll y poll_interval_ms deben proporcionarse juntos")
    if on_poll is not None and (type(poll_interval_ms) is not int or poll_interval_ms <= 0):
        raise ValueError("poll_interval_ms debe ser un entero positivo")


@dataclass(frozen=True, slots=True)
class SignalEvent:
    """Evento de señal D-Bus normalizado para las capas superiores."""

    interface_name: str
    signal_name: str
    object_path: str


@dataclass(slots=True)
class _SubscriptionState:
    callback: SignalCallback
    poll_source: Any = None


class SignalWorker(Protocol):
    """Operaciones que el protocolo necesita del worker de señales."""

    def start(self) -> None:
        """Inicia el worker."""
        ...

    def subscribe(
        self,
        callback: SignalCallback,
        on_ready: ReadyCallback | None = None,
        *,
        on_poll: Callable[[], None] | None = None,
        poll_interval_ms: int | None = None,
    ) -> int:
        """Registra una callback."""
        ...

    def unsubscribe(self, subscription_id: int) -> None:
        """Cancela una suscripción."""
        ...

    def close(self) -> None:
        """Detiene el worker."""
        ...

    @property
    def is_closed(self) -> bool:
        """Indica si el worker está cerrado."""
        ...


WorkerFactory = Callable[[Any, Any, Any, float], SignalWorker]


class _SignalWorker:
    """Own a GLib context and serialize BlueZ signal subscriptions on it."""

    _SIGNALS = (
        ("org.freedesktop.DBus.ObjectManager", "InterfacesAdded"),
        ("org.freedesktop.DBus.ObjectManager", "InterfacesRemoved"),
        ("org.freedesktop.DBus.Properties", "PropertiesChanged"),
    )

    def __init__(self, gio: Any, glib: Any, proxy: Any, operation_timeout: float) -> None:
        self._gio = gio
        self._glib = glib
        self._proxy = proxy
        self._operation_timeout = operation_timeout
        self._context: Any = None
        self._loop: Any = None
        self._connection: Any = None
        self._thread: threading.Thread | None = None
        self._worker_ident: int | None = None
        self._ready = threading.Event()
        self._startup_error: BaseException | None = None
        self._subscriptions: dict[int, _SubscriptionState] = {}
        self._bus_subscription_ids: list[int] = []
        self._next_subscription_id = 1
        self._closed = False
        self._closed_lock = threading.Lock()

    @property
    def is_closed(self) -> bool:
        """Return whether this worker has stopped accepting operations."""
        with self._closed_lock:
            return self._closed

    def start(self) -> None:
        """Start the daemon thread and wait until its GLib loop is ready."""
        if self._thread is not None:
            return
        self._thread = threading.Thread(
            target=self._run, daemon=True, name="openbuds-bluez-signals"
        )
        self._thread.start()
        if not self._ready.wait(self._operation_timeout):
            raise BluetoothError("Tiempo agotado al iniciar el worker de señales de BlueZ")
        if self._startup_error is not None:
            raise BluetoothError(
                "No se pudo iniciar el worker de señales de BlueZ"
            ) from self._startup_error

    def subscribe(
        self,
        callback: SignalCallback,
        on_ready: ReadyCallback | None = None,
        *,
        on_poll: Callable[[], None] | None = None,
        poll_interval_ms: int | None = None,
    ) -> int:
        """Register a logical callback and return its monotonic identifier."""
        _validate_polling_options(on_poll, poll_interval_ms)
        if self.is_closed:
            raise BluetoothError("El worker de señales de BlueZ está cerrado")
        return cast(
            int,
            self._call_worker(
                lambda: self._subscribe(callback, on_ready, on_poll, poll_interval_ms)
            ),
        )

    def unsubscribe(self, subscription_id: int) -> None:
        """Remove a logical callback, stopping the worker when it is the last one."""
        if self.is_closed or self._thread is None or not self._thread.is_alive():
            return
        stopped = self._call_worker(lambda: self._unsubscribe(subscription_id))
        if stopped and self._thread is not None and self._thread is not threading.current_thread():
            self._join()

    def close(self) -> None:
        """Remove all subscriptions and stop the worker without closing Gio objects."""
        with self._closed_lock:
            already_closed = self._closed
            self._closed = True
        if self._thread is None:
            return
        if self._startup_error is not None:
            self._join()
            return
        if not self._thread.is_alive():
            self._join()
            return
        if already_closed and self._thread is threading.current_thread():
            return
        if self._thread is threading.current_thread():
            self._stop_on_worker()
        else:
            if not already_closed:
                self._call_worker(self._stop_on_worker)
            self._join()

    def _run(self) -> None:
        pushed = False
        try:
            self._worker_ident = threading.get_ident()
            self._context = self._glib.MainContext.new()
            self._context.push_thread_default()
            pushed = True
            self._loop = self._glib.MainLoop.new(self._context, False)
        except BaseException as exc:
            self._startup_error = exc
        finally:
            self._ready.set()

        if self._startup_error is not None:
            if pushed:
                self._context.pop_thread_default()
            return

        try:
            self._loop.run()
        finally:
            if pushed:
                self._context.pop_thread_default()

    def _call_worker(self, operation: Callable[[], Any]) -> Any:
        if self._thread is None:
            raise BluetoothError("El worker de señales de BlueZ no está iniciado")
        if threading.get_ident() == self._worker_ident:
            return operation()

        completed = threading.Event()
        result: list[Any] = []
        failure: list[BaseException] = []

        def invoke() -> bool:
            try:
                result.append(operation())
            except BaseException as exc:
                failure.append(exc)
            finally:
                completed.set()
            return False

        try:
            self._context.invoke_full(self._glib.PRIORITY_DEFAULT, invoke)
        except Exception as exc:
            raise BluetoothError("No se pudo enviar una operación al worker de BlueZ") from exc
        if not completed.wait(self._operation_timeout):
            raise BluetoothError("Tiempo agotado en una operación del worker de BlueZ")
        if failure:
            raise failure[0]
        return result[0] if result else None

    def _subscribe(
        self,
        callback: SignalCallback,
        on_ready: ReadyCallback | None = None,
        on_poll: Callable[[], None] | None = None,
        poll_interval_ms: int | None = None,
    ) -> int:
        if not self._subscriptions:
            self._register_bus_signals()
        subscription_id = self._next_subscription_id
        self._next_subscription_id += 1
        state = _SubscriptionState(callback)
        self._subscriptions[subscription_id] = state
        if on_ready is not None:
            try:
                on_ready()
            except BaseException:
                self._subscriptions.pop(subscription_id, None)
                if not self._subscriptions:
                    self._stop_on_worker()
                raise
        if on_poll is not None and poll_interval_ms is not None:
            source: Any = None
            try:
                source = self._glib.timeout_source_new(poll_interval_ms)

                def poll_wrapper(*_args: Any) -> Any:
                    try:
                        on_poll()
                    except Exception:
                        _LOGGER.exception("Error en callback de polling de BlueZ")
                    return self._glib.SOURCE_CONTINUE

                source.set_callback(poll_wrapper)
                source_id = source.attach(self._context)
                if not isinstance(source_id, int) or source_id <= 0:
                    raise RuntimeError("GLib devolvió un identificador de source inválido")
                state.poll_source = source
            except Exception as exc:
                if source is not None:
                    try:
                        source.destroy()
                    except Exception:
                        _LOGGER.exception("No se pudo destruir un source de polling fallido")
                self._subscriptions.pop(subscription_id, None)
                if not self._subscriptions:
                    self._stop_on_worker()
                raise BluetoothError("No se pudo configurar el polling de BlueZ") from exc
        return subscription_id

    def _register_bus_signals(self) -> None:
        self._connection = self._proxy.get_connection()
        for interface_name, signal_name in self._SIGNALS:
            try:
                subscription_id = self._connection.signal_subscribe(
                    "org.bluez",
                    interface_name,
                    signal_name,
                    None,
                    None,
                    self._gio.DBusSignalFlags.NONE,
                    self._on_signal,
                )
            except Exception as exc:
                _LOGGER.exception(
                    "No se pudo registrar la señal BlueZ %s.%s", interface_name, signal_name
                )
                self._stop_on_worker()
                raise BluetoothError("No se pudo registrar una señal de BlueZ") from exc
            self._bus_subscription_ids.append(subscription_id)

    def _on_signal(
        self,
        _connection: Any,
        _sender: Any,
        object_path: Any,
        interface_name: Any,
        signal_name: Any,
        _parameters: Any,
        _user_data: Any = None,
    ) -> None:
        if not isinstance(object_path, str) or not isinstance(interface_name, str):
            return
        if not isinstance(signal_name, str) or (interface_name, signal_name) not in self._SIGNALS:
            return
        event = SignalEvent(interface_name, signal_name, object_path)
        for state in tuple(self._subscriptions.values()):
            try:
                state.callback(event)
            except Exception:
                _LOGGER.exception("Error en callback de señal BlueZ")

    def _unsubscribe(self, subscription_id: int) -> bool:
        if subscription_id not in self._subscriptions:
            return False
        state = self._subscriptions.pop(subscription_id)
        self._destroy_poll_source(state)
        if not self._subscriptions:
            self._stop_on_worker()
            return True
        return False

    def _stop_on_worker(self) -> None:
        with self._closed_lock:
            self._closed = True
        for state in tuple(self._subscriptions.values()):
            self._destroy_poll_source(state)
        self._subscriptions.clear()
        if self._connection is not None:
            for subscription_id in self._bus_subscription_ids:
                try:
                    self._connection.signal_unsubscribe(subscription_id)
                except Exception:
                    _LOGGER.exception("No se pudo cancelar una señal BlueZ")
            self._bus_subscription_ids.clear()
        if self._loop is not None:
            self._loop.quit()

    def _destroy_poll_source(self, state: _SubscriptionState) -> None:
        source = state.poll_source
        state.poll_source = None
        if source is None:
            return
        try:
            source.destroy()
        except Exception:
            _LOGGER.exception("No se pudo destruir un source de polling de BlueZ")

    def _join(self) -> None:
        if self._thread is not None:
            self._thread.join(self._operation_timeout)
            if self._thread.is_alive():
                raise BluetoothError("Tiempo agotado al detener el worker de señales de BlueZ")


class SnapshotProvider(Protocol):
    """Fuente interna capaz de obtener un snapshot nativo de BlueZ."""

    def get_managed_objects(self) -> ManagedObjects:
        """Devuelve el árbol de objetos administrados por BlueZ."""
        ...


class SignalProvider(Protocol):
    """Fuente interna capaz de gestionar suscripciones a señales."""

    def subscribe(
        self,
        callback: SignalCallback,
        on_ready: ReadyCallback | None = None,
        *,
        on_poll: Callable[[], None] | None = None,
        poll_interval_ms: int | None = None,
    ) -> int:
        """Registra una callback y devuelve su identificador."""
        ...

    def unsubscribe(self, subscription_id: int) -> None:
        """Cancela una suscripción por su identificador."""
        ...

    def close(self) -> None:
        """Libera los recursos asociados al proveedor."""
        ...


class ManagedObjectsProvider(SnapshotProvider, SignalProvider, Protocol):
    """Proveedor completo de snapshots y señales de BlueZ."""

    pass


def _load_gi() -> tuple[Any, Any]:
    """Carga Gio y GLib solo cuando se construye el adaptador real."""
    import gi

    gi.require_version("Gio", "2.0")
    from gi.repository import Gio, GLib

    return Gio, GLib


def _validate_snapshot(value: object) -> ManagedObjects:
    """Comprueba la forma completa del resultado desempaquetado."""
    if not isinstance(value, dict):
        raise BluetoothError("El snapshot de BlueZ no tiene forma de diccionario")

    for object_path, interfaces in value.items():
        if not isinstance(object_path, str):
            raise BluetoothError("El snapshot de BlueZ contiene una ruta de objeto inválida")
        if not isinstance(interfaces, dict):
            raise BluetoothError("El snapshot de BlueZ contiene interfaces inválidas")
        for interface_name, properties in interfaces.items():
            if not isinstance(interface_name, str) or not isinstance(properties, dict):
                raise BluetoothError("El snapshot de BlueZ contiene propiedades inválidas")
            if any(not isinstance(property_name, str) for property_name in properties):
                raise BluetoothError("El snapshot de BlueZ contiene nombres de propiedad inválidos")

    return cast(ManagedObjects, value)


class GioDBusProtocol:
    """Proveedor de snapshots de BlueZ usando ``GetManagedObjects``."""

    def __init__(
        self,
        loader: GILoader | None = None,
        worker_factory: WorkerFactory | None = None,
        signal_operation_timeout: float = SIGNAL_OPERATION_TIMEOUT,
    ) -> None:
        try:
            gio, glib = (loader or _load_gi)()
        except (ImportError, ValueError) as exc:
            raise BluetoothError(
                "No se pudo cargar PyGObject/Gio; instala el runtime y ejecuta make check-runtime"
            ) from exc

        self._gio = gio
        self._glib = glib
        self._worker_factory = worker_factory if worker_factory is not None else _SignalWorker
        self._signal_operation_timeout = signal_operation_timeout
        self._state_lock = threading.Lock()
        self._worker: SignalWorker | None = None
        self._worker_starting: threading.Event | None = None
        self._closed = False
        try:
            self._proxy = self._gio.DBusProxy.new_for_bus_sync(
                self._gio.BusType.SYSTEM,
                self._gio.DBusProxyFlags.DO_NOT_AUTO_START,
                None,
                "org.bluez",
                "/",
                "org.freedesktop.DBus.ObjectManager",
                None,
            )
        except self._glib.Error as exc:
            raise BluetoothError(f"No se pudo construir el proxy de BlueZ: {exc}") from exc

    def subscribe(
        self,
        callback: SignalCallback,
        on_ready: ReadyCallback | None = None,
        *,
        on_poll: Callable[[], None] | None = None,
        poll_interval_ms: int | None = None,
    ) -> int:
        """Registra una callback, creando el worker de señales si es necesario."""
        _validate_polling_options(on_poll, poll_interval_ms)
        while True:
            starting: threading.Event | None
            with self._state_lock:
                if self._closed:
                    raise BluetoothError("El protocolo D-Bus de BlueZ está cerrado")
                worker = self._worker
                if worker is None:
                    try:
                        worker = self._worker_factory(
                            self._gio,
                            self._glib,
                            self._proxy,
                            self._signal_operation_timeout,
                        )
                    except BluetoothError:
                        raise
                    except Exception as exc:
                        raise BluetoothError(
                            "No se pudo crear el worker de señales de BlueZ"
                        ) from exc
                    self._worker = worker
                    starting = threading.Event()
                    self._worker_starting = starting
                    creator = True
                else:
                    starting = self._worker_starting
                    creator = False

            if not creator:
                if starting is not None:
                    if not starting.wait(self._signal_operation_timeout):
                        raise BluetoothError(
                            "Tiempo agotado al iniciar el worker de señales de BlueZ"
                        )
                    continue
                break

            assert starting is not None
            try:
                worker.start()
            except Exception as exc:
                with self._state_lock:
                    if self._worker is worker:
                        self._worker = None
                    if self._worker_starting is starting:
                        self._worker_starting = None
                    starting.set()
                self._discard_failed_worker(worker)
                if isinstance(exc, BluetoothError):
                    raise
                raise BluetoothError("No se pudo iniciar el worker de señales de BlueZ") from exc
            with self._state_lock:
                rejected = self._closed or self._worker is not worker
                if self._worker_starting is starting:
                    self._worker_starting = None
                starting.set()
            if rejected:
                self._discard_failed_worker(worker)
                raise BluetoothError("El protocolo D-Bus de BlueZ está cerrado")
            break

        with self._state_lock:
            valid = not self._closed and self._worker is worker and self._worker_starting is None
        if not valid:
            self._discard_failed_worker(worker)
            raise BluetoothError("El protocolo D-Bus de BlueZ está cerrado")

        try:
            subscription_id = worker.subscribe(
                callback,
                on_ready=on_ready,
                on_poll=on_poll,
                poll_interval_ms=poll_interval_ms,
            )
        except BluetoothError:
            self._discard_failed_worker(worker)
            raise
        except Exception as exc:
            self._discard_failed_worker(worker)
            raise BluetoothError("No se pudo registrar una señal de BlueZ") from exc

        with self._state_lock:
            rejected = self._closed or self._worker is not worker
            if not rejected:
                return subscription_id
        self._discard_failed_worker(worker)
        raise BluetoothError("El protocolo D-Bus de BlueZ está cerrado")

    def unsubscribe(self, subscription_id: int) -> None:
        """Cancela una callback delegando la semántica al worker actual."""
        with self._state_lock:
            worker = self._worker
        if worker is None:
            return

        worker.unsubscribe(subscription_id)
        if worker.is_closed:
            self._discard_worker(worker)

    def close(self) -> None:
        """Cierra el worker, sin cerrar el proxy ni la conexión D-Bus."""
        with self._state_lock:
            if self._closed:
                return
            self._closed = True
            worker = self._worker
            self._worker = None
            starting = self._worker_starting
            self._worker_starting = None
            if starting is not None:
                starting.set()
        if worker is not None:
            worker.close()

    def __enter__(self) -> GioDBusProtocol:
        """Devuelve el protocolo para uso como gestor de contexto."""
        return self

    def __exit__(self, _exc_type: Any, _exc_value: Any, _traceback: Any) -> None:
        """Cierra el protocolo al salir del contexto."""
        self.close()

    def _discard_worker(self, worker: SignalWorker) -> None:
        with self._state_lock:
            if self._worker is worker:
                self._worker = None

    def _discard_failed_worker(self, worker: SignalWorker) -> None:
        self._discard_worker(worker)
        if not worker.is_closed:
            try:
                worker.close()
            except Exception:
                _LOGGER.exception("No se pudo cerrar el worker de señales tras un fallo")

    def get_managed_objects(self) -> ManagedObjects:
        """Obtiene y valida un snapshot de objetos administrados por BlueZ."""
        try:
            reply = self._proxy.call_sync(
                "GetManagedObjects",
                None,
                self._gio.DBusCallFlags.NO_AUTO_START,
                DBUS_CALL_TIMEOUT_MS,
                None,
            )
        except self._glib.Error as exc:
            raise BluetoothError(f"No se pudo obtener el snapshot de BlueZ: {exc}") from exc

        if reply.get_type_string() != _EXPECTED_SIGNATURE:
            raise BluetoothError("La respuesta de BlueZ tiene una firma GVariant inesperada")

        unpacked = reply.unpack()
        if not isinstance(unpacked, tuple) or len(unpacked) != 1:
            raise BluetoothError("La respuesta de BlueZ tiene una forma desempaquetada inválida")

        return _validate_snapshot(unpacked[0])
