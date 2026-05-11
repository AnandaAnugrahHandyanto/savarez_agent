#!/usr/bin/env bash
set -euo pipefail
PROXY_URL="http://127.0.0.1:8377"
JSON_MODE=false; SHOW_ICON=false
for arg in "$@"; do case "$arg" in --json) JSON_MODE=true;; --icon) SHOW_ICON=true;; esac; done

tbl_val() {
    python3 -c "
import sys
text=sys.stdin.read(); key=sys.argv[1].lower()
for L in text.splitlines():
    if key.lower() in L.lower():
        parts=L.split('\u2502')
        if len(parts)>=3:
            print(parts[2].strip())
            break
" "$1"
}

STATUS=$(antseed buyer status 2>/dev/null || true)
METER=$(antseed buyer metering 2>/dev/null || true)
proxy_up=false
curl -s --max-time 3 "$PROXY_URL/v1/models" >/dev/null 2>&1 && proxy_up=true

wallet=$(tbl_val "Wallet address" <<< "$STATUS" 2>/dev/null || echo "?")
da=$(tbl_val "Deposits available" <<< "$STATUS" 2>/dev/null | grep -oP '[\d.]+' || echo "0")
dr=$(tbl_val "Deposits reserved" <<< "$STATUS" 2>/dev/null | grep -oP '[\d.]+' || echo "0")
ch=$(tbl_val "Active channels" <<< "$STATUS" 2>/dev/null | grep -oP '\d+' || echo "0")
peer=$(tbl_val "Pinned peer" <<< "$STATUS" 2>/dev/null | cut -c1-10 || echo "?")
svc=$(tbl_val "Pinned service" <<< "$STATUS" 2>/dev/null || echo "?")
cn=$(tbl_val "Connection state" <<< "$STATUS" 2>/dev/null || echo "?")

signed=$(grep -oiP 'Signed:\s*[\d.]+' <<< "$METER" 2>/dev/null | grep -oP '[\d.]+' || echo "0")
reqs_raw=$(grep -oiP 'Requests:\s*\d+' <<< "$METER" 2>/dev/null | grep -oP '\d+' || echo "0")
reqs=$(echo "$reqs_raw" | tr -d '\n')
chst=$(grep -oiP 'Status:\s*\w+' <<< "$METER" 2>/dev/null | tr -d '\n' | sed 's/Status:\s*//' || echo "?")

# Get current model from proxy models list (faster than best-peer)
model=$(curl -s --max-time 5 "$PROXY_URL/v1/models" -H "Authorization: Bearer antseed-p2p" 2>/dev/null | python3 -c "
import json,sys
d=json.load(sys.stdin)
models=[m['id'] for m in d.get('data',[])]
# Pick first interesting model
for prefer in ['step-3.5-flash','qwen3.5','glm-5.1','deepseek','minimax']:
    for m in models:
        if prefer in m.lower():
            print(m); sys.exit(0)
print(models[0] if models else '?')
" 2>/dev/null || echo "?")

total=$(python3 -c "print(f'{float($da)+float($dr):.2f}')")

if $JSON_MODE; then
    python3 <<PYEOF
import json
print(json.dumps({
    "antseed": {
        "proxy_up": ("$proxy_up" == "True"),
        "connected": "$cn" == "connected",
        "wallet": "${wallet:0:10}...",
        "deposits_available": float("$da"),
        "deposits_reserved": float("$dr"),
        "deposits_total": float("$total"),
        "channels": int("${ch:-0}"),
        "peer": "${peer:0:10}",
        "service": "$svc",
        "model": "$model",
        "channel_status": "$chst",
        "requests_served": int("${reqs:-0}"),
        "usd_signed": float("$signed")
    }
}, indent=2))
PYEOF
else
    ICON=""
    $SHOW_ICON && ICON=$'\U1F41D '
    if [ "$cn" = "connected" ] && $proxy_up; then C=$'\033[32m'
    elif $proxy_up; then C=$'\033[33m'
    else C=$'\033[31m'; fi
    R=$'\033[0m'
    echo -e "${C}${ICON}AntSeed${R} | \$${total} | ${model} | req:${reqs:-?} ch:${ch:-?} | ${peer:0:8}... | ${chst}" >&2
fi
