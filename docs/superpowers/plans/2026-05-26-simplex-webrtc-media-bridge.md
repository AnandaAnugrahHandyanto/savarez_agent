# SimpleX WebRTC Media Bridge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first native SimpleX WebRTC compatibility milestone for Hermes: tested signaling, explicit native-call state, a sidecar media port contract, and loud failures instead of silent fallback.

**Architecture:** Use a vertical slice through `gateway/calls/native` with hexagonal ports. The application core owns call decisions and state; SimpleX and media sidecar details sit behind adapters. The first milestone proves native-call plumbing and sidecar control; local STT/TTS speech turns are separate follow-on work.

**Tech Stack:** Python 3.11+, pytest, pytest-asyncio, existing Hermes gateway platform adapter APIs, SimpleX daemon WebSocket commands, JSON-line sidecar protocol.

---

## File Structure

- Create `gateway/calls/native/__init__.py`: exports native call application types.
- Create `gateway/calls/native/ports.py`: protocol and dataclass boundary definitions.
- Create `gateway/calls/native/application.py`: native incoming-call orchestration, authorization, signaling, media startup, state result mapping.
- Create `gateway/calls/native/sidecar.py`: configurable JSON-line process adapter for a future browser/WebRTC sidecar.
- Modify `gateway/calls/models.py`: add native call states needed by `/call status`.
- Modify `gateway/calls/manager.py`: store native sessions and expose native status/end helpers.
- Modify `gateway/run.py`: wire `/call native` through adapter capability checks and keep browser fallback behavior unchanged.
- Modify `plugins/platforms/simplex/adapter.py`: add SimpleX native-call signaling commands and optional native-call handler hook.
- Modify `tests/gateway/test_call_manager.py`: native session state tests.
- Modify `tests/gateway/test_call_command.py`: `/call native` command tests.
- Modify `tests/gateway/test_simplex_plugin.py`: SimpleX signaling serialization and incoming call handler tests.
- Create `tests/gateway/test_native_call_application.py`: domain/application tests.
- Create `tests/gateway/test_native_sidecar.py`: sidecar adapter tests.

## Task 1: Native Call Application Core

**Files:**
- Create: `gateway/calls/native/__init__.py`
- Create: `gateway/calls/native/ports.py`
- Create: `gateway/calls/native/application.py`
- Modify: `gateway/calls/models.py`
- Test: `tests/gateway/test_native_call_application.py`

- [ ] **Step 1: Write failing native application tests**

Create `tests/gateway/test_native_call_application.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from types import SimpleNamespace

import pytest

from gateway.calls.native.application import NativeCallApplication
from gateway.calls.native.ports import (
    NativeCallInvitation,
    NativeMediaOffer,
    NativeMediaStartRequest,
    NativeMediaStartResult,
)


def _source(chat_type="dm"):
    return SimpleNamespace(
        platform=SimpleNamespace(value="simplex"),
        chat_id="42",
        user_id="42",
        chat_type=chat_type,
    )


@dataclass
class FakeSignaling:
    offers: list[tuple[str, NativeMediaOffer]] = field(default_factory=list)
    statuses: list[tuple[str, str]] = field(default_factory=list)
    rejected: list[str] = field(default_factory=list)
    ended: list[str] = field(default_factory=list)

    async def send_offer(self, contact_id: str, offer: NativeMediaOffer) -> None:
        self.offers.append((contact_id, offer))

    async def send_status(self, contact_id: str, status: str) -> None:
        self.statuses.append((contact_id, status))

    async def reject(self, contact_id: str, reason_code: str) -> None:
        self.rejected.append(reason_code)

    async def end(self, contact_id: str) -> None:
        self.ended.append(contact_id)


@dataclass
class FakeMedia:
    result: NativeMediaStartResult
    requests: list[NativeMediaStartRequest] = field(default_factory=list)

    async def start_incoming(self, request: NativeMediaStartRequest) -> NativeMediaStartResult:
        self.requests.append(request)
        return self.result

    async def stop(self, call_id: str) -> None:
        pass


@pytest.mark.asyncio
async def test_incoming_native_call_rejects_group_chat():
    signaling = FakeSignaling()
    media = FakeMedia(NativeMediaStartResult(ok=True))
    app = NativeCallApplication(signaling=signaling, media=media, is_authorized=lambda _s: True)

    result = await app.handle_incoming_invitation(
        _source(chat_type="group"),
        NativeCallInvitation(contact_id="42", media="audio", encrypted=False),
    )

    assert result.ok is False
    assert result.code == "call_private_chat_required"
    assert signaling.rejected == ["call_private_chat_required"]
    assert not signaling.offers


@pytest.mark.asyncio
async def test_incoming_native_call_rejects_unauthorized_contact():
    signaling = FakeSignaling()
    media = FakeMedia(NativeMediaStartResult(ok=True))
    app = NativeCallApplication(signaling=signaling, media=media, is_authorized=lambda _s: False)

    result = await app.handle_incoming_invitation(
        _source(),
        NativeCallInvitation(contact_id="42", media="audio", encrypted=False),
    )

    assert result.ok is False
    assert result.code == "call_auth_denied"
    assert signaling.rejected == ["call_auth_denied"]
    assert not media.requests


@pytest.mark.asyncio
async def test_incoming_native_call_sends_offer_and_connecting_status():
    offer = NativeMediaOffer(
        rtc_session="compressed-offer",
        rtc_ice_candidates="compressed-ice",
        capabilities={"encryption": False},
    )
    signaling = FakeSignaling()
    media = FakeMedia(NativeMediaStartResult(ok=True, offer=offer))
    app = NativeCallApplication(signaling=signaling, media=media, is_authorized=lambda _s: True)

    result = await app.handle_incoming_invitation(
        _source(),
        NativeCallInvitation(contact_id="42", media="audio", encrypted=False, shared_key=None),
    )

    assert result.ok is True
    assert result.code == "call_simplex_native_connecting"
    assert result.call_id.startswith("call_")
    assert media.requests[0].contact_id == "42"
    assert signaling.offers == [("42", offer)]
    assert signaling.statuses == [("42", "connecting")]


@pytest.mark.asyncio
async def test_incoming_native_call_rejects_when_media_start_fails():
    signaling = FakeSignaling()
    media = FakeMedia(
        NativeMediaStartResult(
            ok=False,
            code="call_sidecar_start_failed",
            message="sidecar command is not configured",
        )
    )
    app = NativeCallApplication(signaling=signaling, media=media, is_authorized=lambda _s: True)

    result = await app.handle_incoming_invitation(
        _source(),
        NativeCallInvitation(contact_id="42", media="audio", encrypted=False),
    )

    assert result.ok is False
    assert result.code == "call_sidecar_start_failed"
    assert signaling.rejected == ["call_sidecar_start_failed"]
    assert not signaling.offers
```

