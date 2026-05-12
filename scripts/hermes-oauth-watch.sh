#!/usr/bin/env bash
# hermes-oauth-watch.sh — pi-hermes OpenAI/Codex OAuth renewal watchdog.
#
# Checks Hermes's own OpenAI OAuth credential in auth.json without invoking
# hermes-agent or touching the refresh endpoint. This avoids single-use refresh
# token races and still catches the failure mode we care about: the access JWT
# stops rotating and is approaching expiry.
#
# Silent on healthy no-change unless ALWAYS_REPORT=1.
#
# Env:
#   AUTH_FILE                 default /mnt/usb-ssd/hermes/dot-hermes/auth.json
#   STATE_DIR                 default /mnt/usb-ssd/hermes/state
#   ALWAYS_REPORT             set 1 to print/post even when healthy
#   TELEGRAM_CHAT             optional chat:topic target, e.g. -1003774651323:topic:4
#   TELEGRAM_BOT_TOKEN        required if TELEGRAM_CHAT is set
#   TEST_NOW_EPOCH            test override for current Unix time
#   TEST_ACCESS_EXP_EPOCH     test override for decoded access JWT exp
set -euo pipefail

AUTH_FILE="${AUTH_FILE:-/mnt/usb-ssd/hermes/dot-hermes/auth.json}"
STATE_DIR="${STATE_DIR:-/mnt/usb-ssd/hermes/state}"
STATE_FILE="$STATE_DIR/hermes-oauth-watch.json"
ALWAYS_REPORT="${ALWAYS_REPORT:-0}"
WARN_SECONDS=$((4 * 24 * 60 * 60))
CRIT_SECONDS=$((2 * 24 * 60 * 60))

for cmd in python3 jq; do
  command -v "$cmd" >/dev/null || { echo "missing: $cmd" >&2; exit 1; }
done

mkdir -p "$STATE_DIR"

snapshot=$(AUTH_FILE="$AUTH_FILE" TEST_ACCESS_EXP_EPOCH="${TEST_ACCESS_EXP_EPOCH:-}" python3 - <<'PY'
import base64
import datetime as dt
import json
import os
import sys

path = os.environ.get('AUTH_FILE')
override_exp = os.environ.get('TEST_ACCESS_EXP_EPOCH', '').strip()

def emit(**kwargs):
    print(json.dumps(kwargs, sort_keys=True))

try:
    with open(path, 'r', encoding='utf-8') as fh:
        store = json.load(fh)
except FileNotFoundError:
    emit(ok=False, code='auth_file_missing', message=f'auth file missing: {path}')
    sys.exit(0)
except Exception as exc:
    emit(ok=False, code='auth_file_unreadable', message=f'auth file unreadable: {type(exc).__name__}')
    sys.exit(0)

entries = []
cp = store.get('credential_pool')
if isinstance(cp, dict):
    raw = cp.get('openai-codex')
    if isinstance(raw, list):
        entries.extend(e for e in raw if isinstance(e, dict))

provider_state = (store.get('providers') or {}).get('openai-codex')
if isinstance(provider_state, dict):
    tokens = provider_state.get('tokens')
    if isinstance(tokens, dict):
        entries.append({
            'id': 'providers.openai-codex',
            'label': 'providers.openai-codex',
            'auth_type': 'oauth',
            'source': 'providers.openai-codex',
            'access_token': tokens.get('access_token'),
            'refresh_token': tokens.get('refresh_token'),
            'last_refresh': provider_state.get('last_refresh'),
            'base_url': provider_state.get('base_url'),
        })

entries = [e for e in entries if e.get('auth_type') == 'oauth']
if not entries:
    emit(ok=False, code='openai_codex_missing', message='no openai-codex OAuth entry in auth.json')
    sys.exit(0)

def decode_claims(token):
    if not isinstance(token, str) or token.count('.') != 2:
        return None
    try:
        payload = token.split('.')[1]
        payload += '=' * ((4 - len(payload) % 4) % 4)
        return json.loads(base64.urlsafe_b64decode(payload.encode('utf-8')))
    except Exception:
        return None

best = None
best_exp = -1
best_claims = None
for entry in entries:
    token = entry.get('access_token') or entry.get('runtime_api_key')
    claims = decode_claims(token)
    exp = claims.get('exp') if isinstance(claims, dict) else None
    if isinstance(exp, (int, float)) and exp > best_exp:
        best = entry
        best_exp = int(exp)
        best_claims = claims

if best is None:
    emit(ok=False, code='access_token_exp_missing', message='openai-codex access token is missing a decodable exp claim')
    sys.exit(0)

if not isinstance(best.get('refresh_token'), str) or not best.get('refresh_token').strip():
    emit(ok=False, code='refresh_token_missing', message='openai-codex refresh_token missing; manual re-login required')
    sys.exit(0)

if override_exp:
    try:
        best_exp = int(float(override_exp))
    except Exception:
        emit(ok=False, code='test_override_invalid', message='TEST_ACCESS_EXP_EPOCH is not numeric')
        sys.exit(0)

issued_at = best_claims.get('iat') if isinstance(best_claims, dict) else None
issuer = best_claims.get('iss') if isinstance(best_claims, dict) else None
aud = best_claims.get('aud') if isinstance(best_claims, dict) else None
auth = best_claims.get('https://api.openai.com/auth') if isinstance(best_claims, dict) else None
plan = auth.get('chatgpt_plan_type') if isinstance(auth, dict) else None

def iso(ts):
    try:
        return dt.datetime.fromtimestamp(int(ts), dt.timezone.utc).isoformat().replace('+00:00', 'Z')
    except Exception:
        return None

emit(
    ok=True,
    code='ok',
    provider='openai-codex',
    active_provider=store.get('active_provider'),
    selected_id=best.get('id'),
    selected_label=best.get('label'),
    selected_source=best.get('source'),
    base_url=best.get('base_url'),
    issuer=issuer,
    audience=aud,
    plan=plan,
    issued_at_epoch=issued_at,
    issued_at=iso(issued_at) if isinstance(issued_at, (int, float)) else None,
    access_expires_at_epoch=best_exp,
    access_expires_at=iso(best_exp),
    last_refresh=best.get('last_refresh'),
    auth_file=path,
)
PY
)

