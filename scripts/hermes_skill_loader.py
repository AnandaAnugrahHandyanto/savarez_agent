#!/usr/bin/env python3
"""Hermes skill loader — unified reader for SKILL.md files.

Spec: ~/wiki/concepts/hermes-openclaw-deerflow-integration-plan.md §S1 (se-023)
Inspired by DeerFlow's skills/loader.py + skills/parser.py patterns.

Scans ~/.hermes/skills/ recursively for SKILL.md files, parses YAML
frontmatter, returns Skill dataclass list. Compatible with both:
- DeerFlow-style: name, description, license, allowed-tools
- Hermes-style:   name, description, version, author, metadata.hermes.tags

Usage:
    python scripts/hermes_skill_loader.py                 # list all
    python scripts/hermes_skill_loader.py --json          # JSON
    python scripts/hermes_skill_loader.py --count         # just counts
    python scripts/hermes_skill_loader.py --family apple  # filter top-level
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import yaml

HERMES_SKILLS_ROOT = Path.home() / ".hermes" / "skills"
OPENCLAW_SKILLS_ROOT = Path.home() / ".openclaw" / "custom-skills"


@dataclass
class Skill:
    """Unified skill record — works for DeerFlow + Hermes-style frontmatter."""

    name: str
    description: str
    family: str  # top-level dir (e.g. 'apple', 'bwstudio', 'research')
    skill_dir: Path
    origin: str  # 'hermes' | 'openclaw'
    version: str | None = None
    author: str | None = None
    license: str | None = None
    allowed_tools: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    raw_metadata: dict[str, Any] = field(default_factory=dict)

    def to_json_safe(self) -> dict[str, Any]:
        d = asdict(self)
        d["skill_dir"] = str(self.skill_dir)
        # Don't dump raw metadata in json — it can be noisy
        d.pop("raw_metadata", None)
        return d


def _read_frontmatter(skill_md: Path) -> dict[str, Any] | None:
    try:
        text = skill_md.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return None
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
    if not m:
        return None
    try:
        meta = yaml.safe_load(m.group(1))
    except yaml.YAMLError:
        return None
    return meta if isinstance(meta, dict) else None


def _extract_tags(meta: dict[str, Any]) -> list[str]:
    """Tags can live in top-level `tags` or under metadata.hermes.tags."""
    if isinstance(meta.get("tags"), list):
        return [str(t) for t in meta["tags"]]
    nested = (meta.get("metadata") or {}).get("hermes") or {}
    if isinstance(nested.get("tags"), list):
        return [str(t) for t in nested["tags"]]
    return []


def _parse_skill(
    skill_md: Path, *, origin: str, root: Path
) -> Skill | None:
    meta = _read_frontmatter(skill_md)
    if not meta:
        return None
    name = meta.get("name")
    desc = meta.get("description")
    if not isinstance(name, str) or not isinstance(desc, str):
        return None
    name = name.strip()
    desc = desc.strip()
    if not name or not desc:
        return None

    skill_dir = skill_md.parent
    rel = skill_dir.relative_to(root)
    family = rel.parts[0] if rel.parts else ""

    allowed = meta.get("allowed-tools") or meta.get("allowed_tools") or []
    if isinstance(allowed, str):
        allowed = [allowed]

    return Skill(
        name=name,
        description=desc,
        family=family,
        skill_dir=skill_dir,
        origin=origin,
        version=str(meta["version"]) if "version" in meta else None,
        author=meta.get("author"),
        license=meta.get("license"),
        allowed_tools=[str(t) for t in allowed],
        tags=_extract_tags(meta),
        raw_metadata=meta,
    )


def load_skills(
    *,
    include_hermes: bool = True,
    include_openclaw: bool = True,
) -> list[Skill]:
    """Scan known roots for SKILL.md files and return unified Skill list."""
    skills: list[Skill] = []
    if include_hermes and HERMES_SKILLS_ROOT.exists():
        for skill_md in HERMES_SKILLS_ROOT.rglob("SKILL.md"):
            sk = _parse_skill(skill_md, origin="hermes", root=HERMES_SKILLS_ROOT)
            if sk:
                skills.append(sk)
    if include_openclaw and OPENCLAW_SKILLS_ROOT.exists():
        for skill_md in OPENCLAW_SKILLS_ROOT.rglob("SKILL.md"):
            sk = _parse_skill(skill_md, origin="openclaw", root=OPENCLAW_SKILLS_ROOT)
            if sk:
                skills.append(sk)
    # Sort: origin, then family, then name
    skills.sort(key=lambda s: (s.origin, s.family, s.name))
    return skills


def summarize(skills: list[Skill]) -> dict[str, Any]:
    by_origin: dict[str, int] = {}
    by_family: dict[str, int] = {}
    for s in skills:
        by_origin[s.origin] = by_origin.get(s.origin, 0) + 1
        key = f"{s.origin}/{s.family}"
        by_family[key] = by_family.get(key, 0) + 1
    return {
        "total": len(skills),
        "by_origin": by_origin,
        "by_family": dict(sorted(by_family.items())),
        "with_allowed_tools": sum(1 for s in skills if s.allowed_tools),
        "with_tags": sum(1 for s in skills if s.tags),
        "with_version": sum(1 for s in skills if s.version),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--count", action="store_true")
    ap.add_argument("--family", default=None, help="filter by top-level family dir")
    ap.add_argument("--origin", default=None, choices=["hermes", "openclaw"])
    ap.add_argument("--no-hermes", action="store_true")
    ap.add_argument("--no-openclaw", action="store_true")
    args = ap.parse_args()

    skills = load_skills(
        include_hermes=not args.no_hermes,
        include_openclaw=not args.no_openclaw,
    )
    if args.family:
        skills = [s for s in skills if s.family == args.family]
    if args.origin:
        skills = [s for s in skills if s.origin == args.origin]

    if args.count:
        print(json.dumps(summarize(skills), ensure_ascii=False, indent=2))
        return 0

    if args.json:
        print(json.dumps(
            {"summary": summarize(skills), "skills": [s.to_json_safe() for s in skills]},
            ensure_ascii=False, indent=2,
        ))
        return 0

    # Human-readable
    summary = summarize(skills)
    print(f"Total: {summary['total']}")
    print(f"By origin: {summary['by_origin']}")
    print(f"Top families:")
    top = sorted(summary["by_family"].items(), key=lambda kv: -kv[1])[:10]
    for k, v in top:
        print(f"  {v:>3}  {k}")
    print()
    for s in skills[:15]:
        tags = f"  [{','.join(s.tags[:3])}]" if s.tags else ""
        print(f"  {s.origin:8}/{s.family:15} {s.name:30}  — {s.description[:60]}{tags}")
    if len(skills) > 15:
        print(f"  ... (+{len(skills) - 15} more)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
