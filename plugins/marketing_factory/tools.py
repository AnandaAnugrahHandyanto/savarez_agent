"""Agent-callable tools for Marketing Agent Factory."""

from __future__ import annotations

import json
from typing import Any, Dict

from plugins.marketing_factory.pipeline import MarketingFactoryPipeline
from plugins.marketing_factory.store import MarketingFactoryStore


MARKETING_FACTORY_SCHEMA: Dict[str, Any] = {
    "name": "marketing_factory",
    "description": "Operate the dry-run-first Marketing Agent Factory: initialize brand profiles, generate campaigns, approve/schedule drafts, dry-run publish, inspect state and audit logs. Never performs real public posting.",
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["init", "status", "generate", "full_dry_run", "list_apps", "list_drafts", "approve", "reject", "schedule", "publish_dry_run", "audit"],
            },
            "app_slug": {"type": "string", "description": "Brand/app slug such as pupular or setvenue"},
            "draft_id": {"type": "string"},
            "days": {"type": "integer", "default": 7},
            "reviewer": {"type": "string", "default": "human"},
            "reason": {"type": "string"},
            "scheduled_for": {"type": "string", "description": "ISO timestamp for scheduling one draft"},
            "store_path": {"type": "string", "description": "Optional test/store override path"},
        },
        "required": ["action"],
    },
}


def handle_marketing_factory(args: Dict[str, Any], **_: Any) -> str:
    store = MarketingFactoryStore(args.get("store_path"))
    pipe = MarketingFactoryPipeline(store)
    action = args.get("action")
    try:
        if action == "init":
            result = pipe.initialize_samples()
        elif action == "status":
            store.initialize()
            result = store.summary()
        elif action == "generate":
            result = pipe.generate_campaign(_require_arg(args, "app_slug"), days=int(args.get("days") or 7))
            result = {"campaign": result["campaign"], "drafts": result["drafts"]}
        elif action == "full_dry_run":
            result = pipe.run_full_dry_run(_require_arg(args, "app_slug"), days=int(args.get("days") or 7), reviewer=args.get("reviewer") or "human")
        elif action == "list_apps":
            result = store.list_apps()
        elif action == "list_drafts":
            result = store.list_drafts(app_slug=args.get("app_slug"))
        elif action == "approve":
            result = store.set_approval(_require_arg(args, "draft_id"), "approved", reviewer=args.get("reviewer") or "human", reason=args.get("reason"))
        elif action == "reject":
            result = store.set_approval(_require_arg(args, "draft_id"), "rejected", reviewer=args.get("reviewer") or "human", reason=args.get("reason"))
        elif action == "schedule":
            draft_id = args.get("draft_id")
            if draft_id:
                result = store.schedule_draft(draft_id, _require_arg(args, "scheduled_for"))
            else:
                result = pipe.scheduler.schedule_approved(store, app_slug=args.get("app_slug"))
        elif action == "publish_dry_run":
            draft_id = args.get("draft_id")
            if draft_id:
                result = store.dry_run_publish(draft_id)
            else:
                result = pipe.publisher.dry_run_publish_scheduled(store, app_slug=args.get("app_slug"))
        elif action == "audit":
            result = store.list_audit(app_slug=args.get("app_slug"))
        else:
            raise ValueError(f"Unknown action: {action}")
        return json.dumps({"success": True, "result": result}, sort_keys=True)
    except Exception as exc:
        return json.dumps({"success": False, "error": str(exc)}, sort_keys=True)


def _require_arg(args: Dict[str, Any], name: str) -> str:
    value = args.get(name)
    if not value:
        raise ValueError(f"{name} is required")
    return str(value)
