"""Image reference/edit tool.

Adds an ``image_edit`` tool to the existing ``image_gen`` toolset. It keeps
``image_generate`` focused on text-to-image while allowing providers that
support reference images, masks, or iterative image editing to expose those
capabilities through the normal tool registry.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from agent.image_gen_provider import DEFAULT_ASPECT_RATIO, VALID_ASPECT_RATIOS
from tools.image_generation_tool import check_image_generation_requirements
from tools.registry import registry, tool_error

logger = logging.getLogger(__name__)


IMAGE_EDIT_SCHEMA = {
    "name": "image_edit",
    "description": (
        "Create or edit an image using one or more reference images. Use this "
        "when the user provides an existing logo, character, cover, or mask "
        "and asks to modify, restyle, or regenerate from it. The active "
        "image_gen provider is user-configured. Returns either a URL or an "
        "absolute file path in the `image` field; display it with markdown "
        "![description](url-or-path) and the gateway will deliver it."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "prompt": {
                "type": "string",
                "description": "Editing/reference-generation instruction. Be explicit about what to preserve and what to change.",
            },
            "reference_images": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Local image file paths to use as references. MVP supports local paths; uploaded Telegram/CLI images should be passed as their local cache paths.",
                "default": [],
            },
            "aspect_ratio": {
                "type": "string",
                "enum": list(VALID_ASPECT_RATIOS),
                "description": "The output aspect ratio. 'landscape' is 16:9 wide, 'portrait' is 16:9 tall, 'square' is 1:1.",
                "default": DEFAULT_ASPECT_RATIO,
            },
            "quality": {
                "type": "string",
                "enum": ["low", "medium", "high", "auto"],
                "description": "Optional provider quality hint. OpenAI GPT Image 2 supports low, medium, high, and may accept auto on compatible endpoints.",
                "default": "medium",
            },
            "mode": {
                "type": "string",
                "enum": ["auto", "edit", "reference"],
                "description": "Intent hint for future providers; current OpenAI MVP routes all modes through images.edit.",
                "default": "auto",
            },
            "mask_image": {
                "type": "string",
                "description": "Optional local mask image path for inpainting/editing providers that support masks.",
            },
            "use_last_user_images": {
                "type": "boolean",
                "description": "Reserved for future session attachment reuse. Current tool requires explicit reference_images paths.",
                "default": False,
            },
            "use_last_generated_image": {
                "type": "boolean",
                "description": "Reserved for future generated-image reuse. Current tool requires explicit reference_images paths.",
                "default": False,
            },
        },
        "required": ["prompt"],
    },
}


def _read_configured_image_provider() -> Optional[str]:
    try:
        from hermes_cli.config import load_config

        cfg = load_config()
        section = cfg.get("image_gen") if isinstance(cfg, dict) else None
        if isinstance(section, dict):
            value = section.get("provider")
            if isinstance(value, str) and value.strip():
                return value.strip()
    except Exception as exc:
        logger.debug("Could not read image_gen.provider: %s", exc)
    return None


def _load_provider():
    try:
        from agent.image_gen_registry import get_active_provider, get_provider
        from hermes_cli.plugins import _ensure_plugins_discovered

        _ensure_plugins_discovered()
        configured = _read_configured_image_provider()
        if configured:
            provider = get_provider(configured)
            if provider is None:
                _ensure_plugins_discovered(force=True)
                provider = get_provider(configured)
            return provider, configured
        return get_active_provider(), None
    except Exception as exc:
        logger.warning("image_edit provider discovery failed: %s", exc)
        return None, None


def _normalize_reference_images(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, (list, tuple)):
        return [str(item) for item in value if str(item).strip()]
    return []


def _handle_image_edit(args: Dict[str, Any], **kw) -> str:
    prompt = str(args.get("prompt") or "").strip()
    if not prompt:
        return tool_error("prompt is required for image editing", success=False)

    if args.get("use_last_user_images") or args.get("use_last_generated_image"):
        return tool_error(
            "image_edit does not yet support implicit last-image reuse; pass explicit reference_images paths",
            success=False,
            error_type="unsupported_operation",
        )

    reference_images = _normalize_reference_images(args.get("reference_images"))
    if not reference_images:
        return tool_error(
            "reference_images must include at least one local image path",
            success=False,
            error_type="invalid_argument",
        )

    provider, configured = _load_provider()
    if provider is None:
        return json.dumps({
            "success": False,
            "image": None,
            "error": (
                "No image_gen provider is available for image_edit. Configure "
                "an image provider such as OpenAI with `hermes tools` or "
                "`hermes config set image_gen.provider openai`."
            ),
            "error_type": "provider_not_available",
            "provider": configured or "",
        })

    try:
        result = provider.edit(
            prompt=prompt,
            reference_images=reference_images,
            aspect_ratio=args.get("aspect_ratio", DEFAULT_ASPECT_RATIO),
            quality=args.get("quality"),
            mode=args.get("mode", "auto"),
            mask_image=args.get("mask_image"),
        )
    except Exception as exc:
        logger.warning("Image edit provider '%s' raised: %s", getattr(provider, "name", "?"), exc)
        return json.dumps({
            "success": False,
            "image": None,
            "error": f"Provider '{getattr(provider, 'name', '?')}' error: {exc}",
            "error_type": "provider_exception",
            "provider": getattr(provider, "name", ""),
        })

    if not isinstance(result, dict):
        return json.dumps({
            "success": False,
            "image": None,
            "error": "Provider returned a non-dict result",
            "error_type": "provider_contract",
            "provider": getattr(provider, "name", ""),
        })
    return json.dumps(result, ensure_ascii=False)


registry.register(
    name="image_edit",
    toolset="image_gen",
    schema=IMAGE_EDIT_SCHEMA,
    handler=_handle_image_edit,
    check_fn=check_image_generation_requirements,
    requires_env=[],
    is_async=False,
    emoji="🖼️",
)
