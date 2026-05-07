"""Project role-document router plugin.

Chooses one or more role documents for the current turn by delegating the
selection to a child agent, then injects the selected document content into the
current turn's user message as ephemeral context.
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_DEFAULT_ROLE_DOC_DIR = "role-docs"
_DEFAULT_ROLE_INDEX_FILE = "index.json"
_DEFAULT_MAX_DOCS = 24
_DEFAULT_MAX_SELECTED = 2
_DEFAULT_PREVIEW_CHARS = 320
_DEFAULT_DOC_CHARS = 4000
_DEFAULT_HISTORY_MESSAGES = 6


@dataclass
class RoleDoc:
    path: str
    title: str
    summary: str
    content: str = ""


def _safe_int(raw: str | None, default: int) -> int:
    try:
        if raw is None:
            return default
        value = int(str(raw).strip())
        return value if value > 0 else default
    except Exception:
        return default


def _truncate(text: str, limit: int) -> str:
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 3)].rstrip() + "..."


def _current_cwd() -> Path:
    raw = os.getenv("TERMINAL_CWD") or os.getcwd()
    return Path(raw).expanduser().resolve()


def _role_doc_dir() -> Path:
    raw = (os.getenv("ROLE_DOC_ROUTER_DIR") or _DEFAULT_ROLE_DOC_DIR).strip()
    base = Path(raw).expanduser()
    if base.is_absolute():
        return base.resolve()
    return (_current_cwd() / base).resolve()


def _role_doc_index_path(root: Path) -> Path:
    raw = (os.getenv("ROLE_DOC_ROUTER_INDEX_FILE") or _DEFAULT_ROLE_INDEX_FILE).strip()
    base = Path(raw).expanduser()
    if base.is_absolute():
        return base.resolve()
    return (root / base).resolve()


def _strip_frontmatter(text: str) -> str:
    if text.startswith("---\n"):
        end = text.find("\n---\n", 4)
        if end != -1:
            return text[end + 5 :].lstrip("\n")
    return text


def _infer_title(path: Path, content: str) -> str:
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            return stripped.lstrip("#").strip() or path.stem
    return path.stem.replace("_", " ").replace("-", " ").strip() or path.stem


def _load_role_doc_index(root: Path) -> list[RoleDoc]:
    if not root.exists() or not root.is_dir():
        return []

    max_docs = _safe_int(os.getenv("ROLE_DOC_ROUTER_MAX_DOCS"), _DEFAULT_MAX_DOCS)
    preview_chars = _safe_int(os.getenv("ROLE_DOC_ROUTER_PREVIEW_CHARS"), _DEFAULT_PREVIEW_CHARS)
    index_path = _role_doc_index_path(root)
    if not index_path.exists() or not index_path.is_file():
        logger.warning("role-doc-router index file not found: %s", index_path)
        return []

    try:
        payload = json.loads(index_path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning("role-doc-router failed to read index %s: %s", index_path, exc)
        return []

    entries = payload.get("roles", []) if isinstance(payload, dict) else []
    if not isinstance(entries, list):
        logger.warning("role-doc-router index %s has invalid 'roles' section", index_path)
        return []

    docs: list[RoleDoc] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        rel = str(entry.get("path", "")).strip()
        if not rel:
            continue
        title = str(entry.get("title", "")).strip() or Path(rel).stem
        summary = str(entry.get("summary") or entry.get("description") or "").strip()
        docs.append(
            RoleDoc(
                path=rel,
                title=title,
                summary=_truncate(summary.replace("\n", " "), preview_chars),
            )
        )
        if len(docs) >= max_docs:
            break

    return docs


def _load_selected_role_doc(root: Path, doc: RoleDoc) -> RoleDoc | None:
    doc_chars = _safe_int(os.getenv("ROLE_DOC_ROUTER_DOC_CHARS"), _DEFAULT_DOC_CHARS)
    doc_path = (root / doc.path).resolve()
    root_resolved = root.resolve()
    if not doc_path.is_relative_to(root_resolved):
        logger.warning("role-doc-router blocked path outside role-docs root: %s", doc_path)
        return None
    if not doc_path.exists() or not doc_path.is_file():
        logger.warning("role-doc-router selected missing role doc: %s", doc_path)
        return None
    try:
        raw = doc_path.read_text(encoding="utf-8")
    except Exception as exc:
        logger.warning("role-doc-router failed reading selected role doc %s: %s", doc_path, exc)
        return None

    cleaned = _strip_frontmatter(raw).strip()
    if not cleaned:
        return None

    return RoleDoc(
        path=doc.path,
        title=doc.title or _infer_title(doc_path, cleaned),
        summary=doc.summary,
        content=_truncate(cleaned, doc_chars),
    )


def _stringify_message_content(content: Any) -> str:
    if isinstance(content, list):
        text_parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                text_parts.append(str(block.get("text", "")))
        return " ".join(text_parts)
    return str(content or "")


def _recent_history_snippet(conversation_history: list[dict[str, Any]]) -> str:
    if not isinstance(conversation_history, list):
        return ""
    max_messages = _safe_int(
        os.getenv("ROLE_DOC_ROUTER_HISTORY_MESSAGES"),
        _DEFAULT_HISTORY_MESSAGES,
    )
    include_assistant = str(
        os.getenv("ROLE_DOC_ROUTER_INCLUDE_ASSISTANT_HISTORY", "")
    ).strip().lower() in {"1", "true", "yes", "on"}

    filtered = []
    for message in conversation_history:
        if not isinstance(message, dict):
            continue
        role = str(message.get("role", "unknown"))
        if role == "user" or (include_assistant and role == "assistant"):
            filtered.append(message)

    recent = filtered[-max_messages:]
    parts: list[str] = []
    for message in recent:
        role = str(message.get("role", "unknown"))
        content = _stringify_message_content(message.get("content", ""))
        parts.append(f"- {role}: {_truncate(str(content), 240)}")
    return "\n".join(parts)


def _router_goal(max_selected: int) -> str:
    return (
        "你是角色文档路由器。你的唯一任务是从候选角色文档中，选出本轮最应该生效的文档。"
        f"最多选择 {max_selected} 份；如果都不合适，可以选择 0 份。"
        "只输出一个 JSON 对象，不要输出解释、代码块或额外文本。"
    )


def _router_context(user_message: str, conversation_history: list[dict[str, Any]], docs: list[RoleDoc], max_selected: int) -> str:
    catalog_lines = []
    for doc in docs:
        catalog_lines.append(
            f"- path: {doc.path}\n"
            f"  title: {doc.title}\n"
            f"  description: {doc.summary}"
        )
    history_block = _recent_history_snippet(conversation_history)
    return (
        "当前用户问题：\n"
        f"{user_message.strip()}\n\n"
        "最近对话：\n"
        f"{history_block or '(none)'}\n\n"
        f"当前可用角色数：{len(docs)}\n\n"
        "候选角色索引：\n"
        f"{os.linesep.join(catalog_lines)}\n\n"
        "输出要求：\n"
        "1. 只能返回 JSON。\n"
        "2. JSON 结构必须是："
        '{"selected":["exact/path.md"],"reason":"<=80字"}'
        "\n3. selected 中的路径必须逐字匹配候选 path。"
        f"\n4. selected 最多 {max_selected} 项。"
    )


def _extract_summary(tool_result: Any) -> str:
    if not isinstance(tool_result, dict):
        return ""
    results = tool_result.get("results")
    if not isinstance(results, list) or not results:
        return ""
    first = results[0]
    if not isinstance(first, dict):
        return ""
    summary = first.get("summary")
    return summary.strip() if isinstance(summary, str) else ""


def _parse_router_json(text: str) -> dict[str, Any] | None:
    text = (text or "").strip()
    if not text:
        return None
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else None
    except Exception:
        pass

    match = re.search(r"\{[\s\S]*\}", text)
    if not match:
        return None
    try:
        parsed = json.loads(match.group(0))
        return parsed if isinstance(parsed, dict) else None
    except Exception:
        return None


def _select_docs_from_router(summary: str, docs: list[RoleDoc]) -> tuple[list[RoleDoc], str]:
    parsed = _parse_router_json(summary)
    if not parsed:
        return [], ""

    wanted = parsed.get("selected")
    if not isinstance(wanted, list):
        wanted = []
    wanted_paths = {
        str(item).strip()
        for item in wanted
        if isinstance(item, str) and str(item).strip()
    }
    selected = [doc for doc in docs if doc.path in wanted_paths]
    reason = parsed.get("reason", "")
    return selected, reason.strip() if isinstance(reason, str) else ""


def _render_injected_context(selected_docs: list[RoleDoc], reason: str, docs_root: Path) -> str:
    if not selected_docs:
        return ""

    lines = [
        "Project-selected role documents for this turn.",
        "These documents were chosen by a routing subagent based on the current user request and recent conversation.",
        "Treat them as project guidance for how to answer this turn unless they conflict with higher-priority system instructions.",
    ]
    if reason:
        lines.append(f"Router reason: {reason}")
    lines.append(f"Role doc root: {docs_root}")

    for doc in selected_docs:
        lines.extend(
            [
                "",
                f"[role-doc: {doc.path}]",
                doc.content,
            ]
        )

    return "\n".join(lines).strip()


def _is_top_level_cli_session(ctx: Any, session_id: str) -> bool:
    cli = getattr(getattr(ctx, "_manager", None), "_cli_ref", None)
    active_agent = getattr(cli, "agent", None) if cli else None
    active_session_id = getattr(active_agent, "session_id", None)
    if not active_session_id:
        return True
    return session_id == active_session_id


def _should_run_for_agent(ctx: Any, session_id: str, agent: Any) -> bool:
    if agent is not None and getattr(agent, "_delegate_depth", 0) > 0:
        return False
    return _is_top_level_cli_session(ctx, session_id)


def register(ctx):
    def inject_role_doc_context(
        session_id: str,
        user_message: str,
        conversation_history: list[dict[str, Any]] | None = None,
        agent: Any = None,
        **kwargs: Any,
    ) -> dict[str, str] | None:
        if not _should_run_for_agent(ctx, session_id, agent):
            return None
        if agent is None:
            return None

        docs_root = _role_doc_dir()
        docs = _load_role_doc_index(docs_root)
        if not docs:
            logger.debug("role-doc-router found no role-doc index entries under %s", docs_root)
            return None

        max_selected = _safe_int(
            os.getenv("ROLE_DOC_ROUTER_MAX_SELECTED"),
            _DEFAULT_MAX_SELECTED,
        )

        try:
            raw_result = ctx.dispatch_tool(
                "delegate_task",
                {
                    "goal": _router_goal(max_selected),
                    "context": _router_context(
                        user_message=user_message,
                        conversation_history=conversation_history or [],
                        docs=docs,
                        max_selected=max_selected,
                    ),
                    "role": "leaf",
                    "max_iterations": 2,
                },
                parent_agent=agent,
            )
            tool_result = json.loads(raw_result)
        except Exception as exc:
            logger.warning("role-doc-router failed for session %s: %s", session_id, exc)
            return None

        if isinstance(tool_result, dict) and tool_result.get("error"):
            logger.warning(
                "role-doc-router delegate_task error for session %s: %s",
                session_id,
                tool_result["error"],
            )
            return None

        summary = _extract_summary(tool_result)
        selected_docs, reason = _select_docs_from_router(summary, docs)
        if not selected_docs:
            return None

        resolved_docs = [
            loaded_doc
            for loaded_doc in (_load_selected_role_doc(docs_root, doc) for doc in selected_docs)
            if loaded_doc is not None
        ]
        if not resolved_docs:
            return None

        injected = _render_injected_context(resolved_docs, reason, docs_root)
        if not injected:
            return None
        return {"context": injected}

    ctx.register_hook("pre_llm_call", inject_role_doc_context)