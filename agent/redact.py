"""Regex-based secret redaction for logs and tool output.

Applies pattern matching to mask API keys, tokens, and credentials
before they reach log files, verbose output, or gateway logs.

Short tokens (< 18 chars) are fully masked. Longer tokens preserve
the first 6 and last 4 characters for debuggability.
"""

import logging
import os
import re

logger = logging.getLogger(__name__)

_REDACT_ENABLED = os.getenv("HERMES_REDACT_SECRETS", "").lower() not in ("0", "false", "no", "off")

_PREFIX_PATTERNS = [
    r"sk-[A-Za-z0-9_-]{10,}",
    r"ghp_[A-Za-z0-9]{10,}",
    r"github_pat_[A-Za-z0-9_]{10,}",
    r"gho_[A-Za-z0-9]{10,}",
    r"ghu_[A-Za-z0-9]{10,}",
    r"ghs_[A-Za-z0-9]{10,}",
    r"ghr_[A-Za-z0-9]{10,}",
    r"xox[baprs]-[A-Za-z0-9-]{10,}",
    r"AIza[A-Za-z0-9_-]{30,}",
    r"pplx-[A-Za-z0-9]{10,}",
    r"fal_[A-Za-z0-9_-]{10,}",
    r"fc-[A-Za-z0-9]{10,}",
    r"bb_live_[A-Za-z0-9_-]{10,}",
    r"gAAAA[A-Za-z0-9_=-]{20,}",
    r"AKIA[A-Z0-9]{16}",
    r"sk_live_[A-Za-z0-9]{10,}",
    r"sk_test_[A-Za-z0-9]{10,}",
    r"rk_live_[A-Za-z0-9]{10,}",
    r"SG\.[A-Za-z0-9_-]{10,}",
    r"hf_[A-Za-z0-9]{10,}",
    r"r8_[A-Za-z0-9]{10,}",
    r"npm_[A-Za-z0-9]{10,}",
    r"pypi-[A-Za-z0-9_-]{10,}",
    r"dop_v1_[A-Za-z0-9]{10,}",
    r"doo_v1_[A-Za-z0-9]{10,}",
    r"am_[A-Za-z0-9_-]{10,}",
    r"sk_[A-Za-z0-9_]{10,}",
    r"tvly-[A-Za-z0-9]{10,}",
    r"exa_[A-Za-z0-9]{10,}",
    r"gsk_[A-Za-z0-9]{10,}",
    r"syt_[A-Za-z0-9]{10,}",
    r"mem0_[A-Za-z0-9]{10,}",
    r"brv_[A-Za-z0-9]{10,}",
]

_SECRET_ENV_NAMES = r"(?:api_?[Kk]ey|token|secret|password|access_token|refresh_token|auth_token|bearer|secret_value|raw_secret|secret_input|key_material)"
_ENV_ASSIGN_RE = re.compile(
    rf"([A-Z0-9_]{{0,50}}{_SECRET_ENV_NAMES}[A-Z0-9_]{{0,50}})\s*=\s*(['\"]?)(\S+)\2",
)

_JSON_KEY_NAMES = r"(?:api_?[Kk]ey|token|secret|password|access_token|refresh_token|auth_token|bearer|secret_value|raw_secret|secret_input|key_material)"
_JSON_FIELD_RE = re.compile(
    rf'("{_JSON_KEY_NAMES}")\s*:\s*"([^"]+)"',
    re.IGNORECASE,
)

_AUTH_HEADER_RE = re.compile(r"(Authorization:\s*Bearer\s+)(\S+)", re.IGNORECASE)

_TELEGRAM_RE = re.compile(r"(bot)?(\d{8,}):([-A-Za-z0-9_]{30,})")

_PRIVATE_KEY_RE = re.compile(
    r"-----BEGIN[A-Z ]*PRIVATE KEY-----[\s\S]*?-----END[A-Z ]*PRIVATE KEY-----"
)

_DB_CONNSTR_RE = re.compile(
    r"((?:postgres(?:ql)?|mysql|mongodb(?:\+srv)?|redis|amqp)://[^:]+:)([^@]+)(@)",
    re.IGNORECASE,
)

_SIGNAL_PHONE_RE = re.compile(r"(\+[1-9]\d{6,14})(?![A-Za-z0-9])")

# Interactive password/secret prompts — models may echo these back verbatim.
# Fixes GitHub issue #9590: agent guessed and displayed sudo password.
_INTERACTIVE_PROMPT_RE = re.compile(
    r"(?i)("
    r"with\s+password\s*:|"
    r"enter\s+(?:your\s+)?(?:password|passphrase|pin)\s*:|"
    r"password\s*(?:\[[^\]]+\])?\s*(?:for\s+\w+)?\s*:|"
    r"(?:sudo\s+)?password\s+for|"
    r"passphrase\s*(?:\[[^\]]+\])?\s*:|"
    r"secret\s*(?:\[[^\]]+\])?\s*:|"
    r"api\s*key\s*:|"
    r"bearer\s+token\s*:|"
    r"verification\s*code\s*:|"
    r"otp\s*:"
    r")\s*([^\s\[\]<>]{3,64})"
)

_PREFIX_RE = re.compile(
    r"(?<![A-Za-z0-9_-])(" + "|".join(_PREFIX_PATTERNS) + r")(?![A-Za-z0-9_-])"
)


def _mask_token(token: str) -> str:
    if len(token) < 18:
        return "***"
    return f"{token[:6]}...{token[-4:]}"


def redact_sensitive_text(text: str) -> str:
    if text is None:
        return None
    if not isinstance(text, str):
        text = str(text)
    if not text:
        return text
    if not _REDACT_ENABLED:
        return text

    text = _PREFIX_RE.sub(lambda m: _mask_token(m.group(1)), text)

    def _redact_env(m):
        return f"{m.group(1)}={m.group(2)}{_mask_token(m.group(3))}{m.group(2)}"
    text = _ENV_ASSIGN_RE.sub(_redact_env, text)

    def _redact_json(m):
        return f'{m.group(1)}: "{_mask_token(m.group(2))}"'
    text = _JSON_FIELD_RE.sub(_redact_json, text)

    text = _AUTH_HEADER_RE.sub(lambda m: m.group(1) + _mask_token(m.group(2)), text)

    def _redact_telegram(m):
        return f"{m.group(1) or ''}{m.group(2)}:***"
    text = _TELEGRAM_RE.sub(_redact_telegram, text)

    text = _PRIVATE_KEY_RE.sub("[REDACTED PRIVATE KEY]", text)

    text = _DB_CONNSTR_RE.sub(lambda m: f"{m.group(1)}***{m.group(3)}", text)

    def _redact_phone(m):
        phone = m.group(1)
        return phone[:4] + "****" + phone[-4:] if len(phone) > 8 else phone[:2] + "****" + phone[-2:]
    text = _SIGNAL_PHONE_RE.sub(_redact_phone, text)

    def _redact_interactive(m):
        return m.group(1).strip() + " " + _mask_token(m.group(2))
    text = _INTERACTIVE_PROMPT_RE.sub(_redact_interactive, text)

    return text


class RedactingFormatter(logging.Formatter):
    def __init__(self, fmt=None, datefmt=None, style='%', **kwargs):
        super().__init__(fmt, datefmt, style, **kwargs)

    def format(self, record: logging.LogRecord) -> str:
        return redact_sensitive_text(super().format(record))
