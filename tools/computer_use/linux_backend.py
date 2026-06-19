"""Linux backend for the generic ``computer_use`` tool.

This backend speaks MCP over stdio to the companion ``linux-computer-use``
driver. The driver intentionally mirrors cua-driver's tool names where Linux
allows it, so the model-facing Hermes schema stays unchanged across macOS and
Linux.

Install the driver with:

    pipx install git+https://github.com/tyy130/linux-computer-use

or make a ``linux-computer-use`` executable available on PATH. The command must
support ``linux-computer-use mcp``.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import re
import shutil
import sys
from contextlib import AsyncExitStack
from typing import Any, Dict, List, Optional, Tuple

from tools.computer_use.backend import (
    ActionResult,
    CaptureResult,
    ComputerUseBackend,
    UIElement,
)
from tools.computer_use.cua_backend import (
    _AsyncBridge,
    _extract_tool_result,
    _image_dimensions_from_bytes,
    _parse_elements_from_tree,
    _parse_key_combo,
    _split_tree_text,
)

logger = logging.getLogger(__name__)

_LINUX_DRIVER_CMD = os.environ.get("HERMES_LINUX_COMPUTER_USE_CMD", "linux-computer-use")
_LINUX_DRIVER_ARGS = ["mcp"]


def _is_linux() -> bool:
    return sys.platform.startswith("linux")


def linux_driver_binary_available() -> bool:
    """True if the linux-computer-use executable is on PATH."""
    return bool(shutil.which(_LINUX_DRIVER_CMD))


def linux_driver_install_hint() -> str:
    return (
        "linux-computer-use is not installed or not on PATH. Install it with:\n"
        "  pipx install git+https://github.com/tyy130/linux-computer-use\n"
        "Or clone locally and expose a wrapper that runs `python -m linux_computer_use.cli`."
    )


class _LinuxDriverSession:
    """Long-lived MCP stdio session for ``linux-computer-use mcp``."""

    def __init__(self, bridge: _AsyncBridge) -> None:
        self._bridge = bridge
        self._session = None
        self._exit_stack: Optional[AsyncExitStack] = None
        self._started = False

    async def _aenter(self) -> None:
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        if not linux_driver_binary_available():
            raise RuntimeError(linux_driver_install_hint())

        params = StdioServerParameters(
            command=_LINUX_DRIVER_CMD,
            args=_LINUX_DRIVER_ARGS,
            env={**os.environ},
        )
        stack = AsyncExitStack()
        read, write = await stack.enter_async_context(stdio_client(params))
        session = await stack.enter_async_context(ClientSession(read, write))
        await session.initialize()
        self._exit_stack = stack
        self._session = session

    async def _aexit(self) -> None:
        if self._exit_stack is not None:
            try:
                await self._exit_stack.aclose()
            except Exception as e:
                # The MCP stdio context can raise an anyio cancel-scope warning
                # when closed from a different scheduled task than it was opened
                # in. The process is still torn down by stdio cleanup; don't
                # surface noisy shutdown details to users after successful calls.
                logger.debug("linux-computer-use shutdown error: %s", e)
        self._exit_stack = None
        self._session = None

    def start(self) -> None:
        if self._started:
            return
        self._bridge.start()
        self._bridge.run(self._aenter(), timeout=15.0)
        self._started = True

    def stop(self) -> None:
        if not self._started:
            return
        try:
            self._bridge.run(self._aexit(), timeout=5.0)
        finally:
            self._started = False

    async def _call_tool_async(self, name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        if self._session is None:
            raise RuntimeError("linux-computer-use session not initialized")
        result = await self._session.call_tool(name, args)
        return _extract_tool_result(result)

    def call_tool(self, name: str, args: Dict[str, Any], timeout: float = 30.0) -> Dict[str, Any]:
        if not self._started:
            raise RuntimeError("linux-computer-use session not started")
        return self._bridge.run(self._call_tool_async(name, args), timeout=timeout)


class LinuxComputerUseBackend(ComputerUseBackend):
    """Linux/X11 computer-use backend via the linux-computer-use MCP driver."""

    def __init__(self) -> None:
        self._bridge = _AsyncBridge()
        self._session = _LinuxDriverSession(self._bridge)
        self._active_pid: Optional[int] = None
        self._active_window_id: Optional[int] = None
        self._last_app: Optional[str] = None

    def start(self) -> None:
        self._session.start()

    def stop(self) -> None:
        try:
            self._session.stop()
        finally:
            self._bridge.stop()

    def is_available(self) -> bool:
        return _is_linux() and linux_driver_binary_available()

    def capture(self, mode: str = "som", app: Optional[str] = None) -> CaptureResult:
        lw_out = self._session.call_tool("list_windows", {"on_screen_only": True})
        raw_windows = (lw_out.get("structuredContent") or {}).get("windows")
        windows = []
        if raw_windows:
            windows = [
                {
                    "app_name": w.get("app_name", ""),
                    "pid": int(w.get("pid") or 0),
                    "window_id": int(w.get("window_id") or 0),
                    "title": w.get("title", ""),
                    "z_index": int(w.get("z_index") or 0),
                    "off_screen": not bool(w.get("is_on_screen", True)),
                }
                for w in raw_windows
            ]
            windows.sort(key=lambda w: w["z_index"])

        if not windows:
            return CaptureResult(mode=mode, width=0, height=0, app="", window_title="<no visible Linux windows>")

        if app:
            app_lower = app.lower()
            filtered = [
                w for w in windows
                if app_lower in f"{w['app_name']} {w['title']}".lower()
            ]
            if not filtered:
                return CaptureResult(
                    mode=mode,
                    width=0,
                    height=0,
                    app="",
                    window_title=f"<no visible Linux window matched app={app!r}; call list_apps>",
                )
            windows = filtered

        target = next((w for w in windows if not w["off_screen"]), windows[0])
        self._active_pid = target["pid"]
        self._active_window_id = target["window_id"]
        app_name = target["app_name"]
        if app or not self._last_app:
            self._last_app = app_name

        png_b64: Optional[str] = None
        elements: List[UIElement] = []
        width = height = 0
        window_title = target.get("title", "")

        if mode == "vision":
            sc_out = self._session.call_tool("screenshot", {"window_id": self._active_window_id})
            if sc_out["images"]:
                png_b64 = sc_out["images"][0]
            if isinstance(sc_out.get("data"), str):
                width, height = _parse_metadata_dimensions(sc_out["data"])
        else:
            gws_out = self._session.call_tool(
                "get_window_state",
                {"pid": self._active_pid, "window_id": self._active_window_id},
            )
            text = gws_out["data"] if isinstance(gws_out["data"], str) else ""
            _summary, tree = _split_tree_text(text)
            if tree:
                elements = _parse_elements_from_tree(tree)
            if gws_out["images"]:
                png_b64 = gws_out["images"][0]
            wt = re.search(r'AXWindow\s+"([^"]+)"', tree)
            if wt:
                window_title = wt.group(1)

        png_bytes_len = 0
        if png_b64:
            try:
                raw = base64.b64decode(png_b64, validate=False)
                png_bytes_len = len(raw)
                detected_width, detected_height = _image_dimensions_from_bytes(raw)
                if detected_width and detected_height:
                    width = detected_width
                    height = detected_height
            except Exception:
                png_bytes_len = len(png_b64) * 3 // 4

        return CaptureResult(
            mode=mode,
            width=width,
            height=height,
            png_b64=png_b64 if mode != "ax" else None,
            elements=elements,
            app=app_name,
            window_title=window_title,
            png_bytes_len=png_bytes_len,
        )

    def click(
        self,
        *,
        element: Optional[int] = None,
        x: Optional[int] = None,
        y: Optional[int] = None,
        button: str = "left",
        click_count: int = 1,
        modifiers: Optional[List[str]] = None,
    ) -> ActionResult:
        tool = "click"
        if button == "right":
            tool = "right_click"
        elif button == "middle":
            tool = "middle_click"
        elif click_count == 2:
            tool = "double_click"
        args = _target_args(element=element, x=x, y=y, modifiers=modifiers)
        args.update(_window_args(self._active_pid, self._active_window_id))
        return self._action(tool, args)

    def drag(
        self,
        *,
        from_element: Optional[int] = None,
        to_element: Optional[int] = None,
        from_xy: Optional[Tuple[int, int]] = None,
        to_xy: Optional[Tuple[int, int]] = None,
        button: str = "left",
        modifiers: Optional[List[str]] = None,
    ) -> ActionResult:
        args: Dict[str, Any] = {}
        if from_element is not None and to_element is not None:
            args["from_element"] = from_element
            args["to_element"] = to_element
        elif from_xy is not None and to_xy is not None:
            args["from_x"], args["from_y"] = int(from_xy[0]), int(from_xy[1])
            args["to_x"], args["to_y"] = int(to_xy[0]), int(to_xy[1])
        else:
            return ActionResult(ok=False, action="drag", message="drag requires from/to element or coordinate")
        return self._action("drag", args)

    def scroll(
        self,
        *,
        direction: str,
        amount: int = 3,
        element: Optional[int] = None,
        x: Optional[int] = None,
        y: Optional[int] = None,
        modifiers: Optional[List[str]] = None,
    ) -> ActionResult:
        args = _target_args(element=element, x=x, y=y, modifiers=modifiers, require_target=False)
        args["direction"] = direction
        args["amount"] = max(1, min(50, int(amount)))
        return self._action("scroll", args)

    def type_text(self, text: str) -> ActionResult:
        return self._action("type_text", {"pid": self._active_pid, "text": text})

    def key(self, keys: str) -> ActionResult:
        key_name, modifiers = _parse_key_combo(keys)
        if not key_name:
            return ActionResult(ok=False, action="key", message=f"Could not parse key from {keys!r}")
        if modifiers:
            return self._action("hotkey", {"pid": self._active_pid, "keys": modifiers + [key_name]})
        return self._action("press_key", {"pid": self._active_pid, "key": key_name})

    def list_apps(self) -> List[Dict[str, Any]]:
        out = self._session.call_tool("list_apps", {})
        data = out.get("structuredContent") or out.get("data")
        if isinstance(data, dict):
            return data.get("apps", [])
        return []

    def focus_app(self, app: str, raise_window: bool = False) -> ActionResult:
        res = self._action("focus_app", {"app": app, "raise_window": raise_window})
        # Follow with list_windows to set sticky target for subsequent actions.
        if res.ok:
            cap = self.capture(mode="ax", app=app)
            if cap.app:
                res.message = (res.message + " " if res.message else "") + f"Targeted {cap.app}."
        return res

    def set_value(self, value: str, element: Optional[int] = None) -> ActionResult:
        if element is None:
            return ActionResult(ok=False, action="set_value", message="set_value requires element")
        args = {"pid": self._active_pid, "window_id": self._active_window_id, "element_index": element, "value": value}
        return self._action("set_value", args)

    def _action(self, name: str, args: Dict[str, Any]) -> ActionResult:
        try:
            out = self._session.call_tool(name, {k: v for k, v in args.items() if v is not None})
        except Exception as e:
            logger.exception("linux-computer-use %s call failed", name)
            return ActionResult(ok=False, action=name, message=f"linux-computer-use error: {e}")
        ok = not out.get("isError")
        data = out.get("structuredContent") or out.get("data")
        message = ""
        meta: Dict[str, Any] = {}
        if isinstance(data, dict):
            message = str(data.get("message", ""))
            meta = data
        elif isinstance(data, str):
            message = data
        return ActionResult(ok=ok, action=name, message=message, meta=meta)


def _window_args(pid: Optional[int], window_id: Optional[int]) -> Dict[str, Any]:
    return {"pid": pid, "window_id": window_id}


def _target_args(
    *,
    element: Optional[int],
    x: Optional[int],
    y: Optional[int],
    modifiers: Optional[List[str]] = None,
    require_target: bool = True,
) -> Dict[str, Any]:
    args: Dict[str, Any] = {}
    if element is not None:
        args["element_index"] = element
    elif x is not None and y is not None:
        args["x"] = int(x)
        args["y"] = int(y)
    elif require_target:
        raise ValueError("target requires element or x/y")
    if modifiers:
        args["modifier"] = modifiers
    return args


def _parse_metadata_dimensions(text: str) -> Tuple[int, int]:
    try:
        data = json.loads(text)
    except Exception:
        return 0, 0
    if isinstance(data, dict):
        return int(data.get("width") or 0), int(data.get("height") or 0)
    return 0, 0
