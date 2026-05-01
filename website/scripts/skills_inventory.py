#!/usr/bin/env python3
"""Generate a governance-oriented inventory for local Hermes skills."""

from __future__ import annotations

import argparse
import json
import os
import re
from collections import Counter, defaultdict
from pathlib import Path

import yaml

from hermes_constants import get_hermes_home


REPO_ROOT = Path(__file__).resolve().parents[2]
LOCAL_SKILL_DIRS = [
    (REPO_ROOT / "skills", "built-in"),
    (REPO_ROOT / "optional-skills", "optional"),
]
TESTS_DIR = REPO_ROOT / "tests" / "skills"
DEFAULT_JSON = REPO_ROOT / "website" / "src" / "data" / "skills-inventory.json"
DEFAULT_MARKDOWN = REPO_ROOT / "docs" / "architecture" / "skills-inventory-report.md"
DEFAULT_RUNTIME_JSON = REPO_ROOT / "website" / "src" / "data" / "runtime-skills-inventory.json"
DEFAULT_COMPAT_MARKDOWN = REPO_ROOT / "website" / "docs" / "reference" / "compatibility-skills-catalog.md"
PROMOTION_CANDIDATES = set()
RUNTIME_VALIDATED = {
    "agentmail",
    "siyuan",
    "docx",
    "xlsx",
    "ocr-and-documents",
}
SECTION_PATTERNS = {
    "verification": re.compile(r"^##\s+Verification\b", re.MULTILINE | re.IGNORECASE),
    "pitfalls": re.compile(r"^##\s+Pitfalls\b", re.MULTILINE | re.IGNORECASE),
    "prerequisites": re.compile(r"^##\s+Prerequisites\b", re.MULTILINE | re.IGNORECASE),
    "when_to_use": re.compile(r"^##\s+(When to Use|When to use)\b", re.MULTILINE),
}
RUNTIME_SKILLS_DIR = get_hermes_home() / "skills"
IMPORTED_CANONICAL_NAMES = {
    "china-stock-analysis",
    "lark-approval",
    "lark-base",
    "lark-calendar",
    "lark-contact",
    "lark-doc",
    "lark-drive",
    "lark-event",
    "lark-im",
    "lark-mail",
    "lark-minutes",
    "lark-openapi-explorer",
    "lark-shared",
    "lark-sheets",
    "lark-skill-maker",
    "lark-task",
    "lark-vc",
    "lark-whiteboard",
    "lark-wiki",
    "lark-workflow-meeting-summary",
    "lark-workflow-standup-report",
    "stock-market-pro",
    "tushare",
    "tushare-api",
}
CROSS_NAME_ALIAS_MAP = {
    "a-stock-team-strategy": "stock-team-strategy",
    "Self-Improving + Proactive Agent": "self-improving",
}


def _resolve_runtime_canonical_name(skill_dir_name: str, skill_name: str) -> str:
    if skill_name in CROSS_NAME_ALIAS_MAP:
        return CROSS_NAME_ALIAS_MAP[skill_name]
    if skill_dir_name in CROSS_NAME_ALIAS_MAP:
        return CROSS_NAME_ALIAS_MAP[skill_dir_name]
    return ""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--json", dest="json_path", default=str(DEFAULT_JSON))
    p.add_argument("--markdown", dest="markdown_path", default=str(DEFAULT_MARKDOWN))
    p.add_argument("--runtime-json", dest="runtime_json_path", default=str(DEFAULT_RUNTIME_JSON))
    p.add_argument("--compat-markdown", dest="compat_markdown_path", default=str(DEFAULT_COMPAT_MARKDOWN))
    return p.parse_args(argv)


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _frontmatter_and_body(text: str) -> tuple[dict, str]:
    if not text.startswith("---"):
        return {}, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text
    try:
        fm = yaml.safe_load(parts[1]) or {}
    except yaml.YAMLError:
        fm = {}
    return fm if isinstance(fm, dict) else {}, parts[2]


def _derive_category(skill_root: Path, base_path: Path, frontmatter: dict) -> str:
    rel = skill_root.relative_to(base_path)
    category = rel.parts[0] if rel.parts else "other"
    metadata = frontmatter.get("metadata")
    if isinstance(metadata, dict):
        hermes = metadata.get("hermes", {})
        if isinstance(hermes, dict):
            category = hermes.get("category", category)
    return category


def _derive_tags(frontmatter: dict) -> list[str]:
    metadata = frontmatter.get("metadata")
    if isinstance(metadata, dict):
        hermes = metadata.get("hermes", {})
        if isinstance(hermes, dict) and hermes.get("tags"):
            tags = hermes.get("tags")
            return tags if isinstance(tags, list) else [str(tags)]
    tags = frontmatter.get("tags", [])
    if isinstance(tags, list):
        return [str(x) for x in tags]
    if isinstance(tags, str):
        return [tags]
    return []


