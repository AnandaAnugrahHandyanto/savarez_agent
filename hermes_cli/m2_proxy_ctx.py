"""m2_proxy_ctx — implementer 워커용 부모중개 프록시 컨텍스트 (R4=mock provider, S4)

supervise의 ``proxy_ctx_fn(declared_leaves)`` 자리에 주입된다. canonical /private/tmp
PROXY_SOCK을 만들고 ``m2_parent_proxy.ParentProxy``를 **mock provider_call**(고정 응답, 실 키 0)로
기동한 뒤 sock 경로를 yield한다. 퇴장 시 서버 정지 + sock·임시 디렉토리 정리.

**R5 경계**: 실 credential·실 provider 호출은 여기 ``_mock_provider_call``을 실 provider로
교체하는 **1지점**뿐이다. R4는 mock만 — 워커가 프록시 egress·template 경로를 실제로 타지만
응답은 합성이고 어떤 실 키도 프로세스에 없다.
"""
from __future__ import annotations

import os
import shutil
import tempfile
from contextlib import contextmanager

from hermes_cli import m2_parent_proxy as pp

# 워커(m2_worker_mock)가 요청하는 template_id. slot 없음(slots={}).
MOCK_TEMPLATE_ID = "mock_refactor"
MOCK_TEMPLATES = {MOCK_TEMPLATE_ID: "implementer mock refactor prompt (no slots, R4)."}


def _mock_provider_call(prompt: str, max_tokens: int) -> str:
    """R4 mock provider — 실 LLM·실 credential 0. 고정 inert 응답.
    R5에서 이 함수만 실 provider 호출(credential은 클로저)로 교체한다."""
    return ("MOCK_PROVIDER_RESPONSE: inert refactor suggestion. "
            "no real LLM, no credential (R4).")


@contextmanager
def mock_proxy_ctx(declared_leaves=None):
    """canonical /private/tmp PROXY_SOCK + mock ParentProxy 기동 컨텍스트.

    yield = canonical sock 절대경로(seatbelt unix-socket 매칭용). 퇴장 시 전부 정리.
    """
    sdir = tempfile.mkdtemp(prefix="m2proxy_", dir="/private/tmp")
    sock = os.path.join(sdir, "p.sock")
    # canonical 보장: /private/tmp는 realpath==self, 미존재 leaf도 부모가 canonical이라 OK.
    if os.path.realpath(sock) != sock:
        shutil.rmtree(sdir, ignore_errors=True)
        raise RuntimeError(f"PROXY_SOCK canonical 아님: {sock}")
    audit = os.path.join(sdir, "audit.log")
    proxy = pp.ParentProxy(
        sock,
        provider="mock",
        provider_allowlist=["mock"],
        templates=MOCK_TEMPLATES,
        provider_call=_mock_provider_call,
        audit_log_path=audit,
    )
    proxy.start()
    try:
        yield sock
    finally:
        try:
            proxy.stop()
        finally:
            shutil.rmtree(sdir, ignore_errors=True)
