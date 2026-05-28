"""
Discord reminder-button view + persistence + sentinel parsing.

When a cron reminder's outbound text contains a sentinel block::

    <<<REMINDER_BUTTONS reminder_id="abc123" text_b64="<b64 of reminder text>">>>
    ✅ Done | ⏰ +15min | ⏰ +1h | ⏰ Tomorrow 9am
    <<</REMINDER_BUTTONS>>>

the Discord adapter calls :func:`extract` to (a) strip the block from the
displayed message and (b) attach a :class:`ReminderButtonsView` carrying
four persistent buttons.  The base64-encoded reminder text is also written
to ``~/.hermes/reminders/{reminder_id}.json`` so button callbacks (including
those that fire after the bot restarts) can re-deliver the same reminder
text on snooze.

Discord caps button ``custom_id`` at 100 chars, so the reminder text cannot
ride on the custom_id itself — that's why we persist a per-reminder JSON
file keyed by ``reminder_id`` alongside the platform-agnostic Hermes home.

Buttons
-------
* **Done** — edits the message ("✓ done"), disables all buttons,
  removes the persisted JSON, and reacts ✅.
* **+15min** / **+1h** — schedules a new cron job firing after the chosen
  delay that re-delivers the same reminder text (with a fresh sentinel
  block).  Edits the message and disables the buttons.
* **Tomorrow 9am** — schedules a cron job to fire at the next 09:00 in
  ``Europe/Oslo`` (today's 9am if not yet past; otherwise tomorrow's).
"""

from __future__ import annotations

import base64
import json
import logging
import re
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from zoneinfo import ZoneInfo

from hermes_constants import get_hermes_home

try:
    import discord  # type: ignore
    DISCORD_AVAILABLE = True
except ImportError:  # pragma: no cover - lazy install path covered elsewhere
    DISCORD_AVAILABLE = False
    discord = None  # type: ignore

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Sentinel parsing
# ---------------------------------------------------------------------------

# Reminder ids are short hex/url-safe slugs.  Restrict to what we generate
# (and what cleanly fits inside the 100-char Discord custom_id cap with the
# `reminder:` prefix and `:tomorrow9` suffix).
_ID_PATTERN = r"[A-Za-z0-9_-]{1,40}"

_SENTINEL_RE = re.compile(
    r"<<<REMINDER_BUTTONS\s+"
    r'reminder_id="(?P<reminder_id>' + _ID_PATTERN + r')"\s+'
    r'text_b64="(?P<text_b64>[A-Za-z0-9+/=_-]+)"\s*>>>'
    r".*?<<</REMINDER_BUTTONS>>>",
    re.DOTALL,
)


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def _reminders_dir() -> Path:
    base = Path(get_hermes_home()) / "reminders"
    base.mkdir(parents=True, exist_ok=True)
    return base


def _sanitize_id(reminder_id: str) -> str:
    if not reminder_id or not re.fullmatch(_ID_PATTERN, reminder_id):
        raise ValueError(f"Invalid reminder id: {reminder_id!r}")
    return reminder_id


def _reminder_path(reminder_id: str) -> Path:
    return _reminders_dir() / f"{_sanitize_id(reminder_id)}.json"


def save_reminder(
    reminder_id: str,
    text: str,
    *,
    origin: Optional[Dict[str, Any]] = None,
    deliver: str = "origin",
) -> Path:
    """Persist a reminder's text + delivery target so buttons survive restart."""
    path = _reminder_path(reminder_id)
    payload = {
        "reminder_id": reminder_id,
        "text": text,
        "origin": origin,
        "deliver": deliver,
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def load_reminder(reminder_id: str) -> Optional[Dict[str, Any]]:
    """Return persisted reminder state, or None when the file is missing/corrupt."""
    try:
        path = _reminder_path(reminder_id)
    except ValueError:
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, ValueError):
        logger.warning("Failed to load reminder %s", reminder_id, exc_info=True)
        return None


