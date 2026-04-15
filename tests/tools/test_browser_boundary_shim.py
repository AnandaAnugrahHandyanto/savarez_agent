import importlib

from tools.browser_authority import clear_browser_authority, get_browser_authority, set_browser_authority


class RecordingShim:
    def __init__(self):
        self.calls = []

    def get_session_info(self, task_id=None, authority=None):
        self.calls.append(("get_session_info", task_id, authority.owner_id if authority else None))
        return {"session_name": "shim-session", "owner_key": authority.owner_key if authority else "none"}

    def run_command(self, task_id, command, args=None, timeout=None, authority=None):
        self.calls.append((
            "run_command",
            task_id,
            command,
            list(args or []),
            timeout,
            authority.owner_id if authority else None,
            get_browser_authority().owner_id,
        ))
        return {"success": True, "data": {"command": command}}

    def cleanup_session(self, task_id=None, authority=None):
        self.calls.append(("cleanup_session", task_id, authority.owner_id if authority else None))
        return None


def _reload_browser_tool():
    import tools.browser_tool as browser_tool

    return importlib.reload(browser_tool)


def test_default_browser_boundary_shim_is_inprocess():
    browser_tool = _reload_browser_tool()

    from tools.browser_boundary import InProcessBrowserBoundaryShim

    assert isinstance(browser_tool.get_browser_boundary_shim(), InProcessBrowserBoundaryShim)


def test_set_browser_boundary_shim_overrides_session_lookup():
    browser_tool = _reload_browser_tool()
    shim = RecordingShim()
    browser_tool.set_browser_boundary_shim(shim)

    try:
        session = browser_tool._get_session_info("shim-task")
    finally:
        browser_tool.set_browser_boundary_shim(None)

    assert session["session_name"] == "shim-session"
    assert shim.calls[0][:3] == ("get_session_info", "shim-task", "local")


def test_browser_command_routes_through_boundary_shim_and_preserves_authority():
    browser_tool = _reload_browser_tool()
    shim = RecordingShim()
    browser_tool.set_browser_boundary_shim(shim)
    token = set_browser_authority({
        "source": "remote",
        "owner_id": "owner-shim",
        "capabilities": ["read", "metadata"],
    })

    try:
        result = browser_tool._run_browser_command("shim-task", "snapshot", ["--full"], timeout=12)
    finally:
        clear_browser_authority(token)
        browser_tool.set_browser_boundary_shim(None)

    assert result["success"] is True
    assert shim.calls[0] == (
        "run_command",
        "shim-task",
        "snapshot",
        ["--full"],
        12,
        "owner-shim",
        "owner-shim",
    )


def test_cleanup_browser_routes_through_boundary_shim(monkeypatch):
    browser_tool = _reload_browser_tool()
    shim = RecordingShim()
    browser_tool.set_browser_boundary_shim(shim)
    monkeypatch.setattr(browser_tool, "_is_camofox_mode", lambda: False)

    try:
        browser_tool.cleanup_browser("cleanup-task")
    finally:
        browser_tool.set_browser_boundary_shim(None)

    assert shim.calls[0][:3] == ("cleanup_session", "cleanup-task", "local")
