# Cron Delivery Context Handoff

**Created:** 2026-05-29  
**Status:** Draft Design  
**Priority:** Medium

## Problem

When a cron job delivers output to a channel/thread, the next interactive session in that same channel starts cold with no access to what the cron said. This forces the user to:

- Use `session_search` to hunt for the cron output
- Re-explain or quote what was just delivered
- Lose context about what triggered their reply

The cron runs in an isolated session, and when the user replies moments later, the gateway spawns a new interactive session that has no knowledge of the cron's output.

## User Impact

**Current Workflow:**
1. Daily briefing cron fires at 8am, delivers to Telegram
2. User reads it, replies "Tell me more about X"
3. New interactive session starts, has no idea what "X" refers to
4. User has to quote the briefing or re-explain

**Desired Workflow:**
1. Daily briefing cron fires at 8am, delivers to Telegram
2. User reads it, replies "Tell me more about X"
3. New interactive session automatically sees the last cron output
4. Agent understands context immediately

## Proposed Solution

### Architecture

Add a **lightweight delivery metadata store** that:
- Tracks the last 1-2 cron outputs delivered to each channel
- Auto-injects that context when a new interactive session starts in that channel
- Lives at `~/.hermes/cron/delivery_metadata.json`

### Schema

```json
{
  "channels": {
    "telegram:12345": {
      "last_delivery": {
        "job_id": "abc123def456",
        "job_name": "Daily Briefing",
        "session_id": "cron_abc123def456_20260529_080000",
        "delivered_at": "2026-05-29T08:00:15+00:00",
        "output_path": "~/.hermes/cron/output/abc123def456/20260529_080000.md",
        "preview": "# Daily Briefing\\n\\nCapacity alert: 3 concurrent projects..."
      },
      "previous_delivery": {
        // Same structure, optional
      }
    }
  }
}
```

### Implementation Points

#### 1. Capture delivery metadata (cron/scheduler.py)

In the `_deliver_to_targets()` function, after successful delivery:

```python
def _save_delivery_metadata(
    job: dict,
    target: dict,  # {platform, chat_id, thread_id}
    session_id: str,
    output_path: Path,
    preview: str,  # First ~500 chars of output
):
    """Save delivery metadata for later context injection."""
    channel_key = f"{target['platform']}:{target['chat_id']}"
    if target.get('thread_id'):
        channel_key += f":{target['thread_id']}"
    
    metadata_file = CRON_DIR / "delivery_metadata.json"
    
    # Load existing
    data = {"channels": {}}
    if metadata_file.exists():
        with open(metadata_file) as f:
            data = json.load(f)
    
    # Rotate: last → previous, new → last
    channel_data = data["channels"].get(channel_key, {})
    new_metadata = {
        "job_id": job["id"],
        "job_name": job.get("name", ""),
        "session_id": session_id,
        "delivered_at": _hermes_now().isoformat(),
        "output_path": str(output_path),
        "preview": preview[:500],
    }
    
    channel_data["previous_delivery"] = channel_data.get("last_delivery")
    channel_data["last_delivery"] = new_metadata
    data["channels"][channel_key] = channel_data
    
    # Atomic write
    atomic_replace(temp_write(data), metadata_file)
```

#### 2. Inject context on session start (gateway/session.py)

In `build_session_context_prompt()`:

```python
def build_session_context_prompt(context: SessionContext, ...) -> str:
    lines = [...]  # existing prompt building
    
    # Inject last cron delivery if available
    cron_context = _get_last_cron_delivery(context.source)
    if cron_context:
        lines.append("\n## Recent Scheduled Task Output\n")
        lines.append(f"**Job:** {cron_context['job_name']}")
        lines.append(f"**Delivered:** {cron_context['delivered_at']}")
        lines.append(f"\n{cron_context['preview']}\n")
        lines.append("(This was just delivered by a scheduled task. "
                    "The user may be replying to it.)\n")
    
    return "\n".join(lines)

def _get_last_cron_delivery(source: SessionSource) -> Optional[dict]:
    """Load the last cron delivery to this channel, if any."""
    channel_key = f"{source.platform.value}:{source.chat_id}"
    if source.thread_id:
        channel_key += f":{source.thread_id}"
    
    metadata_file = Path("~/.hermes/cron/delivery_metadata.json").expanduser()
    if not metadata_file.exists():
        return None
    
    try:
        with open(metadata_file) as f:
            data = json.load(f)
        channel_data = data.get("channels", {}).get(channel_key)
        if not channel_data:
            return None
        
        last = channel_data.get("last_delivery")
        if not last:
            return None
        
        # Only inject if delivered within last 24 hours
        delivered_at = datetime.fromisoformat(last["delivered_at"])
        if (datetime.now(delivered_at.tzinfo) - delivered_at).total_seconds() > 86400:
            return None
        
        return last
    except Exception as e:
        logger.debug("Failed to load cron delivery metadata: %s", e)
        return None
```

#### 3. Cleanup old metadata

Add periodic cleanup (runs during cron tick or gateway idle):

```python
def _prune_stale_delivery_metadata():
    """Remove delivery metadata older than 7 days."""
    metadata_file = CRON_DIR / "delivery_metadata.json"
    if not metadata_file.exists():
        return
    
    cutoff = _hermes_now() - timedelta(days=7)
    
    with open(metadata_file) as f:
        data = json.load(f)
    
    for channel_key, channel_data in list(data["channels"].items()):
        for slot in ["last_delivery", "previous_delivery"]:
            delivery = channel_data.get(slot)
            if delivery:
                delivered_at = datetime.fromisoformat(delivery["delivered_at"])
                if delivered_at < cutoff:
                    channel_data.pop(slot, None)
        
        if not channel_data:
            data["channels"].pop(channel_key)
    
    atomic_replace(temp_write(data), metadata_file)
```

## Safety

- **Bounded:** Only stores last 1-2 deliveries per channel
- **TTL:** Auto-prunes after 7 days
- **Lightweight:** Preview is truncated to 500 chars
- **Non-breaking:** Failure to load metadata is logged and ignored
- **No PII leak:** Uses existing channel keys (platform:chat_id:thread_id)

## Testing

1. Create a cron job with `deliver=telegram:<chat_id>`
2. Fire the job manually or wait for schedule
3. Check `~/.hermes/cron/delivery_metadata.json` exists and contains the delivery
4. Send a message to that channel
5. Verify the system prompt includes "Recent Scheduled Task Output"
6. Confirm the agent understands context without `session_search`

## Migration

None required. Feature activates automatically for new cron deliveries after deployment.

## Future Enhancements

- Store full output path and allow agent to load on-demand via tool
- Surface delivery metadata in `/cron status` command
- Add `context_handoff: false` flag for jobs that shouldn't inject context

## Open Questions

1. Should CLI sessions also get this? (Current answer: no, CLI doesn't have channel identity)
2. Should we store multiple deliveries per channel? (Current: last 2, could expand)
3. Should the injection be opt-in per job? (Current: automatic for all)

---

**Implementation Notes:**
- Add delivery metadata capture in `cron/scheduler.py::_deliver_to_targets()`
- Add context injection in `gateway/session.py::build_session_context_prompt()`
- Add cleanup in `cron/scheduler.py::tick()` (once per hour)
- Add tests in `tests/cron/test_delivery_metadata.py`
