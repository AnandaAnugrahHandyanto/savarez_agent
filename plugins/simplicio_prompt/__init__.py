"""SIMPLICIO_PROMPT plugin.

Adds an opt-in pre-LLM prompt overlay for users who want every Hermes turn to
follow the SIMPLICIO_PROMPT V2 tuple-space execution policy automatically.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from utils import env_var_enabled, is_truthy_value


CANONICAL_REPO = "https://github.com/wesleysimplicio/simplicio-prompt"
PLUGIN_NAME = "SIMPLICIO_PROMPT"

SIMPLICIO_PROMPT_CONTEXT = """[SIMPLICIO_PROMPT]
Canonical repo: https://github.com/wesleysimplicio/simplicio-prompt. Apply to every enabled main-agent turn before the model call. Do not require any user trigger word such as "Implement", "Fix", or "Build"; apply equally to questions, layout edits, refactors, debugging, docs, and normal chat.

Plan as tuple-space: root tuple, Hilbert/HAMT work graph, out/in/rd routing, receipts, lane, authority, and source pointers. Use batch_spawn(depth, branching, compression_threshold) as summarized hierarchy for 1,000,000+ subagents; never enumerate. Use real spawn/delegate only when useful, route deterministic work to local tools first, then compress_token, weakref, hookwall, and prune_idle inactive branches.

Safe speed V2: cache by receipt/input hash, batch tiny tasks, compress prompt/context, use stable prefixes, adaptive lanes, backoff+jitter, circuit breakers, and idempotent-only speculation. Respect provider limits and terms.

Default response:
[Tuple Space Snapshot]
[Active Agents/Subagents]
[Total Agents/Subagents]
[Próximo Yool a executar]
[Resultado parcial]
[/SIMPLICIO_PROMPT]"""


def _load_config() -> Dict[str, Any]:
    try:
        from hermes_cli.config import load_config

        config = load_config()
    except Exception:
        return {}
    return config if isinstance(config, dict) else {}


def _config_flag_enabled(config: Dict[str, Any]) -> bool:
    try:
        from hermes_cli.config import cfg_get

        explicit = cfg_get(config, "simplicio_prompt", "enabled", default=False)
    except Exception:
        explicit = False
    if is_truthy_value(explicit):
        return True

    plugins_cfg = config.get("plugins")
    enabled = plugins_cfg.get("enabled") if isinstance(plugins_cfg, dict) else None
    if isinstance(enabled, list):
        normalized = {str(item).strip().lower() for item in enabled}
        return PLUGIN_NAME.lower() in normalized or "simplicio_prompt" in normalized
    return False


def is_enabled(config: Optional[Dict[str, Any]] = None) -> bool:
    """Return True when SIMPLICIO_PROMPT should inject its overlay."""
    if env_var_enabled("SIMPLICIO_PROMPT") or env_var_enabled(
        "HERMES_SIMPLICIO_PROMPT"
    ):
        return True
    return _config_flag_enabled(config if config is not None else _load_config())


def build_context(config: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, str]]:
    """Build a pre_llm_call hook return payload, or None when disabled."""
    if not is_enabled(config):
        return None
    return {"context": SIMPLICIO_PROMPT_CONTEXT}


def _pre_llm_call(**_: Any) -> Optional[Dict[str, str]]:
    """Inject for every enabled turn; message content is intentionally ignored."""
    return build_context()


def register(ctx) -> None:
    """Register the pre_llm_call hook."""
    ctx.register_hook("pre_llm_call", _pre_llm_call)