now_epoch="${TEST_NOW_EPOCH:-$(date -u +%s)}"
if ! [[ "$now_epoch" =~ ^[0-9]+$ ]]; then
  echo "TEST_NOW_EPOCH must be a Unix timestamp" >&2
  exit 1
fi

ok=$(jq -r '.ok' <<<"$snapshot")
code=$(jq -r '.code // "unknown"' <<<"$snapshot")
severity="ok"
tier="healthy"
headline="✅ pi-hermes OpenAI OAuth healthy"
remaining_seconds=""
remaining_text="unknown"

if [ "$ok" != "true" ]; then
  severity="crit"
  tier="$code"
  headline="🚨 pi-hermes OpenAI OAuth watchdog CRIT"
else
  exp=$(jq -r '.access_expires_at_epoch' <<<"$snapshot")
  remaining_seconds=$(( exp - now_epoch ))
  if [ "$remaining_seconds" -le 0 ]; then
    severity="crit"
    tier="expired"
    headline="🚨 pi-hermes OpenAI OAuth expired"
  elif [ "$remaining_seconds" -le "$CRIT_SECONDS" ]; then
    severity="crit"
    tier="crit_${CRIT_SECONDS}s"
    headline="🚨 pi-hermes OpenAI OAuth expires soon"
  elif [ "$remaining_seconds" -le "$WARN_SECONDS" ]; then
    severity="warn"
    tier="warn_${WARN_SECONDS}s"
    headline="⚠️ pi-hermes OpenAI OAuth renewal window"
  fi

  abs=$remaining_seconds
  [ "$abs" -lt 0 ] && abs=$(( -abs ))
  days=$(( abs / 86400 ))
  hours=$(( (abs % 86400) / 3600 ))
  mins=$(( (abs % 3600) / 60 ))
  if [ "$remaining_seconds" -lt 0 ]; then
    remaining_text="expired ${days}d ${hours}h ${mins}m ago"
  else
    remaining_text="${days}d ${hours}h ${mins}m remaining"
  fi