def _skill_test_map() -> dict[str, list[str]]:
    mapping: dict[str, list[str]] = defaultdict(list)
    if not TESTS_DIR.exists():
        return mapping
    for path in TESTS_DIR.glob("test_*.py"):
        text = _read_text(path).lower()
        for skill_name in [
            "agentmail", "siyuan", "telephony", "memento-flashcards", "youtube-content",
            "openclaw-migration", "google-workspace", "docx", "xlsx", "ocr-and-documents",
            "dogfood", "fastmcp", "domain-intel", "duckduckgo-search", "honcho", "docker-management",
        ]:
            if skill_name.lower() in text or skill_name.replace("-", "_") in path.stem:
                mapping[skill_name].append(str(path.relative_to(REPO_ROOT)))
        stem = path.stem.removeprefix("test_")
        normalized = stem.replace("_skill", "").replace("_", "-")
        mapping[normalized].append(str(path.relative_to(REPO_ROOT)))
    deduped = {}
    for k, v in mapping.items():
        deduped[k] = sorted(set(v))
    return deduped


def _quality_tier(has_body: bool, has_exec: bool, has_safe: bool, has_tests: bool, runtime_validated: bool) -> str:
    if runtime_validated and has_tests and has_safe:
        return "D4"
    if has_tests and has_safe:
        return "D3"
    if has_safe:
        return "D2"
    if has_exec:
        return "D1"
    if has_body:
        return "D0"
    return "D0"


def collect_local_skills() -> list[dict]:
    test_map = _skill_test_map()
    skills: list[dict] = []

    for base_path, source in LOCAL_SKILL_DIRS:
        if not base_path.exists():
            continue
        for skill_md in base_path.rglob("SKILL.md"):
            skill_root = skill_md.parent
            text = _read_text(skill_md)
            frontmatter, body = _frontmatter_and_body(text)
            name = frontmatter.get("name", skill_root.name)
            category = _derive_category(skill_root, base_path, frontmatter)
            tags = _derive_tags(frontmatter)
            scripts = sorted(str(p.relative_to(REPO_ROOT)) for p in (skill_root / "scripts").rglob("*") if p.is_file()) if (skill_root / "scripts").exists() else []
            references = sorted(str(p.relative_to(REPO_ROOT)) for p in (skill_root / "references").rglob("*") if p.is_file()) if (skill_root / "references").exists() else []
            templates = sorted(str(p.relative_to(REPO_ROOT)) for p in (skill_root / "templates").rglob("*") if p.is_file()) if (skill_root / "templates").exists() else []
            has_verification = bool(SECTION_PATTERNS["verification"].search(body))
            has_pitfalls = bool(SECTION_PATTERNS["pitfalls"].search(body))
            has_prereq = bool(SECTION_PATTERNS["prerequisites"].search(body)) or bool(frontmatter.get("prerequisites"))
            has_when = bool(SECTION_PATTERNS["when_to_use"].search(body))
            has_exec = bool(scripts or templates or references or re.search(r"```bash|```python|python3\s+- <<'PY'", body))
            tests = sorted(set(test_map.get(name, []) + test_map.get(skill_root.name, [])))
            runtime_validated = name in RUNTIME_VALIDATED
            has_safe = has_verification and has_pitfalls and has_prereq and has_when
            quality_tier = _quality_tier(bool(body.strip()), has_exec, has_safe, bool(tests), runtime_validated)
            skills.append({
                "name": name,
                "source": source,
                "category": category,
                "path": str(skill_root.relative_to(REPO_ROOT)),
                "description": frontmatter.get("description", ""),
                "version": frontmatter.get("version", ""),
                "author": frontmatter.get("author", ""),
                "tags": tags,
                "has_scripts": bool(scripts),
                "has_references": bool(references),
                "has_templates": bool(templates),
                "has_tests": bool(tests),
                "test_files": tests,
                "has_verification_section": has_verification,
                "has_pitfalls_section": has_pitfalls,
                "has_prerequisites": has_prereq,
                "has_when_to_use": has_when,
                "quality_tier": quality_tier,
                "runtime_validated": runtime_validated,
                "promotion_candidate": source == "optional" and name in PROMOTION_CANDIDATES,
            })
    return sorted(skills, key=lambda x: (x["source"], x["category"], x["name"]))


