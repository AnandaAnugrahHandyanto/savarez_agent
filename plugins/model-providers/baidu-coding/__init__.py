"""Baidu Qianfan Coding Plan provider profile.

Separate from a hypothetical standard Baidu profile because it hits a
different endpoint (qianfan.baidubce.com/v2/coding) with a dedicated
Coding Plan API key tier (sk-sp-* prefix keys).

Official Coding Plan model list
(https://cloud.baidu.com/doc/qianfan/s/imlg0beiu):

Only these 7 models are available via Coding Plan subscription.
Do NOT add models from the general model list page — those require
standard Qianfan keys (sk-*), not Coding Plan keys (sk-sp-*).

Context lengths from official Baidu Model List page
(https://cloud.baidu.com/doc/qianfan/s/rmh4stp0j):

  Model                Context   Max Input   Max Output   RPM    TPM
  ─────────────────── ───────── ────────── ──────────── ────── ────────
  glm-5.1               198k      198k      1-131,072     60    250,000
  glm-5                 198k      198k      1-131,072     60    250,000
  deepseek-v3.2         128k       96k           32k    5,000  1,000,000
  deepseek-v4-flash       1M        1M      1-131,072     60    150,000
  kimi-k2.5             256k      224k       1-65,536     60    250,000
  minimax-m2.5          192k      192k      1-131,072     60    250,000
  ernie-4.5-turbo       128k      123k        2-12,288     60    150,000

NOTE: Context lengths differ from the model creator's own specs.
E.g. glm-5.1 is 204,800 on Z.AI but 198,000 on Baidu Qianfan.

Context length lookup is in agent/baidu_qianfan_context.py (following the
same pattern as agent/bedrock_adapter.py).
"""

from providers import register_provider
from providers.base import ProviderProfile

baidu_qianfan = ProviderProfile(
    name="baidu-coding",
    aliases=("baidu", "qianfan", "baidu-coding-plan", "baidu-qianfan"),
    display_name="Baidu Coding Plan",
    description="Baidu Coding Plan",
    signup_url="https://console.bce.baidu.com/ai_apaas/secretKey",
    env_vars=(
        "BAIDU_CODING_API_KEY",   # Coding Plan dedicated key (sk-sp-*)
        "BAIDU_API_KEY",          # fallback for backward compat
        "BAIDU_CODING_BASE_URL",  # custom base URL override
    ),
    base_url="https://qianfan.baidubce.com/v2/coding",
    auth_type="api_key",
    fallback_models=(
        "glm-5",
        "deepseek-v3.2",
    ),
    default_aux_model="deepseek-v3.2",
)

register_provider(baidu_qianfan)