- [ ] **Step 2: Run tests and verify they fail for missing module**

Run:

```bash
scripts/run_tests.sh tests/gateway/test_native_call_application.py -q
```

Expected: FAIL during import with `ModuleNotFoundError: No module named 'gateway.calls.native'`.

- [ ] **Step 3: Implement native ports**

Create `gateway/calls/native/__init__.py`:

```python
from .application import NativeCallApplication
from .ports import (
    NativeCallInvitation,
    NativeCallResult,
    NativeMediaOffer,
    NativeMediaStartRequest,
    NativeMediaStartResult,
)

__all__ = [
    "NativeCallApplication",
    "NativeCallInvitation",
    "NativeCallResult",
    "NativeMediaOffer",
    "NativeMediaStartRequest",
    "NativeMediaStartResult",
]
```

Create `gateway/calls/native/ports.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Protocol


@dataclass(frozen=True)
class NativeCallInvitation:
    contact_id: str
    media: str = "audio"
    encrypted: bool = False
    shared_key: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class NativeMediaOffer:
    rtc_session: str
    rtc_ice_candidates: str
    capabilities: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class NativeMediaStartRequest:
    call_id: str
    contact_id: str
    media: str
    encrypted: bool
    shared_key: str | None = None


@dataclass(frozen=True)
class NativeMediaStartResult:
    ok: bool
    offer: NativeMediaOffer | None = None
    code: str | None = None
    message: str = ""


@dataclass(frozen=True)
class NativeCallResult:
    ok: bool
    code: str
    message: str
    call_id: str | None = None


class NativeCallSignalingPort(Protocol):
    async def send_offer(self, contact_id: str, offer: NativeMediaOffer) -> None:
        raise NotImplementedError

    async def send_status(self, contact_id: str, status: str) -> None:
        raise NotImplementedError

    async def reject(self, contact_id: str, reason_code: str) -> None:
        raise NotImplementedError

    async def end(self, contact_id: str) -> None:
        raise NotImplementedError


class WebRTCMediaPort(Protocol):
    async def start_incoming(self, request: NativeMediaStartRequest) -> NativeMediaStartResult:
        raise NotImplementedError

    async def stop(self, call_id: str) -> None:
        raise NotImplementedError


AuthorizeSource = Callable[[Any], bool]
```

- [ ] **Step 4: Implement native application service**

Create `gateway/calls/native/application.py`:

