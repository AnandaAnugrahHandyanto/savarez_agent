"""Instagram connector — LIVE.

Posts approved drafts to an Instagram Business / Creator account via the
Facebook Graph API. IG publishing is image-required: a draft with no
fetchable image URL cannot post and the connector raises so PublisherAgent
audit-falls-back to dry_run.

Required env vars (read lazily inside `publish()`):
  - IG_USER_ID        — the IG Business account id (NOT the username)
  - IG_ACCESS_TOKEN   — a long-lived page access token with
                        `instagram_basic` + `instagram_content_publish`

Optional:
  - META_GRAPH_VERSION — defaults to "v21.0"

Pre-launch friction (outside code):
  1. Create or convert to an Instagram Business / Creator account.
  2. Connect it to a Facebook Page.
  3. Create a Meta developer app, link the page, request the two
     instagram scopes via App Review.
  4. Exchange the short-lived user token for a long-lived page token
     (~60 days; can be refreshed). Drop into IG_ACCESS_TOKEN.
  5. Find the IG Business account id via Graph API
     `GET /me/accounts?fields=instagram_business_account`.

Image asset hosting:
  IG requires `image_url` to be a public HTTPS URL it can fetch. The
  marketing factory's draft.images[].url field (e.g. RescueGroups CDN
  URLs for Pupular) satisfies this — but if you ever switch to private
  / signed-URL hosting, you'll need to push the asset to a public bucket
  before calling this connector. Caption-only posts are NOT supported by
  the API.

Two-step publish flow:
  a) POST /{ig-user-id}/media       with image_url + caption → container id
  b) POST /{ig-user-id}/media_publish with the container id  → permalinks

Each step has its own potential failure mode (image fetch failed,
container processing failed, etc.) — both are caught and surfaced as
ConnectorError so PublisherAgent can audit + fall back cleanly.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

from plugins.marketing_factory.connectors.base import BaseChannelConnector, ConnectorError

logger = logging.getLogger(__name__)

_REQUIRED_ENV_VARS = ("IG_USER_ID", "IG_ACCESS_TOKEN")
_DEFAULT_GRAPH_VERSION = "v21.0"
_IG_API_TIMEOUT = 30.0


def _graph_base() -> str:
    version = os.environ.get("META_GRAPH_VERSION", _DEFAULT_GRAPH_VERSION)
    return f"https://graph.facebook.com/{version}"


class InstagramConnector(BaseChannelConnector):
    mode = "live"
    channel = "instagram"

    def can_publish(self):
        missing = [name for name in _REQUIRED_ENV_VARS if not os.environ.get(name)]
        if missing:
            return False, f"missing env vars {missing}"
        return True, ""

    def publish(self, draft: Dict[str, Any]) -> Dict[str, Any]:
        body = (draft.get("body") or "").strip()
        if not body:
            raise ConnectorError("InstagramConnector: caption is empty")

        image_url = self._extract_image_url(draft)
        if not image_url:
            raise ConnectorError(
                "InstagramConnector: IG requires an image — draft has no fetchable images[].url"
            )

        missing = [name for name in _REQUIRED_ENV_VARS if not os.environ.get(name)]
        if missing:
            raise ConnectorError(f"InstagramConnector: missing env vars {missing}")

        ig_user_id = os.environ["IG_USER_ID"]
        token = os.environ["IG_ACCESS_TOKEN"]

        import requests

        # Step 1 — create the media container.
        try:
            container = requests.post(
                f"{_graph_base()}/{ig_user_id}/media",
                params={
                    "image_url": image_url,
                    "caption": body,
                    "access_token": token,
                },
                timeout=_IG_API_TIMEOUT,
            )
        except requests.RequestException as exc:
            raise ConnectorError(f"InstagramConnector: network error creating container: {exc}") from exc

        if container.status_code >= 400:
            raise ConnectorError(
                f"InstagramConnector: container creation returned {container.status_code}: {container.text[:300]}"
            )
        try:
            container_id = container.json().get("id")
        except ValueError as exc:
            raise ConnectorError(f"InstagramConnector: container response not JSON: {exc}") from exc
        if not container_id:
            raise ConnectorError(f"InstagramConnector: container response missing id: {container.text[:200]}")

        # Step 2 — publish the container.
        try:
            publish_resp = requests.post(
                f"{_graph_base()}/{ig_user_id}/media_publish",
                params={"creation_id": container_id, "access_token": token},
                timeout=_IG_API_TIMEOUT,
            )
        except requests.RequestException as exc:
            raise ConnectorError(f"InstagramConnector: network error publishing container: {exc}") from exc

        if publish_resp.status_code >= 400:
            raise ConnectorError(
                f"InstagramConnector: media_publish returned {publish_resp.status_code}: {publish_resp.text[:300]}"
            )
        try:
            published_id = publish_resp.json().get("id")
        except ValueError as exc:
            raise ConnectorError(f"InstagramConnector: media_publish response not JSON: {exc}") from exc

        return {
            "mode": "live",
            "would_post": True,
            "posted": True,
            "channel": "instagram",
            "body": body,
            "payload": {
                "draft_id": draft.get("id"),
                "channel": "instagram",
                "body": body,
                "media_id": published_id,
                "container_id": container_id,
                "image_url": image_url,
            },
        }

    def _extract_image_url(self, draft: Dict[str, Any]) -> Optional[str]:
        for image in draft.get("images") or []:
            if isinstance(image, dict):
                url = image.get("url")
                if url:
                    return url
        return None
