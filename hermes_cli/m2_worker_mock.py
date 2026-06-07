"""m2_worker_mock — R4 통제 점화용 **결정적 mock implementer 워커** (LLM 0, 실 credential 0)

R4 목표 = implementer 파이프라인(spawn→reap→capture→phase2→게이트)을 **실 sandbox-exec +
implementer.sbpl + 부모중개 프록시** 위에서 e2e 관찰하는 것. 실제 LLM 추론·실 credential은
R5(별도 승인). 이 모듈은 그 자리를 채우는 **부수효과 없는 mock 워커**다.

이 프로그램은 **샌드박스(implementer.sbpl) 안에서** `ENTRY_BIN m2_worker_mock <MW_0>` 로 실행된다.
샌드박스 계약상 write는 MW_0(선언 manifest leaf) literal + PF_LEAF 뿐이고, network는 PROXY_SOCK
unix-socket egress 하나뿐이다. 따라서 이 워커는:
  1. MW_0(argv[1], 절대경로)에 **benign·inert 변경안**을 O_NOFOLLOW로 기록(부수효과·실행 마커 0).
  2. PROXY_SOCK(env) 있으면 부모 프록시에 template 요청 1회 = **net-deny+프록시-only egress 연결성 증명**
     (mock이라 응답 내용은 쓰지 않음; 실패해도 비치명 — 연결성 확인 목적).

**자기완결(stdlib만)**: hermes_cli import 안 함(clean env에 PYTHONPATH 없음 + import 표면 최소화).
와이어 포맷은 m2_parent_proxy와 동일(4-byte big-endian length || UTF-8 JSON)로 인라인 구현.
"""
from __future__ import annotations

import json
import os
import socket
import struct
import sys


# benign·inert 변경안: 자동실행/부수효과/권한상승 마커 0 (proposal_inert hard 통과 보장).
_MOCK_DELTA = (
    "# implementer mock staged change (R4 점화, 결정적 mock 워커 산출)\n"
    "# 실 LLM·실 credential 0. proposal_inert 게이트 통과용 inert 변경안.\n"
    "MOCK_DELTA_VERSION = 1\n"
)


def _proxy_handshake(sock_path: str, *, timeout: float = 3.0) -> bool:
    """부모 프록시에 template 요청 1회 → 연결성 증명. mock이라 응답은 버린다.
    실패(연결 거부·타임아웃)는 비치명 → False 반환(워커는 계속 진행)."""
    try:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(timeout)
        s.connect(sock_path)
    except OSError:
        return False
    try:
        # m2_parent_proxy 스키마(v=1, kind=llm_call, template_id+slots만; raw prompt 금지).
        req = json.dumps({"v": 1, "kind": "llm_call",
                          "template_id": "mock_refactor", "slots": {},
                          "task_id": "r4-mock"}, ensure_ascii=False).encode("utf-8")
        s.sendall(struct.pack(">I", len(req)) + req)
        hdr = s.recv(4)  # 응답 헤더만 확인(연결성 증명) — 본문 내용 미사용
        return len(hdr) == 4
    except OSError:
        return False
    finally:
        try:
            s.close()
        except OSError:
            pass


def main(argv: list[str]) -> int:
    if len(argv) < 1:
        sys.stderr.write("usage: m2_worker_mock <MW_0_abs>\n")
        return 2
    mw0 = argv[0]
    if not os.path.isabs(mw0):
        sys.stderr.write(f"MW_0는 절대경로여야: {mw0!r}\n")
        return 2

    # MW_0는 부모(run_and_capture._precreate_clean_leaves)가 0600 일반파일로 사전생성한다.
    # O_NOFOLLOW로 symlink 추종 차단하며 truncate-write. (O_CREAT 안 함 = 사전생성분만 기록.)
    try:
        fd = os.open(mw0, os.O_WRONLY | os.O_TRUNC | os.O_NOFOLLOW)
    except OSError as exc:
        sys.stderr.write(f"MW_0 open 실패({type(exc).__name__}): {mw0}\n")
        return 3
    try:
        os.write(fd, _MOCK_DELTA.encode("utf-8"))
    finally:
        os.close(fd)

    # 프록시 연결성 증명(있을 때만, 비치명).
    sock_path = os.environ.get("PROXY_SOCK")
    if sock_path:
        ok = _proxy_handshake(sock_path)
        sys.stderr.write(f"PROXY_SOCK handshake: {'ok' if ok else 'skip/fail (non-fatal)'}\n")

    sys.stdout.write("MOCK_WORKER_DONE\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
