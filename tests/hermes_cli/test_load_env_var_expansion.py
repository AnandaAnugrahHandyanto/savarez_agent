"""Tests for ``${VAR}`` interpolation in ``load_env`` (#20310).

When a ``~/.hermes/.env`` value references another variable, ``load_env``
must expand it instead of returning the raw ``${VAR}`` literal — otherwise
the credential pool seeds the unresolved string into ``auth.json`` and
auxiliary requests send it as the ``x-api-key`` header.
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch


def _write_env(content: str) -> Path:
    fp = tempfile.NamedTemporaryFile(
        mode="w", suffix=".env", delete=False, encoding="utf-8"
    )
    fp.write(content)
    fp.close()
    return Path(fp.name)


def test_load_env_expands_braced_reference_from_os_environ():
    """``ANTHROPIC_API_KEY=${OPENAI_API_KEY}`` resolves via os.environ."""
    from hermes_cli.config import load_env

    env_path = _write_env("ANTHROPIC_API_KEY=${OPENAI_API_KEY}\n")
    try:
        with patch("hermes_cli.config.get_env_path", return_value=env_path), \
             patch.dict(os.environ, {"OPENAI_API_KEY": "sk-real-key"}, clear=False):
            result = load_env()
        assert result["ANTHROPIC_API_KEY"] == "sk-real-key"
    finally:
        env_path.unlink(missing_ok=True)


def test_load_env_expands_bare_reference_from_os_environ():
    """``KEY=$OTHER`` (no braces) expansion."""
    from hermes_cli.config import load_env

    env_path = _write_env("ANTHROPIC_API_KEY=$OPENAI_API_KEY\n")
    try:
        with patch("hermes_cli.config.get_env_path", return_value=env_path), \
             patch.dict(os.environ, {"OPENAI_API_KEY": "sk-bare"}, clear=False):
            result = load_env()
        assert result["ANTHROPIC_API_KEY"] == "sk-bare"
    finally:
        env_path.unlink(missing_ok=True)


def test_load_env_resolves_chained_reference_within_file():
    """Earlier .env entries take precedence over os.environ for expansion."""
    from hermes_cli.config import load_env

    content = (
        "OPENAI_API_KEY=sk-from-file\n"
        "ANTHROPIC_API_KEY=${OPENAI_API_KEY}\n"
    )
    env_path = _write_env(content)
    try:
        with patch("hermes_cli.config.get_env_path", return_value=env_path), \
             patch.dict(
                 os.environ, {"OPENAI_API_KEY": "sk-from-shell"}, clear=False
             ):
            result = load_env()
        assert result["ANTHROPIC_API_KEY"] == "sk-from-file"
    finally:
        env_path.unlink(missing_ok=True)


def test_load_env_unresolved_reference_falls_back_to_default():
    """``${VAR:-default}`` returns the default when VAR is missing."""
    from hermes_cli.config import load_env

    env_path = _write_env("ANTHROPIC_API_KEY=${MISSING_VAR:-fallback}\n")
    try:
        with patch("hermes_cli.config.get_env_path", return_value=env_path), \
             patch.dict(os.environ, {}, clear=False):
            os.environ.pop("MISSING_VAR", None)
            result = load_env()
        assert result["ANTHROPIC_API_KEY"] == "fallback"
    finally:
        env_path.unlink(missing_ok=True)


def test_load_env_preserves_literal_when_reference_unresolved():
    """An unresolvable ``${VAR}`` is left as-is (does not silently empty)."""
    from hermes_cli.config import load_env

    env_path = _write_env("ANTHROPIC_API_KEY=${TOTALLY_UNDEFINED_VAR_XYZ}\n")
    try:
        with patch("hermes_cli.config.get_env_path", return_value=env_path):
            os.environ.pop("TOTALLY_UNDEFINED_VAR_XYZ", None)
            result = load_env()
        assert result["ANTHROPIC_API_KEY"] == "${TOTALLY_UNDEFINED_VAR_XYZ}"
    finally:
        env_path.unlink(missing_ok=True)


def test_load_env_preserves_dollar_signs_in_passwords():
    """A literal ``$`` not followed by a valid identifier stays intact."""
    from hermes_cli.config import load_env

    env_path = _write_env("DB_PASSWORD=p@ss$123word\n")
    try:
        with patch("hermes_cli.config.get_env_path", return_value=env_path):
            result = load_env()
        assert result["DB_PASSWORD"] == "p@ss$123word"
    finally:
        env_path.unlink(missing_ok=True)


def test_load_env_escaped_dollar_passes_through_literally():
    """``\\$VAR`` keeps the dollar sign and is not interpolated."""
    from hermes_cli.config import load_env

    env_path = _write_env(r"PASSWORD=\$NOT_A_VAR" + "\n")
    try:
        with patch("hermes_cli.config.get_env_path", return_value=env_path), \
             patch.dict(os.environ, {"NOT_A_VAR": "should-not-appear"}, clear=False):
            result = load_env()
        assert result["PASSWORD"] == "$NOT_A_VAR"
    finally:
        env_path.unlink(missing_ok=True)


def test_load_env_no_dollar_sign_unchanged():
    """Values without ``$`` are returned verbatim (regression guard)."""
    from hermes_cli.config import load_env

    env_path = _write_env("KEY=plain-value-no-substitution\n")
    try:
        with patch("hermes_cli.config.get_env_path", return_value=env_path):
            result = load_env()
        assert result["KEY"] == "plain-value-no-substitution"
    finally:
        env_path.unlink(missing_ok=True)
