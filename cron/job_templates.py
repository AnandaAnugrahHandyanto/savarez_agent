"""Sync cron job templates from the active Hermes profile."""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from hermes_constants import get_hermes_home

from cron.jobs import create_job, list_jobs, parse_schedule, update_job


TEMPLATES_DIR = "cron/templates"

def _templates_path() -> Path:
    return get_hermes_home() / TEMPLATES_DIR


def _template_version(template: Dict[str, Any]) -> Optional[str]:
    version = template.get("template_version", template.get("version"))
    if version is None:
        return None
    text = str(version).strip()
    return text or None


def _template_key(template: Dict[str, Any], path: Path) -> str:
    key = str(template.get("template_key") or path.stem).strip()
    if not key:
        raise ValueError(f"Cron template has no template_key: {path}")
    return key


def _read_template(path: Path) -> Optional[Dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        template = json.load(f)
    if not isinstance(template, dict):
        raise ValueError(f"Cron template must be a JSON object: {path}")
    if template.get("active", True) is False:
        return None
    return template


def _load_templates() -> List[Dict[str, Any]]:
    templates_dir = _templates_path()
    if not templates_dir.exists():
        return []

    templates: List[Dict[str, Any]] = []
    for path in sorted(templates_dir.glob("*.json")):
        template = _read_template(path)
        if template is None:
            continue
        template = dict(template)
        template["template_key"] = _template_key(template, path)
        template["template_version"] = _template_version(template)
        templates.append(template)
    return templates


def _create_kwargs(template: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "prompt": template.get("prompt", ""),
        "schedule": template["schedule"],
        "name": template.get("name"),
        "deliver": template.get("deliver"),
        "skill": template.get("skill"),
        "skills": template.get("skills"),
        "model": template.get("model"),
        "provider": template.get("provider"),
        "base_url": template.get("base_url"),
        "script": template.get("script"),
        "context_from": template.get("context_from"),
        "enabled_toolsets": template.get("enabled_toolsets"),
        "workdir": template.get("workdir"),
        "no_agent": bool(template.get("no_agent", False)),
        "delivery_mode": template.get("delivery_mode"),
        "thread_title_template": template.get("thread_title_template"),
        "template_key": template["template_key"],
        "template_version": template.get("template_version"),
    }


def _update_fields(template: Dict[str, Any], existing: Dict[str, Any]) -> Dict[str, Any]:
    updates = {
        "prompt": template.get("prompt", ""),
        "name": template.get("name"),
        "deliver": template.get("deliver", "local"),
        "skill": template.get("skill"),
        "skills": template.get("skills"),
        "model": template.get("model"),
        "provider": template.get("provider"),
        "base_url": template.get("base_url"),
        "script": template.get("script"),
        "context_from": template.get("context_from"),
        "enabled_toolsets": template.get("enabled_toolsets"),
        "workdir": template.get("workdir"),
        "no_agent": bool(template.get("no_agent", False)),
        "delivery_mode": template.get("delivery_mode"),
        "thread_title_template": template.get("thread_title_template"),
        "template_key": template["template_key"],
        "template_version": template.get("template_version"),
    }
    if "schedule" in template:
        parsed_schedule = parse_schedule(template["schedule"])
        if parsed_schedule != existing.get("schedule"):
            updates["schedule"] = parsed_schedule
            updates["schedule_display"] = parsed_schedule.get("display", template["schedule"])
    return updates


def sync_cron_templates() -> Dict[str, Any]:
    """Upsert active cron templates into cron/jobs.json."""
    created: List[str] = []
    updated: List[str] = []

    jobs_by_template_key = {
        job.get("template_key"): job
        for job in list_jobs(include_disabled=True)
        if job.get("template_key")
    }

    for template in _load_templates():
        key = template["template_key"]
        existing = jobs_by_template_key.get(key)
        if existing is None:
            create_job(**_create_kwargs(template))
            created.append(key)
            continue

        update_job(existing["id"], _update_fields(template, existing))
        updated.append(key)

    return {"created": created, "updated": updated}
