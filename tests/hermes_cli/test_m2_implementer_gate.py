"""M2 write-role(implementer) 라이브 배선 R1 테스트.

Phase C (role_gate write 분기) · D (_evaluate_gate_recipe 3 check) ·
E (_implementer_enabled flag) · F (_default_spawn 분기 + m2_supervisor) 를
**격리 DB**(tmp_path + HERMES_HOME, 라이브 무접촉)에서 독립 검증한다.

신뢰경계 핵심: implementer 워커=untrusted. 부모(supervisor)만 capture를
기록하고, 그 capture가 없으면 M2 게이트 3종이 **fail-closed**로 완료를 막는다.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from hermes_cli import kanban_db as kb
from hermes_cli import role_gate
from hermes_cli import m2_supervisor


# ---------------------------------------------------------------------------
# 격리 DB fixture (라이브 ~/.hermes/state.db 절대 무접촉)
# ---------------------------------------------------------------------------
@pytest.fixture
def kanban_home(tmp_path, monkeypatch):
    home = tmp_path / ".hermes"
    home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(home))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    kb.init_db()
    return home


# write 정책에 합치하는 implementer 계획(kill switch + [write:proposal/...] + deps).
WRITE_PLAN = """\
구현 계획 (implementer)
- 의존성: 입력 스펙 spec.md, 산출물 경로 proposal/MERGE_PROPOSAL.json
- 중단 조건: 선언 밖 write 시 중단한다. 위험 시 STOP 후 보고.
- 단계:
  1. [read] 입력 스펙 열람
  2. [write:source_staging/gen.py] 변경안 staging
  3. [write:proposal/MERGE_PROPOSAL.json] 제안서 작성
"""


# ===========================================================================
# Phase E — _implementer_enabled flag (기본 off, fail-closed)
# ===========================================================================
def test_implementer_flag_unset_is_off():
    assert kb._implementer_enabled({}) is False


def test_implementer_flag_false_is_off():
    assert kb._implementer_enabled({"implementer_enabled": False}) is False


def test_implementer_flag_true_is_on():
    assert kb._implementer_enabled({"implementer_enabled": True}) is True


def test_implementer_flag_string_true_fails_closed():
    # YAML이 아닌 문자열 "true" 는 off (엄격 is True). 오설정 시 fail-closed.
    assert kb._implementer_enabled({"implementer_enabled": "true"}) is False


# ===========================================================================
# Phase C — role_gate write 분기 + recipe 디스패치
# ===========================================================================
def test_check_plan_write_compliant_passes():
    res = role_gate.check_plan(WRITE_PLAN, policy="write")
    assert res["passed"] is True, res["findings"]
    assert {f["type"] for f in res["findings"]} == {"kill_switch", "scope_write", "dependencies"}


def test_check_plan_write_missing_write_tag_fails():
    plan = WRITE_PLAN.replace("  2. [write:source_staging/gen.py] 변경안 staging\n", "") \
                     .replace("  3. [write:proposal/MERGE_PROPOSAL.json] 제안서 작성\n",
                              "  3. [read] 검토\n")
    res = role_gate.check_plan(plan, policy="write")
    assert res["passed"] is False
    sw = next(f for f in res["findings"] if f["type"] == "scope_write")
    assert sw["ok"] is False


def test_check_plan_write_illegal_area_fails():
    plan = WRITE_PLAN.replace("[write:source_staging/gen.py]", "[write:/etc/passwd]")
    res = role_gate.check_plan(plan, policy="write")
    assert res["passed"] is False
    sw = next(f for f in res["findings"] if f["type"] == "scope_write")
    assert sw["ok"] is False


def test_readonly_policy_unchanged_by_write_branch():
    # read-only 기존 동작 무손상 회귀(같은 finding 타입).
    ro = """\
