#!/usr/bin/env python3
"""Install the Penpot design-to-code rollout into a Hermes home.

Run this on Atlas from the Hermes control repo after local tests pass. It backs
up changed live skill/reference files, copies repo references into the Hermes
skill reference directory, and patches global/profile-local coding skills.
"""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path


ROUTING_BLOCK = """<!-- penpot-design-to-code:start -->
## Penpot Design-To-Code Routing

Use this lane when a task asks for premium UI, concept design, design-system
work, reference screenshots, or high-confidence visual handoff.

- Route concept/reference work to `frontend-eng`.
- Route data/API contract work to `backend-eng`.
- Route mixed app work through `coder`, split into backend contract, frontend
  implementation, and visual QA when quality matters.
- Keep Blue/GHL customer-facing behavior under Blue/GHL doctrine.
- Use `references/penpot-design-to-code.md` for Penpot/reference handling.
- Use `references/frontend-visual-qa.md` before reporting meaningful UI work complete.
- Penpot MCP starts read-only; do not store MCP keys or `userToken` URLs.
<!-- penpot-design-to-code:end -->
"""


FRONTEND_BLOCK = """<!-- penpot-design-to-code:start -->
## Penpot Design-To-Code Lane

For premium UI or concept-led work, start from Penpot, a reference screenshot,
or a written visual brief before implementation. Inspect components, tokens,
and app conventions first. Verify with desktop and mobile screenshots, console
checks, state coverage, and a visual critique pass. Animation should clarify
state, feedback, or orientation; do not add decorative motion.

Load `references/penpot-design-to-code.md` and `references/frontend-visual-qa.md`
when this lane applies.
<!-- penpot-design-to-code:end -->
"""


BACKEND_BLOCK = """<!-- penpot-design-to-code:start -->
## Backend-For-Frontend Lane

When frontend quality depends on server behavior, define predictable contracts
for loading, empty, error, partial, stale, long-content, disabled, and success
states before frontend implementation relies on them. Return useful errors
without leaking secrets, preserve idempotency where retries or repeated UI
submissions are possible, and split backend contract work from frontend visual
work when verification differs.
<!-- penpot-design-to-code:end -->
"""


REFERENCE_COPIES = {
    "docs/architecture/hermes-spine/backend-engineering-doctrine-2026-05-17.md": "backend-engineering-doctrine.md",
    "docs/architecture/hermes-spine/frontend-engineering-doctrine-2026-05-17.md": "frontend-engineering-doctrine.md",
    "docs/runbooks/penpot-design-to-code.md": "penpot-design-to-code.md",
    "docs/runbooks/frontend-visual-qa.md": "frontend-visual-qa.md",
}


def replace_block(text: str, block: str) -> str:
    start = "<!-- penpot-design-to-code:start -->"
    end = "<!-- penpot-design-to-code:end -->"
    if start in text and end in text:
        before = text[: text.index(start)]
        after = text[text.index(end) + len(end) :]
        return before.rstrip() + "\n\n" + block.strip() + after
    return text.rstrip() + "\n\n" + block.strip() + "\n"


def backup_file(path: Path, backup_root: Path) -> None:
    if not path.exists():
        return
    target = backup_root / path.relative_to(path.anchor if path.is_absolute() else Path("."))
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, target)


def patch_file(path: Path, block: str, backup_root: Path, dry_run: bool) -> bool:
    if not path.is_file():
        return False
    text = path.read_text(encoding="utf-8")
    updated = replace_block(text, block)
    if updated == text:
        return False
    if not dry_run:
        backup_file(path, backup_root)
        path.write_text(updated, encoding="utf-8")
    return True


def install(repo: Path, home: Path, dry_run: bool = False) -> dict:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_root = home / "backups" / f"penpot-design-to-code-before-{stamp}"
    refs = home / "skills" / "autonomous-ai-agents" / "hermes-agent" / "references"
    changed: list[str] = []
    copied: list[str] = []

    for src_rel, dest_name in REFERENCE_COPIES.items():
        src = repo / src_rel
        dest = refs / dest_name
        if not src.is_file():
            raise SystemExit(f"missing repo source: {src}")
        if not dry_run:
            refs.mkdir(parents=True, exist_ok=True)
            backup_file(dest, backup_root)
            shutil.copy2(src, dest)
        copied.append(str(dest))

    routing_paths = [
        home / "skills/software-development/coding-agent-routing/SKILL.md",
        home / "profiles/backend-eng/skills/software-development/coding-agent-routing/SKILL.md",
        home / "profiles/frontend-eng/skills/software-development/coding-agent-routing/SKILL.md",
        home / "profiles/coder/skills/software-development/coding-agent-routing/SKILL.md",
    ]
    frontend_paths = [
        home / "skills/software-development/frontend-engineer/SKILL.md",
        home / "profiles/frontend-eng/skills/software-development/frontend-engineer/SKILL.md",
    ]
    backend_paths = [
        home / "skills/software-development/backend-engineer/SKILL.md",
        home / "profiles/backend-eng/skills/software-development/backend-engineer/SKILL.md",
    ]

    for path in routing_paths:
        if patch_file(path, ROUTING_BLOCK, backup_root, dry_run):
            changed.append(str(path))
    for path in frontend_paths:
        if patch_file(path, FRONTEND_BLOCK, backup_root, dry_run):
            changed.append(str(path))
    for path in backend_paths:
        if patch_file(path, BACKEND_BLOCK, backup_root, dry_run):
            changed.append(str(path))

    return {
        "status": "dry_run" if dry_run else "installed",
        "backup": str(backup_root),
        "copied_references": copied,
        "patched_files": changed,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=".", help="Hermes repo checkout")
    parser.add_argument("--home", default="/home/atlas/.hermes", help="Hermes home")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = install(Path(args.repo).resolve(), Path(args.home).resolve(), args.dry_run)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
