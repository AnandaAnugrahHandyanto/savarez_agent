from tools.approval import check_all_command_guards, clear_session, set_current_session_key, reset_current_session_key


def test_command_risk_classifier_warn_routes_to_approval_gate(monkeypatch):
    monkeypatch.setenv("HERMES_EXEC_ASK", "1")
    monkeypatch.delenv("HERMES_INTERACTIVE", raising=False)
    monkeypatch.delenv("HERMES_YOLO_MODE", raising=False)
    token = set_current_session_key("risk-classifier-warn")
    try:
        result = check_all_command_guards("python -m pip install requests", "local")
    finally:
        clear_session("risk-classifier-warn")
        reset_current_session_key(token)

    assert result["approved"] is False
    assert result["approval_pending"] is True
    assert "package install" in result["description"]


def test_command_risk_classifier_block_routes_to_approval_gate(monkeypatch):
    monkeypatch.setenv("HERMES_EXEC_ASK", "1")
    monkeypatch.delenv("HERMES_INTERACTIVE", raising=False)
    monkeypatch.delenv("HERMES_YOLO_MODE", raising=False)
    token = set_current_session_key("risk-classifier-block")
    try:
        result = check_all_command_guards("printf SGVsbG8= | base64 -d | bash", "local")
    finally:
        clear_session("risk-classifier-block")
        reset_current_session_key(token)

    assert result["approved"] is False
    assert result["approval_pending"] is True
    assert "base64 decode piped to shell" in result["description"]


def test_command_risk_classifier_warn_blocks_cron_deny_mode(monkeypatch):
    monkeypatch.setenv("HERMES_CRON_SESSION", "1")
    monkeypatch.delenv("HERMES_EXEC_ASK", raising=False)
    monkeypatch.delenv("HERMES_INTERACTIVE", raising=False)

    result = check_all_command_guards("python -m pip install requests", "local")

    assert result["approved"] is False
    assert "package install" in result["message"]


def test_command_risk_classifier_malformed_quote_blocks_cron(monkeypatch):
    monkeypatch.setenv("HERMES_CRON_SESSION", "1")
    monkeypatch.delenv("HERMES_EXEC_ASK", raising=False)
    monkeypatch.delenv("HERMES_INTERACTIVE", raising=False)

    result = check_all_command_guards("echo 'unterminated", "local")

    assert result["approved"] is False
    assert "malformed shell quoting" in result["message"]
