from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PANEL_TSX = ROOT / "web" / "src" / "components" / "ActiveEnvelopePanel.tsx"
MISSION_TSX = ROOT / "web" / "src" / "pages" / "MissionControlPage.tsx"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_active_envelope_panel_renders_empty_state_heading():
    source = _read(PANEL_TSX)

    assert "No Active Task Envelope" in source


def test_active_envelope_panel_renders_required_empty_state_copy():
    source = _read(PANEL_TSX)

    for phrase in (
        "Display only",
        "No active authorization",
        "Operational actions locked",
        "Discussion/status only",
        "Active lane: Unset",
        "Active mode: Unset",
        "Execution boundary: No active authorization",
        "Allowed actions: None declared",
        "Forbidden actions: Unknown",
        "Checkpoint: None",
        "Repo state: Unknown / not probed",
        "Evidence: No envelope evidence attached",
        "Data source: No persisted envelope",
        "No persisted envelope",
    ):
        assert phrase in source


def test_active_envelope_panel_omits_forbidden_labels_and_controls():
    source = _read(PANEL_TSX)

    for label in (
        ">Run<",
        ">Execute<",
        ">Start<",
        ">Launch<",
        ">Deploy<",
        ">Restart<",
        ">Push<",
        ">Open<",
        ">Edit<",
        ">Create<",
        ">Approve<",
        ">Reject<",
        ">Sync<",
        ">Publish<",
    ):
        assert label not in source

    for token in (
        "<button",
        "<form",
        "<input",
        "<select",
        "<textarea",
        "<a ",
        "href=",
        "onClick",
        "role=\"button\"",
    ):
        assert token not in source


def test_active_envelope_panel_is_static_and_imports_no_api_helper():
    source = _read(PANEL_TSX)

    for token in (
        "@/lib/api",
        "api.",
        "fetch(",
        "XMLHttpRequest",
        "method:",
        "POST",
        "PUT",
        "PATCH",
        "DELETE",
        "useEffect",
        "useState",
    ):
        assert token not in source


def test_mission_control_page_mounts_active_envelope_panel():
    source = _read(MISSION_TSX)

    assert "ActiveEnvelopePanel" in source
    assert "<ActiveEnvelopePanel />" in source
