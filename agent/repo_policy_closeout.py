from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

STANDARD_CLOSEOUT_SECTIONS: tuple[str, ...] = (
    "Policy check",
    "Green 완료",
    "Yellow 대기",
    "Red 필요",
    "검증",
    "Git 상태",
    "Live 상태",
)

RUNTIME_TOOLING_EXTRA_SECTIONS: tuple[str, ...] = (
    "Gateway restart 필요",
    "Live runtime 반영됨",
    "대기열 포함됨",
)

STANDARD_CLOSEOUT_TEMPLATE = """Policy check
- <repo-policy checker result, policy path, pass/fail_closed/drift reason>

Green 완료
- <completed local/green work>

Yellow 대기
- <queued release/live/restart/review items, or none>

Red 필요
- <actions still requiring explicit approval, or none crossed>

검증
- <tests/static checks/proofs>

Git 상태
- <branch/worktree/commit/dirty state/push status>

Live 상태
- <deployed/live/runtime/customer-visible state>
"""

RUNTIME_TOOLING_CLOSEOUT_TEMPLATE = STANDARD_CLOSEOUT_TEMPLATE + """
Gateway restart 필요
- <yes/no and why; do not restart unless explicitly approved>

Live runtime 반영됨
- <yes/no with runtime proof if applied>

대기열 포함됨
- <yes/no; queue entry id/details if restart/live apply is pending>
"""


@dataclass(frozen=True)
class CloseoutSectionValidation:
    ok: bool
    missing_sections: tuple[str, ...]
    required_sections: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "missing_sections": list(self.missing_sections),
            "required_sections": list(self.required_sections),
        }


def required_closeout_sections(*, runtime_tooling: bool = False) -> tuple[str, ...]:
    if runtime_tooling:
        return STANDARD_CLOSEOUT_SECTIONS + RUNTIME_TOOLING_EXTRA_SECTIONS
    return STANDARD_CLOSEOUT_SECTIONS


def validate_closeout_sections(text: str, *, runtime_tooling: bool = False) -> CloseoutSectionValidation:
    required = required_closeout_sections(runtime_tooling=runtime_tooling)
    missing = tuple(section for section in required if section not in text)
    return CloseoutSectionValidation(ok=not missing, missing_sections=missing, required_sections=required)


def render_closeout_template(*, runtime_tooling: bool = False) -> str:
    return RUNTIME_TOOLING_CLOSEOUT_TEMPLATE if runtime_tooling else STANDARD_CLOSEOUT_TEMPLATE


def missing_policy_check_is_incomplete(texts: Iterable[str]) -> bool:
    return any("Policy check" not in text for text in texts)