def build_summary(skills: list[dict]) -> dict:
    by_source = Counter(item["source"] for item in skills)
    by_category = {source: dict(sorted(Counter(item["category"] for item in skills if item["source"] == source).items())) for source in by_source}
    tiers = Counter(item["quality_tier"] for item in skills)
    return {
        "local_total": len(skills),
        "by_source": dict(sorted(by_source.items())),
        "by_category": by_category,
        "quality_tiers": dict(sorted(tiers.items())),
        "with_tests": sum(1 for x in skills if x["has_tests"]),
        "runtime_validated": sum(1 for x in skills if x["runtime_validated"]),
        "promotion_candidates": [x["name"] for x in skills if x["promotion_candidate"]],
    }


def render_markdown(skills: list[dict], summary: dict) -> str:
    lines = [
        "# Hermes Skills Inventory",
        "",
        "## Source Summary",
        "",
        f"- Local total: **{summary['local_total']}**",
    ]
    for source, count in summary["by_source"].items():
        lines.append(f"- {source}: **{count}**")
    lines.extend([
        "",
        "## Quality Summary",
        "",
    ])
    for tier, count in summary["quality_tiers"].items():
        lines.append(f"- {tier}: **{count}**")
    lines.extend([
        f"- Skills with tests: **{summary['with_tests']}**",
        f"- Runtime validated: **{summary['runtime_validated']}**",
        "",
        "## Promotion Candidates",
        "",
    ])
    for name in summary["promotion_candidates"]:
        lines.append(f"- `{name}`")
    lines.extend(["", "## Local Skills", "", "| Name | Source | Category | Tier | Tests | Verification | Pitfalls | Runtime Validated |", "|---|---|---|---|---:|---:|---:|---:|"])
    for item in skills:
        lines.append(
            f"| `{item['name']}` | {item['source']} | {item['category']} | {item['quality_tier']} | {'Y' if item['has_tests'] else 'N'} | {'Y' if item['has_verification_section'] else 'N'} | {'Y' if item['has_pitfalls_section'] else 'N'} | {'Y' if item['runtime_validated'] else 'N'} |"
        )
    return "\n".join(lines) + "\n"


def collect_runtime_skills(local_skills: list[dict]) -> list[dict]:
    if not RUNTIME_SKILLS_DIR.exists():
        return []

    local_names = {item["name"] for item in local_skills}
    local_sources = {item["name"]: item["source"] for item in local_skills}
    runtime_skills: list[dict] = []

    for skill_md in RUNTIME_SKILLS_DIR.rglob("SKILL.md"):
        skill_root = skill_md.parent
        rel = skill_root.relative_to(RUNTIME_SKILLS_DIR)
        rel_posix = rel.as_posix()
        top_level = rel.parts[0] if rel.parts else "other"
        text = _read_text(skill_md)
        frontmatter, _body = _frontmatter_and_body(text)
        name = frontmatter.get("name", skill_root.name)
        description = frontmatter.get("description", "")
        tags = _derive_tags(frontmatter)
        metadata = frontmatter.get("metadata")
        category = top_level
        if isinstance(metadata, dict):
            hermes = metadata.get("hermes", {})
            if isinstance(hermes, dict):
                category = hermes.get("category", category)

        archived = rel_posix.startswith("openclaw-imports/.") or top_level.startswith(".")
        is_imported_variant = rel_posix.startswith("openclaw-imports/") and rel.parts[-1].endswith("-imported")
        alias_canonical = _resolve_runtime_canonical_name(skill_root.name, name)
        if archived:
            source = "openclaw-archived"
            status = "archived"
            catalog = "archived"
        elif top_level == "openclaw-imports":
            source = "openclaw-compat"
            status = "deprecated" if (is_imported_variant or alias_canonical) else "active"
            catalog = "compatibility"
        elif name in local_names:
            source = local_sources.get(name, "official")
            status = "active"
            catalog = "official"
        else:
            source = "runtime-external"
            status = "active"
            catalog = "runtime-external"

        duplicate_of = ""
        if alias_canonical:
            duplicate_of = alias_canonical
        elif is_imported_variant and name in IMPORTED_CANONICAL_NAMES:
            duplicate_of = name
        elif name.endswith("-imported"):
            duplicate_of = name.removesuffix("-imported")
        elif top_level == "openclaw-imports" and name in local_names:
            duplicate_of = name

        runtime_skills.append({
            "name": name,
            "path": rel_posix,
            "top_level": top_level,
            "category": category,
            "description": description,
            "tags": tags,
            "source": source,
            "status": status,
            "catalog": catalog,
            "duplicateOf": duplicate_of,
            "official_match": name in local_names,
            "variant": "imported" if is_imported_variant else "primary",
        })

    return sorted(runtime_skills, key=lambda item: (item["catalog"], item["top_level"], item["name"], item["variant"]))


