import inspect
import json
from pathlib import Path
from types import SimpleNamespace

from scripts import smoke_openai_codex_capabilities as smoke


def _result(model="gpt-5.5", feature="text", ok=True, detail="ok"):
    return smoke.SmokeResult(
        model=model,
        feature=feature,
        ok=ok,
        detail=detail,
        started_at="2026-05-04T10:00:00Z",
        finished_at="2026-05-04T10:00:01Z",
    )


def test_find_regressions_flags_previously_passing_failure():
    baseline = [
        {"model": "gpt-5.5", "feature": "text", "ok": True, "detail": "old ok"},
        {"model": "gpt-5.5", "feature": "vision", "ok": False, "detail": "already broken"},
    ]

    regressions = smoke.find_regressions(
        [_result("gpt-5.5", "text", ok=False), _result("gpt-5.5", "vision", ok=False)],
        baseline,
    )

    assert regressions == [
        {
            "key": "gpt-5.5:text",
            "previous": baseline[0],
            "current": smoke.asdict(_result("gpt-5.5", "text", ok=False)),
            "reason": "failed",
        }
    ]


def test_find_regressions_flags_missing_current_result():
    regressions = smoke.find_regressions([], [{"model": "gpt-5.4-mini", "feature": "tools", "ok": True}])

    assert regressions[0]["key"] == "gpt-5.4-mini:tools"
    assert regressions[0]["reason"] == "missing"
    assert regressions[0]["current"] is None


def test_write_json_and_jsonl_payloads(tmp_path):
    results = [_result()]
    output = tmp_path / "latest.json"
    history = tmp_path / "history.jsonl"

    smoke.write_json(output, results, regressions=[])
    smoke.append_jsonl(history, results)

    payload = json.loads(output.read_text())
    assert payload["schema_version"] == 1
    assert payload["provider"] == "openai-codex"
    assert payload["results"][0]["model"] == "gpt-5.5"
    assert payload["regressions"] == []

    rows = [json.loads(line) for line in history.read_text().splitlines()]
    assert rows[0]["schema_version"] == 1
    assert rows[0]["provider"] == "openai-codex"
    assert rows[0]["run_id"]


def test_load_results_accepts_payload_or_raw_list(tmp_path):
    payload = tmp_path / "payload.json"
    raw = tmp_path / "raw.json"
    result = {"model": "gpt-5.5", "feature": "text", "ok": True}
    payload.write_text(json.dumps({"results": [result]}))
    raw.write_text(json.dumps([result]))

    assert smoke.load_results(payload) == [result]
    assert smoke.load_results(raw) == [result]


def test_resolve_latest_baseline_missing_is_noop(monkeypatch, tmp_path):
    monkeypatch.setattr(smoke, "DEFAULT_BASELINE_PATH", tmp_path / "missing.json")

    assert smoke.resolve_baseline_path(Path("latest")) is None


def test_resolve_latest_baseline_existing(monkeypatch, tmp_path):
    baseline = tmp_path / "baseline.json"
    baseline.write_text("[]")
    monkeypatch.setattr(smoke, "DEFAULT_BASELINE_PATH", baseline)

    assert smoke.resolve_baseline_path(Path("latest")) == baseline


def test_run_one_uses_codex_provider(monkeypatch):
    calls = []

    def fake_call_llm(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="codex-smoke-ok"))])

    monkeypatch.setattr(smoke, "call_llm", fake_call_llm)
    monkeypatch.setattr(smoke, "extract_content_or_reasoning", lambda response: response.choices[0].message.content)

    result = smoke.run_one("gpt-5.4-mini", "text", timeout=1.0)

    assert result.ok is True
    assert calls[0]["provider"] == "openai-codex"
    assert calls[0]["model"] == "gpt-5.4-mini"
    assert "OPENAI_API_KEY" not in inspect.getsource(smoke.run_one)
