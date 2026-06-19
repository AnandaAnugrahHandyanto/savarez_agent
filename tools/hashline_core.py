"""Hashline core: content-hash-anchored, line-addressed file editing.

Adapted from oh-my-pi (https://github.com/can1357/oh-my-pi), MIT License.
Independent Python reimplementation for Hermes; shares no source with the
original TypeScript.

Pure algorithm layer (no Hermes imports) so it is trivially unit-testable.

Patch format (line numbers are 1-based)::

    [path/to/file.py#a3f9]
    replace 12..14:
    +new line 1
    +new line 2
    delete 20..22
    insert after 30:
    +appended line
    insert head:
    +top line

- ``#a3f9`` is the TAG: a 4-hex content hash of the file's normalized content
  at the time the model read it. Before applying, we recompute the tag from the
  current file; if it differs, the patch is REJECTED (stale anchor) and nothing
  is written.
- Body lines are prefixed with ``+``. A lone ``+`` denotes an empty line.
- Operations: ``replace A..B``, ``replace A`` (single line), ``delete A..B``,
  ``delete A``, ``insert before|after N``, ``insert head``, ``insert tail``.
"""

from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple


# --------------------------------------------------------------------------- #
# Normalization & tagging
# --------------------------------------------------------------------------- #

def normalize(text: str) -> str:
    """Normalize for hashing: unify line endings, strip a single trailing newline.

    We keep interior content byte-exact; only CRLF/CR -> LF and one trailing
    newline are normalized so that a file read by the model and the same file on
    disk hash identically regardless of editor newline quirks.
    """
    t = text.replace("\r\n", "\n").replace("\r", "\n")
    if t.endswith("\n"):
        t = t[:-1]
    return t


def content_tag(text: str) -> str:
    """4-hex content anchor (blake2b, digest_size=2). Stdlib, fast, zero deps."""
    h = hashlib.blake2b(normalize(text).encode("utf-8"), digest_size=2)
    return h.hexdigest()


def split_lines(text: str) -> List[str]:
    """Split into logical lines (no trailing-newline ghost element)."""
    return normalize(text).split("\n")


def join_lines(lines: List[str], original_had_trailing_nl: bool) -> str:
    out = "\n".join(lines)
    if original_had_trailing_nl:
        out += "\n"
    return out


# --------------------------------------------------------------------------- #
# Data model
# --------------------------------------------------------------------------- #

@dataclass
class Operation:
    kind: str                      # "replace" | "delete" | "insert"
    start: int                     # 1-based
    end: Optional[int] = None      # inclusive; None for insert
    anchor: Optional[str] = None   # "before"|"after"|"head"|"tail" for insert
    body: List[str] = field(default_factory=list)


@dataclass
class FileEdit:
    path: str
    tag: str
    ops: List[Operation] = field(default_factory=list)


class HashlineError(Exception):
    pass


# --------------------------------------------------------------------------- #
# Parsing
# --------------------------------------------------------------------------- #

_HEADER_RE = re.compile(r"^\[?(?P<path>.+?)#(?P<tag>[0-9a-fA-F]{2,8})\]?\s*$")
_REPLACE_RE = re.compile(r"^replace\s+(?P<a>\d+)(?:\.\.(?P<b>\d+))?\s*:\s*$")
_DELETE_RE = re.compile(r"^delete\s+(?P<a>\d+)(?:\.\.(?P<b>\d+))?\s*$")
_INSERT_POS_RE = re.compile(r"^insert\s+(?P<anchor>before|after)\s+(?P<n>\d+)\s*:\s*$")
_INSERT_HT_RE = re.compile(r"^insert\s+(?P<anchor>head|tail)\s*:\s*$")
_BODY_RE = re.compile(r"^\+(.*)$")


def _strip_fence(text: str) -> str:
    """Tolerate an optional *** Begin Patch / *** End Patch wrapper (oh-my-pi
    style) or a ```hashline fenced block."""
    lines = text.splitlines()
    out = []
    for ln in lines:
        s = ln.strip()
        if s in ("*** Begin Patch", "*** End Patch"):
            continue
        if s.startswith("```"):
            continue
        out.append(ln)
    return "\n".join(out)


def parse_patch(text: str) -> List[FileEdit]:
    """Parse hashline patch text into FileEdit list. Raises HashlineError."""
    text = _strip_fence(text)
    lines = text.split("\n")
    edits: List[FileEdit] = []
    cur: Optional[FileEdit] = None
    pending: Optional[Operation] = None  # op awaiting body lines

    def flush_pending():
        nonlocal pending
        if pending is not None and cur is not None:
            cur.ops.append(pending)
            pending = None

    i = 0
    while i < len(lines):
        raw = lines[i]
        line = raw.rstrip("\n")
        stripped = line.strip()

        # body line for a pending op
        if pending is not None:
            m = _BODY_RE.match(line)
            if m is not None:
                pending.body.append(m.group(1))
                i += 1
                continue
            else:
                flush_pending()  # body ended

        if stripped == "":
            i += 1
            continue

        m = _HEADER_RE.match(stripped)
        if m:
            flush_pending()
            cur = FileEdit(path=m.group("path"), tag=m.group("tag").lower())
            edits.append(cur)
            i += 1
            continue

        if cur is None:
            raise HashlineError(
                f"operation before any [path#tag] header: {stripped!r}"
            )

        m = _REPLACE_RE.match(stripped)
        if m:
            a = int(m.group("a"))
            b = int(m.group("b")) if m.group("b") else a
            pending = Operation(kind="replace", start=a, end=b)
            i += 1
            continue

        m = _DELETE_RE.match(stripped)
        if m:
            a = int(m.group("a"))
            b = int(m.group("b")) if m.group("b") else a
            cur.ops.append(Operation(kind="delete", start=a, end=b))
            i += 1
            continue

        m = _INSERT_POS_RE.match(stripped)
        if m:
            pending = Operation(
                kind="insert", start=int(m.group("n")), anchor=m.group("anchor")
            )
            i += 1
            continue

        m = _INSERT_HT_RE.match(stripped)
        if m:
            anchor = m.group("anchor")
            # head -> insert before line 1; tail -> insert after last line
            pending = Operation(kind="insert", start=0, anchor=anchor)
            i += 1
            continue

        raise HashlineError(f"unrecognized patch line: {stripped!r}")

    flush_pending()
    if not edits:
        raise HashlineError("empty patch: no [path#tag] blocks found")
    return edits


