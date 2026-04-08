#!/usr/bin/env python3
"""
Standalone WeChat QR login script for Hermes Agent.

Run this on the Pi to authenticate the bot with WeChat:
    python3 scripts/wechat_login.py

After scanning the QR code with WeChat, credentials are saved to
~/.hermes/wechat/accounts/<account_id>.json and can be loaded by
the Hermes gateway's WeChat adapter.

Protocol compliance (openclaw-weixin SDK 2.1.x):
  - iLink-App-Id and iLink-App-ClientVersion headers on all requests
  - IDC redirect (scaned_but_redirect) handling
  - QR auto-refresh on expiry (up to 3 times)
  - Fixed base URL for QR requests (ilinkai.weixin.qq.com)
"""

import asyncio
import base64
import json
import os
import struct
import sys
import time
from pathlib import Path

try:
    import httpx
except ImportError:
    print("Error: httpx not installed. Run: pip install httpx")
    sys.exit(1)

# Fixed base URL for all QR code requests (matches SDK login-qr.ts)
FIXED_BASE_URL = "https://ilinkai.weixin.qq.com"
DEFAULT_BOT_TYPE = "3"
ADAPTER_VERSION = "0.2.0"
MAX_QR_REFRESH_COUNT = 3
QR_LONG_POLL_TIMEOUT_S = 35


def _build_client_version(version: str) -> int:
    """Encode version as uint32: 0x00MMNNPP."""
    parts = version.split(".")
    major = int(parts[0]) if len(parts) > 0 else 0
    minor = int(parts[1]) if len(parts) > 1 else 0
    patch = int(parts[2]) if len(parts) > 2 else 0
    return ((major & 0xFF) << 16) | ((minor & 0xFF) << 8) | (patch & 0xFF)


def _random_uin_header() -> str:
    rand_uint32 = struct.unpack(">I", os.urandom(4))[0]
    return base64.b64encode(str(rand_uint32).encode()).decode()


def _headers() -> dict:
    """Build headers with iLink protocol requirements (SDK 2.1.1+)."""
    return {
        "Content-Type": "application/json",
        "X-WECHAT-UIN": _random_uin_header(),
        "iLink-App-Id": os.getenv("WECHAT_ILINK_APP_ID", "bot"),
        "iLink-App-ClientVersion": str(_build_client_version(ADAPTER_VERSION)),
    }


async def fetch_qr_code(client: httpx.AsyncClient) -> dict:
    """Request a QR code from the WeChat iLink API (always from fixed base URL)."""
    url = f"{FIXED_BASE_URL}/ilink/bot/get_bot_qrcode?bot_type={DEFAULT_BOT_TYPE}"
    resp = await client.get(url, headers=_headers())
    resp.raise_for_status()
    return resp.json()


async def poll_qr_status(client: httpx.AsyncClient, base_url: str, qrcode: str) -> dict:
    """Long-poll for QR code scan status."""
    url = f"{base_url}/ilink/bot/get_qrcode_status?qrcode={qrcode}"
    try:
        resp = await client.get(url, headers=_headers(), timeout=QR_LONG_POLL_TIMEOUT_S)
        resp.raise_for_status()
        return resp.json()
    except httpx.TimeoutException:
        return {"status": "wait"}
    except Exception as e:
        # Network/gateway errors: treat as wait and retry
        print(f"\n  (network error, retrying: {e})")
        return {"status": "wait"}


