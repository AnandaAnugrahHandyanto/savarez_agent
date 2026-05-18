"""PythonOSC bridge for VRChat existing-avatar control."""
from __future__ import annotations

import logging
import threading
from typing import Any, Callable

from pythonosc import dispatcher, osc_server, udp_client

logger = logging.getLogger(__name__)

AvatarChangeCallback = Callable[[str], None]
ParameterCallback = Callable[[str, Any], None]


class VrchatOscBridge:
    """Send and receive VRChat OSC messages on localhost."""

    def __init__(
        self,
        *,
        send_host: str = "127.0.0.1",
        send_port: int = 9000,
        listen_host: str = "127.0.0.1",
        listen_port: int = 9001,
        on_avatar_change: AvatarChangeCallback | None = None,
        on_parameter: ParameterCallback | None = None,
    ) -> None:
        if send_host not in {"127.0.0.1", "localhost", "::1"}:
            raise ValueError("VRChat OSC send host must be localhost")
        if listen_host not in {"127.0.0.1", "localhost", "::1"}:
            raise ValueError("VRChat OSC listen host must be localhost")
        self.send_host = send_host
        self.send_port = int(send_port)
        self.listen_host = listen_host
        self.listen_port = int(listen_port)
        self._client = udp_client.SimpleUDPClient(self.send_host, self.send_port)
        self._dispatcher = dispatcher.Dispatcher()
        self._dispatcher.map("/avatar/change", self._handle_avatar_change)
        self._dispatcher.map("/avatar/parameters/*", self._handle_parameter)
        self._dispatcher.set_default_handler(self._handle_default)
        self._server: osc_server.ThreadingOSCUDPServer | None = None
        self._thread: threading.Thread | None = None
        self._timers: list[threading.Timer] = []
        self._on_avatar_change = on_avatar_change
        self._on_parameter = on_parameter
        self.last_error: str | None = None

    @property
    def running(self) -> bool:
        return self._server is not None and self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        if self.running:
            return
        self._server = osc_server.ThreadingOSCUDPServer(
            (self.listen_host, self.listen_port),
            self._dispatcher,
        )
        self._thread = threading.Thread(
            target=self._server.serve_forever,
            name="hypura-vrchat-osc",
            daemon=True,
        )
        self._thread.start()
        self.last_error = None
        logger.info("VRChat OSC bridge listening on %s:%s", self.listen_host, self.listen_port)

    def stop(self) -> None:
        for timer in self._timers:
            timer.cancel()
        self._timers.clear()
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
        self._server = None
        self._thread = None

    def send_parameter(self, address: str, value: bool | int | float | str) -> None:
        if not address.startswith("/avatar/parameters/"):
            raise ValueError("VRChat avatar parameter address must start with /avatar/parameters/")
        self._client.send_message(address, value)

    def send_chatbox(self, text: str, send_immediately: bool = True, notify: bool = False) -> None:
        self._client.send_message("/chatbox/input", [text, bool(send_immediately), bool(notify)])

    def send_typing(self, enabled: bool) -> None:
        self._client.send_message("/chatbox/typing", bool(enabled))

    def send_input(self, name: str, value: int | float, auto_reset_ms: int | None = None) -> None:
        if not name or any(char in name for char in "/\\"):
            raise ValueError("VRChat input name must be a simple input identifier")
        address = f"/input/{name}"
        self._client.send_message(address, value)
        if auto_reset_ms is not None and auto_reset_ms >= 0:
            timer = threading.Timer(auto_reset_ms / 1000, lambda: self._client.send_message(address, 0))
            timer.daemon = True
            self._timers.append(timer)
            timer.start()

    def emergency_stop(self) -> None:
        for timer in self._timers:
            timer.cancel()
        self._timers.clear()
        for input_name in ("MoveForward", "MoveHorizontal", "LookHorizontal", "UseAxisRight", "Jump"):
            try:
                self._client.send_message(f"/input/{input_name}", 0)
            except Exception as exc:  # noqa: BLE001 - best-effort reset after stop
                logger.warning("Failed to reset VRChat input %s: %s", input_name, exc)
        self.send_typing(False)

    def _handle_avatar_change(self, _address: str, *args: Any) -> None:
        avatar_id = str(args[0]) if args else ""
        if avatar_id and self._on_avatar_change is not None:
            self._on_avatar_change(avatar_id)

    def _handle_parameter(self, address: str, *args: Any) -> None:
        value = args[0] if args else None
        if self._on_parameter is not None:
            self._on_parameter(address, value)

    def _handle_default(self, _address: str, *_args: Any) -> None:
        return

