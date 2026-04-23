from __future__ import annotations

import functools
import re
import shlex
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None  # type: ignore[assignment]


@dataclass(frozen=True)
class ExternalSlashCommand:
    name: str
    description: str
    kind: str  # 'prompt' | 'exec'
    source: str
    prompt_path: str | None = None
    binary: str | None = None
    argv: tuple[str, ...] = ()


_FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)
_OMX_SKILL_REF_RE = re.compile(r"\$([a-z0-9][a-z0-9-]*)")
_SPECKIT_REF_RE = re.compile(r"(?<![a-z0-9_-])/?(speckit(?:\.[a-z0-9_-]+)+)")


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _parse_frontmatter(text: str) -> dict:
    match = _FRONTMATTER_RE.match(text)
    if not match:
        return {}
    if yaml is None:
        return {}
    try:
        data = yaml.safe_load(match.group(1)) or {}
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _description_from_file(path: Path, fallback: str) -> str:
    try:
        meta = _parse_frontmatter(_read_text(path))
    except Exception:
        return fallback
    desc = str(meta.get("description") or "").strip()
    return desc or fallback


def _find_omx_root() -> Path | None:
    omx_path = shutil.which("omx")
    if not omx_path:
        return None
    resolved = Path(omx_path).expanduser().resolve()
    for parent in (resolved.parent, *resolved.parents):
        if (parent / "skills").is_dir():
            return parent
    return None


def _find_specify_root() -> Path | None:
    specify_path = shutil.which("specify")
    if not specify_path:
        return None
    resolved = Path(specify_path).expanduser().resolve()
    for parent in (resolved.parent, *resolved.parents):
        matches = sorted(parent.glob("lib/python*/site-packages/specify_cli"))
        if matches:
            return matches[0]
    return None


def _parse_omx_help_subcommands(help_text: str) -> list[str]:
    commands: list[str] = []
    seen: set[str] = set()
    for line in help_text.splitlines():
        match = re.match(r"^\s*omx(?:\s+([a-z][a-z0-9-]*))?(?:\s|$)", line)
        if not match:
            continue
        subcommand = match.group(1)
        if not subcommand or subcommand in seen:
            continue
        seen.add(subcommand)
        commands.append(subcommand)
    return commands


def _parse_specify_help_subcommands(help_text: str) -> list[str]:
    commands: list[str] = []
    seen: set[str] = set()
    for line in help_text.splitlines():
        match = re.match(r"^\s*[│|]\s*([a-z][a-z0-9-]*)\s{2,}", line)
        if not match:
            continue
        subcommand = match.group(1)
        if subcommand in seen:
            continue
        seen.add(subcommand)
        commands.append(subcommand)
    return commands


def _run_help(argv: list[str]) -> str:
    import subprocess

    try:
        proc = subprocess.run(argv, capture_output=True, text=True, timeout=15, check=False)
    except Exception:
        return ""
    return proc.stdout or proc.stderr or ""


def _specify_prompt_slug(path: Path, root: Path) -> str | None:
    rel = path.relative_to(root)
    parts = rel.parts
    stem = path.stem
    if parts[:2] == ("core_pack", "commands"):
        return stem
    if len(parts) >= 5 and parts[:3] == ("core_pack", "extensions", parts[2]) and parts[3] == "commands":
        tokens = stem.split(".")
        if tokens and tokens[0] == "speckit":
            tokens = tokens[1:]
        return "-".join(tokens)
    if len(parts) >= 6 and parts[:3] == ("core_pack", "presets", parts[2]) and parts[3] == "commands":
        preset = parts[2]
        tokens = stem.split(".")
        if tokens and tokens[0] == "speckit":
            tokens = tokens[1:]
        return "-".join([preset, *tokens])
    return None


def _iter_prompt_files(specify_root: Path) -> Iterable[tuple[str, Path]]:
    for path in sorted(specify_root.rglob("commands/*.md")):
        slug = _specify_prompt_slug(path, specify_root)
        if slug:
            yield slug, path


def _discover_omx_skill_commands(commands: dict[str, ExternalSlashCommand]) -> None:
    root = _find_omx_root()
    if not root:
        return
    skills_dir = root / "skills"
    for skill_file in sorted(skills_dir.glob("*/SKILL.md")):
        skill_name = skill_file.parent.name
        command_name = f"omx-{skill_name}"
        commands[command_name] = ExternalSlashCommand(
            name=command_name,
            description=_description_from_file(skill_file, f"OMX skill {skill_name}"),
            kind="prompt",
            source="omx-skill",
            prompt_path=str(skill_file),
        )


def _discover_omx_cli_commands(commands: dict[str, ExternalSlashCommand]) -> None:
    binary = shutil.which("omx")
    if not binary:
        return
    commands.setdefault(
        "omx-cli",
        ExternalSlashCommand(
            name="omx-cli",
            description="Run the OMX CLI",
            kind="exec",
            source="omx-cli",
            binary=binary,
        ),
    )
    for subcommand in _parse_omx_help_subcommands(_run_help([binary, "--help"])):
        name = f"omx-cli-{subcommand}"
        commands[name] = ExternalSlashCommand(
            name=name,
            description=f"Run `omx {subcommand}`",
            kind="exec",
            source="omx-cli",
            binary=binary,
            argv=(subcommand,),
        )


