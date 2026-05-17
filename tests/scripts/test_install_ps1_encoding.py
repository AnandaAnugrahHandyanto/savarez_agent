r"""Regression tests for the Windows one-line installer's file encoding (#27397).

``scripts/install.ps1`` MUST be saved as pure ASCII (or UTF-8 *without* BOM).
When the file accidentally picks up a UTF-8 BOM (``EF BB BF`` -- easy to
introduce by editing the file in a Windows editor that defaults to "UTF-8
with signature"), the canonical Windows one-line installer fails::

    irm https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.ps1 | iex

Why:

* ``irm`` (Invoke-RestMethod) reads the response body and decodes it into a
  .NET string.  A leading UTF-8 BOM is preserved as U+FEFF at position 0
  of that string.
* ``iex`` (Invoke-Expression) calls ``[scriptblock]::Create($string)`` to
  parse.  The expression-context parser does NOT strip a leading U+FEFF
  the way PowerShell's *script file* loader does.
* With a stray U+FEFF in front of ``param(``, PowerShell stops recognising
  ``param`` as a keyword.  Each line inside the ``param()`` block then
  parses as a bare assignment, e.g. ``[string]$Branch = "main"`` becomes a
  cast-on-LHS = literal-on-RHS expression, which is invalid -- yielding
  the exact error reported in #27397::

      The assignment expression is not valid. The input to an assignment
      operator must be an object that is able to accept assignments, such
      as a variable or a property.

Direct ``.\install.ps1`` invocation tolerates the BOM (PowerShell's file
host strips it), so the failure only surfaces via the canonical one-liner --
which is exactly the path the README points new users at.

These tests pin the file's on-disk byte invariants so a future editor save
(or a script that uses ``Set-Content`` with a default encoding on Windows)
cannot silently reintroduce the BOM.
"""

from __future__ import annotations

from pathlib import Path

import pytest


_INSTALL_PS1 = Path(__file__).resolve().parents[2] / "scripts" / "install.ps1"
_UTF8_BOM = b"\xef\xbb\xbf"
_UTF16_LE_BOM = b"\xff\xfe"
_UTF16_BE_BOM = b"\xfe\xff"


@pytest.fixture(scope="module")
def install_ps1_bytes() -> bytes:
    assert _INSTALL_PS1.is_file(), f"missing installer at {_INSTALL_PS1}"
    return _INSTALL_PS1.read_bytes()


class TestInstallPs1ByteInvariants:
    """Catch any encoding regression at the bytes-on-disk level."""

    def test_does_not_start_with_utf8_bom(self, install_ps1_bytes):
        # The exact regression behind #27397.
        assert not install_ps1_bytes.startswith(_UTF8_BOM), (
            "scripts/install.ps1 has a UTF-8 BOM at byte 0. This breaks "
            "`irm <url> | iex` because PowerShell's expression-context "
            "parser leaves U+FEFF in the input and stops recognising "
            "`param` as a keyword. Re-save as ASCII or UTF-8 *without* BOM."
        )

    def test_does_not_start_with_utf16_bom(self, install_ps1_bytes):
        # PowerShell's `Set-Content` defaults to UTF-16 LE on PS 5.1.
        # That would obviously break iex even worse than UTF-8+BOM, and is
        # an easy footgun for an editor save / automation script.
        assert not install_ps1_bytes.startswith(_UTF16_LE_BOM), (
            "scripts/install.ps1 has a UTF-16 LE BOM. Re-save as ASCII."
        )
        assert not install_ps1_bytes.startswith(_UTF16_BE_BOM), (
            "scripts/install.ps1 has a UTF-16 BE BOM. Re-save as ASCII."
        )

    def test_is_pure_ascii(self, install_ps1_bytes):
        # The in-file comment claims pure ASCII for PS 5.1 parser
        # compatibility.  Pin that contract: a stray smart quote or em
        # dash would not break iex on its own, but it weakens the rule
        # of "no surprises in the bytes the parser sees" that the BOM
        # fix relies on.
        offenders = [(i, b) for i, b in enumerate(install_ps1_bytes) if b >= 0x80]
        assert not offenders, (
            f"scripts/install.ps1 contains {len(offenders)} non-ASCII "
            f"byte(s); first at offset {offenders[0][0]} (0x{offenders[0][1]:02x}). "
            "Keep the file pure ASCII (replace em dashes with '--', smart "
            "quotes with regular quotes, etc.)."
        )

    def test_first_line_is_a_comment_or_param(self, install_ps1_bytes):
        # Defensive: after stripping any whitespace, the first real
        # token must be a comment (`#`) or `param` -- never anything that
        # would change the parser's expectation of what the script is.
        text = install_ps1_bytes.decode("ascii")
        first_line = text.split("\n", 1)[0].lstrip()
        assert first_line.startswith("#") or first_line.startswith("param"), (
            f"unexpected first line: {first_line!r}"
        )