def build_runtime_summary(runtime_skills: list[dict]) -> dict:
    by_source = Counter(item["source"] for item in runtime_skills)
    by_catalog = Counter(item["catalog"] for item in runtime_skills)
    by_top_level = Counter(item["top_level"] for item in runtime_skills)
    by_status = Counter(item["status"] for item in runtime_skills)
    return {
        "physical_total": len(runtime_skills),
        "effective_total": sum(1 for item in runtime_skills if item["status"] != "archived"),
        "archived_total": sum(1 for item in runtime_skills if item["status"] == "archived"),
        "by_source": dict(sorted(by_source.items())),
        "by_catalog": dict(sorted(by_catalog.items())),
        "by_top_level": dict(sorted(by_top_level.items())),
        "by_status": dict(sorted(by_status.items())),
        "duplicates": sum(1 for item in runtime_skills if item["duplicateOf"]),
    }


def render_compatibility_markdown(runtime_skills: list[dict], summary: dict) -> str:
    compatibility = [item for item in runtime_skills if item["catalog"] == "compatibility"]
    archived = [item for item in runtime_skills if item["catalog"] == "archived"]
    runtime_external = [item for item in runtime_skills if item["catalog"] == "runtime-external"]
    canonical_count = sum(1 for item in compatibility if not item["duplicateOf"] and item["variant"] == "primary")
    imported_count = sum(1 for item in compatibility if item["variant"] == "imported")

    lines = [
        "---",
        'sidebar_position: 10',
        'title: "Compatibility Skills Catalog"',
        'description: "Runtime compatibility and archived skills carried for migration safety"',
        "---",
        "",
        "# Compatibility Skills Catalog",
        "",
        "This page tracks the runtime-only compatibility layer so it does not pollute the main skills narrative.",
        "",
        "## Runtime split",
        "",
        f"- Physical runtime `SKILL.md` files: **{summary['physical_total']}**",
        f"- Effective runtime skills: **{summary['effective_total']}**",
        f"- Archived compatibility remnants: **{summary['archived_total']}**",
        f"- OpenClaw compatibility skills: **{summary['by_source'].get('openclaw-compat', 0)}**",
        f"- Runtime-only external skills: **{summary['by_source'].get('runtime-external', 0)}**",
        f"- Compatibility canonical records: **{canonical_count}**",
        f"- Compatibility imported/duplicate variants: **{imported_count}**",
        "",
        "## Policy",
        "",
        "- Compatibility skills stay loadable for migration safety.",
        "- They are not part of the main built-in/optional product shelf.",
        "- Imported `*-imported` variants are treated as deprecated duplicates of a canonical compatibility skill.",
        "- Archived `.disabled` remnants are retained only as historical compatibility residue.",
        "",
        "## OpenClaw compatibility layer",
        "",
        "| Skill | Variant | Status | Canonical | Path |",
        "|---|---|---|---|---|",
    ]
    for item in compatibility:
        lines.append(
            f"| `{item['name']}` | {item['variant']} | {item['status']} | {item['duplicateOf'] or '—'} | `{item['path']}` |"
        )

    lines.extend([
        "",
        "## Archived remnants",
        "",
        "| Skill | Status | Path |",
        "|---|---|---|",
    ])
    for item in archived:
        lines.append(f"| `{item['name']}` | {item['status']} | `{item['path']}` |")

    lines.extend([
        "",
        "## Runtime-only extras",
        "",
        "| Skill | Source | Path |",
        "|---|---|---|",
    ])
    for item in runtime_external:
        lines.append(f"| `{item['name']}` | {item['source']} | `{item['path']}` |")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    skills = collect_local_skills()
    summary = build_summary(skills)
    payload = {"summary": summary, "skills": skills}
    runtime_skills = collect_runtime_skills(skills)
    runtime_summary = build_runtime_summary(runtime_skills)
    runtime_payload = {"summary": runtime_summary, "skills": runtime_skills}

    json_path = Path(args.json_path)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    if args.markdown_path:
        markdown_path = Path(args.markdown_path)
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_path.write_text(render_markdown(skills, summary), encoding="utf-8")

    runtime_json_path = Path(args.runtime_json_path)
    runtime_json_path.parent.mkdir(parents=True, exist_ok=True)
    runtime_json_path.write_text(json.dumps(runtime_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    if args.compat_markdown_path:
        compat_markdown_path = Path(args.compat_markdown_path)
        compat_markdown_path.parent.mkdir(parents=True, exist_ok=True)
        compat_markdown_path.write_text(
            render_compatibility_markdown(runtime_skills, runtime_summary),
            encoding="utf-8",
        )

    print(json.dumps({
        "ok": True,
        "json": str(json_path),
        "markdown": str(args.markdown_path),
        "runtime_json": str(runtime_json_path),
        "compat_markdown": str(args.compat_markdown_path),
        "local_total": summary["local_total"],
        "runtime_physical_total": runtime_summary["physical_total"],
        "runtime_effective_total": runtime_summary["effective_total"],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