def delete_reminder(reminder_id: str) -> bool:
    """Remove the persisted JSON for a reminder.  Returns True on delete."""
    try:
        path = _reminder_path(reminder_id)
    except ValueError:
        return False
    try:
        path.unlink()
        return True
    except FileNotFoundError:
        return False
    except OSError:
        logger.warning("Failed to delete reminder %s", reminder_id, exc_info=True)
        return False


def list_active_reminder_ids() -> list[str]:
    """Return ids of all reminders currently persisted on disk."""
    try:
        return sorted(p.stem for p in _reminders_dir().glob("*.json"))
    except OSError:
        return []


# ---------------------------------------------------------------------------
# Snooze scheduling
# ---------------------------------------------------------------------------

OSLO_TZ = ZoneInfo("Europe/Oslo")


def _new_reminder_id() -> str:
    return uuid.uuid4().hex[:12]


def _build_sentinel_block(reminder_id: str, text: str) -> str:
    text_b64 = base64.b64encode(text.encode("utf-8")).decode("ascii")
    return (
        f'<<<REMINDER_BUTTONS reminder_id="{reminder_id}" text_b64="{text_b64}">>>\n'
        "✅ Done | ⏰ +15min | ⏰ +1h | ⏰ Tomorrow 9am\n"
        "<<</REMINDER_BUTTONS>>>"
    )


_SNOOZE_PROMPT_TEMPLATE = (
    "This is an automatic re-fire of a snoozed reminder.\n\n"
    "Send the user this reminder verbatim:\n\n"
    "{text}\n\n"
    "End your reply with EXACTLY the following block, on its own lines, with\n"
    "no modifications:\n\n"
    "{sentinel}\n"
)


def _next_tomorrow_9am(now: Optional[datetime] = None) -> datetime:
    """Return the next 09:00 Europe/Oslo.

    Today's 9am when it hasn't passed yet; otherwise tomorrow's 9am.
    """
    current = now.astimezone(OSLO_TZ) if now else datetime.now(OSLO_TZ)
    target = current.replace(hour=9, minute=0, second=0, microsecond=0)
    if target <= current:
        target = target + timedelta(days=1)
    return target


def schedule_snooze(
    reminder_id: str,
    *,
    delay_minutes: Optional[int] = None,
    run_at: Optional[datetime] = None,
) -> Optional[Dict[str, Any]]:
    """Create a fresh cron job that re-delivers the reminder later.

    Returns the new cron job dict, or None when the persisted reminder is
    missing.  Exactly one of ``delay_minutes`` / ``run_at`` must be set.
    """
    record = load_reminder(reminder_id)
    if not record or not record.get("text"):
        logger.warning(
            "schedule_snooze: no persisted state for reminder %s", reminder_id,
        )
        return None

    new_id = _new_reminder_id()
    text = record["text"]
    sentinel = _build_sentinel_block(new_id, text)
    prompt = _SNOOZE_PROMPT_TEMPLATE.format(text=text, sentinel=sentinel)

    if run_at is not None:
        schedule = run_at.isoformat()
    elif delay_minutes is not None:
        schedule = f"{int(delay_minutes)}m"
    else:
        raise ValueError("schedule_snooze requires delay_minutes or run_at")

    # Persist the new reminder state up-front so the snooze chain works even
    # if the cron run starts before extract() re-saves it from its own
    # outbound text.
    save_reminder(
        new_id,
        text,
        origin=record.get("origin"),
        deliver=record.get("deliver") or "origin",
    )

    # Imported lazily — cron has its own heavy imports we don't want at
    # adapter-load time.
    from cron.jobs import create_job

    job = create_job(
        prompt=prompt,
        schedule=schedule,
        name=f"reminder snooze {new_id}",
        repeat=1,
        deliver=record.get("deliver") or "origin",
        origin=record.get("origin"),
    )
    return job