```python
from __future__ import annotations

import logging
import uuid
from typing import Any

from .ports import (
    AuthorizeSource,
    NativeCallInvitation,
    NativeCallResult,
    NativeCallSignalingPort,
    NativeMediaStartRequest,
    WebRTCMediaPort,
)

logger = logging.getLogger(__name__)


def _is_dm(source: Any) -> bool:
    return str(getattr(source, "chat_type", "dm") or "dm").lower() == "dm"


class NativeCallApplication:
    def __init__(
        self,
        *,
        signaling: NativeCallSignalingPort,
        media: WebRTCMediaPort,
        is_authorized: AuthorizeSource,
    ) -> None:
        self.signaling = signaling
        self.media = media
        self.is_authorized = is_authorized

    async def handle_incoming_invitation(
        self,
        source: Any,
        invitation: NativeCallInvitation,
    ) -> NativeCallResult:
        contact_id = str(invitation.contact_id or "").strip()
        if not contact_id:
            logger.warning("SimpleX native call invitation missing contact id")
            return NativeCallResult(
                ok=False,
                code="call_simplex_native_signaling_failed",
                message="SimpleX-native call setup failed: missing contact id.",
            )

        if not _is_dm(source):
            await self.signaling.reject(contact_id, "call_private_chat_required")
            return NativeCallResult(
                ok=False,
                code="call_private_chat_required",
                message="Calls are private-only. DM me /call to create a private room.",
            )

        try:
            authorized = bool(self.is_authorized(source))
        except Exception:
            logger.exception("SimpleX native call authorization check failed")
            authorized = False

        if not authorized:
            await self.signaling.reject(contact_id, "call_auth_denied")
            return NativeCallResult(
                ok=False,
                code="call_auth_denied",
                message="SimpleX-native call rejected.",
            )

        call_id = f"call_{uuid.uuid4().hex}"
        media_result = await self.media.start_incoming(
            NativeMediaStartRequest(
                call_id=call_id,
                contact_id=contact_id,
                media=invitation.media,
                encrypted=invitation.encrypted,
                shared_key=invitation.shared_key,
            )
        )
        if not media_result.ok or media_result.offer is None:
            code = media_result.code or "call_simplex_native_media_failed"
            logger.warning(
                "SimpleX native call media start failed: call_id=%s code=%s",
                call_id,
                code,
            )
            await self.signaling.reject(contact_id, code)
            return NativeCallResult(
                ok=False,
                code=code,
                message=media_result.message or "SimpleX-native call media setup failed.",
                call_id=call_id,
            )

        await self.signaling.send_offer(contact_id, media_result.offer)
        await self.signaling.send_status(contact_id, "connecting")
        logger.info("SimpleX native call offer sent: call_id=%s", call_id)
        return NativeCallResult(
            ok=True,
            code="call_simplex_native_connecting",
            message="SimpleX-native call is connecting.",
            call_id=call_id,
        )
```

- [ ] **Step 5: Run native application tests and verify they pass**

Run:

```bash
scripts/run_tests.sh tests/gateway/test_native_call_application.py -q
```

Expected: `4 passed`.

- [ ] **Step 6: Commit Task 1**

Run:

```bash
git add gateway/calls/native tests/gateway/test_native_call_application.py
git commit -m "feat: add native call application core"
```

## Task 2: SimpleX Native Signaling Commands

**Files:**
- Modify: `plugins/platforms/simplex/adapter.py`
- Test: `tests/gateway/test_simplex_plugin.py`

- [ ] **Step 1: Write failing SimpleX signaling tests**

Append to `tests/gateway/test_simplex_plugin.py`:

```python
@pytest.mark.asyncio
async def test_send_native_call_offer_serializes_simplex_offer_command(monkeypatch):
    from gateway.config import PlatformConfig
    from gateway.calls.native.ports import NativeMediaOffer

    adapter = SimplexAdapter(PlatformConfig(enabled=True))
    sent = []

    async def fake_send_command(cmd):
        sent.append(cmd)
        return {"type": "ok"}

    adapter._send_command = fake_send_command

    await adapter.send_native_call_offer(
        "42",
        NativeMediaOffer(
            rtc_session="offer-b64",
            rtc_ice_candidates="ice-b64",
            capabilities={"encryption": False},
        ),
        media="audio",
    )

    assert sent == [
        '/_call offer @42 {"callType":{"media":"audio","capabilities":{"encryption":false}},"rtcSession":{"rtcSession":"offer-b64","rtcIceCandidates":"ice-b64"}}'
    ]


@pytest.mark.asyncio
async def test_simplex_native_call_status_end_and_reject_commands():
    from gateway.config import PlatformConfig

    adapter = SimplexAdapter(PlatformConfig(enabled=True))
    sent = []

    async def fake_send_command(cmd):
        sent.append(cmd)
        return {"type": "ok"}

    adapter._send_command = fake_send_command

    assert await adapter.reject_native_call("42", "call_auth_denied") is True
    await adapter.send_native_call_status("42", "connecting")
    await adapter.end_native_call("42")

    assert sent == [
        "/_call reject @42",
        "/_call status @42 connecting",
        "/_call end @42",
    ]
```

- [ ] **Step 2: Run tests and verify they fail for missing methods**

Run:

```bash
scripts/run_tests.sh tests/gateway/test_simplex_plugin.py::test_send_native_call_offer_serializes_simplex_offer_command tests/gateway/test_simplex_plugin.py::test_simplex_native_call_status_end_and_reject_commands -q
```

Expected: FAIL with `AttributeError: 'SimplexAdapter' object has no attribute 'send_native_call_offer'`.

- [ ] **Step 3: Implement SimpleX native signaling helpers**

In `plugins/platforms/simplex/adapter.py`, add near `_voice_send_command`:

