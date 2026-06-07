"""m2_supervisor — write-role(implementer) 워커 감독 프로세스 (M2-6 §1-D, R1 배선)

신뢰경계: implementer 워커는 **untrusted**. 부모(이 supervisor)가 모든 신뢰
동작을 수행한다 — spawn→reap(killpg)→capture(부모전용 0700 dir)→phase2 diff→
codex 검토→제안서 조립→capture 이벤트 기록→complete_task. 워커는 capture 본을
위조할 수 없고(부모전용 dir), 직접 complete_task를 호출해도 capture 이벤트가
없으면 _evaluate_gate_recipe의 M2 게이트 3종이 **fail-closed**로 막는다.

프로세스 모델: 이 supervisor는 dispatch_once 루프와 **분리된 별도 프로세스**다
(사용자 결정 A). 게이트웨이 디스패처는 절대 블로킹되지 않는다. supervisor는
**자기 DB 연결**로 complete_task를 호출 → SQLite 단일-라이터-per-프로세스 유지
(6/5 손상 패턴 회피).

R1 상태: ``kanban.implementer_enabled`` flag **off** → 이 모듈은 라이브에서
실행되지 않는다(_default_spawn이 SpawnRefused로 입구거부). 구조 완비 + mock smoke
가능 상태로만 둔다. 실 credential·실 Codex는 R5(각각 별도 승인)이며, 그 자리는
``codex_review_fn`` / ``provider_call`` seam으로 명시한다.

진입점: ``python -m hermes_cli.m2_supervisor --task <id> [--board <b>]``
자체 로그: ``<board-root>/logs/<task>.supervisor.log`` (spawn 실패 진단 위치)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Optional


# 워커 spawn 기본 timeout(초). max_runtime_seconds가 있으면 그쪽 우선.
DEFAULT_TIMEOUT = 300


# ---------------------------------------------------------------------------
# seam 기본 구현 — 테스트는 이 자리에 mock을 주입한다(R1 hermetic smoke).
# ---------------------------------------------------------------------------
def _real_spawn_capture(task, workspace: str, declared_leaves, *,
                        proxy_sock: str, timeout: int):
    """실 워커 spawn: implementer.sbpl 샌드박스 + clean env + PROXY_SOCK.

    **계약(Codex M2-R1 #2)**: 이 seam의 구현체는 반드시 워커를
    start_new_session으로 띄우고, 종료/timeout 후 **killpg(reap)** 한 뒤에야
    capture를 고정해야 한다. ``m2_spawn.run_and_capture`` 가 그 reap+capture를
    이미 보장하며(killpg→capture 순서), capture_dir도 workspace 밖 0700
    mkdtemp로 만든다. R4 배선은 이 함수에서 run_and_capture를 호출하도록 완성한다.

    R4(ARM) 배선 지점. R1에서는 호출되지 않는다(flag off). sandbox-exec +
    프로파일 entry 바이너리 조립은 R4 승인 후 완성. 미배선이면 fail-closed.
    """
    raise NotImplementedError(
        "real worker spawn is R4 (ARM) scope — the implementation MUST reap "
        "(killpg) before capture, via m2_spawn.run_and_capture(..., timeout=timeout). "
        "Inject spawn_capture_fn for tests; live dispatch is refused at "
        "_default_spawn while implementer_enabled is off"
    )


def _real_codex_review(staged_files) -> dict:
    """실 Codex 검토 → verdict {"verdict","high"}. R5(credential) 배선 지점.

    R1 기본은 **fail-closed**: 실 Codex를 돌릴 수 없으므로 BLOCKED를 돌려
    codex_review_passed가 fail → done 차단. (advisory지만 게이트에서는 block.)
    """
    return {"verdict": "BLOCKED", "high": 0,
            "note": "codex review unwired (R5) → fail-closed"}


@contextmanager
def _no_proxy(*_a, **_k):
    """proxy 미사용 컨텍스트(mock smoke·proxy 불필요 경로). sock 경로 None."""
    yield None


# ---------------------------------------------------------------------------
# core — 감독 1회 실행
# ---------------------------------------------------------------------------
def supervise(
    conn,
    task,
    workspace: str,
    *,
    declared_writes,
    deliverable: str,
    run_id: Optional[int] = None,
    spawn_capture_fn: Callable = _real_spawn_capture,
    codex_review_fn: Callable = _real_codex_review,
    proxy_ctx_fn: Callable = _no_proxy,
    timeout: int = DEFAULT_TIMEOUT,
    assemble_proposal: bool = True,
) -> dict[str, Any]:
    """write-role 워커 1명을 감독하고 완료(또는 게이트 차단)까지 몰고간다.

    단계: phase1 검증 → baseline → proxy up → spawn+reap+capture → phase2 diff →
    codex 검토 → 제안서 조립 → ``m2_supervisor_capture`` 이벤트 기록 →
    complete_task(6 게이트 평가). 반환 = {completed, findings?, phase2, verdict,
    captured, capture_dir, error?}.

    모든 신뢰 동작은 부모(이 함수)가 한다. 입력 ``conn`` 은 **이 프로세스 전용**
    연결이어야 한다(단일-라이터 보존).
    """
    from hermes_cli import kanban_db as kdb
    from hermes_cli import m2_manifest_phase2 as mp
    from hermes_cli import m2_spawn

    ws = str(Path(workspace).resolve())
    result: dict[str, Any] = {"completed": False, "task_id": task.id}

    # phase1: 선언 write → M1 검증 → 절대 leaf. 실패 시 ManifestReject 전파(fail-closed).
    declared_leaves = mp.phase1_validate(list(declared_writes), ws)
    result["declared_leaves"] = declared_leaves

    # 워커 실행 전 baseline 스냅샷(phase2 대조 기준).
    baseline = mp.baseline_snapshot(ws)

    capture_dir = None
    try:
        with proxy_ctx_fn(declared_leaves) as proxy_sock:
            # 계약: spawn_capture_fn은 reap(killpg) 후 capture를 고정해야 한다
            # (m2_spawn.run_and_capture가 보장). timeout을 명시 전달한다.
            run = spawn_capture_fn(
                task, ws, declared_leaves, proxy_sock=proxy_sock, timeout=timeout,
            )
        capture_dir = run.get("capture_dir")
        capture = run.get("capture") or {}
        captured = m2_spawn.captured_paths(capture) if capture else (
            run.get("captured_paths") or []
        )
        result["rc"] = run.get("rc")
        result["captured"] = captured
        result["capture_dir"] = capture_dir

        # phase2: 부모가 fs diff 직접 생성·대조(워커 신뢰 0).
        phase2 = mp.phase2_verify(ws, declared_leaves, baseline)
        result["phase2"] = phase2

        # codex 검토(advisory; 게이트에서는 fail→block). 입력=부모 capture 본.
        verdict = codex_review_fn(captured)
        result["verdict"] = verdict

        # 제안서 조립(inert JSON). artifact_exists 게이트의 deliverable.
        if assemble_proposal:
            _assemble_proposal(ws, deliverable, phase2, verdict, captured)

        # capture/diff/verdict를 **부모가** 이벤트로 기록(워커가 못 만듦).
        with kdb.write_txn(conn):
            kdb._append_event(
                conn, task.id, "m2_supervisor_capture",
                {
                    "phase2_result": phase2,
                    "codex_verdict": verdict,
                    "staged_files": captured,   # 부모전용 capture dir 절대경로
                    "capture_dir": capture_dir,
                },
                run_id=run_id,
            )

        # complete_task → _evaluate_gate_recipe가 6 게이트 평가(M2 3종은 위 이벤트 소비).
        try:
            ok = kdb.complete_task(
                conn, task.id,
                summary="implementer supervised run",
                metadata={"artifacts": [deliverable]},
                expected_run_id=run_id,
            )
            result["completed"] = bool(ok)
        except kdb.VerificationFailedError as exc:
            result["completed"] = False
            result["findings"] = exc.findings
            result["error"] = "verification_failed"
    finally:
        # capture dir은 부모전용 임시 — 게이트 평가까지 보존, 종료 시 정리.
        # (complete_task가 deliverable을 durable 복사하므로 capture 본은 폐기 가능.)
        # **안전가드(Codex M2-R1 #3)**: workspace 안/경계는 절대 rmtree하지 않는다
        # (버그·악성 seam이 workspace 경로를 capture_dir로 반환해도 보호). 실
        # 경로는 m2_spawn.run_and_capture가 workspace 밖 mkdtemp(0700)로 만든다.
        if capture_dir and os.path.isdir(capture_dir):
            cd = os.path.realpath(capture_dir)
            wsr = os.path.realpath(ws)
            if cd != wsr and not cd.startswith(wsr + os.sep):
                import shutil
                shutil.rmtree(capture_dir, ignore_errors=True)
    return result


def _assemble_proposal(workspace: str, deliverable: str, phase2: dict,
                       verdict: dict, captured) -> str:
    """부모가 검증 결과로 MERGE_PROPOSAL.json(inert)을 조립한다.

    이것은 **제안서까지**다 — merge·배포·실행은 절대 하지 않는다(마일3 사람 게이트).
    내용은 diff 요약·verdict·capture 포인터뿐인 정적 JSON.
    """
    out = Path(workspace) / deliverable
    out.parent.mkdir(parents=True, exist_ok=True)
    proposal = {
        "kind": "MERGE_PROPOSAL",
        "inert": True,
        "phase2": {
            "ok": phase2.get("ok"),
            "changed": phase2.get("changed"),
            "out_of_manifest": phase2.get("out_of_manifest"),
            "sha256": phase2.get("sha256"),
        },
        "codex_verdict": verdict,
        "captured_count": len(list(captured or [])),
        "note": "proposal only — merge/deploy is a human gate (milestone3)",
    }
    out.write_text(json.dumps(proposal, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(out)


# ---------------------------------------------------------------------------
# CLI 진입점 — R4(ARM) 이후 실 배선. R1에서는 실행되지 않는다.
# ---------------------------------------------------------------------------
def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="hermes_cli.m2_supervisor")
    parser.add_argument("--task", required=True)
    parser.add_argument("--board", default=None)
    args = parser.parse_args(argv)

    from hermes_cli import kanban_db as kdb
    from hermes_cli import m2_implementer_policy as ip

    # 이중 안전: flag off면 supervisor 자체도 거부(입구 _default_spawn 외 2차 방어).
    if not kdb._implementer_enabled():
        print("implementer lane disabled (kanban.implementer_enabled off) → refuse",
              file=sys.stderr)
        return 3

    conn = kdb.connect(board=args.board)
    task = kdb.get_task(conn, args.task)
    if task is None:
        print(f"task not found: {args.task}", file=sys.stderr)
        return 4
    workspace = kdb.resolve_workspace(task, board=args.board)
    run_id = kdb._current_run_id(conn, args.task)

    # R4 seam: 실 워커 declared manifest는 워커 제출본에서 온다. R1 미배선이라
    # deliverable leaf 하나를 기본으로 둔다(실 배선 시 교체).
    deliverable = ip.IMPLEMENTER_POLICY["deliverable"]
    declared_writes = [deliverable]

    res = supervise(
        conn, task, str(workspace),
        declared_writes=declared_writes,
        deliverable=deliverable,
        run_id=run_id,
    )
    print(json.dumps({"completed": res.get("completed"),
                      "error": res.get("error")}, ensure_ascii=False))
    return 0 if res.get("completed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