class TestParamBlockStillPresent:
    """Sanity: the param() block must remain at top level so direct invocation works."""

    def test_param_block_at_top_level(self, install_ps1_bytes):
        text = install_ps1_bytes.decode("ascii")
        # Find the first non-comment, non-blank line.
        first_code_line = next(
            (
                line.strip()
                for line in text.splitlines()
                if line.strip() and not line.lstrip().startswith("#")
            ),
            None,
        )
        assert first_code_line is not None
        assert first_code_line.startswith("param("), (
            f"first executable line must be `param(`, got {first_code_line!r}"
        )

    def test_param_block_defaults_intact(self, install_ps1_bytes):
        # Pin the documented defaults so a future refactor doesn't drop
        # them silently and reintroduce the symptom in a different shape.
        text = install_ps1_bytes.decode("ascii")
        for needle in (
            '[string]$Branch = "main"',
            '[string]$HermesHome = "$env:LOCALAPPDATA\\hermes"',
            '[string]$InstallDir = "$env:LOCALAPPDATA\\hermes\\hermes-agent"',
        ):
            assert needle in text, f"missing param default: {needle!r}"


class TestSimulateIrmIexParsing:
    """Smoke-test the actual byte sequence iex would receive.

    We can't run PowerShell from this test suite (no PS on CI Linux runners),
    but we can simulate the failure surface: ``iex`` parses the raw bytes
    as a script block.  Pin that the first non-whitespace character is a
    valid script start (``#`` for comments or ``p`` for ``param``) -- if
    it ever becomes U+FEFF / a BOM / a stray control character, this test
    catches it before the user hits #27397 again.
    """

    def test_first_meaningful_codepoint_is_safe(self, install_ps1_bytes):
        text = install_ps1_bytes.decode("ascii")
        # Strip POSIX whitespace + any stray BOM-like sentinel.
        stripped = text.lstrip(" \t\r\n")
        assert stripped, "file appears empty after stripping whitespace"
        first = stripped[0]
        assert first in {"#", "p"}, (
            f"first meaningful character is {first!r} (U+{ord(first):04X}); "
            "expected '#' (comment) or 'p' (start of `param`). A surprise "
            "character here is exactly the class of bug that #27397 hit."
        )

    def test_byte_zero_is_safe_for_iex(self, install_ps1_bytes):
        # The hard guarantee: byte 0 must be a printable ASCII character
        # that PowerShell's expression-context parser accepts as a script
        # start.  In practice that means the comment marker `#` (since
        # the file currently leads with a banner).
        assert install_ps1_bytes, "install.ps1 is empty"
        first_byte = install_ps1_bytes[0]
        assert first_byte == ord("#"), (
            f"byte 0 is 0x{first_byte:02x}; expected '#' (0x23). "
            "Any other byte at position 0 risks breaking `irm | iex`."
        )