```python
def _native_call_offer_command(
    chat_id: str,
    offer,
    *,
    media: str = "audio",
) -> str:
    payload = {
        "callType": {
            "media": media,
            "capabilities": {
                "encryption": bool((offer.capabilities or {}).get("encryption", False)),
            },
        },
        "rtcSession": {
            "rtcSession": offer.rtc_session,
            "rtcIceCandidates": offer.rtc_ice_candidates,
        },
    }
    encoded = json.dumps(payload, separators=(",", ":"))
    return f"/_call offer {_chat_ref_for_chat_id(chat_id)} {encoded}"
```

In `SimplexAdapter`, replace `_reject_native_call` usage with public methods:

```python
    async def send_native_call_offer(self, chat_id: str, offer, *, media: str = "audio") -> bool:
        cmd = _native_call_offer_command(chat_id, offer, media=media)
        await self._send_command(cmd)
        return True

    async def send_native_call_status(self, chat_id: str, status: str) -> bool:
        cmd = f"/_call status {_chat_ref_for_chat_id(chat_id)} {status}"
        await self._send_command(cmd)
        return True

    async def end_native_call(self, chat_id: str) -> bool:
        cmd = f"/_call end {_chat_ref_for_chat_id(chat_id)}"
        await self._send_command(cmd)
        return True

    async def reject_native_call(self, chat_id: str, reason_code: str = "") -> bool:
        cmd = f"/_call reject {_chat_ref_for_chat_id(chat_id)}"
        try:
            await self._send_command(cmd)
            if reason_code:
                logger.info(
                    "SimpleX: rejected native call chat_id=%s reason=%s",
                    chat_id,
                    reason_code,
                )
            return True
        except Exception as exc:
            logger.error(
                "SimpleX: failed to reject native call for chat_id=%s: %s",
                chat_id,
                exc,
                exc_info=True,
            )
            return False

    async def _reject_native_call(self, chat_id: str) -> bool:
        return await self.reject_native_call(chat_id)
```

- [ ] **Step 4: Run SimpleX signaling tests and verify they pass**

Run:

```bash
scripts/run_tests.sh tests/gateway/test_simplex_plugin.py::test_send_native_call_offer_serializes_simplex_offer_command tests/gateway/test_simplex_plugin.py::test_simplex_native_call_status_end_and_reject_commands -q
```

Expected: `2 passed`.

- [ ] **Step 5: Commit Task 2**

Run:

```bash
git add plugins/platforms/simplex/adapter.py tests/gateway/test_simplex_plugin.py
git commit -m "feat: add simplex native call signaling commands"
```

## Task 3: Incoming SimpleX Native Call Handler Hook

**Files:**
- Modify: `plugins/platforms/simplex/adapter.py`
- Test: `tests/gateway/test_simplex_plugin.py`

- [ ] **Step 1: Write failing handler hook tests**

Append to `tests/gateway/test_simplex_plugin.py`:

```python
@pytest.mark.asyncio
async def test_authorized_native_call_uses_native_handler_when_configured():
    from gateway.config import PlatformConfig

    cfg = PlatformConfig(enabled=True, extra={"native_calls": {"enabled": True}})
    adapter = SimplexAdapter(cfg)
    handled = []
    adapter.send = AsyncMock()
    adapter._mark_chat_items_read = AsyncMock()

    async def handler(source, invitation):
        handled.append((source, invitation))
        return SimpleNamespace(ok=True, code="call_simplex_native_connecting", message="connecting")

    adapter.native_call_handler = handler
    adapter.gateway_runner = SimpleNamespace(_is_user_authorized=lambda _source: True)

    source = adapter.build_source(
        chat_id="42",
        chat_name="Bryan",
        chat_type="dm",
        user_id="42",
        user_name="Bryan",
    )

    await adapter._handle_native_call_item(
        source,
        "42",
        {"type": "rcvCall", "status": "pending", "callType": {"media": "audio", "capabilities": {"encryption": True}}, "sharedKey": "secret-key"},
        {"itemId": 99},
    )

    assert handled[0][1].contact_id == "42"
    assert handled[0][1].media == "audio"
    assert handled[0][1].encrypted is True
    assert handled[0][1].shared_key == "secret-key"
    adapter.send.assert_not_called()
    adapter._mark_chat_items_read.assert_awaited_once_with("42", [99])


@pytest.mark.asyncio
async def test_native_handler_failure_sends_loud_fallback_message():
    from gateway.config import PlatformConfig

    cfg = PlatformConfig(enabled=True, extra={"native_calls": {"enabled": True}})
    adapter = SimplexAdapter(cfg)
    adapter.send = AsyncMock(return_value=SimpleNamespace(success=True))
    adapter._mark_chat_items_read = AsyncMock()

    async def handler(source, invitation):
        return SimpleNamespace(
            ok=False,
            code="call_sidecar_start_failed",
            message="SimpleX-native call setup failed: sidecar command is not configured.",
        )

    adapter.native_call_handler = handler
    adapter.gateway_runner = SimpleNamespace(_is_user_authorized=lambda _source: True)
    source = adapter.build_source(chat_id="42", chat_name="Bryan", chat_type="dm", user_id="42", user_name="Bryan")

    await adapter._handle_native_call_item(
        source,
        "42",
        {"type": "rcvCall", "status": "pending"},
        {"itemId": 99},
    )

    adapter.send.assert_awaited_once()
    assert "sidecar command is not configured" in adapter.send.await_args.args[1]
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
scripts/run_tests.sh tests/gateway/test_simplex_plugin.py::test_authorized_native_call_uses_native_handler_when_configured tests/gateway/test_simplex_plugin.py::test_native_handler_failure_sends_loud_fallback_message -q
```