# ---------------------------------------------------------------------------
# Sentinel extraction + view construction
# ---------------------------------------------------------------------------

def extract(
    text: str,
    *,
    origin: Optional[Dict[str, Any]] = None,
    deliver: str = "origin",
) -> Tuple[str, Optional[Any]]:
    """Strip the sentinel block from ``text`` and return a button view.

    Returns ``(cleaned_text, view_or_None)``.  When a sentinel is found:
      · the block is removed from the displayed text,
      · the (base64-decoded) reminder text + origin is persisted to
        ``~/.hermes/reminders/{id}.json`` so buttons survive bot restart,
      · a :class:`ReminderButtonsView` is returned, ready to be passed as
        ``view=`` to ``channel.send``.

    When ``discord`` is not installed (or no sentinel is present), returns
    the original text and ``None``.
    """
    if not text:
        return text, None
    match = _SENTINEL_RE.search(text)
    if not match:
        return text, None
    if not DISCORD_AVAILABLE:
        # Strip the sentinel even when we can't attach buttons — the
        # raw block would otherwise leak into the user's display.
        cleaned = (text[: match.start()] + text[match.end():]).strip()
        return cleaned, None

    reminder_id = match.group("reminder_id")
    text_b64 = match.group("text_b64")
    try:
        reminder_text = base64.b64decode(text_b64).decode("utf-8")
    except (ValueError, UnicodeDecodeError):
        logger.warning(
            "extract: bad text_b64 for reminder %s — leaving sentinel in place",
            reminder_id,
            exc_info=True,
        )
        return text, None

    try:
        save_reminder(
            reminder_id, reminder_text, origin=origin, deliver=deliver,
        )
    except Exception:  # pragma: no cover - defensive
        logger.warning(
            "extract: failed to persist reminder %s",
            reminder_id,
            exc_info=True,
        )

    cleaned = (text[: match.start()] + text[match.end():]).strip()
    return cleaned, ReminderButtonsView(reminder_id)


# ---------------------------------------------------------------------------
# View class
# ---------------------------------------------------------------------------

