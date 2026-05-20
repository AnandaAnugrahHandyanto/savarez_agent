"""Cua-driver backend (macOS only), CLI/app-daemon transport.

The native Hermes tool surface routes through the approved CuaDriver.app daemon.
This backend shells out to ``cua-driver call ...`` so all actions share the same
macOS permission context that the Swift app can onboard, monitor, and stop.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
from typing import Any, Dict, List, Optional, Tuple

from tools.computer_use.backend import ActionResult, CaptureResult, ComputerUseBackend, UIElement

logger = logging.getLogger(__name__)

PINNED_CUA_DRIVER_VERSION = os.environ.get("HERMES_CUA_DRIVER_VERSION", "0.5.0")
_CUA_DRIVER_CMD = os.environ.get("HERMES_CUA_DRIVER_CMD", "cua-driver")

_WINDOW_LINE_RE = re.compile(r'^-\s+(.+?)\s+\(pid\s+(\d+)\)\s+.*\[window_id:\s+(\d+)\]', re.MULTILINE)
_ELEMENT_LINE_RE = re.compile(r'^\s*-\s+\[(\d+)\]\s+(\w+)(?:\s+"([^"]*)")?', re.MULTILINE)


def _is_macos() -> bool:
    return sys.platform == "darwin"


def _is_arm_mac() -> bool:
    return _is_macos() and platform.machine() == "arm64"


def cua_driver_binary_available() -> bool:
    return bool(shutil.which(_CUA_DRIVER_CMD))


def cua_driver_install_hint() -> str:
    return (
        "cua-driver is not installed. Install with `hermes computer-use install` "
        "or run `hermes tools` and enable the Computer Use toolset."
    )


def _parse_json_or_text(text: str) -> Any:
    stripped = (text or "").strip()
    if not stripped:
        return ""
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        pass
    # Some CLIs print logs before a final JSON object. Grab the last plausible JSON line.
    for line in reversed(stripped.splitlines()):
        line = line.strip()
        if line.startswith(("{", "[")):
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue
    return stripped


def _parse_windows_from_text(text: str) -> List[Dict[str, Any]]:
    windows = []
    for m in _WINDOW_LINE_RE.finditer(text):
        windows.append({
            "app_name": m.group(1).strip(),
            "pid": int(m.group(2)),
            "window_id": int(m.group(3)),
            "off_screen": "[off-screen]" in m.group(0),
        })
    return windows


def _parse_elements_from_tree(markdown: str) -> List[UIElement]:
    elements = []
    for m in _ELEMENT_LINE_RE.finditer(markdown or ""):
        elements.append(UIElement(index=int(m.group(1)), role=m.group(2), label=m.group(3) or ""))
    return elements


def _split_tree_text(full_text: str) -> Tuple[str, str]:
    lines = (full_text or "").split("\n", 1)
    return lines[0], lines[1] if len(lines) > 1 else ""


def _parse_key_combo(keys: str) -> Tuple[Optional[str], List[str]]:
    modifiers = []
    key = None
    aliases = {"command": "cmd", "alt": "option", "control": "ctrl"}
    for part in [p.strip().lower() for p in re.split(r'[+\-]', keys or "") if p.strip()]:
        normalized = aliases.get(part, part)
        if normalized in {"cmd", "shift", "option", "ctrl", "fn"}:
            modifiers.append(normalized)
        else:
            key = part
    return key, modifiers


class CuaDriverBackend(ComputerUseBackend):
    """Default computer-use backend using ``cua-driver call``."""

    def __init__(self) -> None:
        self._active_pid: Optional[int] = None
        self._active_window_id: Optional[int] = None
        self._active_app: str = ""

    def start(self) -> None:
        if not cua_driver_binary_available():
            raise RuntimeError(cua_driver_install_hint())
        if _is_macos():
            subprocess.run(["open", "-n", "-g", "-a", "CuaDriver", "--args", "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)

    def stop(self) -> None:
        pass

    def is_available(self) -> bool:
        return _is_macos() and cua_driver_binary_available()

    def _call(self, name: str, args: Dict[str, Any], timeout: float = 30.0) -> Dict[str, Any]:
        if not cua_driver_binary_available():
            raise RuntimeError(cua_driver_install_hint())
        cmd = [_CUA_DRIVER_CMD, "call", name, json.dumps(args or {})]
        proc = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
        parsed = _parse_json_or_text(proc.stdout)
        if proc.returncode != 0:
            return {"data": parsed or proc.stderr.strip(), "images": [], "structuredContent": None, "isError": True}
        images: List[str] = []
        structured = parsed if isinstance(parsed, dict) else None
        data: Any = parsed
        if isinstance(parsed, dict):
            for key in ("image", "png_b64", "screenshot", "data"):
                val = parsed.get(key)
                if isinstance(val, str) and len(val) > 100 and re.match(r"^[A-Za-z0-9+/=]+$", val[:120]):
                    images.append(val)
                    break
            data = parsed.get("data", parsed.get("text", parsed))
        return {"data": data, "images": images, "structuredContent": structured, "isError": False}

    def _windows(self) -> List[Dict[str, Any]]:
        out = self._call("list_windows", {"on_screen_only": True})
        data = out.get("data")
        structured = out.get("structuredContent") or {}
        raw_windows = None
        if isinstance(structured, dict):
            raw_windows = structured.get("windows")
        if raw_windows is None and isinstance(data, dict):
            raw_windows = data.get("windows")
        if raw_windows:
            windows = []
            for w in raw_windows:
                windows.append({
                    "app_name": w.get("app_name") or w.get("app") or w.get("name") or "",
                    "pid": int(w.get("pid") or 0),
                    "window_id": int(w.get("window_id") or w.get("windowId") or 0),
                    "off_screen": not w.get("is_on_screen", True),
                    "title": w.get("title", ""),
                    "z_index": w.get("z_index", 0),
                })
            return sorted(windows, key=lambda w: w.get("z_index", 0))
        if isinstance(data, str):
            return _parse_windows_from_text(data)
        return []

    def _select_window(self, app: Optional[str] = None) -> Optional[Dict[str, Any]]:
        windows = self._windows()
        if app:
            needle = app.lower()
            matched = [w for w in windows if needle in (w.get("app_name", "") + " " + w.get("title", "")).lower()]
            if matched:
                windows = matched
        target = next((w for w in windows if not w.get("off_screen")), windows[0] if windows else None)
        if target:
            self._active_pid = int(target.get("pid") or 0)
            self._active_window_id = int(target.get("window_id") or 0)
            self._active_app = str(target.get("app_name") or "")
        return target

    def capture(self, mode: str = "som", app: Optional[str] = None) -> CaptureResult:
        target = self._select_window(app)
        if not target:
            return CaptureResult(mode=mode, width=0, height=0, elements=[])
        pid, window_id = self._active_pid, self._active_window_id
        png_b64: Optional[str] = None
        elements: List[UIElement] = []
        window_title = str(target.get("title") or "")
        width = height = 0
        if mode == "vision":
            out = self._call("screenshot", {"window_id": window_id, "format": "jpeg", "quality": 85})
            if out["images"]:
                png_b64 = out["images"][0]
        else:
            call_args: Dict[str, Any] = {"pid": pid, "window_id": window_id}
            if mode == "som":
                tmp = tempfile.NamedTemporaryFile(prefix="hermes-cua-", suffix=".jpg", delete=False)
                tmp.close()
                call_args["screenshot_out_file"] = tmp.name
            out = self._call("get_window_state", call_args)
            text = out["data"] if isinstance(out["data"], str) else json.dumps(out["data"])
            _summary, tree = _split_tree_text(text)
            elements = _parse_elements_from_tree(tree or text)
            wt = re.search(r'AXWindow\s+"([^"]+)"', tree or text)
            if wt:
                window_title = wt.group(1)
            if out["images"]:
                png_b64 = out["images"][0]
            elif mode == "som" and call_args.get("screenshot_out_file") and os.path.exists(call_args["screenshot_out_file"]):
                with open(call_args["screenshot_out_file"], "rb") as fh:
                    png_b64 = base64.b64encode(fh.read()).decode("ascii")
        png_bytes_len = 0
        if png_b64:
            try:
                png_bytes_len = len(base64.b64decode(png_b64, validate=False))
            except Exception:
                png_bytes_len = len(png_b64) * 3 // 4
        return CaptureResult(mode=mode, width=width, height=height, png_b64=png_b64, elements=elements, app=self._active_app, window_title=window_title, png_bytes_len=png_bytes_len)

    def _action(self, name: str, args: Dict[str, Any]) -> ActionResult:
        try:
            out = self._call(name, args)
        except Exception as e:
            logger.exception("cua-driver %s call failed", name)
            return ActionResult(ok=False, action=name, message=f"cua-driver error: {e}")
        data = out["data"]
        message = data.get("message", "") if isinstance(data, dict) else str(data or "")
        return ActionResult(ok=not out["isError"], action=name, message=message, meta=data if isinstance(data, dict) else {})

    def _require_pid(self, action: str) -> Optional[ActionResult]:
        if self._active_pid is None:
            return ActionResult(ok=False, action=action, message="No active window — call get_app_state first.")
        return None

    def click(self, *, element: Optional[int] = None, x: Optional[int] = None, y: Optional[int] = None, button: str = "left", click_count: int = 1, modifiers: Optional[List[str]] = None) -> ActionResult:
        if err := self._require_pid("click"):
            return err
        tool = "right_click" if button == "right" else ("double_click" if click_count == 2 else "click")
        args: Dict[str, Any] = {"pid": self._active_pid}
        if element is not None:
            args.update({"window_id": self._active_window_id, "element_index": element})
        elif x is not None and y is not None:
            args.update({"x": x, "y": y})
        else:
            return ActionResult(ok=False, action=tool, message="click requires element or coordinate")
        if modifiers:
            args["modifier"] = modifiers
        return self._action(tool, args)

    def drag(self, *, from_element: Optional[int] = None, to_element: Optional[int] = None, from_xy: Optional[Tuple[int, int]] = None, to_xy: Optional[Tuple[int, int]] = None, button: str = "left", modifiers: Optional[List[str]] = None) -> ActionResult:
        if err := self._require_pid("drag"):
            return err
        args: Dict[str, Any] = {"pid": self._active_pid, "window_id": self._active_window_id}
        if from_element is not None:
            args["from_element_index"] = from_element
        if to_element is not None:
            args["to_element_index"] = to_element
        if from_xy:
            args["from_x"], args["from_y"] = from_xy
        if to_xy:
            args["to_x"], args["to_y"] = to_xy
        return self._action("drag", args)

    def scroll(self, *, direction: str, amount: int = 3, element: Optional[int] = None, x: Optional[int] = None, y: Optional[int] = None, modifiers: Optional[List[str]] = None) -> ActionResult:
        if err := self._require_pid("scroll"):
            return err
        args: Dict[str, Any] = {"pid": self._active_pid, "direction": direction, "amount": max(1, min(50, amount))}
        if element is not None:
            args.update({"window_id": self._active_window_id, "element_index": element})
        elif x is not None and y is not None:
            args.update({"x": x, "y": y})
        return self._action("scroll", args)

    def type_text(self, text: str) -> ActionResult:
        if err := self._require_pid("type_text"):
            return err
        return self._action("type_text_chars", {"pid": self._active_pid, "text": text})

    def key(self, keys: str) -> ActionResult:
        if err := self._require_pid("key"):
            return err
        key_name, modifiers = _parse_key_combo(keys)
        if not key_name:
            return ActionResult(ok=False, action="key", message=f"Could not parse key from {keys!r}.")
        if modifiers:
            return self._action("hotkey", {"pid": self._active_pid, "keys": modifiers + [key_name]})
        return self._action("press_key", {"pid": self._active_pid, "key": key_name})

    def set_value(self, value: str, element: Optional[int] = None) -> ActionResult:
        if err := self._require_pid("set_value"):
            return err
        if element is None:
            return ActionResult(ok=False, action="set_value", message="set_value requires element")
        return self._action("set_value", {"pid": self._active_pid, "window_id": self._active_window_id, "element_index": element, "value": value})

    def perform_secondary_action(self, element: Optional[int] = None, secondary_action: str = "AXShowMenu") -> ActionResult:
        if err := self._require_pid("perform_secondary_action"):
            return err
        if element is None:
            return ActionResult(ok=False, action="perform_secondary_action", message="secondary action requires element")
        return self._action("perform_secondary_action", {"pid": self._active_pid, "window_id": self._active_window_id, "element_index": element, "action": secondary_action})

    def select_text(self, element: Optional[int] = None, text: str = "", selection: str = "all") -> ActionResult:
        if err := self._require_pid("select_text"):
            return err
        args: Dict[str, Any] = {"pid": self._active_pid, "window_id": self._active_window_id, "selection": selection}
        if element is not None:
            args["element_index"] = element
        if text:
            args["text"] = text
        return self._action("select_text", args)

    def list_apps(self) -> List[Dict[str, Any]]:
        out = self._call("list_apps", {})
        data = out["data"]
        if isinstance(data, dict):
            return data.get("apps", [])
        if isinstance(data, list):
            return data
        if isinstance(data, str):
            apps = []
            for line in data.splitlines():
                m = re.search(r'(.+?)\s+\(pid\s+(\d+)\)', line)
                if m:
                    apps.append({"name": m.group(1).strip(), "pid": int(m.group(2))})
            return apps
        return []

    def focus_app(self, app: str, raise_window: bool = False) -> ActionResult:
        target = self._select_window(app)
        if target:
            return ActionResult(ok=True, action="focus_app", message=f"Targeted {target.get('app_name')} (pid {self._active_pid}, window {self._active_window_id}) without raising window.")
        return ActionResult(ok=False, action="focus_app", message=f"No on-screen window found for app {app!r}.")