조사 계획
- 의존성: 입력 키워드, 산출물 경로 note.md
- 중단 조건: 실패 시 중단한다. STOP.
- 단계: 1. [read] 수집 2. [write:조사노트] note.md 작성
"""
    res = role_gate.check_plan(ro, policy="read-only")
    assert res["passed"] is True
    assert {f["type"] for f in res["findings"]} == {"kill_switch", "scope_readonly", "dependencies"}


def test_gate_recipe_for_implementer_six_checks():
    r = role_gate.gate_recipe_for_assignee("implementer")
    assert r is not None
    assert [c["type"] for c in r["checks"]] == [
        "plan_gate", "artifact_exists", "no_child_cards",
        "writes_match_manifest", "codex_review_passed", "proposal_inert",
    ]
    # plan_gate 정책이 write 여야 한다.
    pg = next(c for c in r["checks"] if c["type"] == "plan_gate")
    assert pg["policy"] == "write"


def test_create_task_auto_attaches_implementer_recipe(kanban_home):
    with kb.connect() as conn:
        tid = kb.create_task(conn, title="impl job", assignee="implementer")
        t = kb.get_task(conn, tid)
        assert t.gate_recipe is not None
        types = {c["type"] for c in json.loads(t.gate_recipe)["checks"]}
        assert types == {
            "plan_gate", "artifact_exists", "no_child_cards",
            "writes_match_manifest", "codex_review_passed", "proposal_inert",
        }


# ===========================================================================
# Phase D — _evaluate_gate_recipe M2 3 check (capture 소비 / fail-closed)
# ===========================================================================
def _make_impl_task(conn, ws, deliverable="proposal/MERGE_PROPOSAL.json"):
    recipe = role_gate.gate_recipe_for_assignee("implementer", deliverable)
    return kb.create_task(
        conn, title="impl", assignee="implementer",
        workspace_path=str(ws), gate_recipe=recipe,
    )


def _record_capture(conn, tid, *, phase2, verdict, staged_files):
    with kb.write_txn(conn):
        kb._append_event(conn, tid, "m2_supervisor_capture", {
            "phase2_result": phase2,
            "codex_verdict": verdict,
            "staged_files": staged_files,
        })


def _write_deliverable(ws):
    p = ws / "proposal" / "MERGE_PROPOSAL.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"kind": "MERGE_PROPOSAL", "inert": True}), encoding="utf-8")


def test_m2_gate_fail_closed_without_capture(kanban_home, tmp_path):
    ws = tmp_path / "ws"; ws.mkdir()
    _write_deliverable(ws)
    with kb.connect() as conn:
        tid = _make_impl_task(conn, ws)
        kb.record_plan_submission(conn, tid, WRITE_PLAN)
        # supervisor capture 미존재 → M2 3종 fail-closed → 완료 차단.
        with pytest.raises(kb.VerificationFailedError) as ei:
            kb.complete_task(conn, tid, result="x")
        types = {f["type"] for f in ei.value.findings if not f["ok"]}
        assert {"writes_match_manifest", "codex_review_passed", "proposal_inert"} <= types


def test_load_m2_capture_binds_to_run(kanban_home, tmp_path):
    # Codex M2-R1 #1 수정 입증: capture는 현재 run에 바인딩. 다른 run의
    # capture(stale)는 매칭 안 됨 → None → fail-closed.
    ws = tmp_path / "ws"; ws.mkdir()
    with kb.connect() as conn:
        tid = _make_impl_task(conn, ws)
        with kb.write_txn(conn):
            kb._append_event(conn, tid, "m2_supervisor_capture",
                             {"phase2_result": {"ok": True}}, run_id=101)
        with kb.write_txn(conn):
            kb._append_event(conn, tid, "m2_supervisor_capture",
                             {"phase2_result": {"ok": False}}, run_id=202)
        assert kb._load_m2_capture(conn, tid, run_id=101)["phase2_result"]["ok"] is True
        assert kb._load_m2_capture(conn, tid, run_id=202)["phase2_result"]["ok"] is False
        # 어느 run에도 없는 run_id → None(stale 재사용 차단)
        assert kb._load_m2_capture(conn, tid, run_id=303) is None
        # run_id 미지정(runless 컨텍스트) → latest 허용
        assert kb._load_m2_capture(conn, tid)["phase2_result"]["ok"] is False


def test_m2_gate_passes_with_good_capture(kanban_home, tmp_path):
    ws = tmp_path / "ws"; ws.mkdir()
    _write_deliverable(ws)
    staged = tmp_path / "cap" / "gen.py"
    staged.parent.mkdir(parents=True, exist_ok=True)
    staged.write_text("x = 1\n", encoding="utf-8")  # inert
    with kb.connect() as conn:
        tid = _make_impl_task(conn, ws)
        kb.record_plan_submission(conn, tid, WRITE_PLAN)
        _record_capture(
            conn, tid,
            phase2={"ok": True, "changed": [str(staged)]},
            verdict={"verdict": "PASS", "high": 0},
            staged_files=[str(staged)],
        )
        assert kb.complete_task(conn, tid, result="done") is True


def test_m2_gate_blocks_on_phase2_mismatch(kanban_home, tmp_path):
    ws = tmp_path / "ws"; ws.mkdir()
    _write_deliverable(ws)
    staged = tmp_path / "cap" / "gen.py"
    staged.parent.mkdir(parents=True, exist_ok=True)
    staged.write_text("x = 1\n", encoding="utf-8")
    with kb.connect() as conn:
        tid = _make_impl_task(conn, ws)
        kb.record_plan_submission(conn, tid, WRITE_PLAN)
        _record_capture(
            conn, tid,
            phase2={"ok": False, "reasons": ["선언 밖 변경"]},
            verdict={"verdict": "PASS", "high": 0},
            staged_files=[str(staged)],
        )
        with pytest.raises(kb.VerificationFailedError) as ei:
            kb.complete_task(conn, tid, result="x")
        assert any(f["type"] == "writes_match_manifest" and not f["ok"]
                   for f in ei.value.findings)


def test_m2_gate_blocks_on_codex_blocked(kanban_home, tmp_path):
    ws = tmp_path / "ws"; ws.mkdir()
    _write_deliverable(ws)
    staged = tmp_path / "cap" / "gen.py"
    staged.parent.mkdir(parents=True, exist_ok=True)
    staged.write_text("x = 1\n", encoding="utf-8")
    with kb.connect() as conn:
        tid = _make_impl_task(conn, ws)
        kb.record_plan_submission(conn, tid, WRITE_PLAN)
        _record_capture(
            conn, tid,
            phase2={"ok": True, "changed": [str(staged)]},
            verdict={"verdict": "BLOCKED", "high": 0},
            staged_files=[str(staged)],
        )
        with pytest.raises(kb.VerificationFailedError) as ei:
            kb.complete_task(conn, tid, result="x")
        assert any(f["type"] == "codex_review_passed" and not f["ok"]
                   for f in ei.value.findings)


def test_m2_gate_blocks_on_proposal_not_inert(kanban_home, tmp_path):
    ws = tmp_path / "ws"; ws.mkdir()
    _write_deliverable(ws)
    staged = tmp_path / "cap" / "gen.py"
    staged.parent.mkdir(parents=True, exist_ok=True)
    staged.write_text("#!/bin/sh\nrm -rf /\n", encoding="utf-8")  # shebang → hard violation
    with kb.connect() as conn:
        tid = _make_impl_task(conn, ws)
        kb.record_plan_submission(conn, tid, WRITE_PLAN)
        _record_capture(
            conn, tid,
            phase2={"ok": True, "changed": [str(staged)]},
            verdict={"verdict": "PASS", "high": 0},
            staged_files=[str(staged)],
        )
        with pytest.raises(kb.VerificationFailedError) as ei:
            kb.complete_task(conn, tid, result="x")
        assert any(f["type"] == "proposal_inert" and not f["ok"]
                   for f in ei.value.findings)


# ===========================================================================
# Phase F — _default_spawn 분기 (flag off→refuse / on→supervisor 비블로킹)
# ===========================================================================
def test_default_spawn_refuses_implementer_when_flag_off(kanban_home, tmp_path, monkeypatch):
    monkeypatch.setattr(kb, "_implementer_enabled", lambda *a, **k: False)
    ws = tmp_path / "ws"; ws.mkdir()
    with kb.connect() as conn:
        tid = kb.create_task(conn, title="impl", assignee="implementer",
                             workspace_path=str(ws))
        task = kb.get_task(conn, tid)
    with pytest.raises(kb.SpawnRefused):
        kb._default_spawn(task, str(ws))


def test_default_spawn_launches_supervisor_when_flag_on(kanban_home, tmp_path, monkeypatch):
    monkeypatch.setattr(kb, "_implementer_enabled", lambda *a, **k: True)
    captured = {}

    class _FakeProc:
        pid = 424242

    def _fake_popen(cmd, **kw):
        captured["cmd"] = cmd
        captured["kw"] = kw
        return _FakeProc()

    monkeypatch.setattr(subprocess, "Popen", _fake_popen)
    ws = tmp_path / "ws"; ws.mkdir()
    with kb.connect() as conn:
        tid = kb.create_task(conn, title="impl", assignee="implementer",
                             workspace_path=str(ws))
        task = kb.get_task(conn, tid)
    pid = kb._default_spawn(task, str(ws))
    assert pid == 424242  # 비블로킹: supervisor PID 즉시 반환
    assert "hermes_cli.m2_supervisor" in captured["cmd"]
    assert captured["kw"].get("start_new_session") is True


def test_default_spawn_refuses_when_sbpl_missing(kanban_home, tmp_path, monkeypatch):
    monkeypatch.setattr(kb, "_implementer_enabled", lambda *a, **k: True)
    # sbpl 경로를 존재하지 않게 가장 → fail-closed.
    import hermes_cli.kanban_db as _kdb
    real_is_file = Path.is_file

    def _fake_is_file(self):
        if self.name == "implementer.sbpl":
            return False
        return real_is_file(self)

    monkeypatch.setattr(Path, "is_file", _fake_is_file)
    ws = tmp_path / "ws"; ws.mkdir()
    with kb.connect() as conn:
        tid = kb.create_task(conn, title="impl", assignee="implementer",
                             workspace_path=str(ws))
        task = kb.get_task(conn, tid)
    with pytest.raises(kb.SpawnRefused):
        kb._default_spawn(task, str(ws))


# ===========================================================================
# Phase F — m2_supervisor.supervise 통합 smoke (mock spawn/codex, 격리 DB)
# ===========================================================================
def _mock_spawn_capture_factory(staged_src: str):
    """mock 워커: 부모전용 capture dir에 inert staged 파일을 둔 것처럼 반환."""
    def _fn(task, workspace, declared_leaves, *, proxy_sock, timeout=None):
        import tempfile
        cap_dir = tempfile.mkdtemp(prefix="m2cap_test_")
        leaf = declared_leaves[0]
        # 워크스페이스 leaf 생성(phase2 diff가 변경을 보도록)
        Path(leaf).parent.mkdir(parents=True, exist_ok=True)
        Path(leaf).write_text(staged_src, encoding="utf-8")
        # capture 본(부모전용)
        cap = Path(cap_dir) / Path(leaf).name
        cap.write_text(staged_src, encoding="utf-8")
        return {"rc": 0, "stdout": "WORKER_DONE", "stderr": "",
                "capture": {leaf: {"captured": str(cap)}},
                "capture_dir": cap_dir}
    return _fn


def test_supervise_smoke_done_with_good_run(kanban_home, tmp_path):
    ws = tmp_path / "ws"; ws.mkdir()
    deliverable = "proposal/MERGE_PROPOSAL.json"
    with kb.connect() as conn:
        tid = _make_impl_task(conn, ws, deliverable)
        kb.record_plan_submission(conn, tid, WRITE_PLAN)
        task = kb.get_task(conn, tid)
        res = m2_supervisor.supervise(
            conn, task, str(ws),
            declared_writes=["source_staging/gen.py"],
            deliverable=deliverable,
            spawn_capture_fn=_mock_spawn_capture_factory("x = 1\n"),
            codex_review_fn=lambda staged: {"verdict": "PASS", "high": 0},
            timeout=10,
        )
        assert res["completed"] is True, res
        # 게이트가 6 check 모두 평가했고 done 됐는지 확인.
        assert kb.get_task(conn, tid).status == "done"
        # supervisor가 제안서를 조립했는지(artifact_exists 입력).
        assert (ws / deliverable).exists()


def test_supervise_smoke_blocked_on_codex(kanban_home, tmp_path):
    ws = tmp_path / "ws"; ws.mkdir()
    deliverable = "proposal/MERGE_PROPOSAL.json"
    with kb.connect() as conn:
        tid = _make_impl_task(conn, ws, deliverable)
        kb.record_plan_submission(conn, tid, WRITE_PLAN)
        task = kb.get_task(conn, tid)
        res = m2_supervisor.supervise(
            conn, task, str(ws),
            declared_writes=["source_staging/gen.py"],
            deliverable=deliverable,
            spawn_capture_fn=_mock_spawn_capture_factory("x = 1\n"),
            codex_review_fn=lambda staged: {"verdict": "BLOCKED", "high": 1},
            timeout=10,
        )
        assert res["completed"] is False
        assert res.get("error") == "verification_failed"
        assert any(f["type"] == "codex_review_passed" and not f["ok"]
                   for f in res["findings"])
        assert kb.get_task(conn, tid).status != "done"


# ===========================================================================
# Phase H — dispatch_once 레벨 격리: flag off → implementer dispatchable 0
# ===========================================================================
def test_dispatch_skips_implementer_without_profile(kanban_home, tmp_path):
    # 1차 방어: implementer 디스크 프로파일 부재 → skipped_nonspawnable.
    # R1은 프로파일을 디스크에 만들지 않으므로 implementer는 애초에 spawn 후보가 아니다.
    ws = tmp_path / "ws"; ws.mkdir()
    with kb.connect() as conn:
        tid = kb.create_task(conn, title="impl", assignee="implementer",
                             workspace_path=str(ws))
        kb.record_plan_submission(conn, tid, WRITE_PLAN)
        res = kb.dispatch_once(conn)
        spawned_ids = [s[0] for s in res.spawned]
        assert tid not in spawned_ids  # dispatchable 0
        assert tid in res.skipped_nonspawnable


def test_dispatch_refuses_implementer_when_flag_off_even_with_profile(
        kanban_home, tmp_path, monkeypatch):
    # 2차 방어: 프로파일이 있다고 가정해도 flag off → _default_spawn이
    # SpawnRefused → spawn_failed. 절대 spawned에 들어가지 않는다.
    import hermes_cli.profiles as _profiles
    monkeypatch.setattr(_profiles, "profile_exists", lambda name: True)
    monkeypatch.setattr(kb, "_implementer_enabled", lambda *a, **k: False)
    ws = tmp_path / "ws"; ws.mkdir()
    with kb.connect() as conn:
        tid = kb.create_task(conn, title="impl", assignee="implementer",
                             workspace_path=str(ws))
        kb.record_plan_submission(conn, tid, WRITE_PLAN)
        res = kb.dispatch_once(conn)
        spawned_ids = [s[0] for s in res.spawned]
        assert tid not in spawned_ids  # SpawnRefused → dispatchable 0
        # spawn_failed 이벤트가 기록됐는지(claim 해제·fail-closed) 확인.
        ev = conn.execute(
            "SELECT COUNT(*) FROM task_events WHERE task_id = ? "
            "AND kind IN ('spawn_failed', 'auto_blocked')", (tid,)
        ).fetchone()[0]
        assert ev >= 1
