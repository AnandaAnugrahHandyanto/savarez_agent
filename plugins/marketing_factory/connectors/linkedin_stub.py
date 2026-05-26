"""LinkedIn connector — LIVE.

Posts approved drafts to a LinkedIn page or personal profile via the
LinkedIn `/v2/ugcPosts` API. Text-only posts work without any extra
setup; image posts use the 3-step registerUpload → upload → finalize
flow.

Required env vars (read lazily inside `publish()`):
  - LINKEDIN_ACCESS_TOKEN  — OAuth2 access token with `w_member_social`
                              (personal posts) or `w_organization_social`
                              (org page posts)
  - LINKEDIN_AUTHOR_URN    — the author URN to post as. Examples:
                              urn:li:person:abc123        (personal)
                              urn:li:organization:1234567 (org page)

Pre-launch friction (outside code):
  1. Create a LinkedIn developer app at https://developer.linkedin.com/
  2. For personal posts: request the `w_member_social` scope (no review needed).
  3. For org page posts: get LinkedIn Marketing Developer Platform
     approval AND verify the org's company page admin permissions. Then
     request `w_organization_social` + `r_organization_social`.
  4. Run the OAuth2 flow to obtain a member access token; drop into
     LINKEDIN_ACCESS_TOKEN.
  5. Look up the org URN via `GET /v2/organizationAcls?q=roleAssignee`.

Image posting:
  Three-step flow per LinkedIn docs:
    a) POST /v2/assets?action=registerUpload — returns upload URL + asset URN
    b) PUT the binary to the upload URL (no auth header on this step)
    c) POST /v2/ugcPosts with shareMediaCategory=IMAGE + the asset URN
  Image is best-effort: failure falls back to a text-only post rather
  than failing the entire publish.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

from plugins.marketing_factory.connectors.base import BaseChannelConnector, ConnectorError

logger = logging.getLogger(__name__)

_REQUIRED_ENV_VARS = ("LINKEDIN_ACCESS_TOKEN", "LINKEDIN_AUTHOR_URN")
_UGC_POSTS_URL = "https://api.linkedin.com/v2/ugcPosts"
_REGISTER_UPLOAD_URL = "https://api.linkedin.com/v2/assets?action=registerUpload"
_LI_API_TIMEOUT = 20.0
_IMAGE_FETCH_TIMEOUT = 10.0


class LinkedInConnector(BaseChannelConnector):
    mode = "live"
    channel = "linkedin"

    def can_publish(self):
        missing = [name for name in _REQUIRED_ENV_VARS if not os.environ.get(name)]
        if missing:
            return False, f"missing env vars {missing}"
        return True, ""

    def publish(self, draft: Dict[str, Any]) -> Dict[str, Any]:
        body = (draft.get("body") or "").strip()
        if not body:
            raise ConnectorError("LinkedInConnector: post body is empty")

        missing = [name for name in _REQUIRED_ENV_VARS if not os.environ.get(name)]
        if missing:
            raise ConnectorError(f"LinkedInConnector: missing env vars {missing}")

        token = os.environ["LINKEDIN_ACCESS_TOKEN"]
        author_urn = os.environ["LINKEDIN_AUTHOR_URN"]
        headers = {
            "Authorization": f"Bearer {token}",
            "X-Restli-Protocol-Version": "2.0.0",
            "Content-Type": "application/json",
        }

        media_assets = self._upload_images(draft, author_urn, token)
        share_category = "IMAGE" if media_assets else "NONE"
        media_block: List[Dict[str, Any]] = [
            {"status": "READY", "media": asset_urn} for asset_urn in media_assets
        ]
        payload = {
            "author": author_urn,
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {"text": body},
                    "shareMediaCategory": share_category,
                    "media": media_block,
                }
            },
            "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
        }

        import requests
        try:
            response = requests.post(_UGC_POSTS_URL, json=payload, headers=headers, timeout=_LI_API_TIMEOUT)
        except requests.RequestException as exc:
            raise ConnectorError(f"LinkedInConnector: network error calling /v2/ugcPosts: {exc}") from exc

        if response.status_code >= 400:
            raise ConnectorError(
                f"LinkedInConnector: /v2/ugcPosts returned {response.status_code}: {response.text[:300]}"
            )

        # LinkedIn returns the post URN in either the body's `id` field or the X-RestLi-Id header.
        post_urn = ""
        try:
            data = response.json() or {}
            post_urn = data.get("id") or ""
        except ValueError:
            data = {}
        if not post_urn:
            post_urn = response.headers.get("X-RestLi-Id", "") or response.headers.get("x-restli-id", "")

        return {
            "mode": "live",
            "would_post": True,
            "posted": True,
            "channel": "linkedin",
            "body": body,
            "payload": {
                "draft_id": draft.get("id"),
                "channel": "linkedin",
                "body": body,
                "post_urn": post_urn,
                "media_assets": media_assets,
                "author_urn": author_urn,
            },
        }

    def _upload_images(self, draft: Dict[str, Any], author_urn: str, token: str) -> List[str]:
        """Best-effort image upload. Returns asset URNs of successfully
        uploaded images. Empty list on failure → caller posts text-only."""
        images = draft.get("images") or []
        if not images:
            return []

        import requests

        headers = {
            "Authorization": f"Bearer {token}",
            "X-Restli-Protocol-Version": "2.0.0",
            "Content-Type": "application/json",
        }
        asset_urns: List[str] = []
        for image in images[:9]:  # LinkedIn allows up to 9 media per post
            url = image.get("url") if isinstance(image, dict) else None
            if not url:
                continue
            try:
                fetched = requests.get(url, timeout=_IMAGE_FETCH_TIMEOUT)
                if fetched.status_code >= 400:
                    logger.warning("LinkedInConnector: image fetch %s returned %s", url, fetched.status_code)
                    continue
                content = fetched.content

                register_payload = {
                    "registerUploadRequest": {
                        "recipes": ["urn:li:digitalmediaRecipe:feedshare-image"],
                        "owner": author_urn,
                        "serviceRelationships": [
                            {"relationshipType": "OWNER", "identifier": "urn:li:userGeneratedContent"}
                        ],
                    }
                }
                register_resp = requests.post(
                    _REGISTER_UPLOAD_URL, json=register_payload, headers=headers, timeout=_LI_API_TIMEOUT
                )
                if register_resp.status_code >= 400:
                    logger.warning("LinkedInConnector: registerUpload %s: %s", register_resp.status_code, register_resp.text[:200])
                    continue
                register_data = register_resp.json().get("value") or {}
                asset_urn = register_data.get("asset")
                upload_url = (
                    register_data.get("uploadMechanism", {})
                    .get("com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest", {})
                    .get("uploadUrl")
                )
                if not (asset_urn and upload_url):
                    logger.warning("LinkedInConnector: registerUpload missing asset/uploadUrl: %s", register_resp.text[:200])
                    continue

                # Step b — PUT the binary. No auth header per LinkedIn docs.
                upload_resp = requests.put(upload_url, data=content, timeout=_LI_API_TIMEOUT)
                if upload_resp.status_code >= 400:
                    logger.warning("LinkedInConnector: upload PUT %s: %s", upload_resp.status_code, upload_resp.text[:200])
                    continue
                asset_urns.append(asset_urn)
            except requests.RequestException as exc:
                logger.warning("LinkedInConnector: image upload failed for %s: %s", url, exc)
                continue
            except ValueError as exc:
                logger.warning("LinkedInConnector: non-JSON response during image upload for %s: %s", url, exc)
                continue
        return asset_urns
