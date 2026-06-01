from __future__ import annotations

import asyncio
import importlib.util
import json as jsonlib
import re
import shutil
import shlex
import uuid
from pathlib import Path
from typing import Any

from hermes_constants import get_hermes_home


def _trace_root(value: str | None = None) -> Path:
    if value:
        return Path(value).expanduser()
    return get_hermes_home() / "logs" / "calls"


def _safe_call_id(call_id: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(call_id or ""))
    return safe[:128] or "unknown"


def _trace_path(root: Path, call_id: str) -> Path:
    call_id = _safe_call_id(call_id.removesuffix(".jsonl"))
    return root / f"{call_id}.jsonl"


def _iter_trace_paths(root: Path) -> list[Path]:
    return sorted(
        (path for path in root.rglob("*.jsonl") if path.is_file()),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )


def _find_trace_path(root: Path, call_id: str) -> Path:
    direct = _trace_path(root, call_id)
    if direct.exists():
        return direct
    safe_call_id = _safe_call_id(call_id.removesuffix(".jsonl"))
    matches = [
        path
        for path in _iter_trace_paths(root)
        if path.name == f"{safe_call_id}.jsonl"
    ]
    return matches[0] if matches else direct


def _tail_lines(path: Path, limit: int) -> list[str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    if limit <= 0:
        return lines
    return lines[-limit:]


def _trace_signature(path: Path) -> tuple[int, int]:
    stat = path.stat()
    return (int(stat.st_mtime_ns), int(stat.st_size))


def _iter_trace_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            row = jsonlib.loads(line)
        except jsonlib.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _summarize_trace_file(path: Path) -> dict[str, Any]:
    events: list[str] = []
    media_events: list[str] = []
    reasons: list[str] = []
    statuses: list[str] = []
    call_id = path.stem
    last_ts = None
    for row in _iter_trace_rows(path):
        data = row.get("data") if isinstance(row.get("data"), dict) else {}
        call_id = str(row.get("call_id") or row.get("callId") or call_id)
        event = str(row.get("event") or "")
        if event:
            events.append(event)
        media_event = row.get("media_event") or data.get("media_event")
        if isinstance(media_event, str) and media_event:
            media_events.append(media_event)
        reason = (
            row.get("reason")
            or row.get("reasonCode")
            or data.get("reason")
            or data.get("reasonCode")
        )
        if isinstance(reason, str) and reason:
            reasons.append(reason)
        status = row.get("status") or data.get("status")
        if isinstance(status, str) and status:
            statuses.append(status)
        details = row.get("details") if isinstance(row.get("details"), dict) else None
        if details is None and isinstance(data.get("details"), dict):
            details = data.get("details")
        if isinstance(details, dict):
            detail_status = details.get("status")
            if isinstance(detail_status, str) and detail_status:
                statuses.append(detail_status)
        ts = row.get("ts")
        if isinstance(ts, str) and ts:
            last_ts = ts
    return {
        "path": str(path),
        "call_id": call_id,
        "events": list(dict.fromkeys(events)),
        "media_events": list(dict.fromkeys(media_events)),
        "reasons": list(dict.fromkeys(reasons)),
        "statuses": list(dict.fromkeys(statuses)),
        "last_ts": last_ts,
        "bytes": path.stat().st_size,
    }


def _simplex_acceptance_summary(
    trace_path: Path,
    *,
    manual_heard: bool = False,
) -> dict[str, Any]:
    if not trace_path.exists():
        return {
            "ok": False,
            "technical_ok": False,
            "manual_ok": bool(manual_heard),
            "manual_required": True,
            "trace_path": str(trace_path),
            "error": "call trace not found",
            "checks": {},
            "missing": ["trace_path"],
        }

    summary = _summarize_trace_file(trace_path)
    rows = _iter_trace_rows(trace_path)
    events = set(summary.get("events") or [])
    media_events = set(summary.get("media_events") or [])
    statuses = set(summary.get("statuses") or [])
    signal_types = {
        str(row.get("signal_type") or row.get("signalType") or "").lower()
        for row in rows
        if str(row.get("event") or "") == "native_signal_received"
    }
    inbound_answer_negotiated = (
        "answer" in signal_types or "remote_answer_sdp" in media_events
    )
    outbound_answer_negotiated = (
        "offer" in signal_types
        or "remote_offer_sdp" in media_events
    ) and "local_answer_sdp" in media_events
    checks = {
        "native_call_registered": "native_call_registered" in events,
        "answer_negotiated": (
            inbound_answer_negotiated or outbound_answer_negotiated
        ),
        "webrtc_connected": (
            "connection_state" in media_events and "connected" in statuses
        ),
        "inbound_audio_frames": "first_remote_audio_frame" in media_events,
        "stt_transcribed": "voice_turn_transcribed" in events,
        "agent_responded": "voice_turn_agent_responded" in events,
        "tts_ready": "voice_turn_tts_ready" in events,
        "outbound_tts_playback_started": (
            "outbound_tts_playback_started" in media_events
            or "outbound_tts_playback_completed" in media_events
        ),
    }
    missing = [name for name, ok in checks.items() if not ok]
    technical_ok = not missing
    manual_ok = bool(manual_heard)
    return {
        "ok": bool(technical_ok and manual_ok),
        "technical_ok": bool(technical_ok),
        "manual_ok": manual_ok,
        "manual_required": not manual_ok,
        "trace_path": str(trace_path),
        "call_id": summary.get("call_id"),
        "last_ts": summary.get("last_ts"),
        "checks": checks,
        "missing": missing,
    }


def _row_value(row: dict[str, Any], key: str, default: Any = None) -> Any:
    if key in row:
        return row.get(key)
    data = row.get("data")
    if isinstance(data, dict) and key in data:
        return data.get(key)
    return default


def _new_observed_turn(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "transcript_preview": str(_row_value(row, "preview", "") or ""),
        "transcript_chars": int(_row_value(row, "chars", 0) or 0),
        "stt_provider": str(_row_value(row, "stt_provider", "") or ""),
        "agent_response_preview": "",
        "agent_response_chars": 0,
        "tts_playback_started": False,
        "tts_playback_completed": False,
        "outbound_audio_received": False,
        "tool_intents": [],
    }


def _simplex_observation_summary(trace_path: Path) -> dict[str, Any]:
    if not trace_path.exists():
        return {
            "ok": False,
            "trace_path": str(trace_path),
            "error": "call trace not found",
            "turns": [],
            "weather_intent_observed": False,
        }

    summary = _summarize_trace_file(trace_path)
    turns: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for row in _iter_trace_rows(trace_path):
        event = str(row.get("event") or "")
        if event == "voice_turn_transcript_observed":
            current = _new_observed_turn(row)
            turns.append(current)
            continue
        if current is None and event in {
            "tool_intent_observed",
            "voice_turn_agent_response_observed",
        }:
            current = _new_observed_turn({})
            turns.append(current)

        if event == "tool_intent_observed" and current is not None:
            intent = str(_row_value(row, "intent", "") or "")
            if intent and intent not in current["tool_intents"]:
                current["tool_intents"].append(intent)
            continue
        if event == "voice_turn_agent_response_observed" and current is not None:
            current["agent_response_preview"] = str(
                _row_value(row, "preview", "") or ""
            )
            current["agent_response_chars"] = int(_row_value(row, "chars", 0) or 0)
            continue
        media_event = _row_value(row, "media_event")
        if (
            event == "native_media_event"
            and current is not None
        ):
            if media_event == "outbound_tts_playback_started":
                current["tts_playback_started"] = True
            elif media_event == "outbound_tts_playback_completed":
                current["tts_playback_started"] = True
                current["tts_playback_completed"] = True
        if event == "simulation_outbound_audio_received" and current is not None:
            current["outbound_audio_received"] = True

    weather_intent_observed = any(
        "weather" in turn.get("tool_intents", []) for turn in turns
    )
    return {
        "ok": bool(turns),
        "trace_path": str(trace_path),
        "call_id": summary.get("call_id"),
        "last_ts": summary.get("last_ts"),
        "turns": turns,
        "weather_intent_observed": weather_intent_observed,
    }


_LIVE_DEBUG_DECISIVE_VERDICTS = {
    "voice_turn_audio_ready",
    "inbound_audio_seen",
    "no_inbound_audio",
    "native_call_answer_timeout",
    "call_failed",
    "call_ended",
}


def _simplex_live_debug_verdict(
    *,
    simplex_event: dict[str, Any],
    call_item: dict[str, Any],
    traces: list[dict[str, Any]],
) -> str:
    all_events = {
        str(event)
        for trace in traces
        for event in (trace.get("events") or [])
    }
    all_media_events = {
        str(event)
        for trace in traces
        for event in (trace.get("media_events") or [])
    }
    all_reasons = {
        str(reason)
        for trace in traces
        for reason in (trace.get("reasons") or [])
    }
    all_statuses = {
        str(status)
        for trace in traces
        for status in (trace.get("statuses") or [])
    }
    if any(
        event in all_events
        for event in {
            "voice_turn_tts_ready",
            "voice_turn_completed",
            "simulation_voice_turn_completed",
        }
    ):
        return "voice_turn_audio_ready"
    if "first_remote_audio_frame" in all_media_events:
        return "inbound_audio_seen"
    if (
        "no_inbound_audio_frames" in all_media_events
        or "remote_audio_ended_before_first_frame" in all_reasons
    ):
        return "no_inbound_audio"
    if "native_call_answer_timeout" in all_events:
        return "native_call_answer_timeout"
    if "failed" in all_statuses:
        return "call_failed"
    if "ended" in all_statuses or "remote_ended" in all_reasons:
        return "call_ended"
    if "remote_track" in all_media_events:
        return "remote_track_seen"
    if "connection_state" in all_media_events and "connected" in all_statuses:
        return "webrtc_connected"
    if "remote_answer_sdp" in all_media_events:
        return "remote_answer_seen"
    if traces:
        return "hermes_trace_seen"
    if simplex_event.get("ok") or call_item.get("ok"):
        return "daemon_call_seen"
    return "no_daemon_call"


async def _cancel_task(task: asyncio.Task) -> None:
    if task.done():
        return
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


async def _simplex_live_debug(
    *,
    ws_url: str,
    timeout_seconds: float,
    settle_seconds: float,
    count: int,
    request_timeout_seconds: float,
    interval_seconds: float,
    trace_root: Path,
    raw_events: bool = False,
) -> dict[str, Any]:
    trace_root.mkdir(parents=True, exist_ok=True)
    loop = asyncio.get_running_loop()
    started_at = loop.time()
    deadline = started_at + max(0.0, float(timeout_seconds))
    before = {
        str(path): _trace_signature(path)
        for path in _iter_trace_paths(trace_root)
    }
    event_task: asyncio.Task | None = None
    if raw_events:
        event_task = asyncio.create_task(
            _simplex_event_watch(ws_url=ws_url, timeout_seconds=timeout_seconds)
        )
    item_task = asyncio.create_task(
        _simplex_watch_all_for_call(
            ws_url=ws_url,
            count=count,
            request_timeout_seconds=request_timeout_seconds,
            timeout_seconds=timeout_seconds,
            interval_seconds=interval_seconds,
        )
    )
    simplex_event: dict[str, Any] | None = None
    call_item: dict[str, Any] | None = None
    tasks = {item_task}
    if event_task is not None:
        tasks.add(event_task)
    traces: list[dict[str, Any]] = []
    verdict = "no_daemon_call"
    decisive_seen = False
    try:
        while loop.time() < deadline:
            remaining = max(0.0, deadline - loop.time())
            wait_for = min(max(0.05, interval_seconds), remaining)
            done: set[asyncio.Task] = set()
            if tasks:
                done, tasks = await asyncio.wait(
                    tasks,
                    timeout=wait_for,
                    return_when=asyncio.FIRST_COMPLETED,
                )
            elif wait_for > 0:
                await asyncio.sleep(wait_for)
            for task in done:
                result = task.result()
                if event_task is not None and task is event_task:
                    simplex_event = result
                else:
                    call_item = result

            new_paths = [
                path
                for path in _iter_trace_paths(trace_root)
                if before.get(str(path)) != _trace_signature(path)
            ]
            traces = [_summarize_trace_file(path) for path in new_paths]
            verdict = _simplex_live_debug_verdict(
                simplex_event=simplex_event or {},
                call_item=call_item or {},
                traces=traces,
            )
            if verdict in _LIVE_DEBUG_DECISIVE_VERDICTS:
                decisive_seen = True
                settle = min(
                    max(0.0, float(settle_seconds)),
                    max(0.0, deadline - loop.time()),
                )
                if settle:
                    await asyncio.sleep(settle)
                    new_paths = [
                        path
                        for path in _iter_trace_paths(trace_root)
                        if before.get(str(path)) != _trace_signature(path)
                    ]
                    traces = [_summarize_trace_file(path) for path in new_paths]
                    verdict = _simplex_live_debug_verdict(
                        simplex_event=simplex_event or {},
                        call_item=call_item or {},
                        traces=traces,
                    )
                break
        for task in tasks:
            await _cancel_task(task)
    finally:
        if event_task is not None:
            await _cancel_task(event_task)
        await _cancel_task(item_task)
    if simplex_event is None:
        simplex_event = {
            "ok": False,
            "changed": False,
            "message": (
                "SimpleX raw event watcher disabled for non-invasive live debug."
                if not raw_events
                else "SimpleX raw event watcher did not complete."
            ),
        }
    if call_item is None:
        call_item = {
            "ok": False,
            "changed": False,
            "message": "SimpleX call item watcher did not complete.",
        }
    if not traces:
        new_paths = [
            path
            for path in _iter_trace_paths(trace_root)
            if before.get(str(path)) != _trace_signature(path)
        ]
        traces = [_summarize_trace_file(path) for path in new_paths]
        verdict = _simplex_live_debug_verdict(
            simplex_event=simplex_event,
            call_item=call_item,
            traces=traces,
        )
    duration = loop.time() - started_at
    acceptance = None
    if traces:
        trace_path = Path(str(traces[0].get("path") or ""))
        if trace_path.exists():
            acceptance = _simplex_acceptance_summary(trace_path, manual_heard=False)
    return {
        "ok": verdict != "no_daemon_call",
        "verdict": verdict,
        "decisive": decisive_seen,
        "timed_out": not decisive_seen and loop.time() >= deadline,
        "duration_seconds": round(duration, 3),
        "raw_events": bool(raw_events),
        "simplex_event": simplex_event,
        "call_item": call_item,
        "new_traces": traces,
        "acceptance": acceptance,
    }


def _handle_trace(args: Any) -> int:
    root = _trace_root(getattr(args, "trace_root", None))
    call_id = getattr(args, "call_id", None)
    limit = int(getattr(args, "lines", 50) or 50)
    if call_id:
        path = _find_trace_path(root, str(call_id))
        if not path.exists():
            print(f"No call trace found: {path}")
            return 1
        for line in _tail_lines(path, limit):
            print(line)
        return 0

    if not root.exists():
        print(f"No call traces found in {root}")
        return 0
    traces = _iter_trace_paths(root)
    if not traces:
        print(f"No call traces found in {root}")
        return 0
    for path in traces:
        try:
            label = str(path.relative_to(root))
        except ValueError:
            label = path.name
        print(f"{label}\t{path.stat().st_size} bytes")
    return 0


def _coerce_sidecar_command(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return shlex.split(value)
    return [str(part) for part in value if str(part)]


def _module_available(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def _binary_available(name: str) -> bool:
    return shutil.which(name) is not None


def _call_voice_provider_health() -> dict[str, Any]:
    try:
        from hermes_cli.config import load_config

        cfg = load_config() or {}
    except Exception as exc:
        return {
            "ok": False,
            "error": f"failed to load config: {exc}",
            "stt": {"available": False, "local": False},
            "tts": {"available": False, "local": False},
        }
    if not isinstance(cfg, dict):
        cfg = {}
    stt_cfg = cfg.get("stt") if isinstance(cfg.get("stt"), dict) else {}
    tts_cfg = cfg.get("tts") if isinstance(cfg.get("tts"), dict) else {}

    requested_stt = str(stt_cfg.get("provider") or "local").strip() or "local"
    try:
        from tools import transcription_tools

        resolved_stt = transcription_tools._get_provider(stt_cfg)  # type: ignore[attr-defined]
        stt_error = ""
    except Exception as exc:
        resolved_stt = requested_stt
        stt_error = str(exc)
    stt_local = resolved_stt in {"local", "local_command"}
    stt_available = (
        (_module_available("faster_whisper") if resolved_stt == "local" else False)
        or (_binary_available("whisper") if resolved_stt == "local_command" else False)
        or (resolved_stt not in {"local", "local_command"} and not stt_error)
    )

    tts_provider = str(tts_cfg.get("provider") or "edge").strip() or "edge"
    local_tts_providers = {"neutts", "kittentts", "piper"}
    tts_local = tts_provider in local_tts_providers
    tts_available = False
    tts_error = ""
    if tts_provider == "neutts":
        tts_available = _module_available("neutts")
    elif tts_provider == "kittentts":
        tts_available = _module_available("kittentts")
    elif tts_provider == "piper":
        tts_available = _module_available("piper")
    elif tts_provider == "edge":
        tts_available = _module_available("edge_tts")
    elif tts_provider in {"elevenlabs", "openai", "xai", "minimax", "gemini"}:
        tts_available = True
    else:
        provider_cfg = None
        providers = tts_cfg.get("providers")
        if isinstance(providers, dict):
            provider_cfg = providers.get(tts_provider)
        if isinstance(provider_cfg, dict) and provider_cfg.get("type") == "command":
            command = str(provider_cfg.get("command") or "").strip()
            tts_available = bool(command)
            tts_local = bool(provider_cfg.get("local", False))
        else:
            tts_error = "unknown TTS provider"

    return {
        "ok": bool(stt_local and stt_available and tts_local and tts_available),
        "stt": {
            "requested_provider": requested_stt,
            "provider": resolved_stt,
            "local": stt_local,
            "available": bool(stt_available),
            "error": stt_error,
        },
        "tts": {
            "provider": tts_provider,
            "local": tts_local,
            "available": bool(tts_available),
            "error": tts_error,
        },
    }


def _handle_voice_health(args: Any) -> int:
    result = _call_voice_provider_health()
    if bool(getattr(args, "json", False)):
        print(jsonlib.dumps(result, sort_keys=True))
    else:
        status = "PASS" if result.get("ok") else "FAIL"
        print(f"{status}: native call voice provider health")
        print(f"stt: {jsonlib.dumps(result.get('stt'), sort_keys=True)}")
        print(f"tts: {jsonlib.dumps(result.get('tts'), sort_keys=True)}")
        if result.get("error"):
            print(f"error: {result['error']}")
    return 0 if result.get("ok") else 1


def _chat_ref_for_simplex_contact(contact_id: str) -> str:
    if str(contact_id).startswith("group:"):
        return f"#{str(contact_id)[6:]}"
    if str(contact_id).startswith(("@", "#")):
        return str(contact_id)
    return f"@{contact_id}"


def _preference_enabled(preferences: dict[str, Any], key: str) -> bool:
    value = preferences.get(key)
    if not isinstance(value, dict):
        return False
    enabled = value.get("enabled")
    if isinstance(enabled, dict):
        return bool(enabled.get("forContact") and enabled.get("forUser"))
    allow = value.get("allow")
    if isinstance(allow, str):
        return allow.lower() in {"yes", "always"}
    return False


def _summarize_simplex_item(item: dict[str, Any]) -> dict[str, Any]:
    meta = item.get("meta") if isinstance(item.get("meta"), dict) else {}
    content = item.get("content") if isinstance(item.get("content"), dict) else {}
    chat_dir = item.get("chatDir") if isinstance(item.get("chatDir"), dict) else {}
    msg_content = content.get("msgContent")
    if not isinstance(msg_content, dict):
        msg_content = {}
    text = msg_content.get("text")
    return {
        "item_id": meta.get("itemId"),
        "created_at": meta.get("createdAt"),
        "direction": chat_dir.get("type"),
        "content_type": content.get("type"),
        "msg_type": msg_content.get("type"),
        "text_chars": len(text) if isinstance(text, str) else 0,
    }


def _item_mentions_call(item: dict[str, Any]) -> bool:
    content = item.get("content") if isinstance(item.get("content"), dict) else {}
    content_type = str(content.get("type") or "").lower()
    if "call" in content_type:
        return True
    return any(
        key in content
        for key in (
            "callType",
            "rtcSession",
            "callDhPubKey",
            "answer",
            "extraInfo",
            "extra",
        )
    )


def _item_id(item: dict[str, Any]) -> int:
    meta = item.get("meta") if isinstance(item.get("meta"), dict) else {}
    try:
        return int(meta.get("itemId") or 0)
    except (TypeError, ValueError):
        return 0


def _summarize_simplex_chat_response(
    response: dict[str, Any],
    *,
    contact_id: str,
) -> dict[str, Any]:
    resp = response.get("resp") if isinstance(response.get("resp"), dict) else response
    chat = resp.get("chat") if isinstance(resp.get("chat"), dict) else {}
    chat_info = chat.get("chatInfo") if isinstance(chat.get("chatInfo"), dict) else {}
    contact = chat_info.get("contact") if isinstance(chat_info.get("contact"), dict) else {}
    active_conn = contact.get("activeConn")
    if not isinstance(active_conn, dict):
        active_conn = {}
    conn_status = active_conn.get("connStatus")
    if not isinstance(conn_status, dict):
        conn_status = {}
    preferences = contact.get("mergedPreferences")
    if not isinstance(preferences, dict):
        preferences = {}
    chat_items = chat.get("chatItems")
    if not isinstance(chat_items, list):
        chat_items = []
    typed_items = [item for item in chat_items if isinstance(item, dict)]
    call_items = [item for item in typed_items if _item_mentions_call(item)]
    latest_item = max(typed_items, key=_item_id, default=None)
    latest_call_item = max(call_items, key=_item_id, default=None)
    return {
        "ok": bool(resp.get("type") == "apiChat"),
        "contact_id": str(contact_id),
        "contact_active": contact.get("contactStatus") == "active",
        "connection_ready": conn_status.get("type") == "ready",
        "calls_enabled": _preference_enabled(preferences, "calls"),
        "voice_enabled": _preference_enabled(preferences, "voice"),
        "latest_item": _summarize_simplex_item(latest_item) if latest_item else None,
        "latest_call_item": (
            _summarize_simplex_item(latest_call_item) if latest_call_item else None
        ),
        "recent_call_items": len(call_items),
        "unread_count": (
            chat.get("chatStats", {}).get("unreadCount")
            if isinstance(chat.get("chatStats"), dict)
            else None
        ),
    }


def _contact_id_from_chat(chat: dict[str, Any]) -> str:
    chat_info = chat.get("chatInfo") if isinstance(chat.get("chatInfo"), dict) else {}
    contact = chat_info.get("contact") if isinstance(chat_info.get("contact"), dict) else {}
    contact_id = contact.get("contactId")
    if contact_id is not None:
        return str(contact_id)
    group = chat_info.get("groupInfo") if isinstance(chat_info.get("groupInfo"), dict) else {}
    group_id = group.get("groupId")
    if group_id is not None:
        return f"group:{group_id}"
    return "unknown"


def _summarize_simplex_chats_response(response: dict[str, Any]) -> dict[str, Any]:
    resp = response.get("resp") if isinstance(response.get("resp"), dict) else response
    chats = resp.get("chats")
    if not isinstance(chats, list):
        chats = []
    contacts = []
    for chat in chats:
        if not isinstance(chat, dict):
            continue
        chat_info = chat.get("chatInfo") if isinstance(chat.get("chatInfo"), dict) else {}
        chat_type = str(chat_info.get("type") or "")
        if chat_type not in {"direct", "group"}:
            continue
        contacts.append(
            _summarize_simplex_chat_response(
                {"resp": {"type": "apiChat", "chat": chat}},
                contact_id=_contact_id_from_chat(chat),
            )
        )
    return {
        "ok": bool(resp.get("type") == "apiChats"),
        "contacts": contacts,
        "contact_count": len(contacts),
    }


async def _simplex_ws_request(
    *,
    ws_url: str,
    command: str,
    timeout_seconds: float,
) -> dict[str, Any]:
    try:
        import websockets
    except ImportError as exc:
        return {
            "type": "error",
            "error": f"websockets unavailable: {exc}",
        }
    corr_id = f"hermes-calls-{uuid.uuid4().hex[:12]}"
    async with websockets.connect(ws_url, open_timeout=timeout_seconds) as ws:
        await ws.send(jsonlib.dumps({"corrId": corr_id, "cmd": command}))
        deadline = asyncio.get_running_loop().time() + timeout_seconds
        while True:
            remaining = deadline - asyncio.get_running_loop().time()
            if remaining <= 0:
                return {"type": "error", "error": "timed out waiting for SimpleX response"}
            raw = await asyncio.wait_for(ws.recv(), timeout=remaining)
            payload = jsonlib.loads(raw)
            if payload.get("corrId") == corr_id:
                return payload


_SIMPLEX_REDACT_VALUE_KEYS = {
    "aeskey",
    "callcryption",
    "calldhprivkey",
    "calldhpubkey",
    "displayname",
    "extradata",
    "file",
    "filepath",
    "formattedtext",
    "fullName".lower(),
    "image",
    "localalias",
    "localdisplayname",
    "message",
    "msgcontent",
    "profile",
    "profiles",
    "rtcicecandidates",
    "rtcsession",
    "secret",
    "sharedkey",
    "text",
    "uri",
}


def _redact_simplex_event(value: Any) -> Any:
    if isinstance(value, dict):
        redacted = {}
        for key, item in value.items():
            normalized_key = str(key).lower()
            if normalized_key in _SIMPLEX_REDACT_VALUE_KEYS:
                redacted[key] = "[REDACTED]"
            else:
                redacted[key] = _redact_simplex_event(item)
        return redacted
    if isinstance(value, list):
        return [_redact_simplex_event(item) for item in value]
    return value


def _simplex_event_payload(event: dict[str, Any]) -> dict[str, Any]:
    resp = event.get("resp")
    if isinstance(resp, dict):
        return resp
    return event


def _simplex_event_type(event: dict[str, Any]) -> str:
    payload = _simplex_event_payload(event)
    return str(payload.get("type") or "")


def _simplex_event_is_call(event: dict[str, Any]) -> bool:
    event_type = _simplex_event_type(event).lower()
    if event_type in {"callinvitation", "callanswer", "callextrainfo", "callended"}:
        return True
    payload = _simplex_event_payload(event)
    if "call" in event_type:
        return True
    return any(
        key in payload
        for key in (
            "callInvitation",
            "callType",
            "rtcSession",
            "callDhPubKey",
            "answer",
            "extraInfo",
            "extra",
        )
    )


async def _simplex_event_watch(
    *,
    ws_url: str,
    timeout_seconds: float,
) -> dict[str, Any]:
    try:
        import websockets
    except ImportError as exc:
        return {
            "ok": False,
            "changed": False,
            "checks": 0,
            "error": f"websockets unavailable: {exc}",
        }
    deadline = asyncio.get_running_loop().time() + max(0.0, timeout_seconds)
    checks = 0
    last_event_type = None
    try:
        async with websockets.connect(ws_url, open_timeout=min(10.0, timeout_seconds)) as ws:
            while True:
                remaining = deadline - asyncio.get_running_loop().time()
                if remaining <= 0:
                    return {
                        "ok": False,
                        "changed": False,
                        "checks": checks,
                        "last_event_type": last_event_type,
                        "message": "No SimpleX call websocket event observed before timeout.",
                    }
                raw = await asyncio.wait_for(ws.recv(), timeout=remaining)
                try:
                    event = jsonlib.loads(raw)
                except jsonlib.JSONDecodeError:
                    checks += 1
                    last_event_type = "invalid-json"
                    continue
                if not isinstance(event, dict):
                    checks += 1
                    last_event_type = type(event).__name__
                    continue
                checks += 1
                last_event_type = _simplex_event_type(event)
                if _simplex_event_is_call(event):
                    return {
                        "ok": True,
                        "changed": True,
                        "checks": checks,
                        "event_type": last_event_type,
                        "event": _redact_simplex_event(event),
                    }
    except asyncio.TimeoutError:
        return {
            "ok": False,
            "changed": False,
            "checks": checks,
            "last_event_type": last_event_type,
            "message": "No SimpleX call websocket event observed before timeout.",
        }
    except Exception as exc:
        return {
            "ok": False,
            "changed": False,
            "checks": checks,
            "last_event_type": last_event_type,
            "error": str(exc),
        }


async def _simplex_health_check(
    *,
    ws_url: str,
    contact_id: str,
    count: int,
    timeout_seconds: float,
) -> dict[str, Any]:
    response = await _simplex_ws_request(
        ws_url=ws_url,
        command=f"/_get chat {_chat_ref_for_simplex_contact(contact_id)} count={int(count)}",
        timeout_seconds=timeout_seconds,
    )
    if response.get("type") == "error":
        return {
            "ok": False,
            "contact_id": str(contact_id),
            "error": str(response.get("error") or "SimpleX daemon request failed"),
        }
    return _summarize_simplex_chat_response(response, contact_id=str(contact_id))


async def _simplex_all_chats_health_check(
    *,
    ws_url: str,
    count: int,
    timeout_seconds: float,
) -> dict[str, Any]:
    response = await _simplex_ws_request(
        ws_url=ws_url,
        command=f"/_get chats 1 pcc=on count={int(count)}",
        timeout_seconds=timeout_seconds,
    )
    if response.get("type") == "error":
        return {
            "ok": False,
            "error": str(response.get("error") or "SimpleX daemon request failed"),
            "contacts": [],
            "contact_count": 0,
        }
    return _summarize_simplex_chats_response(response)


def _handle_simplex_health(args: Any) -> int:
    contact_id = str(getattr(args, "contact_id", None) or "4")
    if contact_id.lower() == "all":
        result = asyncio.run(
            _simplex_all_chats_health_check(
                ws_url=str(getattr(args, "ws_url", None) or "ws://127.0.0.1:5225"),
                count=int(getattr(args, "count", 10) or 10),
                timeout_seconds=float(getattr(args, "timeout", 5.0) or 5.0),
            )
        )
    else:
        result = asyncio.run(
            _simplex_health_check(
                ws_url=str(getattr(args, "ws_url", None) or "ws://127.0.0.1:5225"),
                contact_id=contact_id,
                count=int(getattr(args, "count", 10) or 10),
                timeout_seconds=float(getattr(args, "timeout", 5.0) or 5.0),
            )
        )
    if bool(getattr(args, "json", False)):
        print(jsonlib.dumps(result, sort_keys=True))
    else:
        status = "PASS" if result.get("ok") else "FAIL"
        print(f"{status}: SimpleX daemon contact health for @{result.get('contact_id')}")
        for key in (
            "contact_active",
            "connection_ready",
            "calls_enabled",
            "voice_enabled",
            "recent_call_items",
            "unread_count",
        ):
            print(f"{key}: {result.get(key)}")
        if result.get("latest_item"):
            print(f"latest_item: {jsonlib.dumps(result['latest_item'], sort_keys=True)}")
        if result.get("latest_call_item"):
            print(
                "latest_call_item: "
                f"{jsonlib.dumps(result['latest_call_item'], sort_keys=True)}"
            )
        if result.get("error"):
            print(f"error: {result['error']}")
    return 0 if result.get("ok") else 1


def _simplex_item_id(summary: dict[str, Any] | None) -> int:
    if not isinstance(summary, dict):
        return 0
    try:
        return int(summary.get("item_id") or 0)
    except (TypeError, ValueError):
        return 0


def _latest_call_ids_by_contact(health: dict[str, Any]) -> dict[str, int]:
    contacts = health.get("contacts")
    if not isinstance(contacts, list):
        return {}
    result = {}
    for contact in contacts:
        if not isinstance(contact, dict):
            continue
        contact_id = str(contact.get("contact_id") or "unknown")
        result[contact_id] = _simplex_item_id(contact.get("latest_call_item"))
    return result


async def _simplex_watch_for_call(
    *,
    ws_url: str,
    contact_id: str,
    count: int,
    request_timeout_seconds: float,
    timeout_seconds: float,
    interval_seconds: float,
) -> dict[str, Any]:
    baseline = await _simplex_health_check(
        ws_url=ws_url,
        contact_id=contact_id,
        count=count,
        timeout_seconds=request_timeout_seconds,
    )
    baseline_call = baseline.get("latest_call_item")
    baseline_id = _simplex_item_id(baseline_call)
    deadline = asyncio.get_running_loop().time() + max(0.0, timeout_seconds)
    checks = 1
    latest = baseline
    while asyncio.get_running_loop().time() < deadline:
        await asyncio.sleep(max(0.05, interval_seconds))
        latest = await _simplex_health_check(
            ws_url=ws_url,
            contact_id=contact_id,
            count=count,
            timeout_seconds=request_timeout_seconds,
        )
        checks += 1
        latest_call = latest.get("latest_call_item")
        latest_id = _simplex_item_id(latest_call)
        if latest.get("ok") and latest_id > baseline_id:
            return {
                "ok": True,
                "changed": True,
                "contact_id": str(contact_id),
                "checks": checks,
                "baseline_call_item": baseline_call,
                "latest_call_item": latest_call,
                "latest_item": latest.get("latest_item"),
            }
    return {
        "ok": False,
        "changed": False,
        "contact_id": str(contact_id),
        "checks": checks,
        "baseline_call_item": baseline_call,
        "latest_call_item": latest.get("latest_call_item"),
        "latest_item": latest.get("latest_item"),
        "message": "No new SimpleX call item observed before timeout.",
    }


async def _simplex_watch_all_for_call(
    *,
    ws_url: str,
    count: int,
    request_timeout_seconds: float,
    timeout_seconds: float,
    interval_seconds: float,
) -> dict[str, Any]:
    baseline = await _simplex_all_chats_health_check(
        ws_url=ws_url,
        count=count,
        timeout_seconds=request_timeout_seconds,
    )
    baseline_ids = _latest_call_ids_by_contact(baseline)
    deadline = asyncio.get_running_loop().time() + max(0.0, timeout_seconds)
    checks = 1
    latest = baseline
    while asyncio.get_running_loop().time() < deadline:
        await asyncio.sleep(max(0.05, interval_seconds))
        latest = await _simplex_all_chats_health_check(
            ws_url=ws_url,
            count=count,
            timeout_seconds=request_timeout_seconds,
        )
        checks += 1
        contacts = latest.get("contacts") if isinstance(latest.get("contacts"), list) else []
        for contact in contacts:
            if not isinstance(contact, dict):
                continue
            contact_id = str(contact.get("contact_id") or "unknown")
            latest_call = contact.get("latest_call_item")
            latest_id = _simplex_item_id(latest_call)
            if latest.get("ok") and latest_id > baseline_ids.get(contact_id, 0):
                return {
                    "ok": True,
                    "changed": True,
                    "contact_id": "all",
                    "changed_contact_id": contact_id,
                    "checks": checks,
                    "baseline_call_item": None,
                    "latest_call_item": latest_call,
                    "latest_item": contact.get("latest_item"),
                    "contact_count": latest.get("contact_count"),
                }
    return {
        "ok": False,
        "changed": False,
        "contact_id": "all",
        "checks": checks,
        "baseline_call_ids": baseline_ids,
        "latest_call_ids": _latest_call_ids_by_contact(latest),
        "contact_count": latest.get("contact_count"),
        "message": "No new SimpleX call item observed before timeout.",
    }


def _handle_simplex_watch(args: Any) -> int:
    contact_id = str(getattr(args, "contact_id", None) or "4")
    if contact_id.lower() == "all":
        result = asyncio.run(
            _simplex_watch_all_for_call(
                ws_url=str(getattr(args, "ws_url", None) or "ws://127.0.0.1:5225"),
                count=int(getattr(args, "count", 50) or 50),
                request_timeout_seconds=float(
                    getattr(args, "request_timeout", 5.0) or 5.0
                ),
                timeout_seconds=float(getattr(args, "timeout", 60.0) or 60.0),
                interval_seconds=float(getattr(args, "interval", 1.0) or 1.0),
            )
        )
    else:
        result = asyncio.run(
            _simplex_watch_for_call(
                ws_url=str(getattr(args, "ws_url", None) or "ws://127.0.0.1:5225"),
                contact_id=contact_id,
                count=int(getattr(args, "count", 50) or 50),
                request_timeout_seconds=float(
                    getattr(args, "request_timeout", 5.0) or 5.0
                ),
                timeout_seconds=float(getattr(args, "timeout", 60.0) or 60.0),
                interval_seconds=float(getattr(args, "interval", 1.0) or 1.0),
            )
        )
    if bool(getattr(args, "json", False)):
        print(jsonlib.dumps(result, sort_keys=True))
    else:
        status = "PASS" if result.get("ok") else "FAIL"
        print(f"{status}: SimpleX call item watch for @{result.get('contact_id')}")
        print(f"changed: {result.get('changed')}")
        print(f"checks: {result.get('checks')}")
        print(
            "baseline_call_item: "
            f"{jsonlib.dumps(result.get('baseline_call_item'), sort_keys=True)}"
        )
        print(
            "latest_call_item: "
            f"{jsonlib.dumps(result.get('latest_call_item'), sort_keys=True)}"
        )
        if result.get("message"):
            print(f"message: {result['message']}")
    return 0 if result.get("ok") else 1


def _handle_simplex_call(args: Any) -> int:
    from gateway.calls.native.outbound_control import (
        enqueue_simplex_outbound_call_request,
        wait_for_simplex_outbound_call_response,
    )

    contact_id = str(getattr(args, "contact_id", None) or "4")
    wait_timeout = float(getattr(args, "wait_timeout", 0.0) or 0.0)
    result = enqueue_simplex_outbound_call_request(
        contact_id=contact_id,
        reason=str(getattr(args, "reason", "") or ""),
    )
    if wait_timeout > 0:
        gateway_response = wait_for_simplex_outbound_call_response(
            str(result["request_id"]),
            timeout_seconds=wait_timeout,
        )
        if gateway_response is None:
            result = {
                **result,
                "ok": False,
                "gateway_response": None,
                "message": (
                    "Timed out waiting for the running gateway to pick up "
                    "the outbound SimpleX call request."
                ),
            }
        else:
            result = {
                **result,
                "ok": bool(gateway_response.get("ok")),
                "gateway_response": gateway_response,
                "call_id": gateway_response.get("call_id"),
                "message": gateway_response.get("message", ""),
            }
    if bool(getattr(args, "json", False)):
        print(jsonlib.dumps(result, sort_keys=True))
    else:
        status = "PASS" if result.get("ok") else "FAIL"
        print(f"{status}: queued SimpleX outbound call request for @{contact_id}")
        print(f"request_id: {result.get('request_id')}")
        if result.get("call_id"):
            print(f"call_id: {result.get('call_id')}")
        if result.get("message"):
            print(f"message: {result['message']}")
    return 0 if result.get("ok") else 1


def _handle_simplex_events(args: Any) -> int:
    result = asyncio.run(
        _simplex_event_watch(
            ws_url=str(getattr(args, "ws_url", None) or "ws://127.0.0.1:5225"),
            timeout_seconds=float(getattr(args, "timeout", 60.0) or 60.0),
        )
    )
    if isinstance(result.get("event"), dict):
        result = {**result, "event": _redact_simplex_event(result["event"])}
    if bool(getattr(args, "json", False)):
        print(jsonlib.dumps(result, sort_keys=True))
    else:
        status = "PASS" if result.get("ok") else "FAIL"
        print(f"{status}: SimpleX raw call event watch")
        print(f"changed: {result.get('changed')}")
        print(f"checks: {result.get('checks')}")
        if result.get("event_type"):
            print(f"event_type: {result['event_type']}")
        if result.get("last_event_type"):
            print(f"last_event_type: {result['last_event_type']}")
        if result.get("event"):
            print(f"event: {jsonlib.dumps(result['event'], sort_keys=True)}")
        if result.get("message"):
            print(f"message: {result['message']}")
        if result.get("error"):
            print(f"error: {result['error']}")
    return 0 if result.get("ok") else 1


def _handle_simplex_live_debug(args: Any) -> int:
    result = asyncio.run(
        _simplex_live_debug(
            ws_url=str(getattr(args, "ws_url", None) or "ws://127.0.0.1:5225"),
            timeout_seconds=float(getattr(args, "timeout", 75.0) or 75.0),
            settle_seconds=float(getattr(args, "settle", 8.0) or 8.0),
            count=int(getattr(args, "count", 50) or 50),
            request_timeout_seconds=float(
                getattr(args, "request_timeout", 5.0) or 5.0
            ),
            interval_seconds=float(getattr(args, "interval", 1.0) or 1.0),
            trace_root=_trace_root(getattr(args, "trace_root", None)),
            raw_events=bool(getattr(args, "raw_events", False)),
        )
    )
    if bool(getattr(args, "json", False)):
        print(jsonlib.dumps(result, sort_keys=True))
    else:
        status = "PASS" if result.get("ok") else "FAIL"
        print(f"{status}: SimpleX live call debug")
        print(f"verdict: {result.get('verdict')}")
        print(
            "simplex_event: "
            f"{jsonlib.dumps(result.get('simplex_event'), sort_keys=True)}"
        )
        print(
            "call_item: "
            f"{jsonlib.dumps(result.get('call_item'), sort_keys=True)}"
        )
        traces = result.get("new_traces")
        if traces:
            print(f"new_traces: {jsonlib.dumps(traces, sort_keys=True)}")
    return 0 if result.get("ok") else 1


def _handle_simplex_acceptance(args: Any) -> int:
    root = _trace_root(getattr(args, "trace_root", None))
    call_id = getattr(args, "call_id", None)
    if call_id:
        path = _find_trace_path(root, str(call_id))
    else:
        traces = _iter_trace_paths(root) if root.exists() else []
        path = traces[0] if traces else root / "unknown.jsonl"
    result = _simplex_acceptance_summary(
        path,
        manual_heard=bool(getattr(args, "manual_heard", False)),
    )
    if bool(getattr(args, "json", False)):
        print(jsonlib.dumps(result, sort_keys=True))
    else:
        status = "PASS" if result.get("ok") else "PENDING"
        print(f"{status}: SimpleX native voice acceptance")
        print(f"technical_ok: {result.get('technical_ok')}")
        print(f"manual_ok: {result.get('manual_ok')}")
        print(f"manual_required: {result.get('manual_required')}")
        print(f"trace: {result.get('trace_path')}")
        print(f"missing: {', '.join(result.get('missing') or []) or 'none'}")
        checks = result.get("checks")
        if isinstance(checks, dict):
            for name, ok in checks.items():
                print(f"{name}: {ok}")
        if result.get("error"):
            print(f"error: {result['error']}")
    return 0 if result.get("ok") else 1


def _handle_simplex_observe(args: Any) -> int:
    root = _trace_root(getattr(args, "trace_root", None))
    call_id = getattr(args, "call_id", None)
    if call_id:
        path = _find_trace_path(root, str(call_id))
    else:
        traces = _iter_trace_paths(root) if root.exists() else []
        path = traces[0] if traces else root / "unknown.jsonl"
    result = _simplex_observation_summary(path)
    if bool(getattr(args, "json", False)):
        print(jsonlib.dumps(result, sort_keys=True))
    else:
        status = "PASS" if result.get("ok") else "NO-TURNS"
        print(f"{status}: SimpleX observed voice turns")
        print(f"trace: {result.get('trace_path')}")
        print(f"call_id: {result.get('call_id')}")
        print(f"weather_intent_observed: {result.get('weather_intent_observed')}")
        for idx, turn in enumerate(result.get("turns") or [], start=1):
            print(f"turn {idx} transcript: {turn.get('transcript_preview')}")
            print(f"turn {idx} response: {turn.get('agent_response_preview')}")
            print(
                f"turn {idx} tts_playback_completed: "
                f"{turn.get('tts_playback_completed')}"
            )
            print(f"turn {idx} tool_intents: {', '.join(turn.get('tool_intents') or [])}")
        if result.get("error"):
            print(f"error: {result['error']}")
    return 0 if result.get("ok") else 1


def _handle_simulate_simplex_native(args: Any) -> int:
    from gateway.calls.native.simulation import run_native_call_simulation

    result = asyncio.run(
        run_native_call_simulation(
            command=_coerce_sidecar_command(getattr(args, "sidecar_command", None)),
            call_id=str(getattr(args, "call_id", None) or "simulated-call"),
            contact_id=str(getattr(args, "contact_id", None) or "simulated-contact"),
            trace_root=_trace_root(getattr(args, "trace_root", None)),
            encrypted=bool(getattr(args, "encrypted", False)),
            shared_key=getattr(args, "shared_key", None),
            audio_path=getattr(args, "audio_path", None),
            timeout_seconds=float(getattr(args, "timeout", 10.0) or 10.0),
        )
    )
    payload = {
        "ok": result.ok,
        "code": result.code,
        "message": result.message,
        "call_id": result.call_id,
        "contact_id": result.contact_id,
        "trace_path": str(result.trace_path),
        "events": list(result.events),
    }
    if bool(getattr(args, "json", False)):
        print(jsonlib.dumps(payload, sort_keys=True))
    else:
        status = "PASS" if result.ok else "FAIL"
        print(f"{status}: {result.message}")
        print(f"code: {result.code}")
        print(f"trace: {result.trace_path}")
        print(f"events: {', '.join(result.events)}")
    return 0 if result.ok else 1


async def _run_stream_simulation(
    *,
    call_id: str,
    contact_id: str,
    caller_text: str,
    response_text: str,
    barge_in: bool,
    brain_delay_ms: int,
) -> dict[str, Any]:
    """Drive the streaming simulation end-to-end.

    The drive loop lives here (in hermes_cli/) rather than in the slice's
    simulate.py because ``asyncio.sleep(0)`` is forbidden in
    ``gateway/calls/native/streaming/**`` by the ast-grep no-walltime rule.
    Settling between clock advances requires yielding to the event loop, which
    is only expressible via ``asyncio.sleep(0)``.
    """
    from gateway.calls.native.streaming.simulate import build_stream_simulation

    sim = build_stream_simulation(
        call_id=call_id,
        contact_id=contact_id,
        caller_text=caller_text,
        response_text=response_text,
        barge_in=barge_in,
        brain_delay_ms=brain_delay_ms,
    )

    async def settle(ticks: int = 5) -> None:
        for _ in range(ticks):
            await asyncio.sleep(0)

    async def push_frame(seq: int) -> None:
        await sim.transport.push_inbound(sim.make_frame(seq))
        await settle()

    async def drain(total_ms: int, step_ms: int = 20) -> None:
        steps = max(1, total_ms // step_ms)
        for _ in range(steps):
            await sim.clock.advance(step_ms)
            await settle(ticks=3)

    # Start the session.
    run_task = asyncio.create_task(sim.session.run())
    await settle()

    # Push seq 0: triggers ENDPOINT_DETECTED → assistant turn launched.
    await push_frame(0)

    if barge_in:
        # Let TTS emit the first word's frames (10 frames_per_word × 20ms = 200ms).
        await drain(220)

        # Push seq 1: USER_SPEECH_STARTED → fast-reflex vad_trigger flush.
        await push_frame(1)

        # Advance past min_speech_ms (40ms) so policy escalates on next event.
        await drain(60)

        # Push seq 2: USER_SPEECH_STOPPED (escalating) → INTERRUPT decision.
        await push_frame(2)

    # Close inbound and drain the clock until the session finishes.
    await sim.transport.end_inbound()
    for _ in range(400):
        if run_task.done():
            break
        await sim.clock.advance(20)
        await settle(ticks=3)
    await asyncio.wait_for(run_task, timeout=5.0)

    return sim.summary()


def _handle_simplex_simulate_stream(args: Any) -> int:
    result = asyncio.run(
        _run_stream_simulation(
            call_id=str(getattr(args, "call_id", None) or "stream-sim"),
            contact_id=str(getattr(args, "contact_id", None) or "sim-contact"),
            caller_text=str(
                getattr(args, "caller_text", None) or "what's the weather"
            ),
            response_text=str(
                getattr(args, "response_text", None) or "It's sunny today."
            ),
            barge_in=bool(getattr(args, "barge_in", False)),
            brain_delay_ms=int(getattr(args, "brain_delay_ms", 0) or 0),
        )
    )
    if bool(getattr(args, "json", False)):
        print(jsonlib.dumps(result, sort_keys=True))
    else:
        status = "PASS" if result.get("ok") else "FAIL"
        print(f"{status}: streaming simulation")
        print(f"code: {result.get('code')}")
        print(f"call_id: {result.get('call_id')}")
        turns = result.get("turns") or []
        print(f"turns: {len(turns)}")
        for idx, turn in enumerate(turns, start=1):
            print(
                f"  turn {idx}: ended_reason={turn.get('ended_reason')} "
                f"interrupted={turn.get('interrupted')} "
                f"heard_chars={turn.get('heard_chars')} "
                f"abandoned_chars={turn.get('abandoned_chars')}"
            )
        print(f"outbound_audio_frames: {result.get('outbound_audio_frames')}")
        print(f"flushes: {', '.join(result.get('flushes') or []) or 'none'}")
    return 0 if result.get("ok") else 1


def _handle_simplex_native_sidecar(_args: Any) -> int:
    from gateway.calls.native.aiortc_engine import run_simplex_aiortc_sidecar

    asyncio.run(run_simplex_aiortc_sidecar())
    return 0


def _handle_loopback_aiortc(args: Any) -> int:
    from gateway.calls.native.aiortc_engine import run_aiortc_loopback_probe

    result = asyncio.run(
        run_aiortc_loopback_probe(
            timeout_seconds=float(getattr(args, "timeout", 8.0) or 8.0),
            require_voice_turn=bool(getattr(args, "voice_turn", False)),
        )
    )
    payload = {
        "ok": bool(result.ok),
        "message": str(result.message or ""),
        "remote_audio_frames": int(result.remote_audio_frames),
        "voice_turns": int(getattr(result, "voice_turns", 0) or 0),
        "voice_pcm_bytes": int(getattr(result, "voice_pcm_bytes", 0) or 0),
        "local_sdp": dict(result.local_sdp or {}),
        "remote_sdp": dict(result.remote_sdp or {}),
        "stats": dict(result.stats or {}),
    }
    if bool(getattr(args, "json", False)):
        print(jsonlib.dumps(payload, sort_keys=True))
    else:
        status = "PASS" if result.ok else "FAIL"
        print(
            f"{status}: aiortc loopback remote frames={result.remote_audio_frames}, "
            f"voice turns={payload['voice_turns']}, pcm bytes={payload['voice_pcm_bytes']}"
        )
        if result.message:
            print(f"message: {result.message}")
        print(f"local_sdp: {jsonlib.dumps(payload['local_sdp'], sort_keys=True)}")
        print(f"remote_sdp: {jsonlib.dumps(payload['remote_sdp'], sort_keys=True)}")
    return 0 if result.ok else 1


def _handle_simplex_simulate_voice_turn(args: Any) -> int:
    from gateway.calls.native.aiortc_engine import run_aiortc_voice_turn_simulation

    result = asyncio.run(
        run_aiortc_voice_turn_simulation(
            call_id=str(getattr(args, "call_id", None) or "simulated-voice-call"),
            contact_id=str(getattr(args, "contact_id", None) or "simulated-contact"),
            trace_root=_trace_root(getattr(args, "trace_root", None)),
            audio_path=getattr(args, "audio_path", None),
            caller_text=str(
                getattr(args, "caller_text", None) or "Hermes simulation check."
            ),
            expected_transcript=getattr(args, "expect_transcript", None),
            timeout_seconds=float(getattr(args, "timeout", 12.0) or 12.0),
        )
    )
    payload = {
        "ok": bool(result.ok),
        "code": str(result.code),
        "message": str(result.message),
        "call_id": str(result.call_id),
        "contact_id": str(result.contact_id),
        "trace_path": str(result.trace_path),
        "offer_sent": bool(result.offer_sent),
        "answer_applied": bool(result.answer_applied),
        "connected": bool(result.connected),
        "inbound_audio_frames": int(result.inbound_audio_frames),
        "transcript_chars": int(result.transcript_chars),
        "expected_transcript_present": result.expected_transcript_present,
        "agent_response_chars": int(result.agent_response_chars),
        "tts_audio_bytes": int(result.tts_audio_bytes),
        "remote_received_audio_frames": int(result.remote_received_audio_frames),
        "remote_received_non_silent_frames": int(
            result.remote_received_non_silent_frames
        ),
        "local_sdp": dict(result.local_sdp or {}),
        "remote_sdp": dict(result.remote_sdp or {}),
        "events": list(result.events),
    }
    if bool(getattr(args, "json", False)):
        print(jsonlib.dumps(payload, sort_keys=True))
    else:
        status = "PASS" if result.ok else "FAIL"
        print(f"{status}: {result.message}")
        print(f"code: {result.code}")
        print(f"trace: {result.trace_path}")
        print(f"connected: {payload['connected']}")
        print(f"inbound_audio_frames: {payload['inbound_audio_frames']}")
        print(f"transcript_chars: {payload['transcript_chars']}")
        print(f"agent_response_chars: {payload['agent_response_chars']}")
        print(f"tts_audio_bytes: {payload['tts_audio_bytes']}")
        print(
            "remote_received_non_silent_frames: "
            f"{payload['remote_received_non_silent_frames']}"
        )
    return 0 if result.ok else 1


def cmd_calls(args: Any) -> int:
    command = getattr(args, "calls_command", None) or "trace"
    if command == "trace":
        return _handle_trace(args)
    if command == "simulate-simplex-native":
        return _handle_simulate_simplex_native(args)
    if command == "loopback-aiortc":
        return _handle_loopback_aiortc(args)
    if command == "simplex-simulate-voice-turn":
        return _handle_simplex_simulate_voice_turn(args)
    if command == "voice-health":
        return _handle_voice_health(args)
    if command == "simplex-health":
        return _handle_simplex_health(args)
    if command == "simplex-watch":
        return _handle_simplex_watch(args)
    if command == "simplex-call":
        return _handle_simplex_call(args)
    if command == "simplex-events":
        return _handle_simplex_events(args)
    if command == "simplex-live-debug":
        return _handle_simplex_live_debug(args)
    if command == "simplex-acceptance":
        return _handle_simplex_acceptance(args)
    if command == "simplex-observe":
        return _handle_simplex_observe(args)
    if command == "simplex-native-sidecar":
        return _handle_simplex_native_sidecar(args)
    if command == "simplex-simulate-stream":
        return _handle_simplex_simulate_stream(args)
    print(
        "Usage: hermes calls "
        "[trace|simulate-simplex-native|loopback-aiortc|simplex-simulate-voice-turn|"
        "voice-health|simplex-health|simplex-watch|simplex-call|simplex-events|"
        "simplex-live-debug|simplex-acceptance|simplex-observe|simplex-native-sidecar|"
        "simplex-simulate-stream]"
    )
    return 1
