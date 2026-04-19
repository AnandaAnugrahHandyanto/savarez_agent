"""Tests for agent/claude_keychain.py — Claude Code credential discovery.

Parsing and label tests are platform-agnostic. Tests that depend on
``/usr/bin/security`` behaviour are gated behind ``platform.system() == 'Darwin'``
and still mock subprocess so they never actually shell out.
"""

from __future__ import annotations

import json
import platform
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agent import claude_keychain
from agent.claude_keychain import (
    ClaudeAccount,
    ClaudeCredentials,
    SOURCE_FILE,
    SOURCE_KEYCHAIN_PREFIX,
    _ACCT_ATTR_RE,
    _SERVICE_ATTR_RE,
    _build_labels,
    _label_for_subscription,
    _parse_credentials_blob,
    read_all_accounts,
    read_selected_account,
    write_credentials,
)

_IS_DARWIN = platform.system() == "Darwin"


# ---------------------------------------------------------------------------
# _parse_credentials_blob
# ---------------------------------------------------------------------------


class TestParseCredentialsBlob:
    def test_wrapped_shape(self):
        raw = json.dumps({
            "claudeAiOauth": {
                "accessToken": "a",
                "refreshToken": "r",
                "expiresAt": 100,
            }
        })
        creds = _parse_credentials_blob(raw)
        assert creds is not None
        assert creds.access_token == "a"
        assert creds.refresh_token == "r"
        assert creds.expires_at == 100
        assert creds.scopes is None
        assert creds.subscription_type is None

    def test_flat_shape(self):
        raw = json.dumps({
            "accessToken": "a",
            "refreshToken": "r",
            "expiresAt": 100,
        })
        creds = _parse_credentials_blob(raw)
        assert creds is not None
        assert creds.access_token == "a"
        assert creds.refresh_token == "r"
        assert creds.expires_at == 100

    def test_missing_refresh_token_returns_none(self):
        raw = json.dumps({"accessToken": "a"})
        assert _parse_credentials_blob(raw) is None

    def test_missing_access_token_returns_none(self):
        raw = json.dumps({"refreshToken": "r", "expiresAt": 1})
        assert _parse_credentials_blob(raw) is None

    def test_mcp_only_entry_returns_none(self):
        # mcpOAuth without a claudeAiOauth/accessToken is an MCP-server
        # credential, not a user credential.
        raw = json.dumps({"mcpOAuth": {"foo": "bar"}})
        assert _parse_credentials_blob(raw) is None

    def test_preserves_scopes_list(self):
        raw = json.dumps({
            "claudeAiOauth": {
                "accessToken": "a",
                "refreshToken": "r",
                "expiresAt": 100,
                "scopes": ["user:inference", "user:profile"],
            }
        })
        creds = _parse_credentials_blob(raw)
        assert creds is not None
        assert creds.scopes == ["user:inference", "user:profile"]

    def test_string_expires_at_is_coerced_to_int(self):
        raw = json.dumps({
            "claudeAiOauth": {
                "accessToken": "a",
                "refreshToken": "r",
                "expiresAt": "1234",
            }
        })
        creds = _parse_credentials_blob(raw)
        assert creds is not None
        assert creds.expires_at == 1234
        assert isinstance(creds.expires_at, int)

    def test_invalid_json_returns_none(self):
        assert _parse_credentials_blob("{not json") is None
        assert _parse_credentials_blob("") is None

    def test_non_dict_json_returns_none(self):
        assert _parse_credentials_blob(json.dumps([1, 2, 3])) is None
        assert _parse_credentials_blob(json.dumps("string")) is None

    def test_subscription_type_preserved(self):
        raw = json.dumps({
            "claudeAiOauth": {
                "accessToken": "a",
                "refreshToken": "r",
                "expiresAt": 100,
                "subscriptionType": "max",
            }
        })
        creds = _parse_credentials_blob(raw)
        assert creds is not None
        assert creds.subscription_type == "max"


# ---------------------------------------------------------------------------
# Labels
# ---------------------------------------------------------------------------


