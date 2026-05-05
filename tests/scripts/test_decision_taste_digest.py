import json
from pathlib import Path

from scripts.decision_taste_digest import load_decisions, run


def test_decision_taste_digest_writes_wiki_state_and_runs(tmp_path):
    ledger = tmp_path / "decisions.jsonl"
    state = tmp_path / "state.json"
    wiki = tmp_path / "decision-taste-digest.md"
    rows = [
        {
            "decision_id": "dq-1",
            "choice": "A",
            "selected_label": "Use compact buttons",
            "user_id": "111",
            "title": "Decision UI",
            "recommendation": "A",
            "taste_signal": "Does Joohyun prefer low-friction supervision?",
            "recorded_at": "2026-05-05T00:00:00+00:00",
        },
        {
            "decision_id": "dq-2",
            "choice": "__other__",
            "selected_label": "Other / 직접 입력",
            "free_text_reason": "Keep this separate from generic memory.",
            "user_id": "111",
            "title": "Taste memory",
            "recommendation": "B",
            "taste_signal": "Where should taste signals compile?",
            "recorded_at": "2026-05-05T00:01:00+00:00",
        },
    ]
    ledger.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows), encoding="utf-8")

    output = run(ledger_path=ledger, state_path=state, wiki_path=wiki, no_cmem=True)

    assert "processed 2 new record" in output
    assert wiki.exists()
    text = wiki.read_text(encoding="utf-8")
    assert "Joohyun Decision Taste Digest" in text
    assert "Does Joohyun prefer low-friction supervision?" in text
    assert "Keep this separate from generic memory." in text
    saved_state = json.loads(state.read_text(encoding="utf-8"))
    assert len(saved_state["processed_keys"]) == 2
    assert (tmp_path / "taste_digest_runs.jsonl").exists()

    # Second run is silent/idempotent because all records are processed.
    assert run(ledger_path=ledger, state_path=state, wiki_path=wiki, no_cmem=True) == ""


def test_load_decisions_ignores_invalid_json(tmp_path):
    ledger = tmp_path / "decisions.jsonl"
    ledger.write_text('{"decision_id":"ok","choice":"A"}\nnot-json\n', encoding="utf-8")
    records = load_decisions(ledger)
    assert len(records) == 1
    assert records[0].decision_id == "ok"
