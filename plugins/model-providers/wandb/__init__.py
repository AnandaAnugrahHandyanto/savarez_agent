"""Weights & Biases Inference provider profile.

W&B Inference is a standard OpenAI-compatible endpoint (serverless inference
hosted on CoreWeave). API-key auth via ``WANDB_API_KEY``; the ``/v1/models``
catalog is live so the picker fetches models automatically.

W&B also accepts an optional ``openai-project`` header (``team/project``). It is
ONLY required for personal W&B accounts whose default project lacks Inference
access — team accounts need nothing. Because the value is per-user we do not
ship a static ``default_headers`` for it; personal-account users supply it via
``model.default_headers`` in ``config.yaml`` (see the provider docs), which
``_apply_user_default_headers`` merges onto both the main and auxiliary clients.
"""

from providers import register_provider
from providers.base import ProviderProfile

wandb = ProviderProfile(
    name="wandb",
    aliases=("weights-and-biases", "wandb-inference", "wnb"),
    display_name="W&B Inference",
    description="Weights & Biases Inference — open models hosted on CoreWeave",
    signup_url="https://wandb.ai/settings",
    env_vars=("WANDB_API_KEY", "WANDB_BASE_URL"),  # 1st = key, 2nd = base-url override
    base_url="https://api.inference.wandb.ai/v1",
    auth_type="api_key",
    default_aux_model="meta-llama/Llama-3.1-8B-Instruct",
    fallback_models=(
        # Safety net only — the picker fetches the live /v1/models catalog.
        # Only tool-calling / agentic models belong here.
        "deepseek-ai/DeepSeek-V3.1",
        "Qwen/Qwen3-235B-A22B-Instruct-2507",
        "moonshotai/Kimi-K2-Instruct",
        "zai-org/GLM-4.5",
        "openai/gpt-oss-120b",
        "meta-llama/Llama-3.1-8B-Instruct",
    ),
)

register_provider(wandb)
