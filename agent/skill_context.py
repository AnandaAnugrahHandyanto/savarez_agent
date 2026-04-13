"""Shared skill-prompt block builder.

W3 / F-014 audit remediation. Previously two independent code paths spliced
skill content into LLM prompts — `agent/skill_commands._build_skill_message`
for the interactive CLI and `cron/scheduler._build_job_prompt` for cron. They
drifted: cron silently omitted setup hints and supporting-file pointers,
so a skill that degraded without setup would run silently-broken under
cron. This module is the single source of truth.

**Behaviour is byte-identical** to the pre-refactor call-site output. Flag
defaults preserve each caller's historical rendering; changing cron-side
defaults is a deliberate follow-up tracked in the plan.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Optional


def build_skill_context(
    loaded_skill: dict[str, Any],
    *,
    activation_note: str,
    skill_dir: Optional[Path] = None,
    include_setup_hints: bool = True,
    include_supporting_files: bool = True,
) -> str:
    """Render the shared skill-prompt block.

    Both the interactive CLI path (`skill_commands._build_skill_message`)
    and the cron executor path (`cron/scheduler._build_job_prompt`) call
    this with different flag combinations; the BRAID plan + content
    rendering is identical across paths.

    Args:
        loaded_skill: dict returned by `tools.skills_tool.skill_view` or
            equivalent. Looked-up keys: ``content``, ``mermaid_plan``,
            ``setup_skipped``, ``gateway_setup_hint``, ``setup_needed``,
            ``setup_note``, ``linked_files``.
        activation_note: the opening system-ish line that tells the model
            the skill is now active. CLI passes the user-supplied note;
            cron passes its ``[SYSTEM: The user has invoked the "X"
            skill…]`` template. Rendered verbatim — caller controls wording.
        skill_dir: the on-disk skill directory, used to enumerate
            ``references/``, ``templates/``, ``scripts/``, ``assets/``
            for the supporting-files block. Only consulted when
            ``include_supporting_files`` is True AND ``loaded_skill`` has
            no explicit ``linked_files``.
        include_setup_hints: render the single applicable setup-note line
            (``setup_skipped`` > ``gateway_setup_hint`` > ``setup_needed+
            setup_note``). CLI historically True; cron historically False.
        include_supporting_files: render the "[This skill has supporting
            files…]" block + skill_view pointer. CLI historically True;
            cron historically False.

    Returns:
        A multi-line string — the skill block only. Callers are responsible
        for splicing user-instruction, runtime-note, cron-hint, and any
        script-output fencing around / before this block.

    Cron historically passes ``include_setup_hints=False`` and
    ``include_supporting_files=False`` to match legacy behaviour. Flipping
    those to True is a deliberate future change — the cron agent would
    then see setup warnings, which MAY cause it to refuse to run a
    half-configured skill. Do not flip without a brief user-facing review
    of the affected cron jobs.
    """
    content = str(loaded_skill.get("content") or "").strip()

    parts: list[str] = [activation_note]

    # BRAID optional reasoning plan (arXiv:2512.15959). When a skill ships
    # a SKILL.mmd sibling, render it ahead of the prose content so the
    # solver treats the flowchart as the primary decision topology and the
    # SKILL.md body as reference detail.
    mermaid_plan = str(loaded_skill.get("mermaid_plan") or "").strip()
    if mermaid_plan:
        parts.extend(
            [
                "",
                "[BRAID Reasoning Plan — treat this Mermaid flowchart as your primary "
                "decision topology. Each node is an atomic step; labeled edges are "
                "explicit conditions; terminal Check nodes must all pass before emitting "
                "the final response. Do not render the diagram visually — traverse it to "
                "produce the final output. The prose skill content below is reference "
                "detail.]",
                "",
                "```mermaid",
                mermaid_plan,
                "```",
            ]
        )

    parts.extend(["", content])

    if include_setup_hints:
        if loaded_skill.get("setup_skipped"):
            parts.extend(
                [
                    "",
                    "[Skill setup note: Required environment setup was skipped. Continue loading the skill and explain any reduced functionality if it matters.]",
                ]
            )
        elif loaded_skill.get("gateway_setup_hint"):
            parts.extend(
                [
                    "",
                    f"[Skill setup note: {loaded_skill['gateway_setup_hint']}]",
                ]
            )
        elif loaded_skill.get("setup_needed") and loaded_skill.get("setup_note"):
            parts.extend(
                [
                    "",
                    f"[Skill setup note: {loaded_skill['setup_note']}]",
                ]
            )

    if include_supporting_files:
        supporting: list[str] = []
        linked_files = loaded_skill.get("linked_files") or {}
        for entries in linked_files.values():
            if isinstance(entries, list):
                supporting.extend(entries)

        if not supporting and skill_dir:
            for subdir in ("references", "templates", "scripts", "assets"):
                subdir_path = skill_dir / subdir
                if subdir_path.exists():
                    for f in sorted(subdir_path.rglob("*")):
                        if f.is_file():
                            rel = str(f.relative_to(skill_dir))
                            supporting.append(rel)

        if supporting and skill_dir:
            # Import here to avoid a circular dependency at module load:
            # tools.skills_tool → agent.* → this module.
            from tools.skills_tool import SKILLS_DIR
            try:
                skill_view_target = str(skill_dir.relative_to(SKILLS_DIR))
            except ValueError:
                # Skill is from an external dir — use the skill name instead.
                skill_view_target = skill_dir.name
            parts.append("")
            parts.append(
                "[This skill has supporting files you can load with the skill_view tool:]"
            )
            for sf in supporting:
                parts.append(f"- {sf}")
            parts.append(
                f'\nTo view any of these, use: skill_view(name="{skill_view_target}", file_path="<path>")'
            )

    return "\n".join(parts)
