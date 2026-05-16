"""Typed Symphony configuration and validation."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from symphony.errors import SymphonyError


@dataclass(frozen=True, slots=True)
class PollingConfig:
    interval_ms: int = 30000


@dataclass(frozen=True, slots=True)
class AgentConfig:
    max_concurrent_agents: int = 10
    max_turns: int = 20
    runner: str = "hermes"


@dataclass(frozen=True, slots=True)
class HermesConfig:
    mode: str = "subprocess"
    command: str | None = None
    timeout_seconds: int = 3600


@dataclass(frozen=True, slots=True)
class TrackerConfig:
    api_key: str | None = field(default=None, repr=False)
    project_slug: str = "KATO"
    active_states: tuple[str, ...] = ("Todo", "In Progress")
    first: int = 50

    @property
    def redacted_api_key(self) -> str | None:
        """Return a display-safe API key value."""

        if self.api_key:
            return "[REDACTED]"
        return None


@dataclass(frozen=True, slots=True)
class WorkspaceConfig:
    root: Path


@dataclass(frozen=True, slots=True)
class CodexConfig:
    command: str | None = None


@dataclass(frozen=True, slots=True)
class SymphonyConfig:
    polling: PollingConfig
    agent: AgentConfig
    hermes: HermesConfig
    tracker: TrackerConfig
    workspace: WorkspaceConfig
    codex: CodexConfig


def load_config(
    raw_config: Mapping[str, Any] | None,
    *,
    workflow_dir: str | Path,
    env: Mapping[str, str] | None = None,
) -> SymphonyConfig:
    """Load typed Symphony config from workflow front matter.

    Defaults are applied here and cross-section runner requirements are validated.
    ``tracker.api_key`` expands environment references only for full ``$VAR`` values.
    """

    raw = raw_config or {}
    workflow_root = Path(workflow_dir)
    environ = os.environ if env is None else env

    polling_raw = _section(raw, "polling")
    agent_raw = _section(raw, "agent")
    hermes_raw = _section(raw, "hermes")
    tracker_raw = _section(raw, "tracker")
    workspace_raw = _section(raw, "workspace")
    codex_raw = _section(raw, "codex")

    polling = PollingConfig(
        interval_ms=_bounded_int_value(
            polling_raw.get("interval_ms", 30000),
            "polling.interval_ms",
            minimum=1,
            maximum=3_600_000,
        )
    )
    agent = AgentConfig(
        max_concurrent_agents=_bounded_int_value(
            agent_raw.get("max_concurrent_agents", 10),
            "agent.max_concurrent_agents",
            minimum=1,
            maximum=100,
        ),
        max_turns=_bounded_int_value(agent_raw.get("max_turns", 20), "agent.max_turns", minimum=1, maximum=1_000),
        runner=_string_value(agent_raw.get("runner", "hermes"), "agent.runner"),
    )
    hermes = HermesConfig(
        mode=_string_value(hermes_raw.get("mode", "subprocess"), "hermes.mode"),
        command=_optional_string_value(hermes_raw.get("command"), "hermes.command"),
        timeout_seconds=_bounded_int_value(
            hermes_raw.get("timeout_seconds", 3600),
            "hermes.timeout_seconds",
            minimum=1,
            maximum=86_400,
        ),
    )
    tracker = TrackerConfig(
        api_key=_resolve_tracker_api_key(tracker_raw.get("api_key"), environ),
        project_slug=_string_value(tracker_raw.get("project_slug", "KATO"), "tracker.project_slug"),
        active_states=tuple(
            _string_list_value(
                tracker_raw.get("active_states", ["Todo", "In Progress"]),
                "tracker.active_states",
            )
        ),
        first=_bounded_int_value(tracker_raw.get("first", 50), "tracker.first", minimum=1, maximum=250),
    )
    workspace = WorkspaceConfig(root=_resolve_workspace_root(workspace_raw.get("root"), workflow_root))
    codex = CodexConfig(command=_optional_string_value(codex_raw.get("command"), "codex.command"))

    _validate_runner(agent, codex)

    return SymphonyConfig(
        polling=polling,
        agent=agent,
        hermes=hermes,
        tracker=tracker,
        workspace=workspace,
        codex=codex,
    )


def _section(raw: Mapping[str, Any], name: str) -> Mapping[str, Any]:
    value = raw.get(name, {})
    if isinstance(value, Mapping):
        return value
    raise SymphonyError(
        "invalid_config_section",
        f"Symphony config section must be a mapping: {name}",
    )


def _int_value(value: Any, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise SymphonyError(
            "invalid_config_value",
            f"Symphony config value must be an integer: {field_name}",
        )
    return value


def _bounded_int_value(value: Any, field_name: str, *, minimum: int, maximum: int) -> int:
    parsed = _int_value(value, field_name)
    if parsed < minimum or parsed > maximum:
        raise SymphonyError(
            "invalid_config_value",
            f"Symphony config value must be between {minimum} and {maximum}: {field_name}",
        )
    return parsed


def _string_value(value: Any, field_name: str) -> str:
    if not isinstance(value, str):
        raise SymphonyError(
            "invalid_config_value",
            f"Symphony config value must be a string: {field_name}",
        )
    return value


def _optional_string_value(value: Any, field_name: str) -> str | None:
    if value is None:
        return None
    return _string_value(value, field_name)


def _string_list_value(value: Any, field_name: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise SymphonyError(
            "invalid_config_value",
            f"Symphony config value must be a list of strings: {field_name}",
        )
    return value


def _resolve_tracker_api_key(value: Any, env: Mapping[str, str]) -> str | None:
    if value is None:
        return None
    if isinstance(value, str) and value.startswith("$") and len(value) > 1:
        variable_name = value[1:]
        resolved = env.get(variable_name)
        if not resolved:
            raise SymphonyError(
                "missing_tracker_api_key",
                f"Tracker API key environment variable is not set: {variable_name}",
            )
        return resolved
    if not isinstance(value, str):
        raise SymphonyError(
            "invalid_config_value",
            "Symphony config value must be a string: tracker.api_key",
        )
    return value


def _resolve_workspace_root(value: Any, workflow_dir: Path) -> Path:
    if value is None:
        return workflow_dir
    if not isinstance(value, (str, Path)):
        raise SymphonyError(
            "invalid_config_value",
            "Symphony config value must be a string path: workspace.root",
        )
    root = Path(value)
    if root.is_absolute():
        return root
    return workflow_dir / root


def _validate_runner(agent: AgentConfig, codex: CodexConfig) -> None:
    if agent.runner not in {"hermes", "codex"}:
        raise SymphonyError(
            "unsupported_agent_runner",
            f"Unsupported Symphony agent runner: {agent.runner}",
        )

    if agent.runner == "codex" and not _non_empty_string(codex.command):
        raise SymphonyError(
            "missing_codex_command",
            "agent.runner 'codex' requires a non-empty codex.command.",
        )


def _non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())
