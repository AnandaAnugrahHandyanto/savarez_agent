"""Fanhearts feed-image API integration helpers.

This module is intentionally small and dependency-light so the Discord gateway can
forward uploaded images without blocking the main agent flow, and a cron/script
worker can later process queued jobs. The Fanhearts API endpoints are being built
in parallel, so all request/response parsing is tolerant of the expected field
name variants.
"""

from __future__ import annotations

import asyncio
import json
import logging
import mimetypes
import os
import tempfile
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urljoin

import httpx

logger = logging.getLogger(__name__)

DEFAULT_API_BASE_URL = "https://dev-api.fanhearts.com"
DEFAULT_LIMIT = 1
DEFAULT_TIMEOUT_SECONDS = 60.0

_IMAGE_ID_KEYS = ("id", "feed_image_id", "feedImageId")
_IMAGE_URL_KEYS = ("image_url", "imageUrl", "input_image_url", "inputImageUrl", "url")
_PROMPT_KEYS = ("prompt", "user_prompt", "userPrompt", "transform_prompt", "transformPrompt")


def env_enabled() -> bool:
    """Return whether Discord -> Fanhearts forwarding is enabled."""

    return os.getenv("FANHEARTS_FEED_IMAGES_ENABLED", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def env_api_base_url() -> str:
    return os.getenv("FANHEARTS_FEED_IMAGES_API_BASE_URL", DEFAULT_API_BASE_URL).strip() or DEFAULT_API_BASE_URL


def env_jwt() -> str:
    return os.getenv("FANHEARTS_FEED_IMAGES_JWT", "").strip()


def _headers(jwt: str) -> dict[str, str]:
    if not jwt:
        raise ValueError("FANHEARTS_FEED_IMAGES_JWT is required")
    return {"Authorization": f"Bearer {jwt}"}


def _endpoint(api_base_url: str, path: str) -> str:
    base = api_base_url.rstrip("/") + "/"
    return urljoin(base, path.lstrip("/"))


def _first_present(data: Mapping[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        value = data.get(key)
        if value not in (None, ""):
            return value
    return None


def _extract_jobs(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []
    for key in ("feed_images", "feedImages", "jobs", "data", "items"):
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    return []


async def post_discord_feed_image(
    *,
    image_path: str,
    message_text: str,
    source: Mapping[str, Any],
    api_base_url: str | None = None,
    jwt: str | None = None,
) -> dict[str, Any]:
    """POST a Discord image attachment to Fanhearts /feed_images.

    The endpoint is not implemented yet, so this sends a conservative multipart
    body with the image, prompt text, source label, and JSON metadata. The API can
    ignore unknown fields while preserving all Discord routing data.
    """

    api_base_url = api_base_url or env_api_base_url()
    jwt = jwt if jwt is not None else env_jwt()
    image = Path(image_path).expanduser()
    if not image.exists():
        raise FileNotFoundError(str(image))

    metadata = {
        "platform": source.get("platform") or "discord",
        "discord_channel_id": source.get("chat_id") or source.get("channel_id"),
        "discord_thread_id": source.get("thread_id"),
        "discord_message_id": source.get("message_id"),
        "discord_user_id": source.get("user_id"),
        "discord_user_name": source.get("user_name"),
    }
    content_type = mimetypes.guess_type(str(image))[0] or "application/octet-stream"
    data = {
        "source": "discord",
        "prompt": message_text or "",
        "metadata": json.dumps(metadata, ensure_ascii=False),
    }

    with image.open("rb") as fh:
        files = {"image": (image.name, fh, content_type)}
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT_SECONDS) as client:
            response = await client.post(
                _endpoint(api_base_url, "/feed_images"),
                headers=_headers(jwt or ""),
                data=data,
                files=files,
            )
    response.raise_for_status()
    try:
        return response.json()
    except Exception:
        return {"ok": True, "status_code": response.status_code, "text": response.text}


async def _download_image(client: httpx.AsyncClient, url: str, workdir: Path) -> Path:
    response = await client.get(url)
    response.raise_for_status()
    suffix = Path(url.split("?", 1)[0]).suffix.lower()
    if suffix not in {".jpg", ".jpeg", ".png", ".webp", ".gif"}:
        suffix = ".png"
    path = workdir / f"input{suffix}"
    path.write_bytes(response.content)
    return path


def build_transform_prompt(image_path: Path, user_prompt: str) -> str:
    """Build the GPT Image 2 prompt for a queued feed image.

    Current Hermes' FAL GPT Image 2 backend is text-to-image, so this prompt is
    designed to create a transformed output from the user's instruction while
    the original image is kept as job context. If/when the backend supports
    img2img, this function remains the text prompt source.
    """

    base = (user_prompt or "").strip()
    if not base:
        base = "Create a polished social-feed image inspired by the uploaded image."
    return (
        f"{base}\n\n"
        "Create a high-quality, safe, social-media-ready image. Preserve the likely "
        "subject intent and composition implied by the uploaded source image. Use "
        "clean lighting, crisp details, natural colors, and no watermarks."
    )


def generate_with_gpt_image_2(prompt: str, output_dir: Path) -> tuple[Path | None, str | None]:
    """Generate an image through Hermes' FAL gpt-image-2 integration.

    Returns ``(local_output_path, remote_image_url)``. The local path may be None
    when the remote URL could not be downloaded; the PUT updater still sends the
    remote URL so the Fanhearts API can fetch it server-side.
    """

    from tools import image_generation_tool as image_tool

    original_resolver = image_tool._resolve_fal_model
    image_tool._resolve_fal_model = lambda: ("fal-ai/gpt-image-2", image_tool.FAL_MODELS["fal-ai/gpt-image-2"])
    try:
        raw = image_tool.image_generate_tool(prompt=prompt, aspect_ratio="square")
    finally:
        image_tool._resolve_fal_model = original_resolver

    payload = json.loads(raw)
    if not payload.get("success"):
        raise RuntimeError(payload.get("error") or "gpt-image-2 generation failed")
    image_url = payload.get("image")
    if not image_url:
        raise RuntimeError("gpt-image-2 returned no image URL")

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "completed_image.png"
    try:
        with httpx.Client(timeout=DEFAULT_TIMEOUT_SECONDS) as client:
            response = client.get(image_url)
            response.raise_for_status()
            output_path.write_bytes(response.content)
        return output_path, image_url
    except Exception as exc:
        logger.warning("Could not download generated image %s: %s", image_url, exc)
        return None, image_url


async def _mark_failed(
    client: httpx.AsyncClient,
    *,
    api_base_url: str,
    jwt: str,
    feed_image_id: str,
    error: str,
) -> None:
    try:
        response = await client.put(
            _endpoint(api_base_url, f"/feed_images/{feed_image_id}"),
            headers=_headers(jwt),
            data={"status": "failed", "error": error[:2000]},
        )
        response.raise_for_status()
    except Exception:
        logger.exception("Failed to mark feed image %s as failed", feed_image_id)


async def process_queued_feed_images(
    *,
    api_base_url: str | None = None,
    jwt: str | None = None,
    limit: int = DEFAULT_LIMIT,
    workdir: str | Path | None = None,
) -> dict[str, Any]:
    """Process queued Fanhearts feed-image jobs one by one."""

    api_base_url = api_base_url or env_api_base_url()
    jwt = jwt if jwt is not None else env_jwt()
    if not jwt:
        return {"processed": 0, "completed": 0, "failed": 0, "skipped": 0, "error": "missing FANHEARTS_FEED_IMAGES_JWT"}

    root = Path(workdir) if workdir is not None else Path(tempfile.gettempdir()) / "hermes-feed-images"
    root.mkdir(parents=True, exist_ok=True)
    summary = {"processed": 0, "completed": 0, "failed": 0, "skipped": 0}

    async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT_SECONDS) as client:
        response = await client.get(
            _endpoint(api_base_url, "/feed_images/status=queued"),
            headers=_headers(jwt),
            params={"limit": int(limit)},
        )
        response.raise_for_status()
        jobs = _extract_jobs(response.json())[: int(limit)]

        for job in jobs:
            feed_image_id = str(_first_present(job, _IMAGE_ID_KEYS) or "")
            image_url = str(_first_present(job, _IMAGE_URL_KEYS) or "")
            user_prompt = str(_first_present(job, _PROMPT_KEYS) or "")
            if not feed_image_id or not image_url:
                summary["skipped"] += 1
                continue

            summary["processed"] += 1
            job_dir = root / feed_image_id
            job_dir.mkdir(parents=True, exist_ok=True)
            try:
                claim = await client.post(
                    _endpoint(api_base_url, f"/feed_images/{feed_image_id}/claim"),
                    headers=_headers(jwt),
                )
                if claim.status_code in {409, 423}:
                    summary["skipped"] += 1
                    continue
                claim.raise_for_status()

                input_path = await _download_image(client, image_url, job_dir)
                transform_prompt = build_transform_prompt(input_path, user_prompt)
                output_path, output_url = generate_with_gpt_image_2(transform_prompt, job_dir)

                data = {
                    "status": "completed",
                    "transform_prompt": transform_prompt,
                    "output_image_url": output_url or "",
                    "model": "fal-ai/gpt-image-2",
                }
                files = None
                file_handle = None
                try:
                    if output_path and output_path.exists():
                        file_handle = output_path.open("rb")
                        files = {"completed_image": (output_path.name, file_handle, "image/png")}
                    update = await client.put(
                        _endpoint(api_base_url, f"/feed_images/{feed_image_id}"),
                        headers=_headers(jwt),
                        data=data,
                        files=files,
                    )
                    update.raise_for_status()
                finally:
                    if file_handle:
                        file_handle.close()
                summary["completed"] += 1
            except Exception as exc:
                summary["failed"] += 1
                await _mark_failed(
                    client,
                    api_base_url=api_base_url,
                    jwt=jwt,
                    feed_image_id=feed_image_id,
                    error=str(exc),
                )

    return summary


def process_queued_feed_images_sync(**kwargs: Any) -> dict[str, Any]:
    return asyncio.run(process_queued_feed_images(**kwargs))
