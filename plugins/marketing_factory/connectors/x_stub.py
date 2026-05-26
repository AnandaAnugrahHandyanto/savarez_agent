"""X (Twitter) connector — LIVE.

Posts approved drafts to X via the v2 /2/tweets endpoint using OAuth 1.0a
User Context (the simplest auth for a single-user marketing tool managing
one X account, e.g. @pupular).

Required env vars (read lazily inside `publish()` so the module imports
cleanly without creds present):
  - X_API_KEY
  - X_API_SECRET
  - X_ACCESS_TOKEN
  - X_ACCESS_TOKEN_SECRET

Generate these at https://developer.twitter.com/ → your app → Keys and Tokens.
The access token + secret must be issued for the account that will post (i.e.
log in as @pupular before generating the access token).

Image attachment: if the draft carries `images: [{url: ...}]` (e.g. Pupular's
RescueGroups library URLs), the connector fetches the image, uploads it via
the v1.1 /media/upload endpoint, and attaches the returned media_id to the
tweet. Image fetch/upload failures degrade gracefully to a text-only post.

Activation: this file is imported and registered in `connectors/__init__.py`.
The connector only posts when:
  - `channel_modes["x"] == "live"` on the brand profile, AND
  - All four env vars are present.
Otherwise the PublisherAgent falls back to DryRunConnector (audited).
"""

from __future__ import annotations

import io
import logging
import os
from typing import Any, Dict, List, Optional

from plugins.marketing_factory.connectors.base import BaseChannelConnector, ConnectorError

logger = logging.getLogger(__name__)

_TWEETS_URL = "https://api.twitter.com/2/tweets"
_MEDIA_UPLOAD_URL = "https://upload.twitter.com/1.1/media/upload.json"
_REQUIRED_ENV_VARS = ("X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_TOKEN_SECRET")
_IMAGE_FETCH_TIMEOUT = 10.0
_X_API_TIMEOUT = 15.0
_MAX_IMAGE_BYTES = 5 * 1024 * 1024  # X simple-upload limit for images


class XConnector(BaseChannelConnector):
    mode = "live"
    channel = "x"

    def can_publish(self):
        missing = [name for name in _REQUIRED_ENV_VARS if not os.environ.get(name)]
        if missing:
            return False, f"missing env vars {missing}"
        return True, ""

    def publish(self, draft: Dict[str, Any]) -> Dict[str, Any]:
        body = (draft.get("body") or "").strip()
        if not body:
            raise ConnectorError("XConnector: draft body is empty")
        if len(body) > 280:
            raise ConnectorError(f"XConnector: body is {len(body)} chars (>280); safety check should have caught this")

        auth = self._build_auth()  # raises ConnectorError if creds missing
        media_ids = self._upload_images(draft, auth)
        payload: Dict[str, Any] = {"text": body}
        if media_ids:
            payload["media"] = {"media_ids": media_ids}

        import requests  # local import keeps test-time imports cheap

        try:
            response = requests.post(_TWEETS_URL, json=payload, auth=auth, timeout=_X_API_TIMEOUT)
        except requests.RequestException as exc:
            raise ConnectorError(f"XConnector: network error calling /2/tweets: {exc}") from exc

        if response.status_code >= 400:
            raise ConnectorError(
                f"XConnector: /2/tweets returned {response.status_code}: {response.text[:300]}"
            )

        try:
            data = response.json().get("data") or {}
        except ValueError as exc:
            raise ConnectorError(f"XConnector: /2/tweets returned non-JSON: {exc}") from exc

        tweet_id = data.get("id")
        return {
            "mode": "live",
            "would_post": True,
            "posted": True,
            "channel": "x",
            "body": body,
            "payload": {
                "draft_id": draft.get("id"),
                "channel": "x",
                "body": body,
                "tweet_id": tweet_id,
                "tweet_url": f"https://x.com/i/web/status/{tweet_id}" if tweet_id else None,
                "media_ids": media_ids,
            },
        }

    def _build_auth(self):
        """Construct OAuth1 auth or raise ConnectorError if any cred is missing.
        Caller catches ConnectorError → PublisherAgent falls back to dry_run.
        """
        missing = [name for name in _REQUIRED_ENV_VARS if not os.environ.get(name)]
        if missing:
            raise ConnectorError(f"XConnector: missing env vars {missing}")
        try:
            from requests_oauthlib import OAuth1
        except ImportError as exc:
            raise ConnectorError("XConnector: requests_oauthlib not installed") from exc
        return OAuth1(
            os.environ["X_API_KEY"],
            client_secret=os.environ["X_API_SECRET"],
            resource_owner_key=os.environ["X_ACCESS_TOKEN"],
            resource_owner_secret=os.environ["X_ACCESS_TOKEN_SECRET"],
            signature_type="auth_header",
        )

    def _upload_images(self, draft: Dict[str, Any], auth) -> List[str]:
        """Best-effort image upload. Any per-image failure logs and is skipped;
        the tweet still posts text-only rather than failing the whole publish.
        """
        images = draft.get("images") or []
        if not images:
            return []

        import requests

        media_ids: List[str] = []
        for image in images[:4]:  # X allows up to 4 images per tweet
            url = image.get("url") if isinstance(image, dict) else None
            if not url:
                continue
            try:
                fetched = requests.get(url, timeout=_IMAGE_FETCH_TIMEOUT, stream=True)
                if fetched.status_code >= 400:
                    logger.warning("XConnector: image fetch %s returned %s", url, fetched.status_code)
                    continue
                content = fetched.content
                if len(content) > _MAX_IMAGE_BYTES:
                    logger.warning("XConnector: image %s is %d bytes (>%d); skipping", url, len(content), _MAX_IMAGE_BYTES)
                    continue
                upload_resp = requests.post(
                    _MEDIA_UPLOAD_URL,
                    files={"media": ("image", io.BytesIO(content))},
                    auth=auth,
                    timeout=_X_API_TIMEOUT,
                )
                if upload_resp.status_code >= 400:
                    logger.warning("XConnector: media/upload returned %s: %s", upload_resp.status_code, upload_resp.text[:200])
                    continue
                media_id = upload_resp.json().get("media_id_string")
                if media_id:
                    media_ids.append(media_id)
            except requests.RequestException as exc:
                logger.warning("XConnector: image upload failed for %s: %s", url, exc)
                continue
            except ValueError as exc:
                logger.warning("XConnector: media/upload returned non-JSON for %s: %s", url, exc)
                continue
        return media_ids
