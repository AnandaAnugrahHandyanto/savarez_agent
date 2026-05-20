#!/usr/bin/env python3
"""Prepare and inspect sanitized Telegram Business payload probes.

This script is intentionally shape/metadata oriented: it prints the temporary
probe codes that humans should send, but it stores only SHA-256 + length in the
account-scoped life inbox DB. Status output hides raw chat/sender/message ids by
default so it can be pasted into checkpoints without leaking private dialogs.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from collections.abc import Iterable, Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from gateway.life_inbox_store import (
    BUSINESS_PAYLOAD_PROBE_LANE,
    BUSINESS_PAYLOAD_PROBE_SCENARIOS,
    LifeInboxStore,
    resolve_life_inbox_db_path,
)

DEFAULT_OWNER_TELEGRAM_ID = "602562"

_INSTRUCTIONS = {
    "S1_contact_inbound": "CONTACT_1 sends this exact code to Alen in Telegram.",
    "S2_contact_alen_manual_outbound": "Alen manually sends this exact code to CONTACT_1 in Telegram.",
    "S3_known_noncontact_inbound": "KNOWN_NONCONTACT_1 sends this exact code to Alen in Telegram.",
    "S4_known_noncontact_alen_manual_outbound": "Alen manually sends this exact code to KNOWN_NONCONTACT_1 in Telegram.",
    "S5_new_chat_inbound": "NEW_CHAT_1 sends this exact code to Alen in Telegram for the first observed chat.",
    "S6_new_chat_alen_manual_outbound": "Alen manually sends this exact code to NEW_CHAT_1 in Telegram.",
}


def _utc_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _resolve_db_path(args: argparse.Namespace) -> Path:
    if args.db:
        return Path(args.db).expanduser()
    return resolve_life_inbox_db_path(args.owner_telegram_id)


def _json_loads(value: str | None, default: Any) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return default


def _merge_availability(base: Any, incoming: Any) -> Any:
    """Merge field-availability JSON by OR-ing booleans and recursing maps."""

    if isinstance(base, Mapping) and isinstance(incoming, Mapping):
        merged: dict[str, Any] = dict(base)
        for key, value in incoming.items():
            if key in merged:
                merged[key] = _merge_availability(merged[key], value)
            else:
                merged[key] = value
        return merged
    if isinstance(base, bool) or isinstance(incoming, bool):
        return bool(base) or bool(incoming)
    return incoming if incoming not in (None, "", [], {}) else base


def _unique_preserving_order(values: Iterable[Any]) -> list[Any]:
    seen: set[str] = set()
    result: list[Any] = []
    for value in values:
        key = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
        if key in seen:
            continue
        seen.add(key)
        result.append(value)
    return result


def _scenario_payload(run_id: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for scenario in BUSINESS_PAYLOAD_PROBE_SCENARIOS:
        scenario_id = scenario["scenario_id"]
        rows.append(
            {
                "scenario_id": scenario_id,
                "alias": scenario.get("alias"),
                "expected_direction": scenario.get("expected_direction"),
                "instruction": _INSTRUCTIONS.get(scenario_id, "Send this exact code in Telegram."),
                "probe_text": f"TBP-{run_id}-{scenario_id}",
            }
        )
    return rows


def _cmd_prepare(args: argparse.Namespace) -> int:
    db_path = _resolve_db_path(args)
    run_id = args.run_id or _utc_run_id()
    scenarios = _scenario_payload(run_id)
    notes = "Strict Telegram Business Bot API live payload probe; plaintext code not stored in DB."

    store = LifeInboxStore(db_path)
    store.prepare_business_payload_probe_scenarios(
        [
            {
                "scenario_id": row["scenario_id"],
                "alias": row["alias"],
                "expected_direction": row["expected_direction"],
                "probe_text": row["probe_text"],
                "notes": notes,
            }
            for row in scenarios
        ],
        source_lane=args.source_lane,
    )

    payload = {
        "db_path": str(db_path),
        "source_lane": args.source_lane,
        "run_id": run_id,
        "scenarios": scenarios,
        "safety": {
            "stored_in_db": "sha256+length only; plaintext probe codes are not persisted",
            "source_chat_replies": "disabled/proposal-only",
            "raw_text_in_logs": "do not log raw private text",
        },
    }
    _print_payload(payload, args.format)
    return 0


def _load_status_rows(db_path: Path, source_lane: str, include_identifiers: bool) -> dict[str, Any]:
    if not db_path.exists():
        return {"db_path": str(db_path), "source_lane": source_lane, "exists": False, "scenarios": []}

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        scenario_rows = conn.execute(
            """
            SELECT id, scenario_id, alias, expected_direction, probe_text_len,
                   probe_text_sha256, status, matched_event_id, created_at,
                   matched_at, notes
            FROM business_payload_probe_scenarios
            WHERE source_lane = ?
            ORDER BY id
            """,
            (source_lane,),
        ).fetchall()
        event_rows = conn.execute(
            """
            SELECT id, scenario_id, update_type, direction, message_date,
                   text_len, raw_text_stored, field_availability_json,
                   payload_shape_json, media_json, reply_context_json,
                   deleted_message_ids_json, created_at,
                   connection_id, chat_id, message_id, sender_id
            FROM business_payload_probe_events
            WHERE source_lane = ?
            ORDER BY id
            """,
            (source_lane,),
        ).fetchall()

    events_by_scenario: dict[str | None, list[sqlite3.Row]] = {}
    for event in event_rows:
        events_by_scenario.setdefault(event["scenario_id"], []).append(event)

    scenarios: list[dict[str, Any]] = []
    for scenario in scenario_rows:
        scenario_events = events_by_scenario.get(scenario["scenario_id"], [])
        availability: dict[str, Any] = {}
        media_keys: list[str] = []
        reply_present = False
        deleted_message_ids_count = 0
        for event in scenario_events:
            availability = _merge_availability(
                availability,
                _json_loads(event["field_availability_json"], {}),
            )
            media = _json_loads(event["media_json"], {})
            if isinstance(media, Mapping):
                media_keys.extend(str(key) for key in media.keys())
            reply_context = _json_loads(event["reply_context_json"], {})
            if isinstance(reply_context, Mapping) and reply_context.get("present"):
                reply_present = True
            deleted_ids = _json_loads(event["deleted_message_ids_json"], [])
            if isinstance(deleted_ids, list):
                deleted_message_ids_count += len(deleted_ids)

        row = {
            "scenario_id": scenario["scenario_id"],
            "alias": scenario["alias"],
            "expected_direction": scenario["expected_direction"],
            "status": scenario["status"],
            "probe_text_len": scenario["probe_text_len"],
            "probe_text_sha256_prefix": str(scenario["probe_text_sha256"] or "")[:16],
            "matched": bool(scenario["matched_event_id"]),
            "matched_at": scenario["matched_at"],
            "event_count": len(scenario_events),
            "event_update_types": _unique_preserving_order(event["update_type"] for event in scenario_events),
            "event_directions": _unique_preserving_order(event["direction"] for event in scenario_events),
            "first_event_at": scenario_events[0]["created_at"] if scenario_events else None,
            "last_event_at": scenario_events[-1]["created_at"] if scenario_events else None,
            "field_availability": availability,
            "media_keys": sorted(set(media_keys)),
            "reply_present": reply_present,
            "deleted_message_ids_count": deleted_message_ids_count,
            "raw_text_stored_count": sum(int(event["raw_text_stored"] or 0) for event in scenario_events),
        }
        if include_identifiers:
            row["event_identifiers"] = [
                {
                    "id": event["id"],
                    "connection_id": event["connection_id"],
                    "chat_id": event["chat_id"],
                    "message_id": event["message_id"],
                    "sender_id": event["sender_id"],
                    "message_date": event["message_date"],
                }
                for event in scenario_events
            ]
        scenarios.append(row)

    unmatched_events = events_by_scenario.get(None, [])
    payload: dict[str, Any] = {
        "db_path": str(db_path),
        "source_lane": source_lane,
        "exists": True,
        "scenario_count": len(scenarios),
        "matched_count": sum(1 for row in scenarios if row["matched"]),
        "pending_count": sum(1 for row in scenarios if row["status"] == "pending"),
        "unmatched_capture_all_event_count": len(unmatched_events),
        "scenarios": scenarios,
    }
    if include_identifiers and unmatched_events:
        payload["unmatched_capture_all_events"] = [
            {
                "id": event["id"],
                "update_type": event["update_type"],
                "direction": event["direction"],
                "chat_id": event["chat_id"],
                "message_id": event["message_id"],
                "sender_id": event["sender_id"],
                "created_at": event["created_at"],
            }
            for event in unmatched_events
        ]
    return payload


def _cmd_status(args: argparse.Namespace) -> int:
    db_path = _resolve_db_path(args)
    payload = _load_status_rows(db_path, args.source_lane, args.include_identifiers)
    _print_payload(payload, args.format)
    return 0


def _print_payload(payload: dict[str, Any], output_format: str) -> None:
    if output_format == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        return

    if "run_id" in payload:
        print(f"Telegram Business payload probe run: {payload['run_id']}")
        print(f"DB: {payload['db_path']}")
        for row in payload["scenarios"]:
            print(f"- {row['scenario_id']} ({row['alias']}): {row['instruction']}")
            print(f"  code: {row['probe_text']}")
        print("Safety: DB stores hash+length only; no source-chat auto-replies.")
        return

    print(f"Telegram Business payload probe status: {payload['source_lane']}")
    print(f"DB: {payload['db_path']} exists={payload.get('exists')}")
    print(f"matched={payload.get('matched_count', 0)} pending={payload.get('pending_count', 0)}")
    for row in payload.get("scenarios", []):
        updates = ",".join(row["event_update_types"]) or "-"
        directions = ",".join(row["event_directions"]) or "-"
        print(
            f"- {row['scenario_id']}: {row['status']} "
            f"events={row['event_count']} updates={updates} directions={directions}"
        )


def _add_common_args(parser: argparse.ArgumentParser, *, suppress_defaults: bool = False) -> None:
    default: Any = argparse.SUPPRESS if suppress_defaults else None
    parser.add_argument(
        "--db",
        default=default,
        help="Path to account-scoped life_inbox.sqlite",
    )
    parser.add_argument(
        "--owner-telegram-id",
        default=argparse.SUPPRESS if suppress_defaults else DEFAULT_OWNER_TELEGRAM_ID,
        help="Owner numeric Telegram ID used when --db is omitted (default: 602562)",
    )
    parser.add_argument(
        "--source-lane",
        default=argparse.SUPPRESS if suppress_defaults else BUSINESS_PAYLOAD_PROBE_LANE,
    )
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default=argparse.SUPPRESS if suppress_defaults else "text",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    _add_common_args(parser)

    sub = parser.add_subparsers(dest="command", required=True)
    prepare = sub.add_parser("prepare", help="Create a six-scenario run sheet and register hashes")
    _add_common_args(prepare, suppress_defaults=True)
    prepare.add_argument("--run-id", help="Stable run id for code generation, e.g. 20260520T090000Z")
    prepare.set_defaults(func=_cmd_prepare)

    status = sub.add_parser("status", help="Summarize matched payload-probe events")
    _add_common_args(status, suppress_defaults=True)
    status.add_argument(
        "--include-identifiers",
        action="store_true",
        help="Include private chat/sender/message ids in status output (off by default)",
    )
    status.set_defaults(func=_cmd_status)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
