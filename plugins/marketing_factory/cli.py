"""CLI for the Marketing Agent Factory plugin."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, Optional

from plugins.marketing_factory.pipeline import MarketingFactoryPipeline
from plugins.marketing_factory.store import MarketingFactoryStore


def register_cli(subparser: argparse.ArgumentParser) -> None:
    subparser.add_argument("--store-path", default=None, help="Override store path (defaults to $HERMES_HOME/marketing_factory)")
    subs = subparser.add_subparsers(dest="marketing_command")

    subs.add_parser("init", help="Initialize store and seed Pupular/SetVenue brand profiles")
    subs.add_parser("status", help="Show factory status")

    gen = subs.add_parser("generate", help="Generate a dry-run campaign and approval drafts for one app")
    gen.add_argument("--app", required=True, help="App slug, e.g. pupular or setvenue")
    gen.add_argument("--days", type=int, default=7)
    gen.add_argument("--auto-approve", action="store_true", help="Approve generated drafts for verification only")

    full = subs.add_parser("full-dry-run", help="Generate, approve, schedule, dry-run publish, and record analytics for one app")
    full.add_argument("--app", required=True)
    full.add_argument("--days", type=int, default=7)
    full.add_argument("--reviewer", default="human")

    apps = subs.add_parser("apps", help="List brand profiles")
    apps.add_argument("--json", action="store_true")

    campaigns = subs.add_parser("campaigns", help="List campaigns")
    campaigns.add_argument("--app", default=None)
    campaigns.add_argument("--json", action="store_true")

    drafts = subs.add_parser("drafts", help="List drafts")
    drafts.add_argument("--app", default=None)
    drafts.add_argument("--status", default=None)
    drafts.add_argument("--json", action="store_true")

    approvals = subs.add_parser("approvals", help="Show approval queue")
    approvals.add_argument("--app", default=None)
    approvals.add_argument("--json", action="store_true")

    approve = subs.add_parser("approve", help="Approve a draft for scheduling")
    approve.add_argument("draft_id")
    approve.add_argument("--reviewer", default="human")
    approve.add_argument("--reason", default="approved for dry-run")

    reject = subs.add_parser("reject", help="Reject a draft")
    reject.add_argument("draft_id")
    reject.add_argument("--reviewer", default="human")
    reject.add_argument("--reason", default="rejected by reviewer")

    schedule = subs.add_parser("schedule", help="Schedule approved drafts")
    schedule.add_argument("--app", default=None)
    schedule.add_argument("--draft-id", default=None)
    schedule.add_argument("--when", default=None, help="ISO timestamp when scheduling one draft")
    schedule.add_argument("--json", action="store_true")

    publish = subs.add_parser("publish-dry-run", help="Dry-run publish scheduled drafts only; never posts publicly")
    publish.add_argument("--app", default=None)
    publish.add_argument("--draft-id", default=None)
    publish.add_argument("--json", action="store_true")

    poll = subs.add_parser("poll", help="One scheduled-poller tick: fire publish on all due drafts across all apps")
    poll.add_argument("--json", action="store_true")

    audit = subs.add_parser("audit", help="Show audit trail")
    audit.add_argument("--app", default=None)
    audit.add_argument("--limit", type=int, default=20)
    audit.add_argument("--json", action="store_true")

    export = subs.add_parser("export", help="Export full state JSON")
    export.add_argument("--output", default=None)

    subparser.set_defaults(func=marketing_command)


def marketing_command(args: argparse.Namespace) -> int:
    sub = getattr(args, "marketing_command", None)
    if not sub:
        print("usage: hermes marketing-factory {init,status,apps,campaigns,drafts,approvals,approve,reject,schedule,publish-dry-run,poll,audit,export,generate,full-dry-run}")
        return 2
    store = MarketingFactoryStore(getattr(args, "store_path", None))
    pipe = MarketingFactoryPipeline(store)
    try:
        if sub == "init":
            result = pipe.initialize_samples()
            _print_json(result)
            return 0
        if sub == "status":
            store.initialize()
            _print_json(store.summary())
            return 0
        if sub == "apps":
            _print_records(store.list_apps(), as_json=args.json, title="Apps")
            return 0
        if sub == "campaigns":
            _print_records(store.list_campaigns(app_slug=args.app), as_json=args.json, title="Campaigns")
            return 0
        if sub == "drafts":
            _print_records(store.list_drafts(app_slug=args.app, status=args.status), as_json=args.json, title="Drafts")
            return 0
        if sub == "approvals":
            state = store.load()
            records = list(state["approvals"].values())
            if args.app:
                records = [r for r in records if r.get("app_slug") == args.app]
            _print_records(records, as_json=args.json, title="Approvals")
            return 0
        if sub == "approve":
            _print_json(store.set_approval(args.draft_id, "approved", reviewer=args.reviewer, reason=args.reason))
            return 0
        if sub == "reject":
            _print_json(store.set_approval(args.draft_id, "rejected", reviewer=args.reviewer, reason=args.reason))
            return 0
        if sub == "schedule":
            if args.draft_id:
                if not args.when:
                    raise ValueError("--when is required with --draft-id")
                result = [store.schedule_draft(args.draft_id, args.when)]
            else:
                result = pipe.scheduler.schedule_approved(store, app_slug=args.app)
            _print_records(result, as_json=args.json, title="Scheduled")
            return 0
        if sub == "publish-dry-run":
            if args.draft_id:
                result = [store.dry_run_publish(args.draft_id)]
            else:
                result = pipe.publisher.dry_run_publish_scheduled(store, app_slug=args.app)
            _print_records(result, as_json=args.json, title="Dry-run publish events")
            return 0
        if sub == "poll":
            result = pipe.poll()
            summary = {
                "polled_apps": result["polled_apps"],
                "due_count": result["due_count"],
                "fired_count": result["fired_count"],
                "last_poll_at": result["last_poll"].get("last_poll_at"),
            }
            if args.json:
                _print_json(result)
            else:
                _print_json(summary)
            return 0
        if sub == "audit":
            _print_records(store.list_audit(app_slug=args.app, limit=args.limit), as_json=args.json, title="Audit")
            return 0
        if sub == "export":
            state = store.load()
            if args.output:
                Path(args.output).write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
                print(args.output)
            else:
                _print_json(state)
            return 0
        if sub == "generate":
            result = pipe.generate_campaign(args.app, days=args.days, auto_approve=args.auto_approve)
            _print_json({"campaign": result["campaign"], "draft_count": len(result["drafts"]), "draft_ids": [d["id"] for d in result["drafts"]]})
            return 0
        if sub == "full-dry-run":
            result = pipe.run_full_dry_run(args.app, days=args.days, reviewer=args.reviewer)
            _print_json({
                "campaign_id": result["generated"]["campaign"]["id"],
                "draft_count": len(result["generated"]["drafts"]),
                "approvals": len(result["approvals"]),
                "scheduled": len(result["schedules"]),
                "dry_run_publish_events": len(result["publish_events"]),
                "analytics_id": result["analytics"]["id"],
            })
            return 0
    except Exception as exc:
        print(f"marketing-factory error: {exc}")
        return 1
    print(f"Unknown command: {sub}")
    return 2


def _print_json(payload: Any) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def _print_records(records: Any, *, as_json: bool, title: str) -> None:
    if as_json:
        _print_json(records)
        return
    records = list(records)
    print(f"{title}: {len(records)}")
    for record in records:
        bits = [record.get("id") or record.get("slug") or "<unknown>"]
        for key in ("app_slug", "name", "channel", "status", "scheduled_for"):
            if record.get(key):
                bits.append(f"{key}={record[key]}")
        print("- " + " | ".join(bits))
