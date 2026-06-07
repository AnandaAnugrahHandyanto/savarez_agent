"""S1 — m2_worker_mock(R4 결정적 mock 워커) 격리 테스트.

워커는 MW_0(선언 leaf)에만 benign·inert 변경안을 쓰고, 범위 밖 write 0,
symlink leaf는 O_NOFOLLOW로 거부, PROXY_SOCK 핸드셰이크는 비치명. 라이브 무접촉.
"""
from __future__ import annotations

import os
import socket
import struct
import threading
from pathlib import Path

from hermes_cli import m2_worker_mock as mw


def _precreate_leaf(ws: Path, rel: str = "source_staging/gen.py") -> Path:
    leaf = ws / rel
    leaf.parent.mkdir(parents=True, exist_ok=True)
    # 부모(run_and_capture)가 하는 0600 사전생성 모사
    fd = os.open(str(leaf), os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    os.close(fd)
    return leaf


def test_worker_writes_benign_delta_to_mw0(tmp_path, monkeypatch):
    ws = tmp_path / "ws"; ws.mkdir()
    leaf = _precreate_leaf(ws)
    monkeypatch.delenv("PROXY_SOCK", raising=False)
    rc = mw.main([str(leaf)])
    assert rc == 0
    txt = leaf.read_text(encoding="utf-8")
    assert "MOCK_DELTA_VERSION" in txt
    # 범위 밖 write 0: workspace에 leaf 외 새 파일 없음
    files = [p for p in ws.rglob("*") if p.is_file()]
    assert files == [leaf], files


def test_worker_inert_content_passes_proposal_inert(tmp_path, monkeypatch):
    # 산출 내용이 proposal_inert hard 마커(eval/exec/shebang/exec-bit)를 안 가짐.
    from hermes_cli import m2_gate_checks as gc
    ws = tmp_path / "ws"; ws.mkdir()
    leaf = _precreate_leaf(ws)
    monkeypatch.delenv("PROXY_SOCK", raising=False)
    assert mw.main([str(leaf)]) == 0
    res = gc.proposal_inert([str(leaf)])
    assert res["ok"] is True, res["hard_violations"]


def test_worker_rejects_symlink_leaf(tmp_path, monkeypatch):
    ws = tmp_path / "ws"; ws.mkdir()
    (ws / "source_staging").mkdir(parents=True)
    target = tmp_path / "outside.py"
    target.write_text("victim\n", encoding="utf-8")
    sym = ws / "source_staging" / "gen.py"
    sym.symlink_to(target)  # leaf가 symlink → O_NOFOLLOW로 거부돼야
    monkeypatch.delenv("PROXY_SOCK", raising=False)
    rc = mw.main([str(sym)])
    assert rc == 3  # open 실패(ELOOP)
    # 외부 victim 미변경(추종 안 함)
    assert target.read_text(encoding="utf-8") == "victim\n"


def test_worker_requires_absolute_mw0(tmp_path):
    assert mw.main(["relative/path.py"]) == 2
    assert mw.main([]) == 2


def test_worker_proxy_handshake_connectivity(tmp_path, monkeypatch):
    # PROXY_SOCK가 있으면 template 요청 1회 → 부모가 응답 헤더 보내면 ok.
    # AF_UNIX 경로는 ~104자 제한 → 짧은 /private/tmp 경로 사용(실 설계의 canonical 제약과 동일).
    import tempfile
    ws = tmp_path / "ws"; ws.mkdir()
    leaf = _precreate_leaf(ws)
    sdir = tempfile.mkdtemp(prefix="m2p_", dir="/private/tmp")
    sock_path = os.path.join(sdir, "p.sock")
    srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    srv.bind(sock_path)
    srv.listen(1)
    seen = {}

    def _serve():
        srv.settimeout(5)
        try:
            c, _ = srv.accept()
            hdr = c.recv(4)
            (n,) = struct.unpack(">I", hdr)
            body = c.recv(n)
            seen["req"] = body
            # 응답 헤더 + 본문(mock)
            resp = b'{"ok":true}'
            c.sendall(struct.pack(">I", len(resp)) + resp)
            c.close()
        except OSError:
            pass

    th = threading.Thread(target=_serve, daemon=True)
    th.start()
    monkeypatch.setenv("PROXY_SOCK", sock_path)
    rc = mw.main([str(leaf)])
    th.join(timeout=6)
    srv.close()
    import shutil
    shutil.rmtree(sdir, ignore_errors=True)
    assert rc == 0
    assert seen.get("req") is not None  # 워커가 프록시에 template 요청 전송함
    import json as _j
    body = _j.loads(seen["req"])
    assert body["kind"] == "llm_call" and body["template_id"] == "mock_refactor"
    assert "prompt" not in body and "messages" not in body  # raw prompt 금지 계약


def test_worker_proxy_failure_is_nonfatal(tmp_path, monkeypatch):
    # PROXY_SOCK가 죽은 경로여도 워커는 MW_0 기록 후 성공.
    ws = tmp_path / "ws"; ws.mkdir()
    leaf = _precreate_leaf(ws)
    monkeypatch.setenv("PROXY_SOCK", str(tmp_path / "nonexistent.sock"))
    assert mw.main([str(leaf)]) == 0
    assert "MOCK_DELTA_VERSION" in leaf.read_text(encoding="utf-8")
