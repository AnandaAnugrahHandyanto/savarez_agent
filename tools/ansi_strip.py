"""Strip ANSI escape sequences from subprocess output.

Used by terminal_tool, code_execution_tool, and process_registry to clean
command output before returning it to the model.  This prevents ANSI codes
from entering the model's context — which is the root cause of models
copying escape sequences into file writes.

Covers the full ECMA-48 spec: CSI (including private-mode ``?`` prefix,
colon-separated params, intermediate bytes), OSC (BEL and ST terminators),
DCS/SOS/PM/APC string sequences, nF multi-byte escapes, Fp/Fe/Fs
single-byte escapes, and 8-bit C1 control characters.

OSC 1337 (iTerm2 inline images) can be selectively preserved using the
preserve_osc1337 parameter to allow inline image display in compatible
terminals.
"""

import re

_ANSI_ESCAPE_RE = re.compile(
    r"\x1b"
    r"(?:"
        r"\[[\x30-\x3f]*[\x20-\x2f]*[\x40-\x7e]"     # CSI sequence
        r"|\][\s\S]*?(?:\x07|\x1b\\)"                  # OSC (BEL or ST terminator)
        r"|[PX^_][\s\S]*?(?:\x1b\\)"                   # DCS/SOS/PM/APC strings
        r"|[\x20-\x2f]+[\x30-\x7e]"                    # nF escape sequences
        r"|[\x30-\x7e]"                                 # Fp/Fe/Fs single-byte
    r")"
    r"|\x9b[\x30-\x3f]*[\x20-\x2f]*[\x40-\x7e]"       # 8-bit CSI
    r"|\x9d[\s\S]*?(?:\x07|\x9c)"                       # 8-bit OSC
    r"|[\x80-\x9f]",                                    # Other 8-bit C1 controls
    re.DOTALL,
)

# Fast-path check — skip full regex when no escape-like bytes are present.
_HAS_ESCAPE = re.compile(r"[\x1b\x80-\x9f]")

# Pattern to match OSC 1337 sequences specifically (iTerm2 inline images)
_OSC_1337_RE = re.compile(
    r"\x1b\]1337;[^\x07\x1b]*(?:\x07|\x1b\\)",
    re.DOTALL,
)


def strip_ansi(text: str, preserve_osc1337: bool = False) -> str:
    """Remove ANSI escape sequences from text.

    Args:
        text: Input string to process.
        preserve_osc1337: If True, preserve OSC 1337 sequences (iTerm2 inline images).
                         Default False for backward compatibility.

    Returns the input unchanged (fast path) when no ESC or C1 bytes are
    present.  Safe to call on any string — clean text passes through
    with negligible overhead.

    When preserve_osc1337=True, OSC 1337 sequences are preserved to allow
    inline image display in compatible terminals (iTerm2, WezTerm, etc.).
    All other ANSI sequences are still stripped.
    """
    if not text or not _HAS_ESCAPE.search(text):
        return text

    if preserve_osc1337:
        # Strategy: Extract OSC 1337 sequences before stripping, then restore after
        osc1337_sequences = _OSC_1337_RE.findall(text)
        # Strip all ANSI sequences
        text_without_ansi = _ANSI_ESCAPE_RE.sub("", text)
        
        # If we found OSC 1337 sequences, prepend them back
        # (Terminal will process them regardless of position in output stream)
        if osc1337_sequences:
            return "".join(osc1337_sequences) + text_without_ansi
        return text_without_ansi
    else:
        # Strip all ANSI sequences (original behavior)
        return _ANSI_ESCAPE_RE.sub("", text)
