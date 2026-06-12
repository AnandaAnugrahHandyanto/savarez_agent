"""Tests for `hermes portal topup` — the /usage → portal top-up handoff.

The terminal opens the portal billing page with the top-up modal open and gets
out of the way: no polling, no payment confirmation, no waiting state (roadmap
phase 2a). These tests assert the handoff beats: identity line, org-pinned URL
with ?topup=open, and the no-wait closing copy.
"""

from __future__ import annotations

import pytest

import hermes_cli.portal_cli as portal_cli
from hermes_cli.nous_account import NousPortalAccountInfo


def _account(**kwargs) -> NousPortalAccountInfo:
    kwargs.setdefault("logged_in", True)
    kwargs.setdefault("source", "account_api")
    kwargs.setdefault("fresh", True)
    kwargs.setdefault("portal_base_url", "https://portal.example.test")
    return NousPortalAccountInfo(**kwargs)


@pytest.fixture
def _strip_ansi():
    import re

    ansi = re.compile(r"\x1b\[[0-9;]*m")
    return lambda s: ansi.sub("", s)


def test_topup_opens_org_pinned_url_and_prints_identity(monkeypatch, capsys, _strip_ansi):
    info = _account(org_slug="acme", org_name="Acme Inc", email="alice@example.test")
    monkeypatch.setattr(
        "hermes_cli.nous_account.get_nous_portal_account_info",
        lambda *a, **kw: info,
    )
    opened = {}
    monkeypatch.setattr(
        portal_cli.webbrowser, "open", lambda url: opened.setdefault("url", url) or True
    )

    rc = portal_cli._cmd_topup(object())

    assert rc == 0
    assert opened["url"] == "https://portal.example.test/orgs/acme/billing?topup=open"
    out = _strip_ansi(capsys.readouterr().out)
    # Identity line before opening (roadmap §4.4).
    assert "Topping up as alice@example.test" in out
    assert "org Acme Inc" in out
    # No-wait closing copy.
    assert "Complete your top-up in the browser" in out
    assert "/usage" in out


def test_topup_falls_back_to_legacy_url_when_slug_null(monkeypatch, capsys):
    info = _account(org_slug=None, email="alice@example.test")
    monkeypatch.setattr(
        "hermes_cli.nous_account.get_nous_portal_account_info",
        lambda *a, **kw: info,
    )
    opened = {}
    monkeypatch.setattr(
        portal_cli.webbrowser, "open", lambda url: opened.setdefault("url", url) or True
    )

    rc = portal_cli._cmd_topup(object())

    assert rc == 0
    assert opened["url"] == "https://portal.example.test/billing?topup=open"
    assert "/orgs/" not in opened["url"]


def test_topup_prints_url_when_browser_cannot_open(monkeypatch, capsys):
    info = _account(org_slug="acme", email="alice@example.test")
    monkeypatch.setattr(
        "hermes_cli.nous_account.get_nous_portal_account_info",
        lambda *a, **kw: info,
    )
    # Headless: webbrowser.open returns False — still not a hard failure.
    monkeypatch.setattr(portal_cli.webbrowser, "open", lambda url: False)

    rc = portal_cli._cmd_topup(object())

    assert rc == 0
    out = capsys.readouterr().out
    assert "https://portal.example.test/orgs/acme/billing?topup=open" in out
    assert "Could not launch a browser" in out
    # Still shows the no-wait copy so the flow is complete.
    assert "Complete your top-up in the browser" in out


def test_topup_browser_raising_is_not_fatal(monkeypatch, capsys):
    info = _account(org_slug="acme", email="alice@example.test")
    monkeypatch.setattr(
        "hermes_cli.nous_account.get_nous_portal_account_info",
        lambda *a, **kw: info,
    )

    def _boom(url):
        raise RuntimeError("no display")

    monkeypatch.setattr(portal_cli.webbrowser, "open", _boom)

    rc = portal_cli._cmd_topup(object())

    assert rc == 0
    assert "Could not launch a browser" in capsys.readouterr().out


def test_topup_not_logged_in_prompts_login(monkeypatch, capsys, _strip_ansi):
    info = _account(logged_in=False)
    monkeypatch.setattr(
        "hermes_cli.nous_account.get_nous_portal_account_info",
        lambda *a, **kw: info,
    )
    called = {}
    monkeypatch.setattr(
        portal_cli.webbrowser, "open", lambda url: called.setdefault("opened", True)
    )

    rc = portal_cli._cmd_topup(object())

    assert rc == 1
    assert "opened" not in called  # never opens a browser when logged out
    out = _strip_ansi(capsys.readouterr().out)
    assert "Not logged into Nous Portal" in out
    assert "hermes portal" in out


def test_topup_account_fetch_failure_prompts_login(monkeypatch, capsys, _strip_ansi):
    def _boom(*a, **kw):
        raise RuntimeError("portal down")

    monkeypatch.setattr(
        "hermes_cli.nous_account.get_nous_portal_account_info", _boom
    )
    monkeypatch.setattr(portal_cli.webbrowser, "open", lambda url: True)

    rc = portal_cli._cmd_topup(object())

    assert rc == 1
    out = _strip_ansi(capsys.readouterr().out)
    assert "Not logged into Nous Portal" in out


def test_portal_topup_dispatch_routes_to_cmd(monkeypatch):
    seen = {}
    monkeypatch.setattr(portal_cli, "_cmd_topup", lambda args: seen.setdefault("hit", 0) or 0)

    class _Args:
        portal_command = "topup"

    assert portal_cli.portal_command(_Args()) == 0
    assert "hit" in seen