fi

state_key="${severity}:${tier}:$(jq -r '.access_expires_at // .code // "unknown"' <<<"$snapshot")"
today=$(date -u +%F)
prev_key=""
prev_day=""
if [ -r "$STATE_FILE" ]; then
  prev_key=$(jq -r '.last_alert_key // ""' "$STATE_FILE" 2>/dev/null || true)
  prev_day=$(jq -r '.last_alert_day // ""' "$STATE_FILE" 2>/dev/null || true)
fi

should_emit=0
if [ "$ALWAYS_REPORT" = "1" ]; then
  should_emit=1
elif [ "$severity" != "ok" ]; then
  if [ "$state_key" != "$prev_key" ] || [ "$today" != "$prev_day" ]; then
    should_emit=1
  fi
fi

body="*${headline}* — $(date -u +%Y-%m-%dT%H:%MZ)
Severity: ${severity}
Tier: ${tier}
Provider: openai-codex / GPT-5.5 OAuth
Signal: OpenAI access-token JWT expiry (refresh token itself is opaque)
Remaining: ${remaining_text}
Auth file: ${AUTH_FILE}"

if [ "$ok" = "true" ]; then
  body="$body
Access expires: $(jq -r '.access_expires_at // "unknown"' <<<"$snapshot")
Issued at: $(jq -r '.issued_at // "unknown"' <<<"$snapshot")
Last refresh: $(jq -r '.last_refresh // "unknown"' <<<"$snapshot")
Issuer: $(jq -r '.issuer // "unknown"' <<<"$snapshot")
Plan: $(jq -r '.plan // "unknown"' <<<"$snapshot")
Selected entry: $(jq -r '.selected_label // .selected_id // "unknown"' <<<"$snapshot")"
else
  body="$body
Reason: $(jq -r '.message // .code // "unknown"' <<<"$snapshot")"
fi

if [ "$severity" != "ok" ]; then
  body="$body
Action: re-login on pi-hermes with \`hermes auth login\` / Hermes OpenAI OAuth flow before GPT-5.5 degrades."
fi
body="$body
— Puck"

if [ "$should_emit" = "1" ]; then
  if [ -n "${TELEGRAM_CHAT:-}" ] && [ -n "${TELEGRAM_BOT_TOKEN:-}" ]; then
    command -v curl >/dev/null || { echo "missing: curl" >&2; exit 1; }
    chat_id="${TELEGRAM_CHAT%%:*}"
    thread_id=""
    case "$TELEGRAM_CHAT" in *:topic:*) thread_id="${TELEGRAM_CHAT##*:}";; esac
    response=$(curl -sS -X POST \
      "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
      --data-urlencode "chat_id=$chat_id" \
      ${thread_id:+--data-urlencode "message_thread_id=$thread_id"} \
      --data-urlencode "parse_mode=Markdown" \
      --data-urlencode "text=$body")
    if ! jq -e '.ok == true' >/dev/null <<<"$response"; then
      echo "Telegram send failed: $response" >&2
      exit 3
    fi
  else
    printf '%s\n' "$body"
  fi
fi

jq -n \
  --arg checked_at "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --arg severity "$severity" \
  --arg tier "$tier" \
  --arg state_key "$state_key" \
  --arg day "$today" \
  --argjson snapshot "$snapshot" \
  --arg remaining_seconds "${remaining_seconds:-}" \
  '{checked_at: $checked_at, severity: $severity, tier: $tier, last_snapshot: $snapshot, remaining_seconds: $remaining_seconds}' \
  > "$STATE_FILE.tmp"
if [ "$should_emit" = "1" ] && [ "$severity" != "ok" ]; then
  jq --arg k "$state_key" --arg d "$today" '. + {last_alert_key: $k, last_alert_day: $d}' "$STATE_FILE.tmp" > "$STATE_FILE.tmp2"
  mv "$STATE_FILE.tmp2" "$STATE_FILE.tmp"
fi
mv "$STATE_FILE.tmp" "$STATE_FILE"

exit 0
