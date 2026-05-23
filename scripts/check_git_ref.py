#!/usr/bin/env python3
"""Validate a pinned Git dependency ref, with optional remote resolution.

Default mode is offline: validate that the ref is a stable release tag or full
SHA. Set --remote to call `git ls-remote` and verify the ref exists upstream.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys

_FULL_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_RELEASE_TAG_RE = re.compile(r"^v\d+\.\d+\.\d+$")


def ref_format_ok(ref: str) -> bool:
    return bool(_FULL_SHA_RE.fullmatch(ref) or _RELEASE_TAG_RE.fullmatch(ref))


def verify_remote(repo_url: str, ref: str) -> None:
    candidates = [ref]
    if _RELEASE_TAG_RE.fullmatch(ref):
        candidates = [f"refs/tags/{ref}", f"refs/tags/{ref}^{{}}"]
    completed = subprocess.run(
        ["git", "ls-remote", repo_url, *candidates],
        text=True,
        capture_output=True,
        check=True,
    )
    if ref not in completed.stdout:
        raise RuntimeError(f"ref {ref!r} was not found in {repo_url}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate a pinned Git dependency ref")
    parser.add_argument("repo_url")
    parser.add_argument("ref")
    parser.add_argument("--remote", action="store_true", help="verify the ref with git ls-remote")
    args = parser.parse_args(argv)

    if not ref_format_ok(args.ref):
        print(f"invalid ref format: {args.ref!r}", file=sys.stderr)
        return 2
    print(f"ref format ok: {args.ref}")

    if not args.remote:
        print("remote check skipped")
        return 0

    try:
        verify_remote(args.repo_url, args.ref)
    except Exception as exc:
        print(f"remote check failed: {exc}", file=sys.stderr)
        return 1
    print(f"remote ref ok: {args.ref}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
