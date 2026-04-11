"""Shared multimodal helpers for native image passthrough.

The first implementation slice is image input only. The helpers here are
written so Hermes can later grow into per-modality policy handling without
copy-pasting gateway/API-server/runtime logic all over the codebase.
"""

from __future__ import annotations

import base64
import mimetypes
from pathlib import Path
from typing import Any, Iterable, Optional, Sequence
from urllib.parse import urlparse

from agent.models_dev import get_model_info

MAX_INLINE_IMAGE_BYTES = 2_000_000


def message_content_has_image_parts(content: Any) -> bool:
    if not isinstance(content, list):
        return False
    for part in content:
        if isinstance(part, dict) and str(part.get("type", "") or "") in {"image_url", "input_image"}:
            return True
    return False


def prepend_text_to_message_content(prefix: str, content: Any) -> Any:
    text = str(prefix or "").strip()
    if not text:
        return content
    if isinstance(content, list):
        return [{"type": "text", "text": text}, *content]
    body = str(content or "").strip()
    return f"{text}\n\n{body}" if body else text


def normalize_image_input_policy(policy: Optional[str]) -> str:
    """Normalize config values to fallback|auto|strict.

    Backward compatibility:
    - describe -> fallback
    - passthrough -> strict
    """
    value = str(policy or "").strip().lower()
    if value in {"", "fallback", "describe"}:
        return "fallback"
    if value == "auto":
        return "auto"
    if value in {"strict", "passthrough"}:
        return "strict"
    return "fallback"


def resolve_image_input_policy(config: Optional[dict]) -> str:
    """Resolve the configured image input policy from config dict."""
    cfg = config or {}
    multimodal = cfg.get("multimodal") or {}
    if isinstance(multimodal, dict) and multimodal.get("image_input_policy") is not None:
        return normalize_image_input_policy(multimodal.get("image_input_policy"))

    # Back-compat for the older image-specific setting from abandoned drafts.
    auxiliary = cfg.get("auxiliary") or {}
    vision = auxiliary.get("vision") or {}
    if isinstance(vision, dict) and vision.get("gateway_mode") is not None:
        return normalize_image_input_policy(vision.get("gateway_mode"))

    return "fallback"


def _normalize_runtime_provider(
    provider: Optional[str],
    base_url: Optional[str],
    api_mode: Optional[str],
) -> Optional[str]:
    raw_provider = str(provider or "").strip().lower()
    if raw_provider:
        return raw_provider

    if str(api_mode or "").strip().lower() == "anthropic_messages":
        return "anthropic"

    url = str(base_url or "").strip().lower()
    if not url:
        return None

    parsed = urlparse(url if "://" in url else f"https://{url}")
    host = (parsed.netloc or parsed.path or "").lower()

    if "openrouter.ai" in host:
        return "openrouter"
    if "chatgpt.com" in host or "api.openai.com" in host:
        return "openai"
    if "api.githubcopilot.com" in host or "models.github.ai" in host:
        return "copilot"
    if "anthropic.com" in host or url.rstrip("/").endswith("/anthropic"):
        return "anthropic"
    if "googleapis.com" in host:
        return "gemini"
    if "api.deepseek.com" in host:
        return "deepseek"
    return None


def runtime_supports_native_image_input(
    *,
    model: Optional[str],
    provider: Optional[str] = None,
    base_url: Optional[str] = None,
    api_mode: Optional[str] = None,
) -> Optional[bool]:
    """Conservatively determine whether the active runtime supports native images.

    Returns:
    - True when we have a strong signal that native image input is supported
    - False when we have a strong signal that it is not
    - None when support is unknown
    """
    model_id = str(model or "").strip()
    if not model_id:
        return None

    runtime_provider = _normalize_runtime_provider(provider, base_url, api_mode)

    candidates: list[str] = []
    if runtime_provider:
        candidates.append(runtime_provider)
    if runtime_provider == "openai-codex":
        candidates.append("openai")

    seen: set[str] = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        info = get_model_info(candidate, model_id)
        if info is not None:
            return info.supports_vision()

    model_lower = model_id.lower()
    if runtime_provider in {"anthropic"} and model_lower.startswith("claude"):
        return True
    if runtime_provider in {"openai", "openai-codex"} and model_lower.startswith(("gpt-4o", "gpt-4.1", "gpt-5", "codex")):
        return True
    if runtime_provider == "openrouter":
        if any(token in model_lower for token in ("/claude", "/gemini", "gpt-4o", "gpt-4.1", "gpt-5", "/vision", "mimo-v2-omni")):
            return True
    if runtime_provider == "gemini" and "gemini" in model_lower:
        return True

    # We intentionally do not guess for arbitrary custom/local endpoints.
    return None