def _discover_specify_prompt_commands(commands: dict[str, ExternalSlashCommand]) -> None:
    root = _find_specify_root()
    if not root:
        return
    for slug, path in _iter_prompt_files(root):
        name = f"open-spec-{slug}"
        commands[name] = ExternalSlashCommand(
            name=name,
            description=_description_from_file(path, f"Open Spec command {slug}"),
            kind="prompt",
            source="open-spec-command",
            prompt_path=str(path),
        )


def _discover_specify_cli_commands(commands: dict[str, ExternalSlashCommand]) -> None:
    binary = shutil.which("specify")
    if not binary:
        return
    commands.setdefault(
        "open-spec-cli",
        ExternalSlashCommand(
            name="open-spec-cli",
            description="Run the Open Spec CLI",
            kind="exec",
            source="open-spec-cli",
            binary=binary,
        ),
    )
    for subcommand in _parse_specify_help_subcommands(_run_help([binary, "--help"])):
        name = f"open-spec-cli-{subcommand}"
        commands[name] = ExternalSlashCommand(
            name=name,
            description=f"Run `specify {subcommand}`",
            kind="exec",
            source="open-spec-cli",
            binary=binary,
            argv=(subcommand,),
        )


@functools.lru_cache(maxsize=1)
def _discover_external_slash_commands() -> dict[str, ExternalSlashCommand]:
    commands: dict[str, ExternalSlashCommand] = {}
    _discover_omx_skill_commands(commands)
    _discover_omx_cli_commands(commands)
    _discover_specify_prompt_commands(commands)
    _discover_specify_cli_commands(commands)
    return commands


def invalidate_external_slash_commands_cache() -> None:
    _discover_external_slash_commands.cache_clear()


def list_external_slash_commands() -> list[ExternalSlashCommand]:
    return [
        _discover_external_slash_commands()[key]
        for key in sorted(_discover_external_slash_commands())
    ]


def resolve_external_slash_command(command: str | None) -> ExternalSlashCommand | None:
    if not command:
        return None
    normalized = command.strip().lower().lstrip("/").replace("_", "-")
    if not normalized:
        return None
    return _discover_external_slash_commands().get(normalized)


def _rewrite_omx_skill_content(content: str) -> str:
    known_skill_refs = {
        cmd.name.removeprefix("omx-")
        for cmd in list_external_slash_commands()
        if cmd.source == "omx-skill"
    }

    def _replace(match: re.Match[str]) -> str:
        skill_name = match.group(1)
        if skill_name in known_skill_refs:
            return f"/omx-{skill_name}"
        return match.group(0)

    return _OMX_SKILL_REF_RE.sub(_replace, content)


def _rewrite_open_spec_content(content: str) -> str:
    alias_map: dict[str, str] = {}
    for cmd in list_external_slash_commands():
        if cmd.source != "open-spec-command":
            continue
        slug = cmd.name.removeprefix("open-spec-")
        if slug.startswith("lean-"):
            alias_map[f"speckit.{slug.removeprefix('lean-')}"] = cmd.name
        else:
            alias_map[f"speckit.{slug.replace('-', '.')}"] = cmd.name

    def _replace(match: re.Match[str]) -> str:
        key = match.group(1)
        mapped = alias_map.get(key)
        if not mapped:
            return match.group(0)
        return f"/{mapped}"

    return _SPECKIT_REF_RE.sub(_replace, content)


def build_external_prompt_message(command: ExternalSlashCommand, user_instruction: str, task_id: str | None = None) -> str | None:
    if command.kind != "prompt" or not command.prompt_path:
        return None

    from agent.skill_commands import _build_skill_message

    path = Path(command.prompt_path)
    try:
        raw = _read_text(path)
    except Exception:
        return None

    content = raw
    if command.source == "omx-skill":
        content = _rewrite_omx_skill_content(content)
    elif command.source == "open-spec-command":
        content = _rewrite_open_spec_content(content)
        content = content.replace("$ARGUMENTS", user_instruction)
        content = content.replace("{{ARGUMENTS}}", user_instruction)
        content = content.replace("{ARGS}", user_instruction)

    activation_note = (
        f'[SYSTEM: The user has invoked the external slash command "{command.name}", '
        "indicating they want you to follow its loaded instructions.]"
    )
    loaded = {
        "content": content,
        "raw_content": raw,
        "name": command.name,
    }
    return _build_skill_message(
        loaded,
        path.parent,
        activation_note,
        user_instruction=user_instruction,
        session_id=task_id,
    )


def build_external_exec_argv(command: ExternalSlashCommand, user_instruction: str) -> list[str] | None:
    if command.kind != "exec" or not command.binary:
        return None
    extra_args = shlex.split(user_instruction) if user_instruction else []
    return [command.binary, *command.argv, *extra_args]