Expected: FAIL because `_handle_native_call_item` ignores `native_call_handler`.

- [ ] **Step 3: Implement handler hook and invitation extraction**

In `SimplexAdapter.__init__`, add:

```python
        native_calls = extra.get("native_calls") if isinstance(extra.get("native_calls"), dict) else {}
        self.native_calls_enabled = bool(native_calls.get("enabled", False))
        self.native_call_handler = None
```

Add helper near `_handle_native_call_item`:

```python
    @staticmethod
    def _native_call_invitation_from_item(chat_id: str, item_content: dict):
        from gateway.calls.native.ports import NativeCallInvitation

        call_type = item_content.get("callType") if isinstance(item_content.get("callType"), dict) else {}
        capabilities = call_type.get("capabilities") if isinstance(call_type.get("capabilities"), dict) else {}
        media = str(call_type.get("media") or item_content.get("media") or "audio")
        shared_key = item_content.get("sharedKey") or item_content.get("aesKey")
        return NativeCallInvitation(
            contact_id=str(chat_id),
            media=media,
            encrypted=bool(capabilities.get("encryption", False) or shared_key),
            shared_key=str(shared_key) if shared_key else None,
            raw=item_content,
        )
```

Inside `_handle_native_call_item`, after the authorization block and before the existing unsupported rejection block, add:

```python
        if self.native_calls_enabled and callable(self.native_call_handler):
            invitation = self._native_call_invitation_from_item(chat_id, item_content)
            try:
                result = await self.native_call_handler(source, invitation)
            except Exception:
                logger.exception("SimpleX: native call handler failed for chat_id=%s", chat_id)
                result = None
            if result is not None and getattr(result, "ok", False):
                if item_id is not None:
                    await self._mark_chat_items_read(chat_id, [item_id])
                return
            reason = getattr(result, "message", "") or (
                "SimpleX-native call setup failed. Use /call for the private browser fallback."
            )
            await self.reject_native_call(chat_id, getattr(result, "code", "call_simplex_native_media_failed"))
            await self.send(chat_id, reason)
            if item_id is not None:
                await self._mark_chat_items_read(chat_id, [item_id])
            return
```

- [ ] **Step 4: Run handler hook tests and verify they pass**

Run:

```bash
scripts/run_tests.sh tests/gateway/test_simplex_plugin.py::test_authorized_native_call_uses_native_handler_when_configured tests/gateway/test_simplex_plugin.py::test_native_handler_failure_sends_loud_fallback_message -q
```

Expected: `2 passed`.

- [ ] **Step 5: Commit Task 3**

Run:

```bash
git add plugins/platforms/simplex/adapter.py tests/gateway/test_simplex_plugin.py
git commit -m "feat: route simplex native calls through handler"
```

## Task 4: Native Sidecar Process Port

**Files:**
- Create: `gateway/calls/native/sidecar.py`
- Test: `tests/gateway/test_native_sidecar.py`

- [ ] **Step 1: Write failing sidecar tests**

Create `tests/gateway/test_native_sidecar.py`:

```python
from __future__ import annotations

import json
import sys

import pytest

from gateway.calls.native.ports import NativeMediaStartRequest
from gateway.calls.native.sidecar import SidecarMediaPort


@pytest.mark.asyncio
async def test_sidecar_media_port_fails_loudly_without_command():
    port = SidecarMediaPort(command=[])

    result = await port.start_incoming(
        NativeMediaStartRequest(
            call_id="call_1",
            contact_id="42",
            media="audio",
            encrypted=False,
        )
    )

    assert result.ok is False
    assert result.code == "call_sidecar_start_failed"
    assert "sidecar command is not configured" in result.message


@pytest.mark.asyncio
async def test_sidecar_media_port_reads_offer_from_json_line_child(tmp_path):
    child = tmp_path / "fake_sidecar.py"
    child.write_text(
        '''
import json
import sys

for line in sys.stdin:
    request = json.loads(line)
    assert request["type"] == "start_incoming"
    response = {
        "ok": True,
        "offer": {
            "rtcSession": "compressed-offer",
            "rtcIceCandidates": "compressed-ice",
            "capabilities": {"encryption": False},
        },
    }
    print(json.dumps(response), flush=True)
''',
        encoding="utf-8",
    )
    port = SidecarMediaPort(command=[sys.executable, str(child)], timeout_seconds=5)

    result = await port.start_incoming(
        NativeMediaStartRequest(
            call_id="call_1",
            contact_id="42",
            media="audio",
            encrypted=False,
        )
    )

    assert result.ok is True
    assert result.offer is not None
    assert result.offer.rtc_session == "compressed-offer"
    assert result.offer.rtc_ice_candidates == "compressed-ice"
```

