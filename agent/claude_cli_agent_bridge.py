from __future__ import annotations

import secrets
import threading
from multiprocessing.connection import Client, Listener
from typing import Any, Callable


class AgentLoopBridgeServer:
    def __init__(self, callback: Callable[[str, dict[str, Any]], str]):
        self._callback = callback
        self._authkey = secrets.token_bytes(32)
        self._listener = Listener(("127.0.0.1", 0), authkey=self._authkey)
        host, port = self._listener.address
        self.host = str(host)
        self.port = int(port)
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._stop = threading.Event()
        self._started = False

    def start(self) -> None:
        if not self._started:
            self._thread.start()
            self._started = True

    def close(self) -> None:
        self._stop.set()
        try:
            Client((self.host, self.port), authkey=self._authkey).close()
        except Exception:
            pass
        try:
            self._listener.close()
        except Exception:
            pass

    def connection_env(self) -> dict[str, str]:
        return {
            "HERMES_AGENT_BRIDGE_HOST": self.host,
            "HERMES_AGENT_BRIDGE_PORT": str(self.port),
            "HERMES_AGENT_BRIDGE_AUTHKEY": self._authkey.hex(),
        }

    def _serve(self) -> None:
        while not self._stop.is_set():
            try:
                conn = self._listener.accept()
            except Exception:
                break
            with conn:
                try:
                    req = conn.recv()
                    if req == {"type": "shutdown"}:
                        conn.send({"ok": True})
                        break
                    tool_name = str(req.get("tool_name") or "")
                    args = req.get("args") or {}
                    result = self._callback(tool_name, args)
                    conn.send({"ok": True, "result": result})
                except Exception as exc:
                    conn.send({"ok": False, "error": f"{type(exc).__name__}: {exc}"})


def call_agent_loop_tool(tool_name: str, args: dict[str, Any], *, host: str, port: int, authkey_hex: str) -> str:
    conn = Client((host, port), authkey=bytes.fromhex(authkey_hex))
    with conn:
        conn.send({"tool_name": tool_name, "args": args})
        resp = conn.recv()
    if not resp.get("ok"):
        raise RuntimeError(resp.get("error") or "Unknown bridge error")
    return str(resp.get("result") or "")
