"""
WeChat platform transport layer — HTTP API, CDN upload/download, AES encryption.

Handles all network communication with the WeChat iLink Bot API and CDN.
Implements protocol requirements from openclaw-weixin SDK 2.1.x:
  - iLink-App-Id and iLink-App-ClientVersion headers on all requests
  - X-WECHAT-UIN random header
  - AES-128-ECB media encryption/decryption
  - CDN upload with retry and exponential backoff
  - upload_full_url priority over upload_param
"""

import asyncio
import base64
import hashlib
import logging
import os
import struct
import urllib.parse
import uuid
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False
    httpx = None  # type: ignore[assignment]

try:
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    from cryptography.hazmat.primitives import padding as crypto_padding
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_BASE_URL = "https://ilinkai.weixin.qq.com"
CDN_BASE_URL = "https://novac2c.cdn.weixin.qq.com/c2c"
ADAPTER_VERSION = "0.2.0"

# Upload media type constants
UPLOAD_MEDIA_IMAGE = 1
UPLOAD_MEDIA_VIDEO = 2
UPLOAD_MEDIA_FILE = 3
UPLOAD_MEDIA_VOICE = 4

# CDN limits
MEDIA_MAX_BYTES = 100 * 1024 * 1024  # 100 MB
CDN_UPLOAD_MAX_RETRIES = 3


def check_wechat_requirements() -> bool:
    """Check if WeChat adapter dependencies are available."""
    if not HTTPX_AVAILABLE:
        logger.warning("WeChat: httpx not installed. Run: pip install httpx")
        return False
    if not CRYPTO_AVAILABLE:
        logger.warning("WeChat: cryptography not installed. Run: pip install cryptography")
        return False
    return True


# ---------------------------------------------------------------------------
# iLink header computation (SDK 2.1.1+)
# ---------------------------------------------------------------------------

def _build_client_version(version: str) -> int:
    """Encode version as uint32: 0x00MMNNPP (major<<16 | minor<<8 | patch).

    e.g. "0.2.0" -> 0x00000200 = 512
    Matches the SDK's buildClientVersion() in api.ts.
    """
    parts = version.split(".")
    major = int(parts[0]) if len(parts) > 0 else 0
    minor = int(parts[1]) if len(parts) > 1 else 0
    patch = int(parts[2]) if len(parts) > 2 else 0
    return ((major & 0xFF) << 16) | ((minor & 0xFF) << 8) | (patch & 0xFF)


def _build_channel_version() -> str:
    """Dynamic channel_version for base_info (not hardcoded)."""
    return f"hermes-wechat/{ADAPTER_VERSION}"


# ---------------------------------------------------------------------------
# AES-128-ECB crypto (matches SDK aes-ecb.ts)
# ---------------------------------------------------------------------------

def aes_ecb_encrypt(plaintext: bytes, key: bytes) -> bytes:
    """Encrypt with AES-128-ECB + PKCS7 padding."""
    padder = crypto_padding.PKCS7(128).padder()
    padded = padder.update(plaintext) + padder.finalize()
    cipher = Cipher(algorithms.AES(key), modes.ECB())
    enc = cipher.encryptor()
    return enc.update(padded) + enc.finalize()


def aes_ecb_decrypt(ciphertext: bytes, key: bytes) -> bytes:
    """Decrypt AES-128-ECB with PKCS7 padding."""
    cipher = Cipher(algorithms.AES(key), modes.ECB())
    dec = cipher.decryptor()
    padded = dec.update(ciphertext) + dec.finalize()
    unpadder = crypto_padding.PKCS7(128).unpadder()
    return unpadder.update(padded) + unpadder.finalize()