- [ ] **Step 2: Run sidecar tests and verify they fail**

Run:

```bash
scripts/run_tests.sh tests/gateway/test_native_sidecar.py -q
```

Expected: FAIL during import with `ModuleNotFoundError` for `gateway.calls.native.sidecar`.

- [ ] **Step 3: Implement sidecar process port**

Create `gateway/calls/native/sidecar.py`:

```python
from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field

from .ports import NativeMediaOffer, NativeMediaStartRequest, NativeMediaStartResult

logger = logging.getLogger(__name__)


@dataclass
class SidecarMediaPort:
    command: list[str] = field(default_factory=list)
    timeout_seconds: float = 10.0

    async def start_incoming(self, request: NativeMediaStartRequest) -> NativeMediaStartResult:
        if not self.command:
            return NativeMediaStartResult(
                ok=False,
                code="call_sidecar_start_failed",
                message="SimpleX-native call setup failed: sidecar command is not configured.",
            )

        proc = None
        try:
            proc = await asyncio.create_subprocess_exec(
                *self.command,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            assert proc.stdin is not None
            assert proc.stdout is not None
            payload = {
                "type": "start_incoming",
                "callId": request.call_id,
                "contactId": request.contact_id,
                "media": request.media,
                "encrypted": request.encrypted,
                "sharedKey": request.shared_key,
            }
            proc.stdin.write((json.dumps(payload, separators=(",", ":")) + "\n").encode("utf-8"))
            await proc.stdin.drain()
            raw = await asyncio.wait_for(proc.stdout.readline(), timeout=self.timeout_seconds)
            if not raw:
                return NativeMediaStartResult(
                    ok=False,
                    code="call_sidecar_protocol_failed",
                    message="SimpleX-native sidecar exited before returning an offer.",
                )
            response = json.loads(raw.decode("utf-8"))
            if not response.get("ok"):
                return NativeMediaStartResult(
                    ok=False,
                    code=str(response.get("code") or "call_sidecar_protocol_failed"),
                    message=str(response.get("message") or "SimpleX-native sidecar failed."),
                )
            offer = response.get("offer") if isinstance(response.get("offer"), dict) else {}
            return NativeMediaStartResult(
                ok=True,
                offer=NativeMediaOffer(
                    rtc_session=str(offer.get("rtcSession") or ""),
                    rtc_ice_candidates=str(offer.get("rtcIceCandidates") or ""),
                    capabilities=offer.get("capabilities") if isinstance(offer.get("capabilities"), dict) else {},
                ),
            )
        except asyncio.TimeoutError:
            return NativeMediaStartResult(
                ok=False,
                code="call_simplex_native_timeout",
                message="SimpleX-native sidecar timed out while creating an offer.",
            )
        except Exception as exc:
            logger.exception("SimpleX-native sidecar start failed")
            return NativeMediaStartResult(
                ok=False,
                code="call_sidecar_start_failed",
                message=f"SimpleX-native sidecar failed: {exc}",
            )
        finally:
            if proc is not None and proc.returncode is None:
                proc.terminate()
                try:
                    await asyncio.wait_for(proc.wait(), timeout=1)
                except Exception:
                    proc.kill()

    async def stop(self, call_id: str) -> None:
        return None
```

- [ ] **Step 4: Run sidecar tests and verify they pass**

Run:

```bash
scripts/run_tests.sh tests/gateway/test_native_sidecar.py -q
```

Expected: `2 passed`.

- [ ] **Step 5: Commit Task 4**

Run:

```bash
git add gateway/calls/native/sidecar.py tests/gateway/test_native_sidecar.py
git commit -m "feat: add native call sidecar media port"
```

## Task 5: Gateway Native Command And Manager State

**Files:**
- Modify: `gateway/calls/models.py`
- Modify: `gateway/calls/manager.py`
- Modify: `gateway/run.py`
- Test: `tests/gateway/test_call_manager.py`
- Test: `tests/gateway/test_call_command.py`

- [ ] **Step 1: Write failing manager and command tests**

Append to `tests/gateway/test_call_manager.py`:

```python
@pytest.mark.asyncio
async def test_native_session_status_reports_connecting():
    manager = CallManager(
        browser_provider=BrowserRoomProvider(BrowserRoomConfig(base_url="https://host.ts.net/call")),
        token_service=CallTokenService("secret"),
    )

    session = manager.record_native_call(_source(platform="simplex"), "call_native_1", "connecting")
    result = await manager.status(_source(platform="simplex"))

    assert session.mode == "simplex_native"
    assert "call_native_1" in result.message
    assert "connecting" in result.message
```

