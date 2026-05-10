import json

from gateway.action_requests import (
    build_action_buttons,
    dispatch_action_request,
    load_action_request,
    register_action_handler,
)


def test_build_action_buttons_stores_payload(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    buttons = build_action_buttons(
        [{"label": "Create PR", "kind": "sentry", "action": "create_pr"}],
        {"project": "incremnt", "issue": {"id": "INCR-1"}},
    )

    assert buttons == [{"label": "Create PR", "callback_data": buttons[0]["callback_data"]}]
    assert buttons[0]["callback_data"].startswith("ar:sentry-")
    request_id = buttons[0]["callback_data"].split(":", 1)[1]
    stored = json.loads((tmp_path / "action_requests" / f"{request_id}.json").read_text())
    assert stored["kind"] == "sentry"
    assert stored["action"] == "create_pr"
    assert stored["payload"]["project"] == "incremnt"


def test_dispatch_action_request_uses_registered_handler(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    buttons = build_action_buttons(
        [{"label": "Create PR", "kind": "sentry", "action": "create_pr"}],
        {"project": "incremnt"},
    )
    request_id = buttons[0]["callback_data"].split(":", 1)[1]
    seen = {}

    def handler(req):
        seen["req"] = req
        return "launched"

    register_action_handler("sentry", "create_pr", handler)

    assert dispatch_action_request(request_id) == "launched"
    assert seen["req"] == load_action_request(request_id)
    assert seen["req"].payload["project"] == "incremnt"
