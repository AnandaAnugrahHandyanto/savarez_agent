"""Azure AI Foundry image generation backend.

Exposes Azure AI Foundry's gpt-image-2 as an :class:`ImageGenProvider`
implementation using the Azure OpenAI v1 API (``openai.OpenAI`` with
``base_url`` pointing to ``/openai/v1/``).

The user configures one deployment (e.g. ``gpt-image-2``). Quality is
configured globally (``"low"`` / ``"medium"`` / ``"high"``) via the
``AZURE_FOUNDRY_IMAGE_QUALITY`` env var or ``image_gen.azure_foundry.quality``
in ``config.yaml``, defaulting to ``"medium"``.

Configuration
-------------
Resolution order (first hit wins):

1. Environment variables::

       AZURE_FOUNDRY_IMAGE_ENDPOINT   — Azure resource endpoint
                                        e.g. https://my-resource.openai.azure.com
       AZURE_FOUNDRY_IMAGE_KEY        — API key
       AZURE_FOUNDRY_IMAGE_DEPLOYMENT — deployment name (default: gpt-image-2)
       AZURE_FOUNDRY_IMAGE_QUALITY    — quality tier: low / medium / high (default: medium)

2. ``image_gen.azure_foundry`` section in ``config.yaml``::

       image_gen:
         provider: azure_foundry
         azure_foundry:
           endpoint: "https://my-resource.openai.azure.com"
           api_key_env: "AZURE_FOUNDRY_IMAGE_KEY"   # env var name, not the key itself
           deployment_name: "gpt-image-2"

3. Global ``AZURE_OPENAI_*`` fallback env vars
   (``AZURE_OPENAI_API_KEY`` + ``AZURE_OPENAI_ENDPOINT``).

Quality
-------
Set quality via ``AZURE_FOUNDRY_IMAGE_QUALITY`` env var or
``image_gen.azure_foundry.quality`` in ``config.yaml``.
Valid values: ``"low"``, ``"medium"``, ``"high"``. Default: ``"medium"``.

Sizes
-----
``1024x1024`` (square), ``1536x1024`` (landscape), ``1024x1536`` (portrait).
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

from agent.image_gen_provider import (
    DEFAULT_ASPECT_RATIO,
    ImageGenProvider,
    error_response,
    resolve_aspect_ratio,
    save_b64_image,
    success_response,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_DEPLOYMENT = "gpt-image-2"

VALID_QUALITY_VALUES = {"low", "medium", "high"}
DEFAULT_QUALITY = "medium"


def _resolve_quality() -> str:
    """Resolve quality setting from env var or config.yaml.

    Precedence:
    1. ``AZURE_FOUNDRY_IMAGE_QUALITY`` env var
    2. ``image_gen.azure_foundry.quality`` in config.yaml
    3. :data:`DEFAULT_QUALITY` (``"medium"``)

    Unknown values are silently ignored and fall back to the default.
    """
    env_val = os.environ.get("AZURE_FOUNDRY_IMAGE_QUALITY", "").strip().lower()
    if env_val:
        return env_val if env_val in VALID_QUALITY_VALUES else DEFAULT_QUALITY

    cfg = _load_azure_foundry_config()
    cfg_val = str(cfg.get("quality") or "").strip().lower()
    if cfg_val and cfg_val in VALID_QUALITY_VALUES:
        return cfg_val

    return DEFAULT_QUALITY

_SIZES: Dict[str, str] = {
    "landscape": "1536x1024",
    "square": "1024x1024",
    "portrait": "1024x1536",
}


# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------


def _load_azure_foundry_config() -> Dict[str, Any]:
    """Read ``image_gen.azure_foundry`` from config.yaml (returns {} on failure)."""
    try:
        from hermes_cli.config import load_config

        cfg = load_config()
        img_cfg = cfg.get("image_gen") if isinstance(cfg, dict) else None
        if not isinstance(img_cfg, dict):
            return {}
        section = img_cfg.get("azure_foundry")
        return section if isinstance(section, dict) else {}
    except Exception as exc:
        logger.debug("Could not load image_gen.azure_foundry config: %s", exc)
        return {}


def _resolve_credentials() -> Dict[str, Any]:
    """Resolve endpoint, API key, and deployment name.

    Returns a dict with keys: ``endpoint``, ``api_key``, ``deployment``.
    Empty string means not configured.
    """
    # 1. Dedicated env vars
    endpoint = os.environ.get("AZURE_FOUNDRY_IMAGE_ENDPOINT", "").strip()
    api_key = os.environ.get("AZURE_FOUNDRY_IMAGE_KEY", "").strip()
    deployment = os.environ.get("AZURE_FOUNDRY_IMAGE_DEPLOYMENT", "").strip()

    # 2. config.yaml fills gaps
    cfg = _load_azure_foundry_config()
    if not endpoint:
        endpoint = str(cfg.get("endpoint") or "").strip()
    if not api_key:
        key_env = str(cfg.get("api_key_env") or "").strip()
        if key_env:
            api_key = os.environ.get(key_env, "").strip()
    if not deployment:
        deployment = str(cfg.get("deployment_name") or "").strip()

    # 3. Global Azure OpenAI fallback (endpoint + key only)
    if not endpoint:
        endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT", "").strip()
    if not api_key:
        api_key = os.environ.get("AZURE_OPENAI_API_KEY", "").strip()

    return {
        "endpoint": endpoint,
        "api_key": api_key,
        "deployment": deployment or DEFAULT_DEPLOYMENT,
    }


# ---------------------------------------------------------------------------
# Provider
# ---------------------------------------------------------------------------


class AzureFoundryImageGenProvider(ImageGenProvider):
    """Azure AI Foundry gpt-image-2 image generation backend.

    Uses ``openai.OpenAI`` with Azure OpenAI v1 ``base_url``.
    Quality (low / medium / high) is resolved from config, not from the caller.
    """

    @property
    def name(self) -> str:
        return "azure-foundry"

    @property
    def display_name(self) -> str:
        return "Azure AI Foundry"

    def is_available(self) -> bool:
        creds = _resolve_credentials()
        return bool(creds.get("endpoint") and creds.get("api_key"))

    def list_models(self) -> List[Dict[str, Any]]:
        """Return one entry for the configured deployment."""
        creds = _resolve_credentials()
        deployment = creds["deployment"]
        return [
            {
                "id": deployment,
                "display": f"Azure AI Foundry — {deployment}",
                "speed": "varies by quality",
                "strengths": "Quality configured globally: low / medium / high",
                "price": "varies",
            }
        ]

    def default_model(self) -> Optional[str]:
        return _resolve_credentials()["deployment"]

    def get_setup_schema(self) -> Dict[str, Any]:
        return {
            "name": "Azure AI Foundry",
            "badge": "paid",
            "tag": (
                "gpt-image-2 via Azure AI Foundry — requires an Azure "
                "resource with an image generation deployment."
            ),
            "env_vars": [
                {
                    "key": "AZURE_FOUNDRY_IMAGE_ENDPOINT",
                    "prompt": "Azure resource endpoint (e.g. https://my-resource.openai.azure.com)",
                    "url": "https://portal.azure.com",
                    "secret": False,
                },
                {
                    "key": "AZURE_FOUNDRY_IMAGE_KEY",
                    "prompt": "Azure API key",
                    "url": "https://portal.azure.com",
                },
                {
                    "key": "AZURE_FOUNDRY_IMAGE_DEPLOYMENT",
                    "prompt": f"Deployment name (default: {DEFAULT_DEPLOYMENT})",
                    "url": "https://ai.azure.com",
                    "secret": False,
                },
                {
                    "key": "AZURE_FOUNDRY_IMAGE_QUALITY",
                    "prompt": f"Image quality — low / medium / high (default: {DEFAULT_QUALITY})",
                    "url": "https://learn.microsoft.com/azure/ai-services/openai/concepts/models",
                    "secret": False,
                },
            ],
        }

    def generate(
        self,
        prompt: str,
        aspect_ratio: str = DEFAULT_ASPECT_RATIO,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Generate an image using Azure AI Foundry.

        Quality is resolved from configuration (``AZURE_FOUNDRY_IMAGE_QUALITY``
        env var or ``image_gen.azure_foundry.quality`` in config.yaml).
        It is not a per-call parameter.

        Args:
            prompt:       Text description of the image to generate.
            aspect_ratio: ``"landscape"``, ``"square"``, or ``"portrait"``.
            **kwargs:     Ignored (forward-compat).

        Returns:
            A dict from :func:`success_response` or :func:`error_response`.
        """
        prompt = (prompt or "").strip()
        aspect = resolve_aspect_ratio(aspect_ratio)

        # --- quality from config ---
        resolved_quality = _resolve_quality()

        # --- input validation ---
        if not prompt:
            return error_response(
                error="Prompt is required and must be a non-empty string.",
                error_type="invalid_argument",
                provider=self.name,
                aspect_ratio=aspect,
            )

        # --- credentials ---
        creds = _resolve_credentials()
        endpoint = creds.get("endpoint", "")
        api_key = creds.get("api_key", "")

        if not endpoint or not api_key:
            return error_response(
                error=(
                    "Azure AI Foundry credentials not configured. "
                    "Set AZURE_FOUNDRY_IMAGE_ENDPOINT and AZURE_FOUNDRY_IMAGE_KEY, "
                    "or configure image_gen.azure_foundry in config.yaml."
                ),
                error_type="auth_required",
                provider=self.name,
                aspect_ratio=aspect,
            )

        # --- openai SDK ---
        try:
            import openai
        except ImportError:
            return error_response(
                error="openai Python package not installed (pip install openai)",
                error_type="missing_dependency",
                provider=self.name,
                aspect_ratio=aspect,
            )

        deployment = creds["deployment"]
        base_url = endpoint.rstrip("/") + "/openai/v1/"
        size = _SIZES.get(aspect, _SIZES["square"])

        # --- API call (Azure OpenAI v1) ---
        try:
            client = openai.OpenAI(
                api_key=api_key,
                base_url=base_url,
            )
            response = client.images.generate(
                model=deployment,
                prompt=prompt,
                size=size,  # type: ignore[arg-type]
                n=1,
                quality=resolved_quality,  # type: ignore[arg-type]
            )
        except Exception as exc:
            logger.debug("Azure Foundry image generation failed", exc_info=True)
            return error_response(
                error=f"Azure Foundry image generation failed: {exc}",
                error_type="api_error",
                provider=self.name,
                model=deployment,
                prompt=prompt,
                aspect_ratio=aspect,
            )

        # --- response parsing ---
        data = getattr(response, "data", None) or []
        if not data:
            return error_response(
                error="Azure Foundry returned no image data.",
                error_type="empty_response",
                provider=self.name,
                model=deployment,
                prompt=prompt,
                aspect_ratio=aspect,
            )

        first = data[0]
        b64 = getattr(first, "b64_json", None)
        url = getattr(first, "url", None)
        revised_prompt = getattr(first, "revised_prompt", None)

        if b64:
            try:
                saved_path = save_b64_image(b64, prefix=f"azure_foundry_{deployment}")
            except Exception as exc:
                return error_response(
                    error=f"Could not save image to cache: {exc}",
                    error_type="io_error",
                    provider=self.name,
                    model=deployment,
                    prompt=prompt,
                    aspect_ratio=aspect,
                )
            image_ref = str(saved_path)
        elif url:
            image_ref = url
        else:
            return error_response(
                error="Azure Foundry response contained neither b64_json nor URL.",
                error_type="empty_response",
                provider=self.name,
                model=deployment,
                prompt=prompt,
                aspect_ratio=aspect,
            )

        extra: Dict[str, Any] = {"size": size, "quality": resolved_quality}
        if revised_prompt:
            extra["revised_prompt"] = revised_prompt

        return success_response(
            image=image_ref,
            model=deployment,
            prompt=prompt,
            aspect_ratio=aspect,
            provider=self.name,
            extra=extra,
        )


# ---------------------------------------------------------------------------
# Plugin entry point
# ---------------------------------------------------------------------------


def register(ctx) -> None:
    """Plugin entry point — register AzureFoundryImageGenProvider."""
    ctx.register_image_gen_provider(AzureFoundryImageGenProvider())
