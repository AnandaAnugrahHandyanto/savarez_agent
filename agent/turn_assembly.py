"""Turn assembly scaffolds for API-call-time turn preparation only.

Rules:
- no session persistence
- no tool execution
- no policy decisions beyond recording hints/warnings
- compatibility-first extraction from run_agent.py
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from collections import Counter

from agent.memory_manager import build_memory_context_block


@dataclass
class SideChannelContext:
    memory_blocks: list[str] = field(default_factory=list)
    skill_blocks: list[str] = field(default_factory=list)
    reference_blocks: list[str] = field(default_factory=list)
    recall_blocks: list[str] = field(default_factory=list)
    delegation_blocks: list[str] = field(default_factory=list)
    platform_blocks: list[str] = field(default_factory=list)
    extra_blocks: list[str] = field(default_factory=list)

    def flatten(self) -> list[str]:
        return [
            *self.memory_blocks,
            *self.skill_blocks,
            *self.reference_blocks,
            *self.recall_blocks,
            *self.delegation_blocks,
            *self.platform_blocks,
            *self.extra_blocks,
        ]


@dataclass
class TurnAssembly:
    original_user_message: str
    assembled_user_message: str
    system_blocks: list[str] = field(default_factory=list)
    side_channel: SideChannelContext = field(default_factory=SideChannelContext)
    warnings: list[str] = field(default_factory=list)
    references_expanded: bool = False
    references_blocked: bool = False
    injected_token_estimate: int = 0
    tool_visibility_hints: dict[str, Any] = field(default_factory=dict)
    lineage: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


def build_side_channel_context(
    memory_context: str = "",
    plugin_user_context: str = "",
    *,
    platform: str | None = None,
) -> SideChannelContext:
    side_channel = SideChannelContext()

    memory_block = build_memory_context_block(memory_context)
    if memory_block:
        side_channel.memory_blocks.append(memory_block)

    if plugin_user_context and plugin_user_context.strip():
        side_channel.extra_blocks.append(plugin_user_context)

    if platform:
        side_channel.platform_blocks = list(side_channel.platform_blocks)

    return side_channel


def assemble_turn_context(
    user_message: str,
    memory_context: str = "",
    plugin_user_context: str = "",
    *,
    reference_result: Any | None = None,
    platform: str | None = None,
) -> TurnAssembly:
    side_channel = build_side_channel_context(
        memory_context,
        plugin_user_context,
        platform=platform,
    )

    base_message = user_message
    references_expanded = False
    references_blocked = False
    warnings: list[str] = []
    metadata: dict[str, Any] = {}

    if reference_result is not None:
        ref_message = getattr(reference_result, "message", None)
        if isinstance(ref_message, str):
            base_message = ref_message
        references_expanded = bool(getattr(reference_result, "expanded", False))
        references_blocked = bool(getattr(reference_result, "blocked", False))
        ref_warnings = getattr(reference_result, "warnings", None)
        if isinstance(ref_warnings, list):
            warnings.extend(str(w) for w in ref_warnings)
        injected_tokens = getattr(reference_result, "injected_tokens", None)
        if injected_tokens is not None:
            metadata["reference_injected_tokens"] = injected_tokens
        references = getattr(reference_result, "references", None)
        if isinstance(references, list):
            kind_counts = Counter(
                str(getattr(reference, "kind", "unknown") or "unknown")
                for reference in references
            )
            metadata["reference_summary"] = {
                "count": len(references),
                "kinds": dict(sorted(kind_counts.items())),
            }

    injections = side_channel.flatten()
    assembled_user_message = base_message
    if injections:
        assembled_user_message = base_message + "\n\n" + "\n\n".join(injections)

    lineage: dict[str, Any] = {"platform": platform} if platform else {}
    if reference_result is not None:
        lineage["reference_preprocessed"] = True
        if references_expanded:
            lineage["references_expanded"] = True
        if references_blocked:
            lineage["references_blocked"] = True

    return TurnAssembly(
        original_user_message=user_message,
        assembled_user_message=assembled_user_message,
        side_channel=side_channel,
        warnings=warnings,
        references_expanded=references_expanded,
        references_blocked=references_blocked,
        metadata=metadata,
        lineage=lineage,
    )


def apply_turn_assembly_to_user_message(message: dict, assembly: TurnAssembly) -> dict:
    api_message = message.copy()
    if api_message.get("role") == "user" and isinstance(api_message.get("content"), str):
        api_message["content"] = assembly.assembled_user_message
    return api_message


def compose_effective_system_prompt(base_system: str, ephemeral_system_prompt: str | None) -> str:
    effective_system = base_system or ""
    if ephemeral_system_prompt:
        effective_system = (effective_system + "\n\n" + ephemeral_system_prompt).strip()
    return effective_system


def inject_prefill_messages(
    api_messages: list[dict],
    prefill_messages: list[dict],
    effective_system: str,
) -> list[dict]:
    injected_messages = list(api_messages)
    sys_offset = 1 if effective_system else 0
    for idx, prefill_message in enumerate(prefill_messages or []):
        injected_messages.insert(sys_offset + idx, prefill_message.copy())
    return injected_messages


__all__ = [
    "SideChannelContext",
    "TurnAssembly",
    "apply_turn_assembly_to_user_message",
    "assemble_turn_context",
    "build_side_channel_context",
    "compose_effective_system_prompt",
    "inject_prefill_messages",
]
