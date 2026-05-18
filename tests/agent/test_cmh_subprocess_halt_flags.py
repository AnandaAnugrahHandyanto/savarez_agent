import json

import pytest

from agent.cmh_subprocess.halt_flags import (
    default_halt_flags,
    halt_flags_path,
    is_halted,
    load_halt_flags,
    save_halt_flags,
)


def test_missing_halt_file_uses_defaults_and_does_not_halt(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))

    state = load_halt_flags()

    assert state.flags == default_halt_flags()
    assert is_halted("cowork_headless").halted is False


def test_halt_flags_path_uses_hermes_home_state_file(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))

    assert halt_flags_path() == tmp_path / "state" / "cmh_halt_flags.json"


def test_all_true_blocks_every_class(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    path = halt_flags_path()
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"all": True}), encoding="utf-8")

    cowork = is_halted("cowork_headless")
    codex = is_halted("codex_auto_dispatch")

    assert cowork.halted is True
    assert cowork.active_flag == "all"
    assert codex.halted is True
    assert codex.active_flag == "all"


def test_class_halt_blocks_matching_class_only(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    path = halt_flags_path()
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"cowork_headless": True}), encoding="utf-8")

    cowork = is_halted("cowork_headless")
    codex = is_halted("codex_auto_dispatch")

    assert cowork.halted is True
    assert cowork.active_flag == "cowork_headless"
    assert codex.halted is False


def test_malformed_json_fails_closed(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    path = halt_flags_path()
    path.parent.mkdir(parents=True)
    path.write_text("{not valid json", encoding="utf-8")

    state = load_halt_flags()
    decision = is_halted("cowork_headless")

    assert state.malformed is True
    assert decision.halted is True
    assert decision.active_flag == "state_error"
    assert str(path) in decision.message


@pytest.mark.parametrize(
    ("payload", "invalid_key"),
    [
        ({"all": 0}, "all"),
        ({"all": None}, "all"),
        ({"all": ""}, "all"),
        ({"cowork_headless": []}, "cowork_headless"),
    ],
)
def test_non_bool_known_halt_flag_values_fail_closed(
    tmp_path, monkeypatch, payload, invalid_key
):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    path = halt_flags_path()
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(payload), encoding="utf-8")

    state = load_halt_flags()
    decision = is_halted("cowork_headless")

    assert state.flags == default_halt_flags()
    assert state.malformed is True
    assert invalid_key in state.error
    assert state.path == path
    assert decision.halted is True
    assert decision.active_flag == "state_error"


def test_save_halt_flags_rejects_non_bool_known_values_without_writing(tmp_path):
    path = tmp_path / "state" / "cmh_halt_flags.json"

    with pytest.raises(ValueError, match="all"):
        save_halt_flags({"all": "false"}, path=path)

    assert not path.exists()
