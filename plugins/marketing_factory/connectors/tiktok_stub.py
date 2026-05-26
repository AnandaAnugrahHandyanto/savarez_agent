"""TikTok connector — LIVE (inbox / MEDIA_UPLOAD mode for photos).

Sends approved drafts as photo posts to the authenticated TikTok account
via the Content Posting API in MEDIA_UPLOAD mode — the post lands in
the user's TikTok drafts/inbox, and the user manually finalizes
publishing inside the TikTok app. This avoids the much heavier app-review
requirements of DIRECT_POST mode.

Required env vars (read lazily inside `publish()`):
  - TIKTOK_ACCESS_TOKEN  — OAuth2 user access token with `video.upload`
                            scope (covers photo posts too as of 2025)

Pre-launch friction (outside code):
  1. Create a TikTok developer app at https://developers.tiktok.com/
  2. Enable Content Posting API; request `video.upload` scope.
  3. Run the OAuth2 PKCE flow to get a user access token; drop it into
     TIKTOK_ACCESS_TOKEN. Tokens are user-scoped — for posting as @pupular
     the token must be issued to that account.
  4. For DIRECT_POST (auto-publish without user tap), apply for the
     "Content Posting" review track. Not implemented here on purpose —
     the friction is high enough that INBOX/MEDIA_UPLOAD is the right
     starting point.

Image-only:
  TikTok publishing requires a media payload — photo or video. Pupular's
  drafts carry pet photos, so this connector targets the photo mode. Drafts
  with no fetchable image url raise ConnectorError, so PublisherAgent
  audit-falls-back to dry_run.

API surface:
  POST https://open.tiktokapis.com/v2/post/publish/content/init/
       body: {
         "post_info": {"title": "...", "description": "..."},
         "source_info": {
           "source": "PULL_FROM_URL",
           "photo_cover_index": 0,
           "photo_images": [image_url]
         },
         "post_mode": "MEDIA_UPLOAD",
         "media_type": "PHOTO"
       }
  → returns {data: {publish_id: "..."}}
  After this call, the user finalizes the post manually inside the TikTok app.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

from plugins.marketing_factory.connectors.base import BaseChannelConnector, ConnectorError

logger = logging.getLogger(__name__)

_REQUIRED_ENV_VARS = ("TIKTOK_ACCESS_TOKEN",)
_PUBLISH_INIT_URL = "https://open.tiktokapis.com/v2/post/publish/content/init/"
_TIKTOK_API_TIMEOUT = 20.0
_TIKTOK_TITLE_MAX = 90
_TIKTOK_DESCRIPTION_MAX = 2200


class TikTokConnector(BaseChannelConnector):
    mode = "live"
    channel = "tiktok"

    def can_publish(self):
        missing = [name for name in _REQUIRED_ENV_VARS if not os.environ.get(name)]
        if missing:
            return False, f"missing env vars {missing}"
        return True, ""

    def publish(self, draft: Dict[str, Any]) -> Dict[str, Any]:
        body = (draft.get("body") or "").strip()
        if not body:
            raise ConnectorError("TikTokConnector: post body is empty")

        image_url = self._extract_image_url(draft)
        if not image_url:
            raise ConnectorError(
                "TikTokConnector: TikTok photo post requires an image — draft has no fetchable images[].url"
            )

        missing = [name for name in _REQUIRED_ENV_VARS if not os.environ.get(name)]
        if missing:
            raise ConnectorError(f"TikTokConnector: missing env vars {missing}")

        token = os.environ["TIKTOK_ACCESS_TOKEN"]
        title = body[:_TIKTOK_TITLE_MAX]
        description = body[:_TIKTOK_DESCRIPTION_MAX]

        payload = {
            "post_info": {"title": title, "description": description},
            "source_info": {
                "source": "PULL_FROM_URL",
                "photo_cover_index": 0,
                "photo_images": [image_url],
            },
            "post_mode": "MEDIA_UPLOAD",
            "media_type": "PHOTO",
        }
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=UTF-8",
        }

        import requests
        try:
            response = requests.post(
                _PUBLISH_INIT_URL, json=payload, headers=headers, timeout=_TIKTOK_API_TIMEOUT
            )
        except requests.RequestException as exc:
            raise ConnectorError(f"TikTokConnector: network error calling publish/init: {exc}") from exc

        if response.status_code >= 400:
            raise ConnectorError(
                f"TikTokConnector: publish/init returned {response.status_code}: {response.text[:300]}"
            )

        try:
            data = response.json() or {}
        except ValueError as exc:
            raise ConnectorError(f"TikTokConnector: publish/init response not JSON: {exc}") from exc

        error_obj = data.get("error") or {}
        if error_obj.get("code") and error_obj.get("code") != "ok":
            raise ConnectorError(
                f"TikTokConnector: publish/init error: {error_obj.get('code')} — {error_obj.get('message')}"
            )

        publish_id = (data.get("data") or {}).get("publish_id")

        return {
            "mode": "live",
            "would_post": True,
            # posted=False because MEDIA_UPLOAD mode requires the user to finalize
            # the post manually inside the TikTok app — the API call alone does NOT
            # publish to the public feed. Setting posted=True here would mislead the
            # dashboard and audit log.
            "posted": False,
            "channel": "tiktok",
            "body": body,
            "payload": {
                "draft_id": draft.get("id"),
                "channel": "tiktok",
                "body": body,
                "publish_id": publish_id,
                "image_url": image_url,
                "post_mode": "MEDIA_UPLOAD",
                "note": "Post landed in user's TikTok drafts/inbox — finalize manually in the app to go live.",
            },
        }

    def _extract_image_url(self, draft: Dict[str, Any]) -> Optional[str]:
        for image in draft.get("images") or []:
            if isinstance(image, dict):
                url = image.get("url")
                if url:
                    return url
        return None
