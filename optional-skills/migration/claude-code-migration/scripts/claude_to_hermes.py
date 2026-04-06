#!/usr/bin/env python3
"""
Claude Code -> Hermes Agent migration helper.

Migrates Claude Code configuration, rules, memories, MCP servers, and
custom commands into Hermes Agent format. Supports dry-run preview,
selective migration via presets, and structured JSON reporting.

Usage:
    python3 claude_to_hermes.py                          # Dry-run
    python3 claude_to_hermes.py --execute --preset user-data
    python3 claude_to_hermes.py --execute --preset full --migrate-secrets
"""

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

# ── Constants ──

ENTRY_DELIMITER = "\n§\n"
DEFAULT_MEMORY_CHAR_LIMIT = 2200
DEFAULT_USER_CHAR_LIMIT = 1375

MIGRATION_CATEGORIES = {
    "rules": "Global rules from ~/.claude/rules/*.md",
    "memory": "Project memories from ~/.claude/projects/*/memory/*.md",
    "claude-md": "CLAUDE.md files from project directories",
    "mcp-servers": "MCP server definitions from settings.json",
    "custom-commands": "Custom slash commands from ~/.claude/commands/",
    "api-keys": "API keys from settings.json (requires --migrate-secrets)",
    "keybindings": "Keybindings (archived, different system)",
}

MIGRATION_PRESETS = {
    "user-data": {
        "rules", "memory", "claude-md", "mcp-servers", "custom-commands",
    },
    "full": {
        "rules", "memory", "claude-md", "mcp-servers", "custom-commands",
        "api-keys", "keybindings",
    },
}

# Keys safe to migrate
SUPPORTED_SECRET_KEYS = {
    "ANTHROPIC_API_KEY",
    "OPENAI_API_KEY",
    "OPENROUTER_API_KEY",
}


# ── Data classes ──

@dataclass
class MigrationItem:
    kind: str
    source: str
    destination: str
    status: str  # migrated, skipped, archived, conflict, error
    reason: str = ""
    details: dict = field(default_factory=dict)


@dataclass
class MigrationReport:
    timestamp: str
    mode: str
    source_root: str
    target_root: str
    items: list = field(default_factory=list)
    selection: dict = field(default_factory=dict)

    def record(self, kind, source, destination, status, reason="", **details):
        self.items.append(MigrationItem(
            kind=kind, source=str(source), destination=str(destination),
            status=status, reason=reason, details=details,
        ))

    @property
    def summary(self):
        counts = {"migrated": 0, "skipped": 0, "archived": 0, "conflict": 0, "error": 0}
        for item in self.items:
            counts[item.status] = counts.get(item.status, 0) + 1
        return counts

    def to_dict(self):
        return {
            "timestamp": self.timestamp,
            "mode": self.mode,
            "source_root": self.source_root,
            "target_root": self.target_root,
            "summary": self.summary,
            "selection": self.selection,
            "items": [
                {
                    "kind": i.kind, "source": i.source,
                    "destination": i.destination, "status": i.status,
                    "reason": i.reason, "details": i.details,
                }
                for i in self.items
            ],
        }


# ── Helpers ──

