"""Context-aware tool result budgeting.

Prevents tool results from exceeding the model's available context by
enforcing dynamic per-result and per-turn budgets.  Oversized results
are spilled to disk; the model pages through them via read_file.

Budget = max(floor, min(baseline, available))

- baseline: context_length * result_pct (absolute ceiling per result)
- available: (context_length - current_usage) * CHARS_PER_TOKEN
- floor: minimum useful result size (below this, pagination > tiny sliver)
"""

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

CHARS_PER_TOKEN = 4
DEFAULT_RESULT_PCT = 0.25
DEFAULT_TURN_PCT = 0.50
DEFAULT_FLOOR_TOKENS = 2000
DEFAULT_SPILL_DIR = "/tmp/hermes-results"


class ToolBudget:
    __slots__ = (
        "context_length",
        "result_pct",
        "turn_pct",
        "floor_tokens",
        "compact_before_spill",
        "baseline_chars",
        "turn_budget_chars",
        "floor_chars",
        "spill_dir",
    )

    def __init__(
        self,
        context_length: int,
        config: dict | None = None,
        spill_dir: str | None = None,
    ):
        cfg = config or {}
        self.context_length = context_length
        self.result_pct = float(cfg.get("result_pct", DEFAULT_RESULT_PCT))
        self.turn_pct = float(cfg.get("turn_pct", DEFAULT_TURN_PCT))
        self.floor_tokens = int(cfg.get("floor_tokens", DEFAULT_FLOOR_TOKENS))
        self.compact_before_spill = bool(cfg.get("compact_before_spill", True))

        self.baseline_chars = int(context_length * self.result_pct * CHARS_PER_TOKEN)
        self.turn_budget_chars = int(context_length * self.turn_pct * CHARS_PER_TOKEN)
        self.floor_chars = self.floor_tokens * CHARS_PER_TOKEN
        self.spill_dir = spill_dir or DEFAULT_SPILL_DIR

    def effective_budget_chars(self, current_token_usage: int) -> int:
        """Calculate per-result budget based on total capacity and available space."""
        available_tokens = max(0, self.context_length - current_token_usage)
        available_chars = available_tokens * CHARS_PER_TOKEN
        return max(self.floor_chars, min(self.baseline_chars, available_chars))

    def should_compact_first(
        self, result_chars: int, current_token_usage: int
    ) -> bool:
        """True when compaction could meaningfully increase the budget.

        Triggers when available space is smaller than the baseline AND
        the result exceeds available space — compaction would free room
        for a more useful chunk.
        """
        if not self.compact_before_spill:
            return False
        available_tokens = max(0, self.context_length - current_token_usage)
        available_chars = available_tokens * CHARS_PER_TOKEN
        return available_chars < self.baseline_chars and result_chars > available_chars

    def apply(
        self,
        result: str,
        tool_use_id: str,
        current_token_usage: int,
    ) -> tuple[str, bool]:
        """Apply budget to a tool result.

        Returns (possibly_truncated_result, was_spilled).
        """
        budget = self.effective_budget_chars(current_token_usage)
        if len(result) <= budget:
            return result, False

        spill_path = self._spill_to_disk(result, tool_use_id)
        total_lines = result.count("\n") + 1
        preview_end = self._find_line_boundary(result, budget)
        preview = result[:preview_end]
        preview_lines = preview.count("\n") + 1

        footer = (
            f"\n\n[Showing first {preview_lines:,} of {total_lines:,} lines "
            f"({len(result):,} chars total).\n"
            f"Full output: {spill_path}\n"
            f"Use read_file with offset={preview_lines + 1} to continue.]"
        )
        return preview + footer, True

    def _spill_to_disk(self, content: str, tool_use_id: str) -> str:
        os.makedirs(self.spill_dir, exist_ok=True)
        path = os.path.join(self.spill_dir, f"{tool_use_id}.txt")
        Path(path).write_text(content, encoding="utf-8")
        logger.info("Spilled tool result to %s (%d chars)", path, len(content))
        return path

    @staticmethod
    def _find_line_boundary(text: str, max_chars: int) -> int:
        """Find a clean line boundary within max_chars."""
        if max_chars >= len(text):
            return len(text)
        boundary = text.rfind("\n", 0, max_chars)
        return boundary + 1 if boundary > 0 else max_chars