def aes_ecb_padded_size(plaintext_size: int) -> int:
    """Compute AES-128-ECB ciphertext size (PKCS7 to 16-byte boundary)."""
    return ((plaintext_size + 1 + 15) // 16) * 16


def parse_aes_key(aes_key_b64: str) -> bytes:
    """Parse CDNMedia.aes_key into a raw 16-byte key.

    Two encodings exist in the wild:
      - base64(raw 16 bytes)           -> images
      - base64(hex string of 16 bytes) -> file / voice / video
    """
    decoded = base64.b64decode(aes_key_b64)
    if len(decoded) == 16:
        return decoded
    if len(decoded) == 32:
        try:
            hex_str = decoded.decode("ascii")
            if all(c in "0123456789abcdefABCDEF" for c in hex_str):
                return bytes.fromhex(hex_str)
        except (UnicodeDecodeError, ValueError):
            pass
    raise ValueError(
        f"aes_key must decode to 16 raw bytes or 32-char hex string, got {len(decoded)} bytes"
    )


# ---------------------------------------------------------------------------
# MIME helpers
# ---------------------------------------------------------------------------

_MIME_MAP = {
    ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
    ".gif": "image/gif", ".webp": "image/webp", ".bmp": "image/bmp",
    ".mp4": "video/mp4", ".mov": "video/quicktime", ".avi": "video/x-msvideo",
    ".mkv": "video/x-matroska", ".webm": "video/webm",
    ".pdf": "application/pdf", ".doc": "application/msword",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".zip": "application/zip", ".txt": "text/plain",
    ".wav": "audio/wav", ".mp3": "audio/mpeg", ".ogg": "audio/ogg",
    ".opus": "audio/opus", ".m4a": "audio/mp4",
}


def mime_from_path(file_path: str) -> str:
    ext = Path(file_path).suffix.lower()
    return _MIME_MAP.get(ext, "application/octet-stream")


# ---------------------------------------------------------------------------
# WeChatTransport
# ---------------------------------------------------------------------------

class WeChatTransport:
    """Handles all HTTP communication with the WeChat iLink Bot API and CDN.

    Sends required iLink headers on all requests (SDK 2.1.1+):
      - iLink-App-Id
      - iLink-App-ClientVersion (uint32 encoded)
      - X-WECHAT-UIN (random per-request)
      - AuthorizationType: ilink_bot_token
    """

    def __init__(
        self,
        token: str,
        base_url: str = DEFAULT_BASE_URL,
        cdn_base_url: str = CDN_BASE_URL,
        ilink_app_id: str = "bot",
        ilink_client_version: Optional[int] = None,
    ):
        self._token = token
        self._base_url = base_url.rstrip("/")
        self._cdn_base_url = cdn_base_url.rstrip("/")
        self._ilink_app_id = ilink_app_id
        self._ilink_client_version = (
            ilink_client_version
            if ilink_client_version is not None
            else _build_client_version(ADAPTER_VERSION)
        )
        self._http: Optional["httpx.AsyncClient"] = None

    async def open(self) -> None:
        """Initialize the HTTP client."""
        self._http = httpx.AsyncClient(
            timeout=httpx.Timeout(60.0, connect=10.0),
            follow_redirects=True,
        )

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._http:
            await self._http.aclose()
            self._http = None

    @property
    def is_open(self) -> bool:
        return self._http is not None

    # -- Header construction ------------------------------------------------

    def _build_common_headers(self) -> Dict[str, str]:
        """Headers included on every API request (iLink 2.1.1+ protocol)."""
        return {
            "iLink-App-Id": self._ilink_app_id,
            "iLink-App-ClientVersion": str(self._ilink_client_version),
        }

    def _build_headers(self) -> Dict[str, str]:
        """Full header set for POST API requests."""
        rand_uint32 = struct.unpack(">I", os.urandom(4))[0]
        uin_b64 = base64.b64encode(str(rand_uint32).encode()).decode()

        headers = {
            "Content-Type": "application/json",
            "AuthorizationType": "ilink_bot_token",
            "X-WECHAT-UIN": uin_b64,
            **self._build_common_headers(),
        }
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        return headers

    # -- API methods --------------------------------------------------------

    async def api_fetch(self, endpoint: str, body: dict, timeout_s: float = 15) -> dict:
        """POST JSON to a WeChat API endpoint with all required headers."""
        if not self._http:
            raise RuntimeError("HTTP client not initialized")

        url = f"{self._base_url}/{endpoint}"
        payload = {**body, "base_info": {"channel_version": _build_channel_version()}}
        headers = self._build_headers()

        resp = await self._http.post(url, json=payload, headers=headers, timeout=timeout_s)
        if resp.status_code >= 400:
            raise RuntimeError(f"WeChat API {endpoint} HTTP {resp.status_code}: {resp.text[:200]}")
        return resp.json()

    async def get_updates(self, get_updates_buf: str, timeout_s: float = 40) -> dict:
        """Long-poll for inbound messages."""
        return await self.api_fetch("ilink/bot/getupdates", {
            "get_updates_buf": get_updates_buf,
        }, timeout_s=timeout_s)

    async def send_message(self, msg_body: dict) -> dict:
        """Send a message downstream."""
        return await self.api_fetch("ilink/bot/sendmessage", msg_body)

    async def get_config(self, user_id: str, context_token: str = "") -> dict:
        """Fetch bot config (includes typing_ticket) for a user."""
        return await self.api_fetch("ilink/bot/getconfig", {
            "ilink_user_id": user_id,
            "context_token": context_token,
        }, timeout_s=10)

    async def send_typing(self, user_id: str, ticket: str) -> None:
        """Send a typing indicator."""
        try:
            await self.api_fetch("ilink/bot/sendtyping", {
                "ilink_user_id": user_id,
                "typing_ticket": ticket,
                "status": 1,
            }, timeout_s=10)
        except Exception:
            pass  # Non-critical

    # -- CDN download -------------------------------------------------------

    async def cdn_download_decrypt(
        self,
        encrypted_query_param: str,
        aes_key_b64: str,
        full_url: str = "",
    ) -> bytes:
        """Download from WeChat CDN and AES-128-ECB decrypt.

        If full_url is provided, it is used directly (SDK 2.1.x forward-compat).
        Otherwise, the URL is built from encrypted_query_param.
        """
        if not self._http:
            raise RuntimeError("HTTP client not initialized")
        key = parse_aes_key(aes_key_b64)
        if full_url:
            url = full_url
        else:
            url = (
                f"{self._cdn_base_url}/download"
                f"?encrypted_query_param={urllib.parse.quote(encrypted_query_param, safe='')}"
            )
        resp = await self._http.get(url, timeout=60)
        resp.raise_for_status()
        return aes_ecb_decrypt(resp.content, key)

    async def cdn_download_plain(self, encrypted_query_param: str, full_url: str = "") -> bytes:
        """Download from WeChat CDN without decryption."""
        if not self._http:
            raise RuntimeError("HTTP client not initialized")
        if full_url:
            url = full_url
        else:
            url = (
                f"{self._cdn_base_url}/download"
                f"?encrypted_query_param={urllib.parse.quote(encrypted_query_param, safe='')}"
            )
        resp = await self._http.get(url, timeout=60)
        resp.raise_for_status()
        return resp.content

    # -- CDN upload ---------------------------------------------------------

    async def cdn_upload(
        self,
        file_path: str,
        to_user_id: str,
        media_type: int,
    ) -> Dict[str, Any]:
        """Encrypt and upload a file to WeChat CDN.

        Returns dict with: filekey, download_param, aeskey, plaintext_size,
        ciphertext_size, raw_md5.

        Improvements over v0.1:
          - upload_full_url takes precedence over upload_param (SDK 2.1.x)
          - Exponential backoff between retry attempts
          - Proper x-encrypted-param header extraction
        """
        if not self._http:
            raise RuntimeError("HTTP client not initialized")

        file_size_check = Path(file_path).stat().st_size
        if file_size_check > MEDIA_MAX_BYTES:
            raise ValueError(f"File too large: {file_size_check} bytes (max {MEDIA_MAX_BYTES})")

        plaintext = Path(file_path).read_bytes()
        raw_size = len(plaintext)
        raw_md5 = hashlib.md5(plaintext).hexdigest()
        file_size = aes_ecb_padded_size(raw_size)
        filekey = os.urandom(16).hex()
        aes_key = os.urandom(16)

        # Get upload URL
        upload_resp = await self.api_fetch("ilink/bot/getuploadurl", {
            "filekey": filekey,
            "media_type": media_type,
            "to_user_id": to_user_id,
            "rawsize": raw_size,
            "rawfilemd5": raw_md5,
            "filesize": file_size,
            "no_need_thumb": True,
            "aeskey": aes_key.hex(),
        })

        # upload_full_url takes precedence (SDK 2.1.x change)
        upload_full_url = (upload_resp.get("upload_full_url") or "").strip()
        upload_param = upload_resp.get("upload_param")

        if upload_full_url:
            cdn_url = upload_full_url
        elif upload_param:
            cdn_url = (
                f"{self._cdn_base_url}/upload"
                f"?encrypted_query_param={urllib.parse.quote(upload_param, safe='')}"
                f"&filekey={urllib.parse.quote(filekey, safe='')}"
            )
        else:
            raise RuntimeError("getUploadUrl returned no upload URL (need upload_full_url or upload_param)")

        # Encrypt
        ciphertext = aes_ecb_encrypt(plaintext, aes_key)

        # Upload with retry + exponential backoff
        download_param = None
        last_error = None
        for attempt in range(1, CDN_UPLOAD_MAX_RETRIES + 1):
            try:
                resp = await self._http.post(
                    cdn_url,
                    content=ciphertext,
                    headers={"Content-Type": "application/octet-stream"},
                    timeout=60,
                )
                if 400 <= resp.status_code < 500:
                    cdn_err = resp.headers.get("x-error-message", resp.text[:200])
                    raise RuntimeError(f"CDN upload client error {resp.status_code}: {cdn_err}")
                if resp.status_code != 200:
                    cdn_err = resp.headers.get("x-error-message", f"status {resp.status_code}")
                    size_kb = raw_size // 1024
                    if "timeout" in cdn_err.lower():
                        raise RuntimeError(
                            f"CDN upload timeout for {size_kb}KB file. "
                            f"Try compressing the file."
                        )
                    raise RuntimeError(f"CDN upload server error: {cdn_err}")

                download_param = resp.headers.get("x-encrypted-param")
                if not download_param:
                    raise RuntimeError("CDN response missing x-encrypted-param header")
                break
            except Exception as e:
                last_error = e
                if "client error" in str(e):
                    raise
                if attempt < CDN_UPLOAD_MAX_RETRIES:
                    delay = min(2 ** attempt, 10)
                    logger.warning("[WeChat] CDN upload attempt %d failed, retrying in %ds: %s", attempt, delay, e)
                    await asyncio.sleep(delay)
                else:
                    logger.error("[WeChat] CDN upload failed after %d attempts: %s", CDN_UPLOAD_MAX_RETRIES, e)

        if not download_param:
            raise last_error or RuntimeError(f"CDN upload failed after {CDN_UPLOAD_MAX_RETRIES} attempts")

        return {
            "filekey": filekey,
            "download_param": download_param,
            "aeskey": aes_key.hex(),
            "plaintext_size": raw_size,
            "ciphertext_size": file_size,
            "raw_md5": raw_md5,
        }

    # -- File download helper -----------------------------------------------

    async def download_remote_file(self, url: str, cache_dir: Path) -> Tuple[str, str]:
        """Download a remote URL to cache_dir. Returns (local_path, extension)."""
        if not self._http:
            raise RuntimeError("HTTP client not initialized")
        resp = await self._http.get(url, timeout=60, follow_redirects=True)
        resp.raise_for_status()

        ct = resp.headers.get("content-type", "")
        ext = ".bin"
        if "jpeg" in ct or "jpg" in ct:
            ext = ".jpg"
        elif "png" in ct:
            ext = ".png"
        elif "gif" in ct:
            ext = ".gif"
        elif "webp" in ct:
            ext = ".webp"
        elif "mp4" in ct:
            ext = ".mp4"
        else:
            url_ext = Path(url.split("?")[0]).suffix.lower()
            if url_ext in _MIME_MAP:
                ext = url_ext

        filename = f"wx_dl_{uuid.uuid4().hex[:12]}{ext}"
        filepath = cache_dir / filename
        filepath.write_bytes(resp.content)
        return str(filepath), ext