def image_paths_within_inline_limit(
    image_paths: Sequence[str],
    *,
    max_inline_bytes: int = MAX_INLINE_IMAGE_BYTES,
) -> tuple[bool, list[str]]:
    """Return (all_within_limit, oversized_paths)."""
    oversized: list[str] = []
    for raw_path in image_paths:
        path = Path(str(raw_path)).expanduser()
        try:
            size = path.stat().st_size
        except OSError:
            oversized.append(str(path))
            continue
        if size > max_inline_bytes:
            oversized.append(str(path))
    return (len(oversized) == 0), oversized


def local_image_path_to_data_url(path: str) -> str:
    image_path = Path(path).expanduser()
    data = image_path.read_bytes()
    mime_type, _ = mimetypes.guess_type(str(image_path))
    mime_type = mime_type or "image/jpeg"
    encoded = base64.b64encode(data).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def build_native_image_message_content(
    user_text: str,
    image_paths: Sequence[str],
) -> list[dict[str, Any]]:
    """Build chat.completions-style content blocks with inline data URLs."""
    parts: list[dict[str, Any]] = []
    text = str(user_text or "").strip()
    if text:
        parts.append({"type": "text", "text": text})
    for raw_path in image_paths:
        parts.append(
            {
                "type": "image_url",
                "image_url": {"url": local_image_path_to_data_url(str(raw_path))},
            }
        )
    return parts


def build_gateway_image_shadow_text(user_text: str, image_paths: Sequence[str]) -> str:
    """Text-only shadow message for persisted gateway transcripts."""
    chunks: list[str] = []
    text = str(user_text or "").strip()
    if text:
        chunks.append(text)
    for raw_path in image_paths:
        path = Path(str(raw_path)).expanduser()
        chunks.append(f"Attached image: {path.name} (cached path: {path})")
    return "\n\n".join(chunk for chunk in chunks if chunk).strip() or "Attached image"


def build_file_image_shadow_text(user_text: str, image_descriptors: Iterable[str]) -> str:
    """Text shadow for uploaded image/file references."""
    chunks: list[str] = []
    text = str(user_text or "").strip()
    if text:
        chunks.append(text)
    for descriptor in image_descriptors:
        label = str(descriptor or "").strip()
        if label:
            chunks.append(f"Attached image: {label}")
    return "\n\n".join(chunk for chunk in chunks if chunk).strip() or "Attached image"


def preview_text_for_message_content(content: Any) -> str:
    """Compact text preview for list/string message content."""
    if isinstance(content, str):
        return content.strip()
    if not isinstance(content, list):
        return str(content or "").strip()

    chunks: list[str] = []
    for part in content:
        if isinstance(part, str) and part.strip():
            chunks.append(part.strip())
            continue
        if not isinstance(part, dict):
            continue
        ptype = str(part.get("type", "") or "")
        if ptype in {"text", "input_text", "output_text"}:
            text = str(part.get("text", "") or "").strip()
            if text:
                chunks.append(text)
        elif ptype in {"image_url", "input_image"}:
            chunks.append("Attached image")
        elif ptype in {"input_file", "file_url"}:
            filename = str(part.get("filename", "") or "attachment").strip()
            chunks.append(f"Attached: {filename}" if filename else "Attached file")
    return " ".join(chunks).strip()


def chat_content_to_responses_input(content: Any) -> Any:
    """Convert chat-style content blocks to Responses API content blocks."""
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return str(content) if content else ""

    converted: list[dict[str, Any]] = []
    for part in content:
        if not isinstance(part, dict):
            continue
        ptype = str(part.get("type", "") or "")
        if ptype in {"text", "input_text"}:
            converted.append({"type": "input_text", "text": str(part.get("text", "") or "")})
            continue
        if ptype in {"image_url", "input_image"}:
            image_data = part.get("image_url", {})
            if isinstance(image_data, dict):
                url = str(image_data.get("url", "") or "")
                detail = image_data.get("detail")
            else:
                url = str(image_data or "")
                detail = None
            entry: dict[str, Any] = {"type": "input_image", "image_url": url}
            if detail:
                entry["detail"] = detail
            converted.append(entry)
            continue
        text = str(part.get("text", "") or "").strip()
        if text:
            converted.append({"type": "input_text", "text": text})
    return converted or ""
