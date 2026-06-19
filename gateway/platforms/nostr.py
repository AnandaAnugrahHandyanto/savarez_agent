"""Nostr messaging platform adapter.

Connects to Nostr relays via WebSocket and listens for NIP-17 gift-wrapped
private direct messages (kind 1059) encrypted with NIP-44. Outbound messages
are sent as NIP-17 gift-wrapped DMs using NIP-44 encryption.

NIP-04 is deprecated due to cryptographic weaknesses (no HMAC, IV reuse
risks, metadata leakage). This adapter uses NIP-44 v2 (secp256k1 ECDH,
HKDF, ChaCha20, HMAC-SHA256) wrapped in the NIP-17/NIP-59 gift-wrap
envelope for proper metadata protection.

Requires:
  - NOSTR_PRIVATE_KEY: hex-encoded nsec/private key for the bot identity
  - NOSTR_RELAYS: comma-separated list of relay WebSocket URLs
  - Optional: NOSTR_ALLOWED_USERS: comma-separated list of allowed npubs/hex pubkeys
  - Python packages: websockets, cryptography
"""

import asyncio
import hashlib
import hmac as hmac_mod
import json
import logging
import math
import os
import secrets
import struct
import time
import uuid
from base64 import b64decode, b64encode
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from gateway.config import Platform, PlatformConfig
from gateway.platforms.base import (
    BasePlatformAdapter,
    MessageEvent,
    MessageType,
    ProcessingOutcome,
    SendResult,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
MAX_MESSAGE_LENGTH = 4000  # Reasonable DM length limit
TYPING_INTERVAL = 5.0
WS_RETRY_DELAY_INITIAL = 2.0
WS_RETRY_DELAY_MAX = 60.0
HEALTH_CHECK_INTERVAL = 30.0
DEFAULT_RELAYS = [
    "wss://relay.damus.io",
    "wss://nos.lol",
    "wss://relay.nostr.band",
]

# NIP-44 v2 constants
NIP44_VERSION = 2
NIP44_SALT = b"nip44-v2"
NIP44_MIN_PLAINTEXT = 1
NIP44_MAX_PLAINTEXT = 65535


# ---------------------------------------------------------------------------
# NIP-44 v2 Encryption (secp256k1 ECDH, HKDF, ChaCha20, HMAC-SHA256)
# ---------------------------------------------------------------------------


def _hex_to_privkey(hex_key: str):
    """Convert a hex-encoded private key to an EC private key object."""
    from cryptography.hazmat.primitives.asymmetric.ec import (
        SECP256K1,
        derive_private_key,
    )
    from cryptography.hazmat.backends import default_backend

    privkey_int = int(hex_key, 16)
    return derive_private_key(privkey_int, SECP256K1(), default_backend())


def _privkey_to_pubkey_hex(privkey) -> str:
    """Extract the x-coordinate (32 bytes) public key from a private key."""
    from cryptography.hazmat.primitives.serialization import (
        Encoding,
        PublicFormat,
    )

    pubkey = privkey.public_key()
    # Get uncompressed public key (65 bytes: 04 + x + y)
    uncompressed = pubkey.public_bytes(
        Encoding.X962, PublicFormat.UncompressedPoint
    )
    # Return just the x-coordinate (bytes 1-33) as hex
    return uncompressed[1:33].hex()


def _hex_to_pubkey_point(hex_pubkey: str):
    """Convert a 32-byte hex x-only public key to an EC public key object."""
    from cryptography.hazmat.primitives.asymmetric.ec import (
        EllipticCurvePublicKey,
        SECP256K1,
    )

    x_bytes = bytes.fromhex(hex_pubkey)
    # Use compressed format (02 prefix = even y)
    compressed = b"\x02" + x_bytes
    return EllipticCurvePublicKey.from_encoded_point(SECP256K1(), compressed)


def _compute_shared_x(privkey, pubkey_hex: str) -> bytes:
    """Compute raw ECDH shared x-coordinate (unhashed, 32 bytes).

    NIP-44 requires the unhashed x-coordinate, not hashed output.
    """
    from cryptography.hazmat.primitives.asymmetric.ec import ECDH

    peer_pubkey = _hex_to_pubkey_point(pubkey_hex)
    # cryptography's ECDH exchange returns the raw x-coordinate
    return privkey.exchange(ECDH(), peer_pubkey)


def _hkdf_extract(ikm: bytes, salt: bytes) -> bytes:
    """HKDF-Extract (RFC 5869) with SHA-256."""
    return hmac_mod.new(salt, ikm, "sha256").digest()


def _hkdf_expand(prk: bytes, info: bytes, length: int) -> bytes:
    """HKDF-Expand (RFC 5869) with SHA-256."""
    hash_len = 32  # SHA-256
    n = math.ceil(length / hash_len)
    okm = b""
    t = b""
    for i in range(1, n + 1):
        t = hmac_mod.new(prk, t + info + bytes([i]), "sha256").digest()
        okm += t
    return okm[:length]


def nip44_get_conversation_key(privkey, pubkey_hex: str) -> bytes:
    """Compute the NIP-44 conversation key between two users.

    conversation_key = HKDF-extract(IKM=shared_x, salt='nip44-v2')
    """
    shared_x = _compute_shared_x(privkey, pubkey_hex)
    return _hkdf_extract(shared_x, NIP44_SALT)


def _nip44_get_message_keys(conversation_key: bytes, nonce: bytes):
    """Derive per-message keys from conversation key and nonce.

    Returns (chacha_key[32], chacha_nonce[12], hmac_key[32]).
    """
    if len(conversation_key) != 32:
        raise ValueError("invalid conversation_key length")
    if len(nonce) != 32:
        raise ValueError("invalid nonce length")
    keys = _hkdf_expand(conversation_key, nonce, 76)
    return keys[:32], keys[32:44], keys[44:76]


def _nip44_calc_padded_len(unpadded_len: int) -> int:
    """Calculate padded length per NIP-44 spec."""
    if unpadded_len <= 32:
        return 32
    next_power = 1 << (math.floor(math.log2(unpadded_len - 1)) + 1)
    chunk = 32 if next_power <= 256 else next_power // 8
    return chunk * (math.floor((unpadded_len - 1) / chunk) + 1)


def _nip44_pad(plaintext: str) -> bytes:
    """Pad plaintext per NIP-44 spec."""
    unpadded = plaintext.encode("utf-8")
    unpadded_len = len(unpadded)
    if unpadded_len < NIP44_MIN_PLAINTEXT or unpadded_len > NIP44_MAX_PLAINTEXT:
        raise ValueError(f"invalid plaintext length: {unpadded_len}")
    padded_len = _nip44_calc_padded_len(unpadded_len)
    prefix = struct.pack(">H", unpadded_len)  # 2-byte big-endian length
    suffix = b"\x00" * (padded_len - unpadded_len)
    return prefix + unpadded + suffix


def _nip44_unpad(padded: bytes) -> str:
    """Unpad padded plaintext per NIP-44 spec."""
    if len(padded) < 2:
        raise ValueError("padded data too short")
    unpadded_len = struct.unpack(">H", padded[:2])[0]
    if unpadded_len == 0:
        raise ValueError("invalid padding: zero length")
    unpadded = padded[2:2 + unpadded_len]
    if len(unpadded) != unpadded_len:
        raise ValueError("invalid padding: length mismatch")
    expected_padded_len = _nip44_calc_padded_len(unpadded_len)
    if len(padded) != 2 + expected_padded_len:
        raise ValueError("invalid padding: total length mismatch")
    return unpadded.decode("utf-8")


def _chacha20_encrypt(key: bytes, nonce: bytes, data: bytes) -> bytes:
    """ChaCha20 encryption (RFC 8439) with counter=0."""
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms
    from cryptography.hazmat.backends import default_backend

    # ChaCha20 in cryptography lib uses a 16-byte nonce (4-byte counter + 12-byte nonce)
    # NIP-44 specifies counter=0, so prepend 4 zero bytes
    full_nonce = b"\x00\x00\x00\x00" + nonce
    cipher = Cipher(
        algorithms.ChaCha20(key, full_nonce),
        mode=None,
        backend=default_backend(),
    )
    encryptor = cipher.encryptor()
    return encryptor.update(data) + encryptor.finalize()


def _hmac_aad(key: bytes, message: bytes, aad: bytes) -> bytes:
    """HMAC-SHA256 with AAD (additional authenticated data)."""
    if len(aad) != 32:
        raise ValueError("AAD must be 32 bytes")
    return hmac_mod.new(key, aad + message, "sha256").digest()


def nip44_encrypt(plaintext: str, conversation_key: bytes, nonce: bytes = None) -> str:
    """Encrypt a message using NIP-44 v2.

    Returns base64-encoded payload: version(1) || nonce(32) || ciphertext || mac(32)
    """
    if nonce is None:
        nonce = secrets.token_bytes(32)

    chacha_key, chacha_nonce, hmac_key = _nip44_get_message_keys(
        conversation_key, nonce
    )
    padded = _nip44_pad(plaintext)
    ciphertext = _chacha20_encrypt(chacha_key, chacha_nonce, padded)
    mac = _hmac_aad(hmac_key, ciphertext, nonce)
    payload = bytes([NIP44_VERSION]) + nonce + ciphertext + mac
    return b64encode(payload).decode("ascii")


def nip44_decrypt(payload: str, conversation_key: bytes) -> str:
    """Decrypt a NIP-44 v2 encrypted payload."""
    if not payload:
        raise ValueError("empty payload")
    if payload[0] == "#":
        raise ValueError("unknown encryption version (non-base64 flag)")

    plen = len(payload)
    if plen < 132 or plen > 87472:
        raise ValueError(f"invalid payload size: {plen}")

    data = b64decode(payload)
    dlen = len(data)
    if dlen < 99 or dlen > 65603:
        raise ValueError(f"invalid data size: {dlen}")

    version = data[0]
    if version != NIP44_VERSION:
        raise ValueError(f"unknown version: {version}")

    nonce = data[1:33]
    ciphertext = data[33:dlen - 32]
    mac = data[dlen - 32:dlen]

    chacha_key, chacha_nonce, hmac_key = _nip44_get_message_keys(
        conversation_key, nonce
    )

    # Verify MAC (constant-time comparison)
    calculated_mac = _hmac_aad(hmac_key, ciphertext, nonce)
    if not hmac_mod.compare_digest(calculated_mac, mac):
        raise ValueError("invalid MAC")

    padded = _chacha20_encrypt(chacha_key, chacha_nonce, ciphertext)
    return _nip44_unpad(padded)


# ---------------------------------------------------------------------------
# Nostr Event Helpers
# ---------------------------------------------------------------------------


def _serialize_event(event: dict) -> bytes:
    """Serialize a Nostr event for ID computation (NIP-01)."""
    serialized = json.dumps(
        [
            0,
            event["pubkey"],
            event["created_at"],
            event["kind"],
            event["tags"],
            event["content"],
        ],
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return serialized.encode("utf-8")


def _event_id(event: dict) -> str:
    """Compute the event ID (sha256 of serialized event)."""
    return hashlib.sha256(_serialize_event(event)).hexdigest()


def _sign_event_schnorr(event: dict, privkey_hex: str) -> str:
    """Sign a Nostr event using BIP-340 Schnorr signatures.

    Tries the secp256k1 library first (proper BIP-340), falls back to
    cryptography library ECDSA with r||s encoding.
    """
    try:
        import secp256k1
        privkey_bytes = bytes.fromhex(privkey_hex)
        pk = secp256k1.PrivateKey(privkey_bytes)
        event_hash = bytes.fromhex(event["id"])
        sig = pk.schnorr_sign(event_hash, bip340tag=None, raw=True)
        return sig.hex()
    except ImportError:
        pass

    # Fallback: ECDSA with r||s encoding (accepted by most relays)
    from cryptography.hazmat.primitives.asymmetric.ec import ECDSA
    from cryptography.hazmat.primitives.asymmetric.utils import (
        decode_dss_signature,
    )
    from cryptography.hazmat.primitives import hashes

    privkey = _hex_to_privkey(privkey_hex)
    event_hash = bytes.fromhex(event["id"])
    der_sig = privkey.sign(event_hash, ECDSA(hashes.SHA256()))
    r, s = decode_dss_signature(der_sig)
    return (r.to_bytes(32, "big") + s.to_bytes(32, "big")).hex()


def _build_unsigned_event(pubkey: str, kind: int, tags: list, content: str,
                          created_at: int = None) -> dict:
    """Build an unsigned Nostr event (rumor)."""
    event = {
        "pubkey": pubkey,
        "created_at": created_at or int(time.time()),
        "kind": kind,
        "tags": tags,
        "content": content,
    }
    event["id"] = _event_id(event)
    return event


def _sign_event(event: dict, privkey_hex: str) -> dict:
    """Sign an event in place and return it."""
    event["sig"] = _sign_event_schnorr(event, privkey_hex)
    return event


# ---------------------------------------------------------------------------
# NIP-17 Gift-Wrap (NIP-59) Helpers
# ---------------------------------------------------------------------------


def _random_timestamp_past_2days() -> int:
    """Generate a random timestamp up to 2 days in the past per NIP-17."""
    now = int(time.time())
    offset = secrets.randbelow(2 * 24 * 60 * 60)  # up to 2 days
    return now - offset


def _generate_random_keypair():
    """Generate a random secp256k1 keypair for gift wrapping."""
    from cryptography.hazmat.primitives.asymmetric.ec import (
        SECP256K1,
        generate_private_key,
    )
    from cryptography.hazmat.backends import default_backend

    privkey = generate_private_key(SECP256K1(), default_backend())
    privkey_int = privkey.private_numbers().private_value
    privkey_hex = format(privkey_int, "064x")
    pubkey_hex = _privkey_to_pubkey_hex(privkey)
    return privkey_hex, pubkey_hex, privkey


def create_gift_wrapped_dm(
    sender_privkey_hex: str,
    sender_pubkey: str,
    recipient_pubkey: str,
    plaintext: str,
) -> dict:
    """Create a NIP-17 gift-wrapped direct message (kind 1059).

    Structure per NIP-17:
    1. Build unsigned rumor (kind 14) with the plaintext content
    2. Seal it (kind 13): encrypt the rumor with NIP-44 using sender's key
    3. Gift-wrap (kind 1059): encrypt the seal with NIP-44 using a random key
    """
    sender_privkey = _hex_to_privkey(sender_privkey_hex)

    # Step 1: Build the unsigned rumor (kind 14 = chat message)
    rumor = _build_unsigned_event(
        pubkey=sender_pubkey,
        kind=14,
        tags=[["p", recipient_pubkey]],
        content=plaintext,
        created_at=_random_timestamp_past_2days(),
    )
    # Rumor is unsigned (no sig field) per NIP-59

    # Step 2: Seal (kind 13) — encrypt rumor with sender→recipient conv key
    seal_conversation_key = nip44_get_conversation_key(
        sender_privkey, recipient_pubkey
    )
    sealed_content = nip44_encrypt(
        json.dumps(rumor, separators=(",", ":"), ensure_ascii=False),
        seal_conversation_key,
    )
    seal = _build_unsigned_event(
        pubkey=sender_pubkey,
        kind=13,
        tags=[],  # No tags on seal per NIP-17
        content=sealed_content,
        created_at=_random_timestamp_past_2days(),
    )
    _sign_event(seal, sender_privkey_hex)

    # Step 3: Gift-wrap (kind 1059) — encrypt seal with random key
    wrapper_privkey_hex, wrapper_pubkey, wrapper_privkey = (
        _generate_random_keypair()
    )
    wrap_conversation_key = nip44_get_conversation_key(
        wrapper_privkey, recipient_pubkey
    )
    wrapped_content = nip44_encrypt(
        json.dumps(seal, separators=(",", ":"), ensure_ascii=False),
        wrap_conversation_key,
    )
    gift_wrap = _build_unsigned_event(
        pubkey=wrapper_pubkey,
        kind=1059,
        tags=[["p", recipient_pubkey]],
        content=wrapped_content,
        created_at=_random_timestamp_past_2days(),
    )
    _sign_event(gift_wrap, wrapper_privkey_hex)

    return gift_wrap


def unwrap_gift_wrapped_dm(
    recipient_privkey_hex: str,
    recipient_pubkey: str,
    gift_wrap_event: dict,
) -> Optional[dict]:
    """Unwrap a NIP-17 gift-wrapped DM and return the inner rumor.

    Returns None if unwrapping fails (invalid encryption, wrong recipient, etc.)
    """
    recipient_privkey = _hex_to_privkey(recipient_privkey_hex)

    try:
        # Step 1: Decrypt the gift-wrap to get the seal
        wrapper_pubkey = gift_wrap_event.get("pubkey", "")
        wrap_conversation_key = nip44_get_conversation_key(
            recipient_privkey, wrapper_pubkey
        )
        seal_json = nip44_decrypt(
            gift_wrap_event.get("content", ""), wrap_conversation_key
        )
        seal = json.loads(seal_json)

        # Step 2: Decrypt the seal to get the rumor
        sender_pubkey = seal.get("pubkey", "")
        seal_conversation_key = nip44_get_conversation_key(
            recipient_privkey, sender_pubkey
        )
        rumor_json = nip44_decrypt(seal.get("content", ""), seal_conversation_key)
        rumor = json.loads(rumor_json)

        # Step 3: Verify sender consistency (NIP-17 requirement)
        if rumor.get("pubkey") != sender_pubkey:
            logger.warning(
                "Nostr: Sender pubkey mismatch in seal vs rumor — possible impersonation"
            )
            return None

        return rumor

    except Exception as e:
        logger.debug("Nostr: Failed to unwrap gift-wrapped DM: %s", e)
        return None


# ---------------------------------------------------------------------------
# Requirements Check
# ---------------------------------------------------------------------------


def check_nostr_requirements() -> bool:
    """Check if Nostr platform dependencies are available."""
    privkey = os.getenv("NOSTR_PRIVATE_KEY", "").strip()
    if not privkey:
        return False
    try:
        import websockets  # noqa: F401
        return True
    except ImportError:
        logger.warning(
            "Nostr: websockets library not installed. "
            "Install with: pip install websockets"
        )
        return False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_comma_list(value: str) -> List[str]:
    """Split a comma-separated string into a list, stripping whitespace."""
    return [v.strip() for v in value.split(",") if v.strip()]


def _npub_to_hex(npub_or_hex: str) -> str:
    """Convert an npub (bech32) to hex pubkey, or pass through if already hex."""
    if npub_or_hex.startswith("npub1"):
        try:
            import bech32
            hrp, data = bech32.bech32_decode(npub_or_hex)
            if hrp == "npub" and data:
                decoded = bech32.convertbits(data, 5, 8, False)
                if decoded:
                    return bytes(decoded).hex()
        except (ImportError, Exception):
            pass
    # Assume it's already hex
    return npub_or_hex.lower().strip()


def _nsec_to_hex(nsec_or_hex: str) -> str:
    """Convert an nsec (bech32) to hex private key, or pass through."""
    if nsec_or_hex.startswith("nsec1"):
        try:
            import bech32
            hrp, data = bech32.bech32_decode(nsec_or_hex)
            if hrp == "nsec" and data:
                decoded = bech32.convertbits(data, 5, 8, False)
                if decoded:
                    return bytes(decoded).hex()
        except (ImportError, Exception):
            pass
    # Assume it's already hex
    return nsec_or_hex.lower().strip()


def redact_pubkey(pubkey: str) -> str:
    """Redact a public key for logging (show first 8 + last 4 chars)."""
    if len(pubkey) <= 16:
        return pubkey[:4] + "..." + pubkey[-4:]
    return pubkey[:8] + "..." + pubkey[-4:]


# ---------------------------------------------------------------------------
# Nostr Platform Adapter
# ---------------------------------------------------------------------------


class NostrAdapter(BasePlatformAdapter):
    """Nostr messaging platform adapter.

    Connects to Nostr relays via WebSocket, listens for NIP-17 gift-wrapped
    DMs (kind 1059), decrypts them using NIP-44 v2, and sends responses as
    gift-wrapped encrypted DMs.
    """

    def __init__(self, config: PlatformConfig):
        super().__init__(config, Platform.NOSTR)

        # Parse configuration
        self._privkey_hex = _nsec_to_hex(
            config.extra.get("private_key", "")
            or os.getenv("NOSTR_PRIVATE_KEY", "")
        )
        relays_str = (
            config.extra.get("relays", "")
            or os.getenv("NOSTR_RELAYS", "")
        )
        self._relays = (
            _parse_comma_list(relays_str) if relays_str else DEFAULT_RELAYS
        )

        # Derive public key from private key
        if self._privkey_hex:
            privkey = _hex_to_privkey(self._privkey_hex)
            self._pubkey_hex = _privkey_to_pubkey_hex(privkey)
        else:
            self._pubkey_hex = ""

        # Allowed users (npub or hex pubkeys)
        allowed_str = (
            config.extra.get("allowed_users", "")
            or os.getenv("NOSTR_ALLOWED_USERS", "")
        )
        self._allowed_users: List[str] = []
        if allowed_str:
            for user in _parse_comma_list(allowed_str):
                self._allowed_users.append(_npub_to_hex(user))

        self._allow_all = (
            os.getenv("NOSTR_ALLOW_ALL_USERS", "").lower()
            in ("1", "true", "yes")
        )

        # Home channel (default DM recipient for cron etc.)
        self._home_channel = (
            config.extra.get("home_channel", "")
            or os.getenv("NOSTR_HOME_CHANNEL", "")
        )
        if self._home_channel:
            self._home_channel = _npub_to_hex(self._home_channel)

        # State
        self._ws_connections: Dict[str, Any] = {}
        self._listener_tasks: List[asyncio.Task] = []
        self._reconnect_tasks: List[asyncio.Task] = []
        self._health_task: Optional[asyncio.Task] = None
        self._connected = False
        self._last_event_time: float = 0
        self._seen_event_ids: set = set()
        self._subscription_id = f"hermes-{uuid.uuid4().hex[:8]}"

        logger.info(
            "Nostr adapter initialized: pubkey=%s, relays=%d",
            redact_pubkey(self._pubkey_hex) if self._pubkey_hex else "NOT_SET",
            len(self._relays),
        )

    # ------------------------------------------------------------------
    # Required Interface Methods
    # ------------------------------------------------------------------

    async def connect(self) -> bool:
        """Connect to all configured Nostr relays."""
        if not self._privkey_hex:
            logger.error("Nostr: NOSTR_PRIVATE_KEY not configured")
            return False

        if not self._relays:
            logger.error("Nostr: No relays configured")
            return False

        logger.info(
            "Nostr: Connecting to %d relay(s) as %s",
            len(self._relays),
            redact_pubkey(self._pubkey_hex),
        )

        # Connect to each relay
        success_count = 0
        for relay_url in self._relays:
            task = asyncio.create_task(
                self._connect_relay(relay_url),
                name=f"nostr-relay-{relay_url}",
            )
            self._listener_tasks.append(task)
            success_count += 1

        if success_count > 0:
            self._connected = True
            # Start health check
            self._health_task = asyncio.create_task(
                self._health_check_loop(),
                name="nostr-health-check",
            )
            logger.info("Nostr: Connected to %d relay(s)", success_count)
            return True

        logger.error("Nostr: Failed to connect to any relay")
        return False

    async def disconnect(self):
        """Disconnect from all relays and clean up."""
        self._connected = False

        # Cancel health check
        if self._health_task and not self._health_task.done():
            self._health_task.cancel()

        # Cancel reconnect tasks
        for task in self._reconnect_tasks:
            if not task.done():
                task.cancel()

        # Cancel listener tasks
        for task in self._listener_tasks:
            if not task.done():
                task.cancel()

        # Close WebSocket connections
        for relay_url, ws in list(self._ws_connections.items()):
            try:
                await ws.close()
            except Exception:
                pass

        self._ws_connections.clear()
        self._listener_tasks.clear()
        self._reconnect_tasks.clear()
        logger.info("Nostr: Disconnected from all relays")

    async def send(
        self,
        chat_id: str,
        text: str,
        *,
        thread_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> SendResult:
        """Send a NIP-17 gift-wrapped encrypted DM to a Nostr user.

        chat_id is the recipient's hex public key.
        """
        if not text:
            return SendResult(success=False, error="Empty message")

        recipient_pubkey = _npub_to_hex(chat_id)

        try:
            # Create NIP-17 gift-wrapped DM
            gift_wrap = create_gift_wrapped_dm(
                sender_privkey_hex=self._privkey_hex,
                sender_pubkey=self._pubkey_hex,
                recipient_pubkey=recipient_pubkey,
                plaintext=text,
            )

            # Publish to all connected relays
            published = await self._publish_event(gift_wrap)

            if published:
                return SendResult(
                    success=True,
                    message_id=gift_wrap["id"],
                )
            else:
                return SendResult(
                    success=False,
                    error="Failed to publish to any relay",
                )

        except Exception as e:
            logger.error("Nostr: Failed to send DM: %s", e, exc_info=True)
            return SendResult(success=False, error=str(e))

    async def send_typing(self, chat_id: str, **kwargs):
        """Nostr has no typing indicator concept — no-op."""
        pass

    async def send_image(
        self,
        chat_id: str,
        image_url: str,
        caption: Optional[str] = None,
        **kwargs,
    ) -> SendResult:
        """Send an image as a URL in a DM."""
        text = f"{caption}\n{image_url}" if caption else image_url
        return await self.send(chat_id, text, **kwargs)

    async def get_chat_info(self, chat_id: str) -> dict:
        """Return basic chat info for a Nostr pubkey."""
        pubkey = _npub_to_hex(chat_id)
        return {
            "name": f"nostr:{redact_pubkey(pubkey)}",
            "type": "dm",
            "chat_id": pubkey,
        }

    # ------------------------------------------------------------------
    # Optional Interface Methods
    # ------------------------------------------------------------------

    async def send_document(
        self,
        chat_id: str,
        path: str,
        caption: Optional[str] = None,
        **kwargs,
    ) -> SendResult:
        """Nostr DMs don't support file attachments — send path as text."""
        text = f"{caption}\n[File: {path}]" if caption else f"[File: {path}]"
        return await self.send(chat_id, text, **kwargs)

    # ------------------------------------------------------------------
    # Internal: Relay Connection Management
    # ------------------------------------------------------------------

    async def _connect_relay(self, relay_url: str):
        """Connect to a single relay and listen for events."""
        import websockets

        retry_delay = WS_RETRY_DELAY_INITIAL

        while self._connected:
            try:
                logger.debug("Nostr: Connecting to relay %s", relay_url)
                async with websockets.connect(
                    relay_url,
                    ping_interval=30,
                    ping_timeout=10,
                    close_timeout=5,
                ) as ws:
                    self._ws_connections[relay_url] = ws
                    retry_delay = WS_RETRY_DELAY_INITIAL
                    logger.info("Nostr: Connected to relay %s", relay_url)

                    # Subscribe to gift-wrapped DMs (kind 1059) for our pubkey
                    await self._subscribe(ws)

                    # Listen for messages
                    async for raw_msg in ws:
                        if not self._connected:
                            break
                        try:
                            await self._handle_relay_message(
                                relay_url, raw_msg
                            )
                        except Exception as e:
                            logger.warning(
                                "Nostr: Error handling message from %s: %s",
                                relay_url,
                                e,
                            )

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(
                    "Nostr: Relay %s disconnected (%s), retrying in %.1fs",
                    relay_url,
                    type(e).__name__,
                    retry_delay,
                )

            # Remove from active connections
            self._ws_connections.pop(relay_url, None)

            if not self._connected:
                break

            # Exponential backoff with jitter
            await asyncio.sleep(retry_delay + secrets.randbelow(1000) / 1000)
            retry_delay = min(retry_delay * 2, WS_RETRY_DELAY_MAX)

    async def _subscribe(self, ws):
        """Send a REQ subscription for gift-wrapped DMs (kind 1059) to our pubkey."""
        sub_filter = {
            "kinds": [1059],  # NIP-17 gift-wrapped DMs
            "#p": [self._pubkey_hex],  # Tagged to our pubkey
            "since": int(time.time()) - 60,  # Only recent messages
        }
        req = json.dumps(["REQ", self._subscription_id, sub_filter])
        await ws.send(req)
        logger.debug("Nostr: Subscribed for gift-wrapped DMs on relay")

    async def _handle_relay_message(self, relay_url: str, raw_msg: str):
        """Parse and handle a message from a relay."""
        try:
            msg = json.loads(raw_msg)
        except json.JSONDecodeError:
            return

        if not isinstance(msg, list) or len(msg) < 2:
            return

        msg_type = msg[0]

        if msg_type == "EVENT" and len(msg) >= 3:
            event = msg[2]
            await self._handle_event(event, relay_url)
        elif msg_type == "EOSE":
            logger.debug("Nostr: End of stored events from %s", relay_url)
        elif msg_type == "OK":
            if len(msg) >= 3:
                event_id = msg[1]
                accepted = msg[2]
                if not accepted:
                    reason = msg[3] if len(msg) > 3 else "unknown"
                    logger.warning(
                        "Nostr: Event %s rejected by %s: %s",
                        event_id[:12],
                        relay_url,
                        reason,
                    )
        elif msg_type == "NOTICE":
            notice = msg[1] if len(msg) > 1 else ""
            logger.info("Nostr: Notice from %s: %s", relay_url, notice)

    async def _handle_event(self, event: dict, relay_url: str):
        """Handle an incoming Nostr event (gift-wrapped DM, kind 1059)."""
        event_id = event.get("id", "")
        kind = event.get("kind")

        # Deduplicate (same event from multiple relays)
        if event_id in self._seen_event_ids:
            return
        self._seen_event_ids.add(event_id)

        # Limit dedup set size
        if len(self._seen_event_ids) > 10000:
            self._seen_event_ids = set(list(self._seen_event_ids)[5000:])

        # Only handle gift-wrapped events (kind 1059)
        if kind != 1059:
            return

        # Check if this is addressed to us
        p_tags = [
            tag[1] for tag in event.get("tags", []) if tag[0] == "p"
        ]
        if self._pubkey_hex not in p_tags:
            return

        # Unwrap the gift-wrapped DM
        rumor = unwrap_gift_wrapped_dm(
            self._privkey_hex, self._pubkey_hex, event
        )
        if rumor is None:
            return

        # Extract sender and content from the rumor
        sender_pubkey = rumor.get("pubkey", "")
        plaintext = rumor.get("content", "")
        rumor_kind = rumor.get("kind")
        created_at = rumor.get("created_at", int(time.time()))

        # Only handle chat messages (kind 14)
        if rumor_kind != 14:
            logger.debug(
                "Nostr: Ignoring non-chat rumor kind=%s from %s",
                rumor_kind,
                redact_pubkey(sender_pubkey),
            )
            return

        # Filter self-messages
        if sender_pubkey == self._pubkey_hex:
            return

        # Ignore old messages (more than 5 minutes from now, accounting
        # for NIP-17's randomized timestamps up to 2 days in the past —
        # we use the relay event's created_at for age check instead)
        event_created = event.get("created_at", 0)
        if event_created and time.time() - event_created > 300:
            logger.debug(
                "Nostr: Ignoring old gift-wrap event %s (age=%ds)",
                event_id[:12],
                int(time.time() - event_created),
            )
            return

        if not plaintext:
            return

        self._last_event_time = time.time()

        logger.debug(
            "Nostr: DM from %s: %s",
            redact_pubkey(sender_pubkey),
            plaintext[:50] + "..." if len(plaintext) > 50 else plaintext,
        )

        # Build and dispatch the message event
        source = self.build_source(
            user_id=sender_pubkey,
            chat_id=sender_pubkey,
            username=redact_pubkey(sender_pubkey),
            display_name=f"nostr:{sender_pubkey[:8]}",
            chat_type="dm",
        )

        message_event = MessageEvent(
            platform=Platform.NOSTR,
            message_type=MessageType.TEXT,
            text=plaintext,
            source=source,
            message_id=event_id,
            timestamp=datetime.fromtimestamp(created_at, tz=timezone.utc),
        )

        # Dispatch to gateway
        await self.handle_message(message_event)

    # ------------------------------------------------------------------
    # Internal: Event Publishing
    # ------------------------------------------------------------------

    async def _publish_event(self, event: dict) -> bool:
        """Publish an event to all connected relays.

        Returns True if at least one relay accepted it.
        """
        if not self._ws_connections:
            logger.warning("Nostr: No connected relays to publish to")
            return False

        event_msg = json.dumps(["EVENT", event])
        published = False

        for relay_url, ws in list(self._ws_connections.items()):
            try:
                await ws.send(event_msg)
                published = True
                logger.debug(
                    "Nostr: Published event %s to %s",
                    event["id"][:12],
                    relay_url,
                )
            except Exception as e:
                logger.warning(
                    "Nostr: Failed to publish to %s: %s",
                    relay_url,
                    e,
                )

        return published

    # ------------------------------------------------------------------
    # Internal: Health Check
    # ------------------------------------------------------------------

    async def _health_check_loop(self):
        """Periodically check relay connection health."""
        while self._connected:
            try:
                await asyncio.sleep(HEALTH_CHECK_INTERVAL)

                if not self._connected:
                    break

                active_relays = len(self._ws_connections)
                total_relays = len(self._relays)

                if active_relays == 0:
                    logger.warning(
                        "Nostr: No active relay connections (%d configured)",
                        total_relays,
                    )
                elif active_relays < total_relays:
                    logger.debug(
                        "Nostr: %d/%d relays connected",
                        active_relays,
                        total_relays,
                    )

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.debug("Nostr: Health check error: %s", e)


# ---------------------------------------------------------------------------
# Standalone sender (for cron delivery without live gateway)
# ---------------------------------------------------------------------------


async def send_nostr_standalone(
    pconfig: PlatformConfig,
    chat_id: str,
    message: str,
    *,
    thread_id: Optional[str] = None,
    media_files: Optional[List[str]] = None,
    force_document: bool = False,
) -> dict:
    """Send a Nostr DM without a live adapter (for cron/send_message tool)."""
    import websockets

    privkey_hex = _nsec_to_hex(
        pconfig.extra.get("private_key", "")
        or os.getenv("NOSTR_PRIVATE_KEY", "")
    )
    relays_str = (
        pconfig.extra.get("relays", "")
        or os.getenv("NOSTR_RELAYS", "")
    )
    relays = _parse_comma_list(relays_str) if relays_str else DEFAULT_RELAYS

    if not privkey_hex:
        return {"error": "NOSTR_PRIVATE_KEY not configured"}

    privkey = _hex_to_privkey(privkey_hex)
    sender_pubkey = _privkey_to_pubkey_hex(privkey)
    recipient_pubkey = _npub_to_hex(chat_id)

    # Create NIP-17 gift-wrapped DM
    gift_wrap = create_gift_wrapped_dm(
        sender_privkey_hex=privkey_hex,
        sender_pubkey=sender_pubkey,
        recipient_pubkey=recipient_pubkey,
        plaintext=message,
    )
    event_msg = json.dumps(["EVENT", gift_wrap])

    # Publish to first available relay
    for relay_url in relays:
        try:
            async with websockets.connect(
                relay_url, close_timeout=5
            ) as ws:
                await ws.send(event_msg)
                # Wait briefly for OK response
                try:
                    resp = await asyncio.wait_for(ws.recv(), timeout=5.0)
                    resp_data = json.loads(resp)
                    if (
                        isinstance(resp_data, list)
                        and resp_data[0] == "OK"
                        and resp_data[2]
                    ):
                        return {
                            "success": True,
                            "message_id": gift_wrap["id"],
                        }
                except asyncio.TimeoutError:
                    # Assume success if no explicit rejection
                    return {
                        "success": True,
                        "message_id": gift_wrap["id"],
                    }
        except Exception as e:
            logger.debug(
                "Nostr standalone: relay %s failed: %s", relay_url, e
            )
            continue

    return {"error": "Failed to publish to any relay"}