# --------------------------------------------------------------------------- #
# Preflight & apply
# --------------------------------------------------------------------------- #

ReadFn = Callable[[str], str]
WriteFn = Callable[[str, str], None]


def _resolve(root: str, path: str) -> str:
    return path if os.path.isabs(path) else os.path.join(root, path)


def preflight(edits: List[FileEdit], read_fn: ReadFn, root: str = ".") -> List[str]:
    """Validate every edit: tag match + line bounds. Returns error list (empty=ok)."""
    errors: List[str] = []
    for fe in edits:
        full = _resolve(root, fe.path)
        try:
            content = read_fn(full)
        except FileNotFoundError:
            errors.append(f"{fe.path}: file not found")
            continue
        except Exception as e:  # noqa: BLE001
            errors.append(f"{fe.path}: cannot read ({e})")
            continue

        if "\x00" in content:
            errors.append(f"{fe.path}: binary file, hashline not applicable")
            continue

        actual = content_tag(content)
        if actual != fe.tag:
            errors.append(
                f"{fe.path}: stale anchor (expected tag {fe.tag} but file is "
                f"{actual}). Re-read the file and regenerate the patch."
            )
            continue

        nlines = len(split_lines(content))
        for op in fe.ops:
            if op.kind in ("replace", "delete"):
                if op.start < 1 or (op.end or op.start) > nlines or op.start > (op.end or op.start):
                    errors.append(
                        f"{fe.path}: {op.kind} {op.start}..{op.end} out of range "
                        f"(file has {nlines} lines)."
                    )
            elif op.kind == "insert":
                if op.anchor in ("before", "after"):
                    if op.start < 1 or op.start > nlines:
                        errors.append(
                            f"{fe.path}: insert {op.anchor} {op.start} out of range "
                            f"(file has {nlines} lines)."
                        )
    return errors


def _apply_ops_to_lines(lines: List[str], ops: List[Operation]) -> List[str]:
    """Apply ops to a line list. Ops sorted by start DESC so earlier (higher-line)
    edits don't shift the indices of later (lower-line) ones."""
    # Establish a deterministic order: by start descending; inserts vs replace at
    # same line: process inserts after (so they don't collide oddly) — but since
    # we go descending and rebuild, ordering within same line is stable enough.
    def sort_key(op: Operation) -> Tuple[int, int]:
        # head/tail use sentinel positions
        if op.kind == "insert" and op.anchor == "head":
            return (0, 0)
        if op.kind == "insert" and op.anchor == "tail":
            return (len(lines) + 1, 0)
        return (op.start, 0)

    for op in sorted(ops, key=sort_key, reverse=True):
        if op.kind == "replace":
            lines[op.start - 1: op.end] = op.body
        elif op.kind == "delete":
            del lines[op.start - 1: op.end]
        elif op.kind == "insert":
            if op.anchor == "head":
                lines[0:0] = op.body
            elif op.anchor == "tail":
                lines.extend(op.body)
            elif op.anchor == "before":
                lines[op.start - 1: op.start - 1] = op.body
            elif op.anchor == "after":
                lines[op.start: op.start] = op.body
    return lines


def apply_edits(
    edits: List[FileEdit],
    read_fn: ReadFn,
    write_fn: WriteFn,
    root: str = ".",
) -> Dict[str, object]:
    """Preflight then apply atomically. Returns a result dict.

    On any preflight error, NOTHING is written.
    """
    errors = preflight(edits, read_fn, root)
    if errors:
        return {"ok": False, "errors": errors, "files_written": []}

    # Stage all new contents first, write after all succeed (atomicity).
    staged: List[Tuple[str, str]] = []
    for fe in edits:
        full = _resolve(root, fe.path)
        content = read_fn(full)
        had_nl = content.endswith("\n") or content.endswith("\r\n")
        lines = split_lines(content)
        new_lines = _apply_ops_to_lines(lines, fe.ops)
        staged.append((full, join_lines(new_lines, had_nl)))

    for full, new_content in staged:
        write_fn(full, new_content)

    return {
        "ok": True,
        "errors": [],
        "files_written": [p for p, _ in staged],
        "edit_count": sum(len(fe.ops) for fe in edits),
    }


# --------------------------------------------------------------------------- #
# Convenience: real-filesystem entry point
# --------------------------------------------------------------------------- #

def _fs_read(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _fs_write(path: str, content: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def apply_patch_text(patch_text: str, root: str = ".") -> Dict[str, object]:
    """Parse + apply against the real filesystem rooted at ``root``."""
    try:
        edits = parse_patch(patch_text)
    except HashlineError as e:
        return {"ok": False, "errors": [f"parse error: {e}"], "files_written": []}
    return apply_edits(edits, _fs_read, _fs_write, root=root)
