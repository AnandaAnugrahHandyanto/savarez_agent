"""S2 — m2_sandbox.build_implementer_cmd 격리 테스트 (조립 + fail-closed 검증).

실 sandbox-exec 호출은 S5 e2e에서. 여기선 명령/env 조립과 파라미터 거부만 검증.
"""
from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

import pytest

from hermes_cli import m2_sandbox as sb


def _synth_with_worker(tmp_path: Path) -> Path:
    """SYNTH_ROOT(=workspace) 준비: 워커 스크립트 복사 + source_staging/."""
    ws = tmp_path / "ws"; ws.mkdir()
    (ws / "source_staging").mkdir()
    src = Path(__file__).resolve().parents[2] / "hermes_cli" / sb.WORKER_SCRIPT_NAME
    shutil.copy(str(src), str(ws / sb.WORKER_SCRIPT_NAME))
    return ws


def _canonical_sock() -> tuple[str, str]:
    d = tempfile.mkdtemp(prefix="m2sbx_", dir="/private/tmp")
    return os.path.join(d, "p.sock"), d


def test_resolve_runtime_returns_existing():
    entry, r2 = sb.resolve_runtime()
    assert os.path.isfile(entry)
    assert os.path.isdir(r2)
    assert entry.startswith(r2 + os.sep)


def test_build_cmd_happy_path():
    import tempfile as _t
    base = _t.mkdtemp(prefix="m2sbx_ws_")
    ws = _synth_with_worker(Path(base))
    leaf = str(ws / "source_staging" / "gen.py")
    sock, sdir = _canonical_sock()
    try:
        cmd, env = sb.build_implementer_cmd(str(ws), [leaf], proxy_sock=sock)
        # sandbox-exec + -p 인라인정책 + 6개 -D + -- + entry 실행
        assert cmd[0] == sb.SANDBOX_EXEC
        assert "-p" in cmd
        policy = cmd[cmd.index("-p") + 1]
        assert "(version 1)" in policy and "(deny default)" in policy
        joined = " ".join(cmd)
        for key in ("SYNTH_ROOT=", "R2=", "MW_0=", "PF_LEAF=", "ENTRY_BIN=", "PROXY_SOCK="):
            assert key in joined
        assert "--" in cmd
        # `--` 뒤 = ENTRY_BIN -I -S -B <worker> <MW_0>
        tail = cmd[cmd.index("--") + 1:]
        assert tail[1:4] == ["-I", "-S", "-B"]
        assert tail[-2].endswith(sb.WORKER_SCRIPT_NAME)
        # MW_0는 canonical(realpath) → endswith로 확인
        assert tail[-1].endswith("source_staging/gen.py")
        assert os.path.isabs(tail[-1])
        # env: credential 0, PROXY_SOCK만 egress
        assert env["PROXY_SOCK"] == sock
        assert "OPENAI_API_KEY" not in env and "ANTHROPIC_API_KEY" not in env
        assert "GITHUB_TOKEN" not in env
        assert set(env) == {"PATH", "HOME", "TMPDIR", "LC_ALL", "PROXY_SOCK"}
    finally:
        shutil.rmtree(base, ignore_errors=True)
        shutil.rmtree(sdir, ignore_errors=True)


def test_build_cmd_rejects_multi_leaf(tmp_path):
    ws = _synth_with_worker(tmp_path)
    sock, sdir = _canonical_sock()
    try:
        with pytest.raises(sb.SandboxAssemblyError, match="단일 MW_0"):
            sb.build_implementer_cmd(
                str(ws),
                [str(ws / "source_staging" / "a.py"), str(ws / "source_staging" / "b.py")],
                proxy_sock=sock)
    finally:
        shutil.rmtree(sdir, ignore_errors=True)


