# ev/oauth-max-billing

## Problem
On Claude Max subscriptions, OAuth-authenticated Hermes requests bill to
"extra usage" (org credits) instead of consuming the Max plan quota.

## Root cause
Wrong OAuth authorize/token/redirect URLs and missing scopes in
`agent/anthropic_adapter.py`. The legacy `claude.ai/oauth/authorize` URL
routes through the Console / API-key flow; the current Max flow lives at
`claude.com/cai/oauth/authorize` with `platform.claude.com` token endpoints.

## Files changed
- `agent/anthropic_adapter.py` — OAuth constants + one inline URL reference

## Test command (obsolete-if condition)
This patch is obsolete IF stock upstream `agent/anthropic_adapter.py` already
contains all of the following constants:
- `_OAUTH_AUTHORIZE_URL = "https://claude.com/cai/oauth/authorize"` (or equivalent)
- `_OAUTH_TOKEN_URL = "https://platform.claude.com/v1/oauth/token"`
- `_OAUTH_REDIRECT_URI = "https://platform.claude.com/oauth/code/callback"`
- `_OAUTH_SCOPES` includes `user:sessions:claude_code`

Quick check:
```bash
grep -E '(claude\.com/cai/oauth/authorize|platform\.claude\.com/v1/oauth/token|user:sessions:claude_code)' agent/anthropic_adapter.py | wc -l
# obsolete if output >= 3
```

## Watched upstream issues / PRs
- https://github.com/NousResearch/hermes-agent/issues/15291 (primary — "OAuth CC billing all usage as extra usage")
- https://github.com/NousResearch/hermes-agent/issues/15080
- https://github.com/NousResearch/hermes-agent/issues/10575
- Our PR will be linked here after open.

## Evidence
See ANALYSIS.md (saved at /tmp/oauth-fix-cc/ANALYSIS.md at investigation time)
or the original investigation in this session's record. Independent verification
from the actual claude CLI v2.1.126 binary confirmed the four wrong constants.
