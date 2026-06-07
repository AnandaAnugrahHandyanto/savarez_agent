"""m2_spawn — write-role 워커 spawn + reap + capture (M2-5, Codex M2 #2 TOCTOU 방어)

문제(재현 확정): 워커가 benign을 쓰고 종료 → 부모가 snapshot/gate/proposal 수행 → setsid로 그룹 탈출한
fork 자식이 그 뒤 같은 MW_0를 malicious로 덮어씀. 부모는 stale benign을 검증/제안.

방어(이중):
  1. **reap**: start_new_session으로 워커를 자기 프로세스그룹 리더로 띄우고, 종료/timeout 후 killpg(SIGKILL)로
     그룹 잔존 자식 제거(일반 fork 자식 차단).
  2. **capture**: reap 직후 선언 leaf를 **부모 전용 capture_dir**(워커 write 불가 영역)로 즉시 복사·고정.
     setsid 탈출 자식이 이후 MW_0를 덮어써도, 검증·proposal은 capture 본을 쓰므로 무의미해짐.
  → "benign 검증 / malicious 산출물" 분리 불가. 검증시점==capture시점==제안바이트.
"""
from __future__ import annotations

import os
import signal
import stat as _stat
import subprocess
import tempfile
from pathlib import Path

from hermes_cli import m2_manifest_phase2 as mp  # noqa: E402


class SpawnRefused(Exception):
    """fail-closed: 안전하게 spawn할 수 없음(사전오염 등)."""


def _reap(pid: int) -> None:
    """워커 프로세스그룹(pgid==pid, start_new_session) 통째 SIGKILL. 그룹 내 잔존 자식 제거."""
    try:
        os.killpg(pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError, OSError):
        pass


def _precreate_clean_leaves(declared_leaves) -> None:
    """Codex M2 r2 #High3: 각 선언 leaf를 **부모 소유 fresh 일반파일**(빈, 0600)로 사전생성.
    기존 path가 symlink/하드링크면 제거 후 재생성(precheck가 이미 fail-closed라 도달 시 정상경로)."""
    for leaf in declared_leaves:
        try:
            st = os.lstat(leaf)
            if _stat.S_ISLNK(st.st_mode) or (_stat.S_ISREG(st.st_mode) and st.st_nlink > 1):
                os.unlink(leaf)         # 오염 inode 제거(precheck 통과분이라 방어적)
                raise FileNotFoundError
            if _stat.S_ISREG(st.st_mode):
                continue                # 깨끗한 기존 파일 유지
        except FileNotFoundError:
            pass
        except OSError:
            pass
        Path(leaf).parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(leaf, os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        os.close(fd)


def run_and_capture(cmd, env, *, timeout: int, declared_leaves, capture_dir=None,
                    workspace=None) -> dict:
    """워커 spawn → 종료/timeout → reap → capture. 반환 {rc, stdout, stderr, capture, capture_dir}.

    하드닝(Codex M2 r2):
      - spawn 전 precheck_leaf_safety(workspace) fail-closed + 깨끗한 leaf 사전생성(#High3).
      - capture_dir은 **workspace 밖 부모 전용 mkdtemp**(#NEW High). caller capture_dir 무시.
    """
    if workspace is not None:
        ok, reasons = mp.precheck_leaf_safety(workspace, declared_leaves)
        if not ok:
            raise SpawnRefused(f"사전오염 감지 → spawn 거부: {reasons}")
    _precreate_clean_leaves(declared_leaves)
    # capture_dir = workspace 밖 fresh 부모 전용 경로(symlink·사전오염 차단)
    cap_dir = tempfile.mkdtemp(prefix="m2cap_")
    os.chmod(cap_dir, 0o700)

    proc = subprocess.Popen(
        cmd, env=env, stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        close_fds=True, start_new_session=True)
    rc, out, err = None, "", ""
    try:
        out, err = proc.communicate(timeout=timeout)
        rc = proc.returncode
    except subprocess.TimeoutExpired:
        _reap(proc.pid)
        try:
            out, err = proc.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            try:
                proc.kill()
            except OSError:
                pass
            try:
                out, err = proc.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                out, err = "", ""
        rc = -signal.SIGKILL
    # 정상 종료여도 그룹 잔존 자식 제거(TOCTOU 사후 write 차단) → 즉시 capture
    _reap(proc.pid)
    capture = mp.capture_leaves(declared_leaves, cap_dir, workspace=workspace)
    return {"rc": rc, "stdout": out or "", "stderr": err or "",
            "capture": capture, "capture_dir": cap_dir}


def captured_paths(capture: dict) -> list[str]:
    """capture 결과에서 실제 고정된(captured≠None) 파일 경로 리스트. gate/proposal 입력."""
    return [v["captured"] for v in capture.values() if v.get("captured")]
