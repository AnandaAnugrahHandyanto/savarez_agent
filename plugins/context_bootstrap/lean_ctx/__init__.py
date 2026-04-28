"""lean-ctx context bootstrap provider.

This provider talks to lean-ctx through its MCP stdio interface so Hermes can
reuse the same ctx_* workflow that worker agents use. Lean-ctx owns ephemeral
context discovery here; configured Hermes memory and compression providers keep
their own responsibilities.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, Callable

from tools.lean_ctx_client import (
    LeanCtxClient,
    LeanCtxRuntimeConfig,
    load_config_from_mapping,
)

logger = logging.getLogger(__name__)

_CODE_TASK_RE = re.compile(
    r"\b("
    r"code|repo|file|class|function|symbol|callers?|implementation|implement|"
    r"plugin|test|tests|pytest|fix|debug|review|refactor|build|compile|"
    r"trace|inspect|setup|config|configuration|AGENTS\.md|README|CLAUDE\.md"
    r")\b",
    re.IGNORECASE,
)
_SYMBOL_RE = re.compile(
    r"(?:`([A-Za-z_][A-Za-z0-9_]{2,80})(?:\(\))?`|\b(?:class|def|function|method)\s+([A-Za-z_][A-Za-z0-9_]{2,80}))"
)


LeanCtxConfig = LeanCtxRuntimeConfig


class LeanCtxBootstrapProvider:
    name = "lean_ctx"

    def __init__(
        self,
        config: LeanCtxConfig,
        *,
        default_workspace_root: Path | None = None,
        call_tool: Callable[[str, dict[str, Any], Path, float], str] | None = None,
    ):
        self.config = config
        self.default_workspace_root = default_workspace_root
        self._call_tool = call_tool
        self._bootstrapped_sessions: dict[str, None] = {}

    def is_available(self) -> bool:
        return LeanCtxClient(self.config).available(require_mcp=True)

    def context_for_turn(
        self,
        *,
        session_id: str,
        user_message: str,
        is_first_turn: bool,
        workspace_root: Path,
        conversation_history: list[dict[str, Any]] | None = None,
    ) -> str:
        if self.config.first_turn_only and not is_first_turn:
            return ""
        if session_id in self._bootstrapped_sessions:
            return ""
        task = _clip_task(user_message, self.config.max_task_chars)
        if self.config.code_task_only and not _looks_like_code_task(task):
            return ""

        root = _resolve_root(workspace_root, self.default_workspace_root)
        context = self._build_packet(
            task=task,
            root=root,
            max_chars=self.config.max_chars,
            include_symbols=True,
            header="LEAN-CTX BOOTSTRAP CONTEXT",
        )
        if context:
            self._bootstrapped_sessions[session_id] = None
            if len(self._bootstrapped_sessions) > self.config.max_sessions:
                self._bootstrapped_sessions.pop(next(iter(self._bootstrapped_sessions)), None)
        return context

    def context_for_delegation(
        self,
        *,
        goal: str,
        context: str,
        workspace_root: Path,
    ) -> str:
        task = _clip_task(
            "\n\n".join(part for part in (goal, context) if part),
            self.config.max_task_chars,
        )
        if self.config.code_task_only and not _looks_like_code_task(task):
            return ""

        root = _resolve_root(workspace_root, self.default_workspace_root)
        return self._build_packet(
            task=task,
            root=root,
            max_chars=self.config.delegation_max_chars,
            include_symbols=True,
            header="LEAN-CTX DELEGATION CONTEXT",
        )

    def _build_packet(
        self,
        *,
        task: str,
        root: Path,
        max_chars: int,
        include_symbols: bool,
        header: str,
    ) -> str:
        calls: list[tuple[str, str, dict[str, Any]]] = []
        if self.config.include_session:
            calls.append(("ctx_session:load", "ctx_session", {"action": "load"}))
            calls.append(("ctx_session:task", "ctx_session", {"action": "task", "task": task}))
        if self.config.include_knowledge:
            calls.append(("ctx_knowledge:wakeup", "ctx_knowledge", {"action": "wakeup"}))
            calls.append(("ctx_knowledge:status", "ctx_knowledge", {"action": "status"}))
        if self.config.include_intent:
            calls.append(("ctx_intent", "ctx_intent", {"query": task, "path": str(root)}))
        if self.config.include_overview:
            calls.append(("ctx_overview", "ctx_overview", {"path": str(root), "task": task}))
        if self.config.include_preload:
            calls.append(("ctx_preload", "ctx_preload", {"path": str(root), "task": task}))
        if self.config.include_graph_status:
            calls.append(("ctx_graph:status", "ctx_graph", {"action": "status", "path": str(root)}))
        if self.config.include_handoff:
            calls.append(("ctx_handoff", "ctx_handoff", {"action": "list"}))

        if include_symbols and self.config.include_symbols:
            for symbol in _extract_symbols(task, self.config.max_symbols):
                calls.append((f"ctx_symbol:{symbol}", "ctx_symbol", {"name": symbol}))
                if self.config.include_callers:
                    calls.append((f"ctx_callers:{symbol}", "ctx_callers", {"symbol": symbol}))

        sections = self._safe_tools(calls, root)

        parts = [
            f"<{header.lower().replace(' ', '_')}>",
            header,
            "Use this as ephemeral lean-ctx context and verify files and symbols before acting.",
            f"workspace_root: {root}",
            f"task: {_clip(task, 700)}",
        ]
        budget_per_section = max(500, max_chars // max(1, len([s for s in sections if s[1]]) + 1))
        for name, content in sections:
            if not content:
                continue
            parts.append(f"\n## {name}\n{_clip(content, budget_per_section)}")
        parts.append(f"</{header.lower().replace(' ', '_')}>")
        return _clip("\n".join(parts), max_chars)

    def _safe_tools(
        self,
        calls: list[tuple[str, str, dict[str, Any]]],
        root: Path,
    ) -> list[tuple[str, str]]:
        if not calls:
            return []
        try:
            if self._call_tool is not None:
                return [
                    (label, self._call_tool(tool_name, args, root, self.config.timeout_seconds))
                    for label, tool_name, args in calls
                ]
            return LeanCtxClient(self.config, cwd=root).call_tools(
                calls,
                cwd=root,
                timeout=self.config.timeout_seconds,
            )
        except Exception as exc:
            logger.debug("lean-ctx bootstrap failed: %s", type(exc).__name__)
            return []

def create_provider(
    *,
    cfg: dict[str, Any],
    workspace_root: Path | None = None,
) -> LeanCtxBootstrapProvider:
    return LeanCtxBootstrapProvider(
        _load_config(cfg),
        default_workspace_root=workspace_root,
    )


def _load_config(cfg: dict[str, Any]) -> LeanCtxConfig:
    return load_config_from_mapping(cfg)


def _looks_like_code_task(message: str) -> bool:
    if not message:
        return False
    if _CODE_TASK_RE.search(message):
        return True
    return bool(re.search(r"(^|\s)(\.?/|~/)?[\w.-]+/[\w./-]+", message))


def _extract_symbols(message: str, limit: int) -> list[str]:
    seen: set[str] = set()
    symbols: list[str] = []
    for match in _SYMBOL_RE.finditer(message or ""):
        symbol = next((group for group in match.groups() if group), "")
        if not symbol or symbol in seen:
            continue
        seen.add(symbol)
        symbols.append(symbol)
        if len(symbols) >= limit:
            break
    return symbols


def _resolve_root(workspace_root: Path, fallback: Path | None) -> Path:
    root = workspace_root or fallback or Path.cwd()
    try:
        return root.expanduser().resolve()
    except Exception:
        return Path.cwd()


def _clip(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[: max(0, max_chars - 80)].rstrip() + "\n...[lean-ctx bootstrap truncated]"


def _clip_task(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[: max(0, max_chars - 80)].rstrip() + "\n...[lean-ctx task truncated]"
