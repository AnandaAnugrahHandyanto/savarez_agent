# rate-limiter

Cross-session rate limit guard for side clients (Nous Portal, NVIDIA, etc.) that prevents
retry amplification and 429 errors by proactively blocking requests before hitting the API.

## Problem

Each 429 (rate limit) error from a provider triggers up to 9 API calls per conversation turn:
- 3 SDK retries × 3 Hermes retries = 9 calls
- Every call counts against RPH (requests per hour)
- This amplification can quickly exhaust rate limits

## Solution

This plugin has TWO layers of protection:

1. **Proactive rate limiting** (NEW): Tracks request counts per minute and blocks requests BEFORE hitting the API when approaching the limit
2. **Reactive rate limiting**: Records rate limit state on the first 429 and checks it before subsequent attempts across all sessions

## How it works

### Proactive Rate Limiting (NEW)

The plugin tracks request counts per minute for each provider and blocks requests when approaching the configured limit:

| Provider | Config Key | Example |
|----------|-----------|---------|
| NVIDIA | `nvidia` | `rate_limit.nvidia.requests_per_minute: 40` |
| OpenRouter | `openrouter` | `rate_limit.openrouter.requests_per_minute: 60` |
| Nous | `nous` | `rate_limit.nous.requests_per_minute: 30` |
| Default | `default` | `rate_limit.default.requests_per_minute: 40` |

When the limit is reached:
- The plugin waits up to 60 seconds for the rate limit to reset
- A message is displayed: "⏳ nvidia rate limit active — resets in 15s. Waiting..."
- After waiting, the request is retried

### Reactive Rate Limiting (Legacy)

| Hook | Behaviour |
|---|---|
| `pre_llm_call` | Check if provider is currently rate-limited. If so, inject context to inform the user about the rate limit. |
| `post_llm_call` | If a 429 error is received, parse reset time from headers/error context and record to shared state file. |

**NOTE**: The reactive layer is kept for backward compatibility with the existing `nous_rate_guard.py` system.

## Configuration

Add rate limits to your `~/.hermes/config.yaml`:

```yaml
rate_limit:
  default:
    requests_per_minute: 40  # Default limit for all providers
  nvidia:
    requests_per_minute: 40  # NVIDIA-specific limit
  openrouter:
    requests_per_minute: 60  # OpenRouter-specific limit
  nous:
    requests_per_minute: 30  # Nous-specific limit
```

## Slash commands

```
/ratelimit status    # Show current rate limit status
/ratelimit clear     # Clear rate limit state manually
/ratelimit enable    # Enable the rate limiter
/ratelimit disable   # Disable the rate limiter
/ratelimit set <s>   # Set default cooldown time (seconds)
```

## Safety

- Atomic writes: temp file + rename for safe concurrent access
- Expired entries are automatically cleaned up on read
- State file is scoped to `$HERMES_HOME/rate_limits/`
- No external dependencies beyond standard library
- Proactive blocking prevents 429 errors before they happen

## Testing

Run the test suite:

```bash
pytest tests/plugins/test_rate_limiter_plugin.py -v
```

Tests cover:
- Header parsing (priority order, invalid values)
- Rate limit recording (headers, error context, default cooldown)
- Rate limit checking (remaining time, expiration)
- Plugin hooks (pre_llm_call, post_llm_call)
- Slash commands (status, clear, enable, disable, set)
- Bundled plugin discovery
- Proactive rate limiting (request tracking, limit enforcement)
