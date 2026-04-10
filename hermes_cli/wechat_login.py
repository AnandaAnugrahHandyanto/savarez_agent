"""WeChat QR login flow for Hermes CLI."""

from __future__ import annotations

import base64
import json
import os
import struct
import time
from pathlib import Path
from typing import Any, Dict

import httpx

from hermes_cli.config import get_hermes_home
from hermes_constants import display_hermes_home

DEFAULT_BASE_URL = "https://ilinkai.weixin.qq.com"
DEFAULT_BOT_TYPE = "3"


def _random_uin_header() -> str:
    rand_uint32 = struct.unpack(">I", os.urandom(4))[0]
    return base64.b64encode(str(rand_uint32).encode()).decode()


def _headers() -> dict[str, str]:
    return {
        "Content-Type": "application/json",
        "X-WECHAT-UIN": _random_uin_header(),
    }


def _accounts_dir() -> Path:
    path = get_hermes_home() / "weixin" / "accounts"
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_credentials(account_id: str, token: str, base_url: str, user_id: str = "") -> Path:
    """Save WeChat QR login credentials under the active Hermes home."""
    accounts_dir = _accounts_dir()
    normalized = account_id.strip().lower().replace("@", "-").replace(".", "-")

    data: Dict[str, Any] = {
        "token": token,
        "baseUrl": base_url,
        "savedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    if user_id:
        data["userId"] = user_id

    filepath = accounts_dir / f"{normalized}.json"
    filepath.write_text(json.dumps(data, indent=2), encoding="utf-8")
    filepath.chmod(0o600)

    index_path = accounts_dir.parent / "accounts.json"
    index_path.write_text(json.dumps([normalized], indent=2), encoding="utf-8")
    index_path.chmod(0o600)
    return filepath


async def fetch_qr_code(client: httpx.AsyncClient, base_url: str) -> dict[str, Any]:
    """Request a QR code from the official WeChat iLink API."""
    url = f"{base_url.rstrip('/')}/ilink/bot/get_bot_qrcode?bot_type={DEFAULT_BOT_TYPE}"
    resp = await client.get(url, headers=_headers(), timeout=15)
    resp.raise_for_status()
    return resp.json()


async def poll_qr_status(client: httpx.AsyncClient, base_url: str, qrcode: str) -> dict[str, Any]:
    """Long-poll for QR code scan status."""
    url = f"{base_url.rstrip('/')}/ilink/bot/get_qrcode_status?qrcode={qrcode}"
    headers = {**_headers(), "iLink-App-ClientVersion": "1"}
    try:
        resp = await client.get(url, headers=headers, timeout=35)
        resp.raise_for_status()
        return resp.json()
    except httpx.TimeoutException:
        return {"status": "wait"}


def _print_qr(qrcode_url: str) -> None:
    try:
        import qrcode as qr_lib
    except ImportError:
        qr_lib = None

    if qr_lib:
        qr = qr_lib.QRCode(box_size=1, border=1)
        qr.add_data(qrcode_url)
        qr.make()
        qr.print_ascii(invert=True)
        print("\nScan this QR code with WeChat to connect.\n")
        return

    print("\nTerminal QR rendering is unavailable because the `qrcode` package is not installed.")
    print(f"\nQR Code URL: {qrcode_url}")
    print("\nOpen the link above to load the QR code in a browser, then scan it with WeChat.\n")


async def run_wechat_login(base_url: str | None = None, max_attempts: int = 60) -> dict[str, str]:
    """Run the official WeChat QR login flow and return login credentials."""
    resolved_base_url = (base_url or os.getenv("WEIXIN_BASE_URL", DEFAULT_BASE_URL)).strip() or DEFAULT_BASE_URL
    print(f"WeChat Login for Hermes Agent")
    print(f"API: {resolved_base_url}\n")

    async with httpx.AsyncClient(follow_redirects=True) as client:
        print("Fetching QR code...")
        qr_data = await fetch_qr_code(client, resolved_base_url)
        qrcode = str(qr_data.get("qrcode", "")).strip()
        qrcode_url = str(qr_data.get("qrcode_img_content", "")).strip()

        if not qrcode:
            raise RuntimeError("Failed to get QR code from the WeChat server")

        _print_qr(qrcode_url or qrcode)

        scanned_printed = False
        for _ in range(max_attempts):
            status = await poll_qr_status(client, resolved_base_url, qrcode)
            state = str(status.get("status", "wait")).strip().lower()

            if state == "wait":
                if not scanned_printed:
                    print(".", end="", flush=True)
                continue

            if state == "scaned":
                if not scanned_printed:
                    print("\n\nQR code scanned. Confirm on your phone...")
                    scanned_printed = True
                continue

            if state == "expired":
                raise RuntimeError("QR code expired. Run `hermes wechat` again.")

            if state == "confirmed":
                token = str(status.get("bot_token", "")).strip()
                account_id = str(status.get("ilink_bot_id", "")).strip()
                response_base_url = str(status.get("baseurl", resolved_base_url)).strip() or resolved_base_url
                user_id = str(status.get("ilink_user_id", "")).strip()

                if not token or not account_id:
                    raise RuntimeError(
                        "Login confirmed but the WeChat server returned incomplete credentials: "
                        + json.dumps(status, ensure_ascii=False)
                    )

                filepath = save_credentials(account_id, token, response_base_url, user_id)
                print("\n\nConnected successfully!")
                print(f"\nCredentials saved to: {filepath}")
                print(f"\nAccount ID: {account_id}")
                if user_id:
                    print(f"User ID:    {user_id}")
                print(f"\nHermes home: {display_hermes_home()}")

                return {
                    "token": token,
                    "account_id": account_id,
                    "base_url": response_base_url,
                    "user_id": user_id,
                    "credentials_path": str(filepath),
                }

        raise RuntimeError("Login timed out. Please try again.")
