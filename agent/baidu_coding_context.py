"""Baidu Qianfan Coding Plan — static context length table.

This module lives under agent/ (like bedrock_adapter.py) so it can be
imported with a standard ``from agent.baidu_coding_context import …``
instead of fighting the plugins.model-providers namespace (which uses a
hyphen in the directory name and cannot be imported with a dotted path).

Source: https://cloud.baidu.com/doc/qianfan/s/rmh4stp0j
(Baidu Model List)

Only the 7 models on the official Coding Plan subscription are listed.
See https://cloud.baidu.com/doc/qianfan/s/imlg0beiu
"""

from typing import Dict

# ---------------------------------------------------------------------------
# Static context-length table for Baidu Qianfan Coding Plan.
#
# Baidu's /v2/coding/models endpoint does not reliably return context_length
# metadata, and models.dev has no Baidu provider entry.  This table follows
# the same pattern as BEDROCK_CONTEXT_LENGTHS in bedrock_adapter.py — it is
# consulted at step 1c in agent/model_metadata.py before generic probing.
#
# Values reflect Baidu Coding Plan limits, which may differ from the same
# model's context on its native provider (e.g. glm-5.1 is 204,800 on Z.AI
# but 198,000 on Baidu Qianfan).
# ---------------------------------------------------------------------------

BAIDU_CODING_CONTEXT_LENGTHS: Dict[str, int] = {
    # GLM models — Baidu imposes a 198k cap (vs 204,800 on Z.AI)
    "glm-5.1": 198_000,
    "glm-5": 198_000,
    # DeepSeek
    "deepseek-v3.2": 128_000,
    "deepseek-v4-flash": 1_000_000,
    # Kimi — Baidu caps at 256k (vs 262,144 natively on Moonshot)
    "kimi-k2.5": 256_000,
    # MiniMax — Baidu caps at 192k (vs 204,800 natively on MiniMax)
    "minimax-m2.5": 192_000,
    "MiniMax-M2.5": 192_000,
    # ERNIE
    "ernie-4.5-turbo": 128_000,
}

# Default for unknown models on Baidu Qianfan Coding Plan
BAIDU_CODING_DEFAULT_CONTEXT_LENGTH = 128_000


def get_baidu_coding_context_length(model: str) -> int:
    """Look up the context window size for a Baidu Qianfan Coding Plan model.

    Uses substring matching (longest key first for specificity) so versioned
    or suffixed model IDs resolve correctly.
    """
    model_lower = model.lower()
    best_key = ""
    best_val = BAIDU_CODING_DEFAULT_CONTEXT_LENGTH
    for key, val in BAIDU_CODING_CONTEXT_LENGTHS.items():
        if key.lower() in model_lower and len(key) > len(best_key):
            best_key = key
            best_val = val
    return best_val