class TestLabelForSubscription:
    def test_pro(self):
        assert _label_for_subscription("pro") == "Claude Pro"

    def test_max(self):
        assert _label_for_subscription("max") == "Claude Max"

    def test_max5x(self):
        assert _label_for_subscription("max5x") == "Claude Max"

    def test_max20x(self):
        assert _label_for_subscription("max20x") == "Claude Max"

    def test_none_returns_bare_claude(self):
        assert _label_for_subscription(None) == "Claude"

    def test_empty_string_returns_bare_claude(self):
        assert _label_for_subscription("") == "Claude"

    def test_custom_subscription_formats_title(self):
        assert _label_for_subscription("custom") == "Claude custom"

    def test_mixed_case_pro_is_normalized(self):
        # Implementation lowercases before matching.
        assert _label_for_subscription("PRO") == "Claude Pro"


def _mk_account(label: str, source: str = "file") -> ClaudeAccount:
    creds = ClaudeCredentials(access_token="a", refresh_token="r", expires_at=0)
    return ClaudeAccount(label=label, source=source, credentials=creds)


class TestBuildLabels:
    def test_single_account_label_unchanged(self):
        accts = [_mk_account("Claude Pro")]
        _build_labels(accts)
        assert accts[0].label == "Claude Pro"

    def test_duplicates_get_numeric_suffix(self):
        accts = [
            _mk_account("Claude Max", source="keychain:a"),
            _mk_account("Claude Max", source="keychain:b"),
            _mk_account("Claude Pro", source="keychain:c"),
        ]
        _build_labels(accts)
        labels = [a.label for a in accts]
        assert labels == ["Claude Max 1", "Claude Max 2", "Claude Pro"]

    def test_mixed_duplicates(self):
        accts = [
            _mk_account("Claude Pro"),
            _mk_account("Claude Max"),
            _mk_account("Claude Pro"),
            _mk_account("Claude Max"),
        ]
        _build_labels(accts)
        assert [a.label for a in accts] == [
            "Claude Pro 1",
            "Claude Max 1",
            "Claude Pro 2",
            "Claude Max 2",
        ]


# ---------------------------------------------------------------------------
# write_credentials — file branch (platform-agnostic)
# ---------------------------------------------------------------------------


class TestWriteCredentialsFile:
    def test_writes_expected_json_to_file_source(self, tmp_path, monkeypatch):
        target = tmp_path / ".credentials.json"
        monkeypatch.setattr(claude_keychain, "_FILE_PATH", target)

        creds = ClaudeCredentials(
            access_token="new-access",
            refresh_token="new-refresh",
            expires_at=12345,
        )
        ok = write_credentials(SOURCE_FILE, creds, raw_blob={})
        assert ok is True
        assert target.exists()

        data = json.loads(target.read_text(encoding="utf-8"))
        oauth = data["claudeAiOauth"]
        assert oauth["accessToken"] == "new-access"
        assert oauth["refreshToken"] == "new-refresh"
        assert oauth["expiresAt"] == 12345

    def test_preserves_scopes_when_provided(self, tmp_path, monkeypatch):
        target = tmp_path / ".credentials.json"
        monkeypatch.setattr(claude_keychain, "_FILE_PATH", target)

        creds = ClaudeCredentials(
            access_token="a",
            refresh_token="r",
            expires_at=1,
            scopes=["user:inference", "user:profile"],
        )
        write_credentials(SOURCE_FILE, creds, raw_blob={})
        data = json.loads(target.read_text(encoding="utf-8"))
        assert data["claudeAiOauth"]["scopes"] == [
            "user:inference",
            "user:profile",
        ]

    def test_preserves_subscription_type_when_provided(self, tmp_path, monkeypatch):
        target = tmp_path / ".credentials.json"
        monkeypatch.setattr(claude_keychain, "_FILE_PATH", target)

        creds = ClaudeCredentials(
            access_token="a",
            refresh_token="r",
            expires_at=1,
            subscription_type="max",
        )
        write_credentials(SOURCE_FILE, creds, raw_blob={})
        data = json.loads(target.read_text(encoding="utf-8"))
        assert data["claudeAiOauth"]["subscriptionType"] == "max"

    def test_preserves_extra_raw_blob_fields(self, tmp_path, monkeypatch):
        target = tmp_path / ".credentials.json"
        monkeypatch.setattr(claude_keychain, "_FILE_PATH", target)

        creds = ClaudeCredentials("a", "r", 1)
        write_credentials(
            SOURCE_FILE,
            creds,
            raw_blob={"unrelatedField": "preserve-me"},
        )
        data = json.loads(target.read_text(encoding="utf-8"))
        assert data["unrelatedField"] == "preserve-me"

    def test_unknown_source_returns_false(self, tmp_path, monkeypatch):
        target = tmp_path / ".credentials.json"
        monkeypatch.setattr(claude_keychain, "_FILE_PATH", target)

        creds = ClaudeCredentials("a", "r", 1)
        ok = write_credentials("not-a-real-source", creds, raw_blob={})
        assert ok is False