Update `_source` in `tests/gateway/test_call_manager.py` to accept platform:

```python
def _source(chat_type="dm", platform="telegram"):
    platform_obj = SimpleNamespace(value=platform)
    return SimpleNamespace(platform=platform_obj, chat_id="123", user_id="456", chat_type=chat_type)
```

Append to `tests/gateway/test_call_command.py`:

```python
@pytest.mark.asyncio
async def test_handle_call_native_reports_missing_simplex_adapter():
    result = await _runner()._handle_call_command(_event("/call native", platform="simplex"))

    assert "SimpleX-native calls are unavailable" in result
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
scripts/run_tests.sh tests/gateway/test_call_manager.py::test_native_session_status_reports_connecting tests/gateway/test_call_command.py::test_handle_call_native_reports_missing_simplex_adapter -q
```

Expected: FAIL because `record_native_call` does not exist and `/call native` does not inspect adapters.

- [ ] **Step 3: Extend call manager for native status**

In `gateway/calls/models.py`, extend `CallState`:

```python
class CallState(str, Enum):
    WAITING = "waiting"
    CONNECTING = "connecting"
    ACTIVE = "active"
    ENDED = "ended"
    FAILED = "failed"
```

In `gateway/calls/manager.py`, add:

```python
    def record_native_call(self, source, call_id: str, state: str = "connecting") -> CallSession:
        key = _session_key(source)
        created_at = self.now()
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        expires_at = created_at + timedelta(seconds=self.ttl_seconds)
        try:
            call_state = CallState(state)
        except ValueError:
            call_state = CallState.CONNECTING
        session = CallSession(
            call_id=call_id,
            platform=key[0],
            chat_id=key[1],
            user_id=key[2],
            mode="simplex_native",
            state=call_state,
            room_url=None,
            created_at=created_at,
            expires_at=expires_at,
        )
        self._sessions[key] = session
        return session
```

- [ ] **Step 4: Make `/call native` inspect the SimpleX adapter**

In `gateway/run.py`, replace the `args == "native"` block with:

```python
        if args == "native":
            platform = getattr(event.source.platform, "value", event.source.platform)
            if str(platform) != "simplex":
                return "SimpleX-native calls are only available from an authorized SimpleX DM."
            adapter = getattr(self, "adapters", {}).get(event.source.platform) if hasattr(self, "adapters") else None
            if adapter is None:
                return "SimpleX-native calls are unavailable: SimpleX adapter is not connected."
            if not getattr(adapter, "native_calls_enabled", False):
                return "SimpleX-native calls are unavailable: native WebRTC bridge is not enabled."
            return "SimpleX-native calls are enabled for incoming SimpleX app calls. Call Hermes from the SimpleX app to start."
```

- [ ] **Step 5: Run manager and command tests and verify they pass**

Run:

```bash
scripts/run_tests.sh tests/gateway/test_call_manager.py::test_native_session_status_reports_connecting tests/gateway/test_call_command.py::test_handle_call_native_reports_missing_simplex_adapter -q
```

Expected: `2 passed`.

- [ ] **Step 6: Commit Task 5**

Run:

```bash
git add gateway/calls/models.py gateway/calls/manager.py gateway/run.py tests/gateway/test_call_manager.py tests/gateway/test_call_command.py
git commit -m "feat: track simplex native call state"
```

## Task 6: Gateway Wiring For Incoming Native Calls

**Files:**
- Modify: `gateway/run.py`
- Modify: `plugins/platforms/simplex/adapter.py`
- Test: `tests/gateway/test_call_command.py`
- Test: `tests/gateway/test_simplex_plugin.py`

- [ ] **Step 1: Write failing gateway wiring test**

Append to `tests/gateway/test_call_command.py`:

```python
def test_get_call_manager_configures_native_call_handler_when_simplex_adapter_present():
    runner = _runner()
    runner.adapters = {}

    adapter = SimpleNamespace(
        platform=SimpleNamespace(value="simplex"),
        native_calls_enabled=True,
        native_call_handler=None,
    )
    runner.adapters[adapter.platform] = adapter

    manager = runner._get_call_manager()
    runner._configure_native_call_handlers()

    assert callable(adapter.native_call_handler)
    assert manager is runner._call_manager
```

- [ ] **Step 2: Run test and verify it fails**

Run:

```bash
scripts/run_tests.sh tests/gateway/test_call_command.py::test_get_call_manager_configures_native_call_handler_when_simplex_adapter_present -q
```

Expected: FAIL because `_configure_native_call_handlers` does not exist.

- [ ] **Step 3: Add gateway native handler configuration**

In `gateway/run.py`, add near `_get_call_manager`:

