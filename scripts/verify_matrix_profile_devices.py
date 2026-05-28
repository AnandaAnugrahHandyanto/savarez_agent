#!/usr/bin/env python3
"""Verify/sign Hermes Matrix profile devices for multi-profile E2EE.

Purpose:
- Detect whether each profile's Matrix device is signed by the account
  self-signing key.
- If a MATRIX_RECOVERY_KEY is available, import cross-signing secrets into the
  profile's crypto store and self-sign the profile device automatically.
- If automatic signing is not possible, print an unmistakable manual fallback.

Safety:
- Never prints Matrix tokens, passwords, or recovery keys.
- Does not create rooms, rotate devices, or send Matrix room messages.
- Only signs devices for the same Matrix account as the profile token.

Manual verification warning:
The printed ``/verify <device_id> <ed25519>`` fallback is a local Matrix client
command. It must be typed into an already-verified Matrix client/device logged in
as the same account. Sending that text through Hermes, a Matrix bot, a gateway
``send_message`` tool, or an ordinary room chat does not execute verification.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import urllib.request
from pathlib import Path
from typing import Any, Sequence

def default_profiles_root() -> Path:
    """Return the Hermes profile root that contains .env and profiles/*/.env.

    The helper starts from the top-level multi-profile root, not the active
    worker profile directory. Profile-scoped HERMES_HOME/HOME values are
    collapsed back to their parent root so the audit workflow can inspect
    profiles/*/.env. HERMES_ROOT remains accepted as an explicit override for
    existing operator workflows, and --hermes-root can override both at runtime.
    """
    override = os.environ.get("HERMES_MATRIX_PROFILES_ROOT") or os.environ.get("HERMES_ROOT")
    if override:
        return Path(override).expanduser()

    hermes_home = os.environ.get("HERMES_HOME")
    if hermes_home:
        p = Path(hermes_home).expanduser()
        # Profile-scoped workers set HERMES_HOME to
        # <root>/profiles/<profile>; collapse that back to <root> so
        # --profiles coordinator_x resolves to <root>/profiles/coordinator_x.
        if p.parent.name == "profiles":
            return p.parent.parent
        return p

    home = Path.home()
    # Some sandboxed profile processes also set HOME to
    # <root>/profiles/<profile>/home. Collapse that synthetic home too.
    if home.name == "home" and home.parent.parent.name == "profiles":
        return home.parent.parent.parent
    return home / ".hermes"


ROOT = default_profiles_root()


def load_env(home: Path) -> dict[str, str]:
    vals: dict[str, str] = {}
    p = home / ".env"
    if not p.exists():
        return vals
    for line in p.read_text(errors="replace").splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        k, v = s.split("=", 1)
        vals[k.strip()] = v.strip().strip('"').strip("'")
    return vals


def matrix_req(hs: str, tok: str, path: str, data: dict[str, Any] | None = None) -> dict[str, Any]:
    headers = {"Authorization": "Bearer " + tok, "Content-Type": "application/json"}
    body = None if data is None else json.dumps(data).encode()
    req = urllib.request.Request(
        hs.rstrip("/") + path,
        data=body,
        headers=headers,
        method="POST" if data is not None else "GET",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        txt = resp.read().decode()
        return json.loads(txt or "{}")


def profile_home(profile: str) -> Path:
    return ROOT if profile in ("default", "root") else ROOT / "profiles" / profile


def discover_profiles() -> list[str]:
    out = []
    if (ROOT / ".env").exists():
        env = load_env(ROOT)
        if env.get("MATRIX_USER_ID") and env.get("MATRIX_ACCESS_TOKEN"):
            out.append("default")
    prof_root = ROOT / "profiles"
    if prof_root.exists():
        for p in sorted(prof_root.iterdir()):
            if (p / ".env").exists():
                env = load_env(p)
                if env.get("MATRIX_USER_ID") and env.get("MATRIX_ACCESS_TOKEN"):
                    out.append(p.name)
    return out


def _first_ed25519_key(keys: dict[str, Any]) -> str | None:
    for k, v in keys.items():
        if str(k).startswith("ed25519:"):
            return str(v)
    return None


def query_signature_status(env: dict[str, str]) -> dict[str, Any]:
    hs = env["MATRIX_HOMESERVER"].rstrip("/")
    tok = env["MATRIX_ACCESS_TOKEN"]
    user = env["MATRIX_USER_ID"]
    who = matrix_req(hs, tok, "/_matrix/client/v3/account/whoami")
    dev_id = env.get("MATRIX_DEVICE_ID") or who.get("device_id")
    q = matrix_req(hs, tok, "/_matrix/client/v3/keys/query", {"device_keys": {user: [dev_id]}})
    ssk = _first_ed25519_key(q.get("self_signing_keys", {}).get(user, {}).get("keys", {}))
    dk = q.get("device_keys", {}).get(user, {}).get(dev_id, {})
    ed = _first_ed25519_key(dk.get("keys", {}))
    sig_keyids = list(dk.get("signatures", {}).get(user, {}).keys())
    signed_by_ssk = bool(ssk and any(str(keyid) == "ed25519:" + ssk for keyid in sig_keyids))
    return {
        "user": user,
        "device_id": dev_id,
        "ed25519": ed,
        "self_signing_public_key": ssk,
        "signed_by_self_signing_key": signed_by_ssk,
        "signature_keyids": sig_keyids,
    }


def manual_verification_lines(device_id: str, ed25519: str | None) -> list[str]:
    """Return explicit manual fallback lines for an unsigned Matrix device."""
    fingerprint = ed25519 or "<missing-ed25519-fingerprint>"
    return [
        f"  manual_verify_command=/verify {device_id} {fingerprint}",
        "  manual_verify_run_from=already_verified_matrix_client_for_same_account",
        "  manual_verify_do_not_send_as=bot_gateway_message_or_room_chat",
        "  manual_verify_instruction=This is a local Matrix client command. Type it in an already-verified Matrix client/device for the same Matrix account. Do not send it through Hermes, a Matrix bot, send_message, or an ordinary room message; outbound bot/gateway messages are just chat text and cannot execute trust verification.",
    ]


async def sign_profile_device(profile: str, home: Path, recovery_key: str) -> None:
    # Heavy optional imports stay inside the signing path so dry-run checks and
    # tests can import this script without Matrix E2EE dependencies installed.
    import aiohttp
    from mautrix.api import HTTPAPI
    from mautrix.client import Client
    from mautrix.client.state_store import MemoryStateStore, MemorySyncStore
    from mautrix.crypto import OlmMachine
    from mautrix.crypto.store.asyncpg import PgCryptoStore
    from mautrix.types import TrustState, UserID
    from mautrix.util.async_db import Database

    env = load_env(home)
    hs = env["MATRIX_HOMESERVER"].rstrip("/")
    tok = env["MATRIX_ACCESS_TOKEN"]
    uid = env["MATRIX_USER_ID"]
    configured_did = env.get("MATRIX_DEVICE_ID", "")

    session = aiohttp.ClientSession(trust_env=True)
    db = None
    try:
        api = HTTPAPI(base_url=hs, token=tok, client_session=session)
        client = Client(
            mxid=UserID(uid),
            device_id=configured_did or None,
            api=api,
            state_store=MemoryStateStore(),
            sync_store=MemorySyncStore(),
        )
        who = await client.whoami()
        client.device_id = configured_did or str(who.device_id)  # type: ignore[assignment]
        store_dir = home / "platforms/matrix/store"
        store_dir.mkdir(parents=True, exist_ok=True)
        db_path = store_dir / "crypto.db"
        db = Database.create(f"sqlite:///{db_path}", upgrade_table=PgCryptoStore.upgrade_table)
        await db.start()
        store = PgCryptoStore(account_id=uid, pickle_key=f"{uid}:{client.device_id or 'default'}", db=db)
        await store.open()
        await store.put_device_id(client.device_id)
        olm = OlmMachine(client, store, client.state_store)  # type: ignore[arg-type]
        olm.share_keys_min_trust = TrustState.UNVERIFIED
        olm.send_keys_min_trust = TrustState.UNVERIFIED
        await olm.load()
        if olm.account and not olm.account.shared:
            await olm.share_keys()
        await olm.verify_with_recovery_key(recovery_key)
    finally:
        if db is not None:
            await db.stop()
        await session.close()


async def main_async(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Verify/sign Hermes Matrix profile devices")
    ap.add_argument("--profiles", nargs="*", help="Profiles to check; default: all profiles with Matrix creds")
    ap.add_argument(
        "--hermes-root",
        type=Path,
        help=(
            "Top-level Hermes profile root containing .env and profiles/*/.env; "
            "defaults to HERMES_MATRIX_PROFILES_ROOT, HERMES_ROOT, then ~/.hermes"
        ),
    )
    ap.add_argument("--sign", action="store_true", help="Attempt to self-sign unsigned devices using MATRIX_RECOVERY_KEY")
    ap.add_argument("--require-signed", action="store_true", help="Exit nonzero if any checked device remains unsigned")
    args = ap.parse_args(argv)

    global ROOT
    if args.hermes_root:
        ROOT = args.hermes_root.expanduser()

    profiles = args.profiles or discover_profiles()
    default_env = load_env(ROOT)
    default_recovery_key = default_env.get("MATRIX_RECOVERY_KEY", "")
    remaining_unsigned: list[str] = []

    for profile in profiles:
        home = profile_home(profile)
        env = load_env(home)
        if not env.get("MATRIX_HOMESERVER") or not env.get("MATRIX_ACCESS_TOKEN") or not env.get("MATRIX_USER_ID"):
            print(f"PROFILE {profile} skipped=no_matrix_credentials")
            continue
        before = query_signature_status(env)
        print(f"PROFILE {profile}")
        print(f"  user={before['user']}")
        print(f"  device_id={before['device_id']}")
        print(f"  ed25519={before['ed25519']}")
        print(f"  signed_by_self_signing_key_before={before['signed_by_self_signing_key']}")
        if args.sign and not before["signed_by_self_signing_key"]:
            recovery_key = env.get("MATRIX_RECOVERY_KEY", "") or default_recovery_key
            if not recovery_key:
                print("  sign_attempt=skipped_missing_MATRIX_RECOVERY_KEY")
                print("  sign_attempt_note=automatic self-signing requires MATRIX_RECOVERY_KEY; no bot/gateway message will be sent because room messages cannot verify devices")
            else:
                try:
                    await sign_profile_device(profile, home, recovery_key)
                    print("  sign_attempt=ok")
                except Exception as exc:
                    print(f"  sign_attempt=failed:{type(exc).__name__}:{exc}")
        after = query_signature_status(load_env(home))
        print(f"  signed_by_self_signing_key_after={after['signed_by_self_signing_key']}")
        if not after["signed_by_self_signing_key"]:
            for line in manual_verification_lines(str(after["device_id"]), after.get("ed25519")):
                print(line)
            remaining_unsigned.append(profile)

    if remaining_unsigned and args.require_signed:
        print("unsigned_profiles=" + ",".join(remaining_unsigned))
        return 2
    return 0


def main_sync(argv: Sequence[str] | None = None) -> int:
    return asyncio.run(main_async(argv))


if __name__ == "__main__":
    raise SystemExit(main_sync())
