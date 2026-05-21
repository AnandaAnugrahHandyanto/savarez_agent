"""Tests for Layer-2 credential redaction on outbound gateway messages."""

from gateway.credential_redaction import REDACTION_PLACEHOLDER, redact_credentials


class TestAnthropic:
    def test_redacts_sk_ant_key(self):
        # 90+ chars after sk-ant-
        key = "sk-ant-test1234567890abc" + "X" * 90
        out = redact_credentials(f"oops the key is {key} please rotate")
        assert key not in out
        assert REDACTION_PLACEHOLDER in out

    def test_redacts_sk_ant_inside_traceback(self):
        msg = "AuthenticationError(401): bad key sk-ant-api03-" + "a" * 90
        out = redact_credentials(msg)
        assert "sk-ant-" not in out


class TestOpenAI:
    def test_redacts_sk_key(self):
        key = "sk-" + "A" * 48
        out = redact_credentials(f"OPENAI_API_KEY={key}")
        assert key not in out
        assert REDACTION_PLACEHOLDER in out

    def test_redacts_sk_proj_key(self):
        key = "sk-proj-" + "B" * 48
        out = redact_credentials(f"using {key} for the call")
        assert key not in out


class TestGoogle:
    def test_redacts_aiza_key(self):
        key = "AIza" + "C" * 35
        out = redact_credentials(f"google api key {key} failed")
        assert key not in out
        assert REDACTION_PLACEHOLDER in out


class TestAWS:
    def test_redacts_akia_key_id(self):
        key = "AKIAIOSFODNN7EXAMPLE"
        out = redact_credentials(f"AWS_ACCESS_KEY_ID={key}")
        assert key not in out


class TestGitHub:
    def test_redacts_ghp_token(self):
        token = "ghp_" + "z" * 36
        out = redact_credentials(token)
        assert token not in out
        assert out == REDACTION_PLACEHOLDER


class TestJWT:
    def test_redacts_jwt(self):
        jwt = (
            "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
            ".eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4iLCJpYXQiOjE1MTYyMzkwMjJ9"
            ".SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
        )
        out = redact_credentials(f"Bearer {jwt}")
        assert jwt not in out


class TestBasicAuthURL:
    def test_redacts_userpass_in_url(self):
        url = "https://alice:supersecret@example.com/path"
        out = redact_credentials(f"connect to {url} please")
        assert "supersecret" not in out
        assert "alice" not in out
        # Scheme and host preserved for diagnosability
        assert "https://" in out
        assert "example.com/path" in out

    def test_redacts_postgres_url(self):
        url = "postgres://user:p%40ss@db.internal:5432/mydb"
        out = redact_credentials(url)
        assert "p%40ss" not in out
        assert "postgres://" in out
        assert "db.internal" in out


class TestNonCredentials:
    def test_normal_url_unchanged(self):
        url = "https://example.com/some/path?query=value&foo=bar"
        assert redact_credentials(url) == url

    def test_plain_prose_unchanged(self):
        text = "The user asked about formatting a Discord embed with a code block."
        assert redact_credentials(text) == text

    def test_short_hex_unchanged(self):
        # Git short SHAs, etc. should pass through
        text = "commit 656308e on branch main"
        assert redact_credentials(text) == text

    def test_long_alphanumeric_without_prefix_unchanged(self):
        # Conservative: we don't blanket-redact 32+ char strings that lack
        # a known credential prefix.
        text = "hash abcdef0123456789abcdef0123456789abcdef0123456789"
        assert redact_credentials(text) == text

    def test_markdown_code_block_unchanged(self):
        text = "```python\ndef foo():\n    return 42\n```"
        assert redact_credentials(text) == text


class TestEdgeCases:
    def test_none_returns_none(self):
        assert redact_credentials(None) is None  # type: ignore[arg-type]

    def test_empty_string(self):
        assert redact_credentials("") == ""

    def test_non_string_stringified(self):
        out = redact_credentials(12345)  # type: ignore[arg-type]
        assert out == "12345"

    def test_idempotent(self):
        key = "sk-ant-" + "a" * 90
        once = redact_credentials(key)
        twice = redact_credentials(once)
        assert once == twice

    def test_multiple_credentials_in_one_string(self):
        text = (
            "AWS=AKIAIOSFODNN7EXAMPLE and Google=AIza"
            + "X" * 35
            + " and ghp_"
            + "y" * 36
        )
        out = redact_credentials(text)
        assert "AKIA" not in out
        assert "AIza" not in out
        assert "ghp_" not in out