```python
    def _configure_native_call_handlers(self) -> None:
        adapters = getattr(self, "adapters", {}) or {}
        for adapter in adapters.values():
            if getattr(adapter, "platform", None) and str(getattr(adapter.platform, "value", adapter.platform)) == "simplex":
                if getattr(adapter, "native_calls_enabled", False):
                    adapter.native_call_handler = self._handle_simplex_native_call

    async def _handle_simplex_native_call(self, source, invitation):
        from gateway.calls.native.application import NativeCallApplication
        from gateway.calls.native.sidecar import SidecarMediaPort

        adapter = getattr(self, "adapters", {}).get(source.platform)
        if adapter is None:
            return SimpleNamespace(
                ok=False,
                code="call_simplex_ws_disconnected",
                message="SimpleX-native call setup failed: SimpleX adapter is not connected.",
            )
        extra = getattr(getattr(adapter, "config", None), "extra", {}) or {}
        native_cfg = extra.get("native_calls") if isinstance(extra.get("native_calls"), dict) else {}
        sidecar_command = native_cfg.get("sidecar_command") or []
        if isinstance(sidecar_command, str):
            import shlex
            sidecar_command = shlex.split(sidecar_command)
        app = NativeCallApplication(
            signaling=adapter,
            media=SidecarMediaPort(command=list(sidecar_command)),
            is_authorized=self._is_user_authorized,
        )
        result = await app.handle_incoming_invitation(source, invitation)
        if result.call_id:
            self._get_call_manager().record_native_call(source, result.call_id, "connecting" if result.ok else "failed")
        return result
```

Add `from types import SimpleNamespace` at the top of `gateway/run.py` if it is not already imported.

Call `_configure_native_call_handlers()` after adapters connect and on reconnect, immediately after `self.adapters[platform] = adapter` and `_sync_voice_mode_state_to_adapter(adapter)`.

- [ ] **Step 4: Run gateway wiring test and existing call tests**

Run:

```bash
scripts/run_tests.sh tests/gateway/test_call_command.py -q
```

Expected: all tests in `test_call_command.py` pass.

- [ ] **Step 5: Commit Task 6**

Run:

```bash
git add gateway/run.py tests/gateway/test_call_command.py
git commit -m "feat: wire simplex native call handler"
```

## Task 7: Focused Verification And Documentation

**Files:**
- Modify: `docs/plans/2026-05-26-private-simplex-call-flow.md`

- [ ] **Step 1: Update existing call-flow plan with implementation status**

Append a short section to `docs/plans/2026-05-26-private-simplex-call-flow.md`:

```markdown
## 11. Native WebRTC Bridge Status

The first native bridge milestone adds tested SimpleX call signaling, explicit native call state, and a configurable media sidecar port. It does not claim full speech-to-speech until a SimpleX mobile call verifies the WebRTC media path and the local STT/TTS runtime is connected.

Native calls fail loudly when `platforms.simplex.extra.native_calls.enabled` is false or when `native_calls.sidecar_command` is missing.
```

- [ ] **Step 2: Run focused test suite**

Run:

```bash
scripts/run_tests.sh tests/gateway/test_native_call_application.py tests/gateway/test_native_sidecar.py tests/gateway/test_call_manager.py tests/gateway/test_call_command.py tests/gateway/test_simplex_plugin.py -q
```

Expected: all selected tests pass.

- [ ] **Step 3: Run linter on touched Python files**

Run:

```bash
.venv/bin/ruff check gateway/calls/models.py gateway/calls/manager.py gateway/calls/native plugins/platforms/simplex/adapter.py gateway/run.py tests/gateway/test_native_call_application.py tests/gateway/test_native_sidecar.py tests/gateway/test_call_manager.py tests/gateway/test_call_command.py tests/gateway/test_simplex_plugin.py
```

Expected: `All checks passed!`

- [ ] **Step 4: Commit verification/docs**

Run:

```bash
git add docs/plans/2026-05-26-private-simplex-call-flow.md
git commit -m "docs: record simplex native bridge milestone"
```

## Final Verification

- [ ] Run:

```bash
scripts/run_tests.sh tests/gateway/test_native_call_application.py tests/gateway/test_native_sidecar.py tests/gateway/test_call_manager.py tests/gateway/test_call_command.py tests/gateway/test_simplex_plugin.py -q
```

Expected: all selected tests pass.

- [ ] Run:

```bash
.venv/bin/ruff check gateway/calls/models.py gateway/calls/manager.py gateway/calls/native plugins/platforms/simplex/adapter.py gateway/run.py tests/gateway/test_native_call_application.py tests/gateway/test_native_sidecar.py tests/gateway/test_call_manager.py tests/gateway/test_call_command.py tests/gateway/test_simplex_plugin.py
```

Expected: `All checks passed!`

- [ ] Run:

```bash
git status --short --branch
```

Expected: clean worktree on `codex/simplex-webrtc-media-bridge`.

## Manual Verification Required For Full Native Claim

After code lands and gateway is restarted with:

```yaml
platforms:
  simplex:
    extra:
      native_calls:
        enabled: true
        sidecar_command:
          - python
          - /absolute/path/to/sidecar
```

Manual verification must call Hermes from the SimpleX mobile app. This implementation milestone may report the sidecar as missing or failed loudly. Full native call support is not claimed until a real browser/WebRTC sidecar returns an offer and a mobile SimpleX call reaches connected media.
