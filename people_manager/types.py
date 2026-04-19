from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(slots=True)
class ParserResult:
    action: str
    raw_text: str
    report_name: Optional[str] = None
    role_title: Optional[str] = None
    body: Optional[str] = None
    prompt_variant: Optional[str] = None
    is_mutating: bool = False