# ---------------------------------------------------------------------------
# Regex extraction (platform-agnostic — tests the parser only)
# ---------------------------------------------------------------------------


class TestKeychainRegexParsers:
    def test_service_attr_extracts_primary_and_extra(self):
        # Representative fragment from `security dump-keychain` output —
        # two Claude Code entries, one primary, one with a -<hex> suffix.
        sample = """
        keychain: "login.keychain-db"
        class: "genp"
        attributes:
            0x00000007 <blob>="Claude Code-credentials"
            "acct"<blob>="se0nghe0n"
        ---
        keychain: "login.keychain-db"
        class: "genp"
        attributes:
            0x00000007 <blob>="Claude Code-credentials-abc123"
            "acct"<blob>="other-user"
        """

        services = sorted({m.group(1) for m in _SERVICE_ATTR_RE.finditer(sample)})
        assert services == [
            "Claude Code-credentials",
            "Claude Code-credentials-abc123",
        ]

    def test_acct_attr_extracts_username(self):
        sample = '"acct"<blob>="se0nghe0n"'
        m = _ACCT_ATTR_RE.search(sample)
        assert m is not None
        assert m.group(1) == "se0nghe0n"

    def test_acct_attr_extracts_empty_username(self):
        sample = '"acct"<blob>=""'
        m = _ACCT_ATTR_RE.search(sample)
        assert m is not None
        assert m.group(1) == ""

    def test_service_attr_ignores_unrelated_services(self):
        sample = """
            0x00000007 <blob>="Some Other App-credentials"
            0x00000007 <blob>="Claude Code-credentials"
        """
        services = sorted({m.group(1) for m in _SERVICE_ATTR_RE.finditer(sample)})
        assert services == ["Claude Code-credentials"]


# ---------------------------------------------------------------------------
# Keychain lookup — Darwin only (still mocked, never touches the real CLI)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not _IS_DARWIN, reason="Keychain subprocess paths only on macOS")
class TestFindKeychainServicesDarwin:
    def test_parses_dump_keychain_output(self):
        sample_stdout = (
            'keychain: "login.keychain-db"\n'
            'class: "genp"\n'
            'attributes:\n'
            '    0x00000007 <blob>="Claude Code-credentials"\n'
            'keychain: "login.keychain-db"\n'
            'class: "genp"\n'
            'attributes:\n'
            '    0x00000007 <blob>="Claude Code-credentials-deadbeef"\n'
        )
        fake = MagicMock(returncode=0, stdout=sample_stdout, stderr="")

        with patch.object(claude_keychain, "_security", return_value=fake) as mock_sec:
            services = claude_keychain._find_keychain_services()

        mock_sec.assert_called_once()
        assert services == [
            "Claude Code-credentials",
            "Claude Code-credentials-deadbeef",
        ]

    def test_returns_empty_list_on_security_failure(self):
        fake = MagicMock(returncode=1, stdout="", stderr="error")
        with patch.object(claude_keychain, "_security", return_value=fake):
            assert claude_keychain._find_keychain_services() == []

    def test_returns_empty_list_on_security_exception(self):
        with patch.object(
            claude_keychain,
            "_security",
            side_effect=subprocess.TimeoutExpired("security", 10.0),
        ):
            assert claude_keychain._find_keychain_services() == []


