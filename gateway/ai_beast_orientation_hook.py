"""Opt-in AI Beast orientation command hook.

This built-in hook is intentionally inert unless a caller supplies explicit
configuration with ``enabled`` and a safe local ``project_root``.  It only
handles read-only orientation commands and leaves Hermes-owned commands to the
normal gateway dispatch path.
"""

from __future__ import annotations

import importlib
import inspect
import sys
from pathlib import Path
from typing import Any, Callable, Mapping

HERMES_OWNED_COMMANDS = frozenset({"status", "sessions"})
FORBIDDEN_COMMANDS = frozenset(
    {
        "task",
        "steer",
        "pause",
        "resume",
        "bindtopic",
        "switch",
        "open",
        "newsession",
    }
)
ORIENTATION_COMMANDS = frozenset({"whereami", "projects"})


def _get_value(source: Any, key: str, default: Any = None) -> Any:
    if isinstance(source, Mapping):
        return source.get(key, default)
    return getattr(source, key, default)


def _normalise_command(event_type: str, context: Mapping[str, Any]) -> str:
    command = str(context.get("command") or "").strip().lower()
    if not command and event_type.startswith("command:"):
        command = event_type.split(":", 1)[1].strip().lower()
    return command.lstrip("/")


def _orientation_config(context: Mapping[str, Any]) -> Any:
    gateway_config = context.get("gateway_config")
    if gateway_config is None:
        return {}
    return _get_value(gateway_config, "ai_beast_orientation", {}) or {}


def _source_value(context: Mapping[str, Any], key: str) -> Any:
    source = context.get("source")
    if source is None:
        return None
    return _get_value(source, key)


def _inside_root(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root)
        return True
    except ValueError:
        return False


def _safe_project_root(project_root_value: Any) -> Path | None:
    if not project_root_value:
        return None
    project_root = Path(str(project_root_value)).expanduser().resolve()
    if not project_root.exists() or not project_root.is_dir():
        return None
    return project_root


def _registry_paths(config: Any, project_root: Path) -> tuple[Path, Path]:
    registry_root_value = _get_value(
        config,
        "registry_root",
        project_root / "docs" / "interaction-layer" / "registry",
    )
    registry_root = Path(str(registry_root_value)).expanduser()
    if not registry_root.is_absolute():
        registry_root = project_root / registry_root
    registry_root = registry_root.resolve()
    if not _inside_root(registry_root, project_root):
        raise ValueError("registry_root must stay inside project_root")
    workspaces_path = (registry_root / "workspaces.json").resolve()
    bindings_path = (registry_root / "bindings.json").resolve()
    for registry_file in (workspaces_path, bindings_path):
        if not _inside_root(registry_file, registry_root):
            raise ValueError("registry files must stay inside registry_root")
        if not registry_file.is_file():
            raise ValueError("registry files must be regular files")
    return workspaces_path, bindings_path


def _module_file_inside_root(module: Any, project_root: Path) -> bool:
    module_file = getattr(module, "__file__", None)
    return bool(module_file and _inside_root(Path(module_file), project_root))


def _import_ai_beast_modules(project_root: Path) -> tuple[Any, Any]:
    root_text = str(project_root)
    original_path = list(sys.path)
    original_modules = dict(sys.modules)
    module_names = (
        "ai_beast_registry",
        "ai_beast_registry.loader",
        "ai_beast_registry.telegram_adapter",
    )
    previous_modules = {name: sys.modules.get(name) for name in module_names}
    try:
        for name in module_names:
            sys.modules.pop(name, None)
        sys.path = [root_text, *(entry for entry in original_path if entry != root_text)]
        loader = importlib.import_module("ai_beast_registry.loader")
        telegram_adapter = importlib.import_module("ai_beast_registry.telegram_adapter")
        if not (
            _module_file_inside_root(loader, project_root)
            and _module_file_inside_root(telegram_adapter, project_root)
        ):
            raise ImportError("AI Beast adapter resolved outside project_root")
    finally:
        sys.path = original_path
        for name, module in list(sys.modules.items()):
            if name not in original_modules and _module_file_inside_root(module, project_root):
                sys.modules.pop(name, None)
        for name in module_names:
            previous = previous_modules[name]
            if previous is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = previous
    return loader, telegram_adapter


def _lazy_orientation_adapter(config: Any, project_root: Path, context: Mapping[str, Any]) -> Callable[..., Any]:
    loader, telegram_adapter = _import_ai_beast_modules(project_root)
    workspaces_path, bindings_path = _registry_paths(config, project_root)
    registry = loader.load_registry(workspaces_path, bindings_path)

    def _adapter(*, command: str, project_root: Path, context: Mapping[str, Any]) -> str | None:
        del project_root
        return telegram_adapter.handle_telegram_orientation_command(
            f"/{command}",
            registry,
            chat_id=_source_value(context, "chat_id"),
            thread_id=_source_value(context, "thread_id"),
            bot_username=_get_value(config, "bot_username"),
        )

    return _adapter


async def _call_adapter(
    orientation_adapter: Callable[..., Any],
    *,
    command: str,
    project_root: Path,
    context: Mapping[str, Any],
) -> Any:
    result = orientation_adapter(
        command=command,
        project_root=project_root,
        context=context,
    )
    if inspect.isawaitable(result):
        result = await result
    return result


async def handle(
    event_type: str,
    context: Mapping[str, Any] | None,
    *,
    orientation_adapter: Callable[..., Any] | None = None,
    side_effects: Mapping[str, Callable[..., Any]] | None = None,
) -> dict[str, str] | None:
    """Handle a safe, explicitly enabled AI Beast orientation command.

    ``side_effects`` is accepted only as a test seam proving this hook does not
    invoke forbidden side-effect paths.  It is deliberately unused.
    """
    del side_effects

    if context is None:
        return None

    command = _normalise_command(event_type, context)
    if command in HERMES_OWNED_COMMANDS or command in FORBIDDEN_COMMANDS:
        return None
    if command not in ORIENTATION_COMMANDS:
        return None

    config = _orientation_config(context)
    if not bool(_get_value(config, "enabled", False)):
        return None

    project_root_value = _get_value(config, "project_root")
    if not project_root_value:
        return {
            "decision": "deny",
            "message": "AI Beast orientation root is not available.",
        }

    project_root = _safe_project_root(project_root_value)
    if project_root is None:
        return {
            "decision": "deny",
            "message": "AI Beast orientation root is not available.",
        }

    if orientation_adapter is None:
        try:
            orientation_adapter = _lazy_orientation_adapter(config, project_root, context)
        except (ImportError, ModuleNotFoundError):
            return {
                "decision": "deny",
                "message": "AI Beast orientation adapter is not configured.",
            }
        except Exception:
            return {
                "decision": "deny",
                "message": "AI Beast orientation adapter failed safely.",
            }

    try:
        message = await _call_adapter(
            orientation_adapter,
            command=command,
            project_root=project_root,
            context=context,
        )
    except Exception:
        return {
            "decision": "deny",
            "message": "AI Beast orientation adapter failed safely.",
        }
    return {
        "decision": "handled",
        "message": str(message),
    }