if DISCORD_AVAILABLE:
    _ACTION_LABELS = {
        "done": "✅ Done",
        "snooze15": "⏰ +15min",
        "snooze60": "⏰ +1h",
        "tomorrow9": "⏰ Tomorrow 9am",
    }
    _ACTIONS = ("done", "snooze15", "snooze60", "tomorrow9")

    class ReminderButtonsView(discord.ui.View):
        """Four-button view attached to cron reminder messages.

        Persistence: ``timeout=None`` plus stable ``custom_id``s on every
        child make this a persistent view in discord.py terms.  The adapter
        re-registers one view per active ``~/.hermes/reminders/*.json`` on
        bot startup via :func:`register_persistent_views`, so button
        callbacks fire correctly after the bot has restarted.
        """

        def __init__(self, reminder_id: str):
            super().__init__(timeout=None)
            self.reminder_id = _sanitize_id(reminder_id)
            for action in _ACTIONS:
                self._add_button(action)

        def _add_button(self, action: str) -> None:
            label = _ACTION_LABELS[action]
            style = (
                discord.ButtonStyle.success if action == "done"
                else discord.ButtonStyle.secondary
            )
            btn = discord.ui.Button(
                label=label,
                style=style,
                custom_id=f"reminder:{self.reminder_id}:{action}",
            )
            btn.callback = self._make_callback(action)
            self.add_item(btn)

        def _make_callback(self, action: str):
            async def _callback(interaction: "discord.Interaction") -> None:
                await self._dispatch(interaction, action)
            return _callback

        def _disable_buttons(self) -> None:
            for child in self.children:
                child.disabled = True

        async def _dispatch(
            self, interaction: "discord.Interaction", action: str,
        ) -> None:
            if action == "done":
                await self._on_done(interaction)
            elif action == "snooze15":
                await self._on_snooze(interaction, delay_minutes=15, label="+15min")
            elif action == "snooze60":
                await self._on_snooze(interaction, delay_minutes=60, label="+1h")
            elif action == "tomorrow9":
                await self._on_tomorrow9(interaction)
            else:  # pragma: no cover - defensive
                logger.warning("Unknown reminder action: %s", action)

        async def _edit_with_suffix(
            self,
            interaction: "discord.Interaction",
            suffix: str,
        ) -> None:
            self._disable_buttons()
            message = getattr(interaction, "message", None)
            new_content: Optional[str] = None
            if message is not None:
                existing = getattr(message, "content", "") or ""
                new_content = f"{existing}\n\n{suffix}" if existing else suffix
            try:
                if new_content is None:
                    await interaction.response.edit_message(view=self)
                else:
                    await interaction.response.edit_message(
                        content=new_content, view=self,
                    )
            except Exception:
                logger.debug(
                    "Reminder edit_message failed (rid=%s)",
                    self.reminder_id,
                    exc_info=True,
                )
                try:
                    await interaction.response.defer()
                except Exception:
                    pass

        async def _on_done(self, interaction: "discord.Interaction") -> None:
            await self._edit_with_suffix(interaction, "✓ done")
            delete_reminder(self.reminder_id)
            message = getattr(interaction, "message", None)
            if message is not None and hasattr(message, "add_reaction"):
                try:
                    await message.add_reaction("✅")
                except Exception:
                    logger.debug(
                        "Reminder add_reaction failed (rid=%s)",
                        self.reminder_id,
                        exc_info=True,
                    )

        async def _on_snooze(
            self,
            interaction: "discord.Interaction",
            *,
            delay_minutes: int,
            label: str,
        ) -> None:
            job = None
            try:
                job = schedule_snooze(
                    self.reminder_id, delay_minutes=delay_minutes,
                )
            except Exception as exc:
                logger.error(
                    "Reminder snooze failed (rid=%s, +%dm): %s",
                    self.reminder_id, delay_minutes, exc, exc_info=True,
                )
            if job is None:
                await self._edit_with_suffix(
                    interaction,
                    f"⚠ couldn't snooze ({label}) — reminder state not found",
                )
                return
            await self._edit_with_suffix(interaction, f"⏰ snoozed {label}")

        async def _on_tomorrow9(
            self, interaction: "discord.Interaction",
        ) -> None:
            target = _next_tomorrow_9am()
            job = None
            try:
                job = schedule_snooze(self.reminder_id, run_at=target)
            except Exception as exc:
                logger.error(
                    "Reminder tomorrow-9 snooze failed (rid=%s): %s",
                    self.reminder_id, exc, exc_info=True,
                )
            if job is None:
                await self._edit_with_suffix(
                    interaction,
                    "⚠ couldn't snooze (Tomorrow 9am) — reminder state not found",
                )
                return
            stamp = target.strftime("%Y-%m-%d %H:%M %Z")
            await self._edit_with_suffix(
                interaction, f"⏰ snoozed → {stamp}",
            )

else:  # pragma: no cover - shim when discord isn't installed
    class ReminderButtonsView:  # type: ignore[no-redef]
        def __init__(self, reminder_id: str):
            self.reminder_id = reminder_id


def register_persistent_views(bot: Any) -> int:
    """Re-register one persistent view per active reminder on bot startup.

    Returns the number of views registered.  Safe to call multiple times —
    discord.py de-duplicates by custom_id.
    """
    if not DISCORD_AVAILABLE or bot is None or not hasattr(bot, "add_view"):
        return 0
    count = 0
    for reminder_id in list_active_reminder_ids():
        try:
            bot.add_view(ReminderButtonsView(reminder_id))
            count += 1
        except Exception:
            logger.debug(
                "register_persistent_views: failed for %s",
                reminder_id,
                exc_info=True,
            )
    return count