@pytest.mark.skipif(not _IS_DARWIN, reason="Keychain subprocess paths only on macOS")
class TestFindAccountNameDarwin:
    def test_extracts_acct_from_security_output(self):
        fake = MagicMock(
            returncode=0,
            stdout='attributes:\n    "acct"<blob>="se0nghe0n"\n',
            stderr="",
        )
        with patch.object(claude_keychain, "_security", return_value=fake):
            name = claude_keychain._find_account_name("Claude Code-credentials")
        assert name == "se0nghe0n"

    def test_returns_none_when_security_fails(self):
        fake = MagicMock(returncode=1, stdout="", stderr="err")
        with patch.object(claude_keychain, "_security", return_value=fake):
            assert claude_keychain._find_account_name("whatever") is None

    def test_returns_none_when_acct_attr_missing(self):
        fake = MagicMock(
            returncode=0,
            stdout="attributes:\n    0x00000007 <blob>=\"x\"\n",
            stderr="",
        )
        with patch.object(claude_keychain, "_security", return_value=fake):
            assert claude_keychain._find_account_name("whatever") is None


# ---------------------------------------------------------------------------
# read_selected_account
# ---------------------------------------------------------------------------


def _acct(label: str, source: str, token: str = "a") -> ClaudeAccount:
    creds = ClaudeCredentials(
        access_token=token,
        refresh_token="r",
        expires_at=0,
    )
    return ClaudeAccount(label=label, source=source, credentials=creds)


class TestReadSelectedAccount:
    def test_returns_none_when_no_accounts(self, tmp_path):
        with patch.object(claude_keychain, "read_all_accounts", return_value=[]):
            assert read_selected_account(source_path=tmp_path / "sel.txt") is None

    def test_uses_persisted_source_when_present(self, tmp_path):
        sel_file = tmp_path / "sel.txt"
        sel_file.write_text("keychain:Claude Code-credentials-second", encoding="utf-8")
        accts = [
            _acct("Claude Max", "keychain:Claude Code-credentials", token="first"),
            _acct(
                "Claude Max",
                "keychain:Claude Code-credentials-second",
                token="second",
            ),
        ]
        with patch.object(claude_keychain, "read_all_accounts", return_value=accts):
            chosen = read_selected_account(source_path=sel_file)
        assert chosen is not None
        assert chosen.credentials.access_token == "second"

    def test_falls_back_to_first_when_persisted_missing(self, tmp_path):
        sel_file = tmp_path / "sel.txt"  # not created
        accts = [
            _acct("Claude Pro", "file", token="first"),
            _acct("Claude Max", "keychain:X", token="second"),
        ]
        with patch.object(claude_keychain, "read_all_accounts", return_value=accts):
            chosen = read_selected_account(source_path=sel_file)
        assert chosen is not None
        assert chosen.credentials.access_token == "first"

    def test_falls_back_to_first_when_persisted_value_no_longer_matches(self, tmp_path):
        sel_file = tmp_path / "sel.txt"
        sel_file.write_text("keychain:gone", encoding="utf-8")
        accts = [
            _acct("Claude Pro", "file", token="first"),
        ]
        with patch.object(claude_keychain, "read_all_accounts", return_value=accts):
            chosen = read_selected_account(source_path=sel_file)
        assert chosen is not None
        assert chosen.credentials.access_token == "first"

    def test_respects_hermes_home_when_source_path_omitted(
        self, tmp_path, monkeypatch
    ):
        # When ``source_path`` is None, the function should read
        # ``<HERMES_HOME>/claude_account_source.txt``.  The autouse
        # ``_isolate_hermes_home`` fixture already points HERMES_HOME at a
        # tmp dir, but we override it explicitly to be unambiguous.
        hermes_home = tmp_path / ".hermes"
        hermes_home.mkdir()
        monkeypatch.setenv("HERMES_HOME", str(hermes_home))

        sel_file = hermes_home / "claude_account_source.txt"
        sel_file.write_text("file", encoding="utf-8")

        accts = [
            _acct("Claude Max", "keychain:X", token="kc"),
            _acct("Claude Pro", "file", token="file-tok"),
        ]
        with patch.object(claude_keychain, "read_all_accounts", return_value=accts):
            chosen = read_selected_account()
        assert chosen is not None
        assert chosen.credentials.access_token == "file-tok"