def save_credentials(account_id: str, token: str, base_url: str, user_id: str = "") -> Path:
    """Save credentials to $HERMES_HOME/wechat/accounts/<id>.json"""
    hermes_home = Path(os.getenv("HERMES_HOME", Path.home() / ".hermes"))
    accounts_dir = hermes_home / "wechat" / "accounts"
    accounts_dir.mkdir(parents=True, exist_ok=True)

    normalized = account_id.strip().lower().replace("@", "-").replace(".", "-")

    data = {
        "token": token,
        "baseUrl": base_url,
        "savedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    if user_id:
        data["userId"] = user_id

    filepath = accounts_dir / f"{normalized}.json"
    filepath.write_text(json.dumps(data, indent=2))
    filepath.chmod(0o600)

    index_path = hermes_home / "wechat" / "accounts.json"
    index_path.write_text(json.dumps([normalized], indent=2))

    return filepath


def display_qr(qrcode_url: str) -> None:
    """Display QR code in terminal, with fallback to URL."""
    try:
        import qrcode as qr_lib
        qr = qr_lib.QRCode(box_size=1, border=1)
        qr.add_data(qrcode_url)
        qr.make()
        qr.print_ascii(invert=True)
    except ImportError:
        pass
    print(f"\nQR Code URL: {qrcode_url}")
    print("\nScan this QR code with WeChat to connect.\n")


async def main():
    print("WeChat Login for Hermes Agent")
    print(f"API: {FIXED_BASE_URL}")
    print(f"Protocol: iLink 2.1.x (App-Id + ClientVersion headers)\n")

    async with httpx.AsyncClient(follow_redirects=True) as client:
        # Step 1: Get QR code
        print("Fetching QR code...")
        qr_data = await fetch_qr_code(client)
        qrcode = qr_data.get("qrcode", "")
        qrcode_url = qr_data.get("qrcode_img_content", "")

        if not qrcode:
            print("Error: Failed to get QR code from server")
            sys.exit(1)

        display_qr(qrcode_url)

        # Step 2: Poll for scan with IDC redirect + QR refresh support
        scanned_printed = False
        qr_refresh_count = 1
        polling_base_url = FIXED_BASE_URL  # May change on IDC redirect
        max_attempts = 120  # ~10 minutes with long-poll

        for attempt in range(max_attempts):
            status = await poll_qr_status(client, polling_base_url, qrcode)
            state = status.get("status", "wait")

            if state == "wait":
                if not scanned_printed:
                    print(".", end="", flush=True)

            elif state == "scaned":
                if not scanned_printed:
                    print("\n\n  QR code scanned! Confirm on your phone...")
                    scanned_printed = True

            elif state == "scaned_but_redirect":
                # IDC redirect: switch polling to a different datacenter (SDK 2.1.1+)
                redirect_host = str(status.get("redirect_host", "")).strip()
                if redirect_host:
                    polling_base_url = f"https://{redirect_host}"
                    print(f"\n  IDC redirect -> {redirect_host}")
                else:
                    print("\n  IDC redirect received but no redirect_host, continuing...")

            elif state == "expired":
                qr_refresh_count += 1
                if qr_refresh_count > MAX_QR_REFRESH_COUNT:
                    print(f"\n\nQR code expired {MAX_QR_REFRESH_COUNT} times. Please try again.")
                    sys.exit(1)

                print(f"\n\n  QR expired, refreshing ({qr_refresh_count}/{MAX_QR_REFRESH_COUNT})...")
                try:
                    qr_data = await fetch_qr_code(client)
                    qrcode = qr_data.get("qrcode", "")
                    qrcode_url = qr_data.get("qrcode_img_content", "")
                    if not qrcode:
                        print("  Failed to refresh QR code")
                        sys.exit(1)
                    scanned_printed = False
                    polling_base_url = FIXED_BASE_URL  # Reset polling URL
                    display_qr(qrcode_url)
                except Exception as e:
                    print(f"  Failed to refresh QR: {e}")
                    sys.exit(1)

            elif state == "confirmed":
                bot_token = status.get("bot_token", "")
                account_id = status.get("ilink_bot_id", "")
                response_base_url = status.get("baseurl", FIXED_BASE_URL)
                user_id = status.get("ilink_user_id", "")

                if not bot_token or not account_id:
                    print("\n\nLogin confirmed but missing credentials. Response:")
                    print(json.dumps(status, indent=2))
                    sys.exit(1)

                filepath = save_credentials(account_id, bot_token, response_base_url, user_id)

                print(f"\n\nConnected successfully!")
                print(f"\nCredentials saved to: {filepath}")
                print(f"\nAccount ID: {account_id}")
                if user_id:
                    print(f"User ID:    {user_id}")

                print(f"\n--- Add these to ~/.hermes/.env ---")
                print(f"WECHAT_BOT_TOKEN={bot_token}")
                print(f"WECHAT_ACCOUNT_ID={account_id}")
                if response_base_url != FIXED_BASE_URL:
                    print(f"WECHAT_API_BASE_URL={response_base_url}")
                if user_id:
                    print(f"WECHAT_ALLOWED_USERS={user_id}")
                print(f"-----------------------------------")

                # Quick connection test
                print(f"\nTesting connection...")
                try:
                    test_headers = {
                        **_headers(),
                        "AuthorizationType": "ilink_bot_token",
                        "Authorization": f"Bearer {bot_token}",
                    }
                    test_body = {
                        "get_updates_buf": "",
                        "base_info": {"channel_version": f"hermes-wechat/{ADAPTER_VERSION}"},
                    }
                    test_resp = await client.post(
                        f"{response_base_url}/ilink/bot/getupdates",
                        json=test_body,
                        headers=test_headers,
                        timeout=10,
                    )
                    if test_resp.status_code == 200:
                        print("Connection test passed!")
                    else:
                        print(f"Connection test returned HTTP {test_resp.status_code}")
                except Exception as e:
                    print(f"Connection test failed: {e}")
                    print("(This may be normal if the server holds the long-poll)")

                return

            await asyncio.sleep(1)

        print("\n\nLogin timed out. Please try again.")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
