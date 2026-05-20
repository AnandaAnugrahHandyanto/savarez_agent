"""Regression tests for #28500.

`hermes_cli.auth` constructs ``httpx.Client`` instances around provider
OAuth/OIDC endpoints. When the provider hostname resolves to multiple IPs
(e.g. ``portal.nousresearch.com``) and the first IP refuses the connection,
httpx must be given a non-default transport with ``retries>0`` so that
httpcore iterates over the remaining addrinfo records instead of dying on
the first ``ConnectError``.

These tests pin the contract:
  * ``_httpx_transport()`` returns an ``httpx.HTTPTransport`` with retries.
  * Every ``httpx.Client(...)`` call site inside ``hermes_cli/auth.py``
    passes a ``transport=`` kwarg (so the retrying transport is wired in).
"""
from __future__ import annotations

import ast
from pathlib import Path

import httpx

from hermes_cli import auth as auth_module


def test_httpx_transport_has_retries() -> None:
    transport = auth_module._httpx_transport()
    assert isinstance(transport, httpx.HTTPTransport)
    # httpx stores the retries on the inner connection pool.
    pool = transport._pool
    assert getattr(pool, "_retries", 0) >= 1, (
        "transport must enable httpcore retries so multi-IP DNS resolution "
        "falls back to the next address on ConnectError (issue #28500)"
    )


def test_httpx_transport_retries_constant_at_least_one() -> None:
    assert auth_module._HTTPX_TRANSPORT_RETRIES >= 1


def test_httpx_transport_respects_verify_flag() -> None:
    # Should accept verify= without raising; default verify=True path.
    t_default = auth_module._httpx_transport()
    t_verified = auth_module._httpx_transport(verify=True)
    assert isinstance(t_default, httpx.HTTPTransport)
    assert isinstance(t_verified, httpx.HTTPTransport)


def test_every_httpx_client_callsite_passes_transport() -> None:
    """AST scan: no `httpx.Client(...)` in auth.py without `transport=`.

    Catches future call sites that forget to wire the retrying transport.
    """
    source = Path(auth_module.__file__).read_text()
    tree = ast.parse(source)

    offenders: list[int] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        is_httpx_client = (
            isinstance(func, ast.Attribute)
            and func.attr == "Client"
            and isinstance(func.value, ast.Name)
            and func.value.id == "httpx"
        )
        if not is_httpx_client:
            continue
        kwargs = {kw.arg for kw in node.keywords if kw.arg}
        if "transport" not in kwargs:
            offenders.append(node.lineno)

    assert not offenders, (
        f"httpx.Client(...) calls missing transport= at lines {offenders}; "
        "use transport=_httpx_transport(...) to preserve multi-IP retry "
        "behavior (#28500)"
    )