def sha256(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def parse_env_file(path: Path) -> dict:
    """Parse a .env file into a dict, ignoring comments and empty lines."""
    env = {}
    if not path.exists():
        return env
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, _, value = line.partition("=")
            env[key.strip()] = value.strip()
    return env


def append_env_vars(path: Path, new_vars: dict):
    """Append new env vars to .env file without overwriting existing keys."""
    existing = parse_env_file(path)
    additions = []
    for key, value in new_vars.items():
        if key not in existing:
            additions.append(f"{key}={value}")
    if additions:
        with open(path, "a") as f:
            f.write("\n# Migrated from Claude Code\n")
            for line in additions:
                f.write(line + "\n")
    return additions


def extract_markdown_entries(text: str) -> list:
    """Parse structured markdown into memory entries with heading context."""
    entries = []
    current_heading = ""
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("## "):
            current_heading = stripped[3:].strip()
        elif stripped.startswith("- ") and len(stripped) > 20:
            entry = stripped[2:].strip()
            if current_heading:
                entry = f"{current_heading}: {entry}"
            entries.append(entry)
        elif stripped.startswith("# ") or not stripped:
            continue
        elif len(stripped) > 30 and not stripped.startswith("```"):
            # Standalone paragraph
            if current_heading:
                entries.append(f"{current_heading}: {stripped}")
            else:
                entries.append(stripped)
    return entries


def merge_entries(existing: list, incoming: list, limit: int) -> tuple:
    """Merge incoming entries into existing, respecting char limit.

    Returns: (merged_list, stats_dict, overflow_list)
    """
    seen = {e.strip().lower() for e in existing}
    merged = list(existing)
    stats = {"added": 0, "duplicates": 0, "overflow": 0}
    overflow = []

    for entry in incoming:
        normalized = entry.strip().lower()
        if normalized in seen:
            stats["duplicates"] += 1
            continue
        # Check if adding would exceed limit
        test = ENTRY_DELIMITER.join(merged + [entry])
        if len(test) > limit:
            stats["overflow"] += 1
            overflow.append(entry)
            continue
        merged.append(entry)
        seen.add(normalized)
        stats["added"] += 1

    return merged, stats, overflow


def parse_existing_memory(path: Path) -> list:
    """Parse existing Hermes memory file into entries."""
    if not path.exists():
        return []
    raw = path.read_text()
    if ENTRY_DELIMITER in raw:
        return [e.strip() for e in raw.split(ENTRY_DELIMITER) if e.strip()]
    return extract_markdown_entries(raw)


# ── Migrator ──

class ClaudeCodeMigrator:
    """Handles Claude Code → Hermes migration."""

    def __init__(self, source: Path, target: Path, execute: bool = False,
                 migrate_secrets: bool = False, preset: str = None,
                 include: set = None, exclude: set = None,
                 output_dir: Path = None):
        self.source = source
        self.target = target
        self.execute = execute
        self.migrate_secrets = migrate_secrets
        self.output_dir = output_dir or (
            target / "migration" / "claude-code" /
            datetime.now().strftime("%Y%m%dT%H%M%S")
        )

        # Determine selected categories
        if preset and preset in MIGRATION_PRESETS:
            selected = MIGRATION_PRESETS[preset].copy()
        elif include:
            selected = include
        else:
            selected = MIGRATION_PRESETS["user-data"].copy()

        if exclude:
            selected -= exclude

        # API keys require explicit flag
        if "api-keys" in selected and not migrate_secrets:
            selected.discard("api-keys")

        self.selected = selected
        self.report = MigrationReport(
            timestamp=datetime.now().strftime("%Y%m%dT%H%M%S"),
            mode="execute" if execute else "dry-run",
            source_root=str(source),
            target_root=str(target),
            selection={
                "selected": sorted(selected),
                "preset": preset or "custom",
                "available": sorted(MIGRATION_CATEGORIES.keys()),
            },
        )

    def migrate(self) -> dict:
        """Run all selected migrations and return report."""
        if self.execute:
            self.output_dir.mkdir(parents=True, exist_ok=True)
            (self.output_dir / "backups").mkdir(exist_ok=True)
            (self.output_dir / "archive").mkdir(exist_ok=True)
            (self.output_dir / "overflow").mkdir(exist_ok=True)

        handlers = {
            "rules": self._migrate_rules,
            "memory": self._migrate_memory,
            "claude-md": self._migrate_claude_md,
            "mcp-servers": self._migrate_mcp_servers,
            "custom-commands": self._migrate_custom_commands,
            "api-keys": self._migrate_api_keys,
            "keybindings": self._migrate_keybindings,
        }

        for category in sorted(self.selected):
            handler = handlers.get(category)
            if handler:
                try:
                    handler()
                except Exception as e:
                    self.report.record(
                        category, str(self.source), str(self.target),
                        "error", reason=str(e),
                    )

        # Write report
        if self.execute:
            report_path = self.output_dir / "report.json"
            report_path.write_text(
                json.dumps(self.report.to_dict(), indent=2, default=str)
            )
            self._write_summary_md()

        return self.report.to_dict()

    def _backup(self, path: Path):
        """Backup a file before overwriting."""
        if path.exists() and self.execute:
            backup = self.output_dir / "backups" / path.name
            shutil.copy2(path, backup)

    # ── Migration handlers ──

    def _migrate_rules(self):
        """Migrate ~/.claude/rules/*.md → SOUL.md + MEMORY.md."""
        rules_dir = self.source / "rules"
        if not rules_dir.is_dir():
            self.report.record("rules", str(rules_dir), "", "skipped",
                               reason="No rules directory found")
            return

        soul_entries = []
        memory_entries = []

        # Categorize rules by filename
        behavioral_patterns = {"workflow", "eec-art-direction"}
        for fpath in sorted(rules_dir.glob("*.md")):
            text = fpath.read_text()
            fname = fpath.stem

            if any(p in fname for p in behavioral_patterns):
                # Behavioral rules → SOUL.md context
                sections = self._split_sections(text)
                soul_entries.extend(sections[:5])  # Top sections only
            elif "gotchas" in fname:
                # Gotchas → MEMORY.md entries (one per rule)
                for line in text.splitlines():
                    line = line.strip()
                    if line.startswith("- ") and len(line) > 30:
                        section = fname.replace("gotchas-", "").replace(".md", "")
                        memory_entries.append(f"[{section}] {line[2:]}")
            else:
                # Other rules → MEMORY.md sections
                entries = extract_markdown_entries(text)
                memory_entries.extend(entries)

        # Write SOUL.md
        soul_dest = self.target / "SOUL.md"
        if soul_entries:
            soul_text = "\n\n".join(soul_entries[:10])  # Cap at 10 sections
            if self.execute:
                self._backup(soul_dest)
                if soul_dest.exists():
                    # Append to existing SOUL.md
                    existing = soul_dest.read_text()
                    soul_dest.write_text(
                        existing + "\n\n## Imported from Claude Code\n\n" + soul_text
                    )
                else:
                    soul_dest.write_text(
                        "# Hermes Agent Persona\n\n"
                        "## Imported from Claude Code\n\n" + soul_text
                    )
            self.report.record("rules", str(rules_dir), str(soul_dest),
                               "migrated", reason=f"{len(soul_entries)} behavioral rules",
                               soul_entries=len(soul_entries))

        # Write MEMORY.md
        if memory_entries:
            mem_dest = self.target / "memories" / "MEMORY.md"
            existing = parse_existing_memory(mem_dest)
            merged, stats, overflow = merge_entries(
                existing, memory_entries, DEFAULT_MEMORY_CHAR_LIMIT
            )
            if self.execute:
                mem_dest.parent.mkdir(parents=True, exist_ok=True)
                self._backup(mem_dest)
                mem_dest.write_text(ENTRY_DELIMITER.join(merged) + "\n")
                if overflow:
                    of_path = self.output_dir / "overflow" / "rules_overflow.txt"
                    of_path.write_text("\n---\n".join(overflow))
            self.report.record("rules", str(rules_dir), str(mem_dest),
                               "migrated",
                               reason=f"{stats['added']} added, {stats['duplicates']} dupes, {stats['overflow']} overflow",
                               **stats)

    def _migrate_memory(self):
        """Migrate Claude project memories → MEMORY.md."""
        projects_dir = self.source / "projects"
        if not projects_dir.is_dir():
            self.report.record("memory", str(projects_dir), "", "skipped",
                               reason="No projects directory found")
            return

        all_entries = []
        file_count = 0

        for memory_dir in projects_dir.glob("*/memory"):
            if not memory_dir.is_dir():
                continue
            for fpath in sorted(memory_dir.glob("*.md")):
                if fpath.name == "MEMORY.md":
                    continue  # Skip index files
                text = fpath.read_text()
                if len(text.strip()) < 30:
                    continue
                entries = extract_markdown_entries(text)
                if not entries:
                    # Treat whole file as one entry if no structure found
                    entries = [text.strip()[:500]]
                all_entries.extend(entries)
                file_count += 1

        if not all_entries:
            self.report.record("memory", str(projects_dir), "", "skipped",
                               reason="No memory files found")
            return

        mem_dest = self.target / "memories" / "MEMORY.md"
        existing = parse_existing_memory(mem_dest)
        merged, stats, overflow = merge_entries(
            existing, all_entries, DEFAULT_MEMORY_CHAR_LIMIT
        )

        if self.execute:
            mem_dest.parent.mkdir(parents=True, exist_ok=True)
            self._backup(mem_dest)
            mem_dest.write_text(ENTRY_DELIMITER.join(merged) + "\n")
            if overflow:
                of_path = self.output_dir / "overflow" / "memory_overflow.txt"
                of_path.write_text("\n---\n".join(overflow))

        self.report.record("memory", str(projects_dir), str(mem_dest),
                           "migrated",
                           reason=f"{file_count} files, {stats['added']} entries added, {stats['overflow']} overflow",
                           files=file_count, **stats)

    def _migrate_claude_md(self):
        """Archive CLAUDE.md files for reference."""
        claude_md = Path.home() / "CLAUDE.md"
        if not claude_md.exists():
            # Check common project dirs
            found = list(Path.home().glob("*/CLAUDE.md"))[:10]
            if not found:
                self.report.record("claude-md", "~/*/CLAUDE.md", "", "skipped",
                                   reason="No CLAUDE.md files found")
                return
        else:
            found = [claude_md]

        for fpath in found:
            dest = self.output_dir / "archive" / f"CLAUDE_{fpath.parent.name}.md"
            if self.execute:
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(fpath, dest)
            self.report.record("claude-md", str(fpath), str(dest),
                               "archived", reason="Saved for reference")

    def _migrate_mcp_servers(self):
        """Migrate MCP server configs from settings.json → config.yaml."""
        settings_path = self.source / "settings.json"
        if not settings_path.exists():
            self.report.record("mcp-servers", str(settings_path), "", "skipped",
                               reason="No settings.json found")
            return

        try:
            settings = json.loads(settings_path.read_text())
        except json.JSONDecodeError:
            self.report.record("mcp-servers", str(settings_path), "", "error",
                               reason="Invalid JSON in settings.json")
            return

        mcp_servers = settings.get("mcpServers", {})
        if not mcp_servers:
            self.report.record("mcp-servers", str(settings_path), "", "skipped",
                               reason="No MCP servers defined")
            return

        # Convert to Hermes MCP format
        hermes_servers = {}
        for name, config in mcp_servers.items():
            server = {}
            if "command" in config:
                server["transport"] = "stdio"
                server["command"] = config["command"]
                if "args" in config:
                    server["args"] = config["args"]
            elif "url" in config:
                server["transport"] = "sse"
                server["url"] = config["url"]

            if "env" in config:
                server["env"] = config["env"]

            hermes_servers[name] = server

        # Save as JSON for manual integration into config.yaml
        dest = self.output_dir / "archive" / "mcp_servers.json"
        if self.execute:
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(json.dumps(hermes_servers, indent=2))

        self.report.record("mcp-servers", str(settings_path), str(dest),
                           "migrated",
                           reason=f"{len(hermes_servers)} MCP servers exported",
                           servers=list(hermes_servers.keys()))

    def _migrate_custom_commands(self):
        """Migrate custom slash commands → Hermes skills."""
        commands_dir = self.source / "commands"
        if not commands_dir.is_dir():
            self.report.record("custom-commands", str(commands_dir), "", "skipped",
                               reason="No commands directory found")
            return

        imported = 0
        skills_dest = self.target / "skills" / "claude-imports"

        for fpath in sorted(commands_dir.glob("*.md")):
            skill_name = fpath.stem.lower().replace("_", "-")
            skill_dir = skills_dest / skill_name
            skill_md = skill_dir / "SKILL.md"

            content = fpath.read_text()

            # Create minimal SKILL.md from command
            skill_content = f"""---
name: {skill_name}
description: Imported from Claude Code command /{fpath.stem}
version: 1.0.0
author: imported
license: MIT
metadata:
  hermes:
    tags: [Imported, Claude Code]
---

# {fpath.stem}

Imported from Claude Code custom command.

## Procedure

{content}
"""
            if self.execute:
                skill_dir.mkdir(parents=True, exist_ok=True)
                skill_md.write_text(skill_content)

            self.report.record("custom-commands", str(fpath), str(skill_md),
                               "migrated", reason=f"Converted to skill: {skill_name}")
            imported += 1

        if imported == 0:
            self.report.record("custom-commands", str(commands_dir), "", "skipped",
                               reason="No command files found")

    def _migrate_api_keys(self):
        """Migrate API keys from settings.json → .env."""
        if not self.migrate_secrets:
            self.report.record("api-keys", "", "", "skipped",
                               reason="Secrets migration disabled (use --migrate-secrets)")
            return

        settings_path = self.source / "settings.json"
        if not settings_path.exists():
            self.report.record("api-keys", str(settings_path), "", "skipped",
                               reason="No settings.json found")
            return

        try:
            settings = json.loads(settings_path.read_text())
        except json.JSONDecodeError:
            return

        env_vars = {}
        # Check for API keys in various locations
        for key in SUPPORTED_SECRET_KEYS:
            value = settings.get(key) or os.environ.get(key)
            if value and value.strip():
                env_vars[key] = value.strip()

        if not env_vars:
            self.report.record("api-keys", str(settings_path), "", "skipped",
                               reason="No supported API keys found")
            return

        env_dest = self.target / ".env"
        if self.execute:
            added = append_env_vars(env_dest, env_vars)
        else:
            added = list(env_vars.keys())

        self.report.record("api-keys", str(settings_path), str(env_dest),
                           "migrated",
                           reason=f"{len(added)} API keys {'would be ' if not self.execute else ''}added",
                           keys=[k for k in added])

    def _migrate_keybindings(self):
        """Archive keybindings (different system, can't auto-migrate)."""
        kb_path = self.source / "keybindings.json"
        if not kb_path.exists():
            self.report.record("keybindings", str(kb_path), "", "skipped",
                               reason="No keybindings.json found")
            return

        dest = self.output_dir / "archive" / "keybindings.json"
        if self.execute:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(kb_path, dest)

        self.report.record("keybindings", str(kb_path), str(dest),
                           "archived",
                           reason="Keybinding systems differ; saved for manual review")

    # ── Helpers ──

    def _split_sections(self, text: str) -> list:
        """Split markdown by ## headers."""
        sections = []
        current = []
        for line in text.splitlines():
            if line.startswith("## ") and current:
                sections.append("\n".join(current))
                current = [line]
            else:
                current.append(line)
        if current:
            sections.append("\n".join(current))
        return [s.strip() for s in sections if s.strip() and len(s.strip()) > 20]

    def _write_summary_md(self):
        """Write human-readable summary."""
        summary = self.report.summary
        lines = [
            "# Claude Code → Hermes Migration Report",
            f"- Timestamp: {self.report.timestamp}",
            f"- Mode: {self.report.mode}",
            f"- Source: `{self.report.source_root}`",
            f"- Target: `{self.report.target_root}`",
            "",
            "## Summary",
        ]
        for key, count in summary.items():
            lines.append(f"- {key}: {count}")

        lines.append("")
        lines.append("## Details")
        for item in self.report.items:
            emoji = {"migrated": "+", "skipped": "-", "archived": "~",
                     "conflict": "!", "error": "X"}.get(item.status, "?")
            lines.append(f"  [{emoji}] {item.kind}: {item.reason}")

        path = self.output_dir / "summary.md"
        path.write_text("\n".join(lines) + "\n")


# ── CLI ──

def parse_args():
    parser = argparse.ArgumentParser(
        description="Migrate Claude Code settings to Hermes Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Presets:
  user-data   Rules, memories, MCP servers, custom commands (no secrets)
  full        Everything including API keys (requires --migrate-secrets)

Examples:
  %(prog)s                                    # Dry run
  %(prog)s --execute --preset user-data       # Migrate user data
  %(prog)s --execute --include rules,memory   # Selective migration
""",
    )
    parser.add_argument("--source", type=Path,
                        default=Path.home() / ".claude",
                        help="Claude Code config directory (default: ~/.claude)")
    parser.add_argument("--target", type=Path,
                        default=Path.home() / ".hermes",
                        help="Hermes config directory (default: ~/.hermes)")
    parser.add_argument("--execute", action="store_true",
                        help="Apply changes (default: dry-run only)")
    parser.add_argument("--migrate-secrets", action="store_true",
                        help="Include API keys in migration")
    parser.add_argument("--preset", choices=["user-data", "full"],
                        help="Migration preset")
    parser.add_argument("--include", type=str,
                        help="Comma-separated category IDs to include")
    parser.add_argument("--exclude", type=str,
                        help="Comma-separated category IDs to exclude")
    parser.add_argument("--output-dir", type=Path,
                        help="Report output directory")
    return parser.parse_args()


def main():
    args = parse_args()

    include = set(args.include.split(",")) if args.include else None
    exclude = set(args.exclude.split(",")) if args.exclude else None

    if not args.source.is_dir():
        print(f"Error: Claude Code directory not found: {args.source}")
        sys.exit(1)

    migrator = ClaudeCodeMigrator(
        source=args.source,
        target=args.target,
        execute=args.execute,
        migrate_secrets=args.migrate_secrets,
        preset=args.preset,
        include=include,
        exclude=exclude,
        output_dir=args.output_dir,
    )

    print(f"{'=' * 60}")
    print(f"Claude Code → Hermes Migration")
    print(f"Mode: {'EXECUTE' if args.execute else 'DRY-RUN (preview only)'}")
    print(f"Source: {args.source}")
    print(f"Target: {args.target}")
    print(f"Categories: {', '.join(sorted(migrator.selected))}")
    print(f"{'=' * 60}")
    print()

    report = migrator.migrate()

    # Print summary
    summary = report["summary"]
    print()
    print(f"{'=' * 60}")
    print("Results:")
    for key, count in summary.items():
        if count > 0:
            marker = {"migrated": "+", "skipped": "-", "archived": "~",
                       "conflict": "!", "error": "X"}.get(key, " ")
            print(f"  [{marker}] {key}: {count}")
    print(f"{'=' * 60}")

    if not args.execute:
        print()
        print("This was a dry run. To apply changes, add --execute")
        print(f"  python3 {sys.argv[0]} --execute --preset user-data")

    # Output JSON report to stdout for programmatic use
    print()
    print(json.dumps(report, indent=2, default=str))


if __name__ == "__main__":
    main()
