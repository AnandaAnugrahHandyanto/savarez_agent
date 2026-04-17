"""Resolve cron-job context for replies to cron deliveries.

When a user replies to a message that originated from a cron delivery,
the gateway needs to know:

1. Which cron job produced the message (so we can find its bound skills).
2. What instructions to inject so the agent can act on the follow-up
   (e.g. delete an email after a mail-triage delivery), not just see the
   quoted text.

This module is the single entry point gateway code uses for that
resolution. It encapsulates all knowledge of cron internals (the delivery
registry, the job store, skill loading) so callers stay platform-agnostic.

Resolution order:

1. **Delivery registry** by message_id. Required for multi-chunk
   deliveries (e.g. Discord splits long output into 2000-char messages
   and only chunk 0 carries the ``Cronjob Response: <name>`` header).
2. **"Cronjob Response: <name>" prefix** in the reply text. Fallback for
   single-chunk deliveries when the registry has no record (e.g. after
   a gateway restart that truncated old entries).
"""

import json
import logging
from typing import List, Optional

logger = logging.getLogger(__name__)

_CRON_DELIVERY_PREFIX = "Cronjob Response: "


def resolve_skill_for_reply(
    platform: str,
    chat_id: str,
    message_id: Optional[str],
    reply_text: Optional[str],
) -> Optional[str]:
    """Return a system-prompt fragment to inject for a cron-reply, or None.

    The returned string (when non-None) ends with ``\\n\\n`` so callers can
    concatenate it directly in front of their own message text.
    """
    job_name = _resolve_job_name(platform, chat_id, message_id, reply_text)
    if not job_name:
        return None

    skills = _load_job_skills(job_name)
    if not skills:
        return None

    parts: List[str] = []
    for sname in skills:
        content = _load_skill_content(sname)
        if content:
            parts.append(
                f'[SYSTEM: The original cron job used the "{sname}" skill. '
                f"Follow its instructions to handle the user's request.]\n\n"
                f"{content}"
            )

    if not parts:
        return None
    return "\n\n".join(parts) + "\n\n"


def _resolve_job_name(
    platform: str,
    chat_id: str,
    message_id: Optional[str],
    reply_text: Optional[str],
) -> Optional[str]:
    if message_id:
        try:
            from cron.delivery_registry import lookup as _lookup_delivery

            name = _lookup_delivery(platform, chat_id, message_id)
            if name:
                return name
        except Exception:
            logger.debug("delivery_registry lookup failed", exc_info=True)

    if reply_text and reply_text.startswith(_CRON_DELIVERY_PREFIX):
        first_line = reply_text.split("\n", 1)[0]
        candidate = first_line[len(_CRON_DELIVERY_PREFIX):].strip()
        return candidate or None

    return None


def _load_job_skills(job_name: str) -> List[str]:
    try:
        from cron.jobs import list_jobs

        for job in list_jobs(include_disabled=True):
            if job.get("name") == job_name or job.get("id") == job_name:
                skills = job.get("skills") or []
                if not skills:
                    legacy = job.get("skill")
                    if legacy:
                        skills = [legacy]
                return [str(s).strip() for s in skills if str(s).strip()]
    except Exception:
        logger.debug("Failed to load cron job skills for %s", job_name, exc_info=True)
    return []


def _load_skill_content(skill_name: str) -> Optional[str]:
    try:
        from tools.skills_tool import skill_view

        loaded = json.loads(skill_view(skill_name))
        if loaded.get("success") and loaded.get("content"):
            return loaded["content"]
    except Exception:
        logger.debug("Failed to load skill '%s'", skill_name, exc_info=True)
    return None
