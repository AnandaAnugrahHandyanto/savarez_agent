# Mem0 Lifecycle Management — Reference Implementation

> **Note**: This is a vibe-coded reference implementation submitted under the [vibe coding guidelines](https://github.com/NousResearch/hermes-agent/blob/main/CONTRIBUTING.md). Code was generated iteratively with LLM assistance, reviewed against production requirements, and validated through local testing before submission.

## Overview

Memory lifetime management bridge layer for Mem0, adding:
- Access frequency tracking (auto-incremented on every search)
- Exponential decay scoring (half-life = 7 days)
- Grace period protection (14 days for new memories)  
- Automated cleanup (threshold-based)

## Background

Mem0 SDK has no built-in mechanism for memory expiration or decay. Over time, databases accumulate stale entries that degrade retrieval quality and inflate context windows. This plugin implements a production-tested solution used in our deployment.

## Core Formula

```python
weighted_score = min(access_count, 255) * 0.5^(days_since_last_access / 7)
```

### Tunable Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `HALF_LIFE_DAYS` | 7.0 | Exponential decay half-life (days) |
| `CLEANUP_THRESHOLD` | 0.05 | Memories below this score are deleted |
| `ACCESS_COUNT_CAP` | 255 | Hard cap preventing unbounded growth |
| `GRACE_PERIOD_DAYS` | 14 | New memories protected from deletion |

## Usage

```bash
# Search memories (auto-tracks access frequency)
python mem0_server.py search "query text" hermes-user

# Get stats
python mem0_server.py stats hermes-user

# Cleanup stale memories
python mem0_server.py cleanup --dry-run hermes-user   # Preview
python mem0_server.py cleanup hermes-user             # Execute
```

## Automation via systemd

Create a drop-in config at `$SYSTEMD_USER_DIR/your-gateway.service.d/mem0-cleanup.conf`:

```ini
[Service]
ExecStartPre=/path/to/mem0-daily-cleanup.sh
TimeoutStartSec=300
```

## Production Results

After running in production:
- ~20 active memories, access counts range 0–2
- Zero false deletions
- Zero manual intervention needed
- Single-access memory auto-cleaned after ~33 days
- Max-count memory (255) auto-cleaned after ~86 days of inactivity

## References

- Issue: [mem0ai/mem0#5330](https://github.com/mem0ai/mem0/issues/5330)
- Reference repo: [HH1162/mem0-lifecycle](https://github.com/HH1162/mem0-lifecycle)
