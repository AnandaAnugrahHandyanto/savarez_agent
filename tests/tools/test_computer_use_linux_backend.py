"""Tests for the Linux computer_use backend adapter."""

from __future__ import annotations

from typing import Any, cast
from unittest.mock import patch


def _png_b64() -> str:
    return (
        "iVBORw0KGgoAAAANSUhEUgAAAAgAAAAICAYAAADED76LAAAADUlEQVR4nG"
        "NgGAUgAAABCAABgukLHQAAAABJRU5ErkJggg=="
    )


class FakeSession:
    def __init__(self) -> None:
        self.calls = []

    def call_tool(self, name, args, timeout=30.0):
        self.calls.append((name, args))
        if name == "list_windows":
            return {
                "data": None,
                "images": [],
                "structuredContent": {
                    "windows": [
                        {
                            "app_name": "demo",
                            "pid": 123,
                            "window_id": 456,
                            "title": "Demo Window",
                            "z_index": 0,
                            "is_on_screen": True,
                        }
                    ]
                },
                "isError": False,
            }
        if name == "get_window_state":
            text = '✅ demo — 1 elements\nAXWindow "Demo Window" [0,0,800,600]\n  - [1] AXButton "Save" [10,20,30,40]'
            return {"data": text, "images": [_png_b64()], "structuredContent": None, "isError": False}
        if name == "screenshot":
            return {"data": '{"width": 8, "height": 8, "format": "png"}', "images": [_png_b64()], "structuredContent": None, "isError": False}
        return {"data": {"ok": True, "message": f"{name} ok"}, "images": [], "structuredContent": None, "isError": False}


def test_linux_capture_som_maps_mcp_result_to_capture_result():
    from tools.computer_use.linux_backend import LinuxComputerUseBackend

    backend = LinuxComputerUseBackend()
    fake = FakeSession()
    cast(Any, backend)._session = fake

    cap = backend.capture(mode="som", app="demo")

    assert cap.app == "demo"
    assert cap.window_title == "Demo Window"
    assert cap.width == 8
    assert cap.height == 8
    assert cap.png_b64 == _png_b64()
    assert len(cap.elements) == 1
    assert cap.elements[0].index == 1
    assert fake.calls[0][0] == "list_windows"
    assert fake.calls[1] == ("get_window_state", {"pid": 123, "window_id": 456})


def test_linux_capture_vision_uses_screenshot_tool():
    from tools.computer_use.linux_backend import LinuxComputerUseBackend

    backend = LinuxComputerUseBackend()
    fake = FakeSession()
    cast(Any, backend)._session = fake

    cap = backend.capture(mode="vision")

    assert cap.png_b64 == _png_b64()
    assert cap.width == 8
    assert cap.height == 8
    assert any(name == "screenshot" for name, _args in fake.calls)


def test_linux_click_routes_button_tools_and_target_args():
    from tools.computer_use.linux_backend import LinuxComputerUseBackend

    backend = LinuxComputerUseBackend()
    fake = FakeSession()
    cast(Any, backend)._session = fake
    backend._active_pid = 123
    backend._active_window_id = 456

    res = backend.click(element=7, button="middle")

    assert res.ok is True
    assert fake.calls[-1] == ("middle_click", {"element_index": 7, "pid": 123, "window_id": 456})


def test_linux_requirement_check_respects_platform_and_binary():
    from tools.computer_use import linux_backend

    with patch.object(linux_backend.sys, "platform", "linux"), \
         patch.object(linux_backend.shutil, "which", return_value="/usr/bin/linux-computer-use"):
        assert linux_backend.LinuxComputerUseBackend().is_available() is True

    with patch.object(linux_backend.sys, "platform", "darwin"), \
         patch.object(linux_backend.shutil, "which", return_value="/usr/bin/linux-computer-use"):
        assert linux_backend.LinuxComputerUseBackend().is_available() is False