def test_build_cmd_rejects_leaf_outside_synth(tmp_path):
    ws = _synth_with_worker(tmp_path)
    outside = tmp_path / "outside.py"
    sock, sdir = _canonical_sock()
    try:
        with pytest.raises(sb.SandboxAssemblyError, match="SYNTH_ROOT 밖"):
            sb.build_implementer_cmd(str(ws), [str(outside)], proxy_sock=sock)
    finally:
        shutil.rmtree(sdir, ignore_errors=True)


def test_build_cmd_rejects_noncanonical_sock(tmp_path):
    ws = _synth_with_worker(tmp_path)
    leaf = str(ws / "source_staging" / "gen.py")
    # /tmp/... → realpath /private/tmp/... ≠ self → 비canonical
    with pytest.raises(sb.SandboxAssemblyError, match="canonical"):
        sb.build_implementer_cmd(str(ws), [leaf], proxy_sock="/tmp/x/p.sock")


def test_prepare_synth_happy(tmp_path):
    ws = tmp_path / "ws"; ws.mkdir()
    root = sb.prepare_synth_workspace(str(ws))
    assert os.path.realpath(str(ws)) == root
    wscript = ws / sb.WORKER_SCRIPT_NAME
    st = os.lstat(str(wscript))
    import stat as _s
    assert _s.S_ISREG(st.st_mode) and not _s.S_ISLNK(st.st_mode)
    assert (ws / "synth" / "sample_input.py").exists()
    # 재실행 멱등(symlink-safe 재기록)
    sb.prepare_synth_workspace(str(ws))


def test_prepare_synth_rejects_real_data_marker(tmp_path):
    ws = tmp_path / "ws"; ws.mkdir()
    (ws / ".env").write_text("OPENAI_API_KEY=sk-secret\n", encoding="utf-8")  # 실데이터 마커
    with pytest.raises(sb.SandboxAssemblyError, match="실데이터/비밀 마커"):
        sb.prepare_synth_workspace(str(ws))


def test_prepare_synth_rejects_git(tmp_path):
    ws = tmp_path / "ws"; ws.mkdir()
    (ws / ".git").mkdir()
    with pytest.raises(sb.SandboxAssemblyError, match="실데이터/비밀 마커"):
        sb.prepare_synth_workspace(str(ws))


def test_prepare_synth_rejects_symlinked_worker_dst(tmp_path):
    # 사전 심은 symlink가 워커 스크립트 자리를 차지 → 추종 쓰기 거부(H2).
    ws = tmp_path / "ws"; ws.mkdir()
    victim = tmp_path / "victim.txt"
    victim.write_text("DO NOT OVERWRITE\n", encoding="utf-8")
    (ws / sb.WORKER_SCRIPT_NAME).symlink_to(victim)
    with pytest.raises(sb.SandboxAssemblyError, match="symlink dst 거부"):
        sb.prepare_synth_workspace(str(ws))
    assert victim.read_text(encoding="utf-8") == "DO NOT OVERWRITE\n"  # 미변경


def test_prepare_synth_rejects_symlinked_dir(tmp_path):
    ws = tmp_path / "ws"; ws.mkdir()
    outside = tmp_path / "outside"; outside.mkdir()
    (ws / "source_staging").symlink_to(outside)  # symlink 디렉토리
    with pytest.raises(sb.SandboxAssemblyError, match="symlink 디렉토리 거부"):
        sb.prepare_synth_workspace(str(ws))


def test_build_cmd_rejects_missing_worker_script(tmp_path):
    ws = tmp_path / "ws"; ws.mkdir()
    (ws / "source_staging").mkdir()
    # 워커 스크립트 미복사 → fail-closed
    leaf = str(ws / "source_staging" / "gen.py")
    sock, sdir = _canonical_sock()
    try:
        with pytest.raises(sb.SandboxAssemblyError, match="워커 스크립트"):
            sb.build_implementer_cmd(str(ws), [leaf], proxy_sock=sock)
    finally:
        shutil.rmtree(sdir, ignore_errors=True)
