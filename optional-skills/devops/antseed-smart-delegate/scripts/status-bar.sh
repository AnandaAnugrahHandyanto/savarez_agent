#!/usr/bin/env bash
# antseed-smart-delegate/scripts/status-bar.sh
# One-line AntSeed status: balance | model | tokens | peer | channel
# Usage: bash status-bar.sh [--json] [--icon]
set -euo pipefail

PROXY_URL="http://127.0.0.1:8377"
JSON_MODE=false; SHOW_ICON=false

for arg in "$@"; do
    case "$arg" in --json) JSON_MODE=true;; --icon) SHOW_ICON=true;; esac
done

parse_table() {
    python3 -c "
import sys, re
text = sys.stdin.read()
key = sys.argv[1]
for line in text.splitlines():
    if key.lower() in line.lower():
        parts = line.split('\u2502')
        if len(parts) >= 3:
            val = parts[2].strip()
            print(val)
            break
" "$1"
}

STATUS_OUTPUT=$(antseed buyer status 2>/dev/null || echo "")
METERING_OUTPUT=$(antseed buyer metering 2>/dev/null || echo "")

proxy_up=false; wallet="unknown"; deposits="0"; reserved="0"; channels="0"
pinned_peer="none"; pinned_service="none"; conn_state="disconnected"
signed_usd="0"; requests="0"; channel_status="none"

if [ -n "$STATUS_OUTPUT" ]; then
    if curl -s --max-time 3 "$PROXY_URL/v1/models" > /dev/null 2>&1; then
        proxy_up=true
    fi
    wallet=$(parse_table "Wallet address" "$STATUS_OUTPUT" 2>/dev/null || echo "unknown")
    deposits=$(parse_table "Deposits available" "$STATUS_OUTPUT" 2>/dev/null | grep -oP '[\d.]+' || echo "0")
    reserved=$(parse_table "Deposits reserved" "$STATUS_OUTPUT" 2>/dev/null | grep -oP '[\d.]+' || echo "0")
    channels=$(parse_table "Active channels" "$STATUS_OUTPUT" 2>/dev/null | grep -oP '\d+' || echo "0")
    pinned_peer=$(parse_table "Pinned peer" "$STATUS_OUTPUT" 2>/dev/null | head -c 10 || echo "none")
    pinned_service=$(parse_table "Pinned service" "$STATUS_OUTPUT" 2>/dev/null || echo "none")
    conn_state=$(parse_table "Connection state" "$STATUS_OUTPUT" 2>/dev/null || echo "unknown")
fi

if [ -n "$METERING_OUTPUT" ]; then
    signed_usd=$(echo "$METERING_OUTPUT" | grep -oiP 'Signed:\s*[\d.]+' | grep -oP '[\d.]+' || echo "0")
    requests=$(echo "$METERING_OUTPUT" | grep -oiP 'Requests:\s*\d+' | grep -oP '\d+' || echo "0")
    channel_status=$(echo "$METERING_OUTPUT" | grep -oiP 'Status:\s*\w+' | grep -oP '(?<=Status:\s*)\w+' || echo "none")
fi

current_model=$(bash "$(dirname "$0")/best-peer.sh" code --json 2>/dev/null | python3 -c "
import json,sys
try:
    d=json.load(sys.stdin)
    print(d.get('best',{}).get('model','?'))
except: print('?')
" 2>/dev/null || echo "?")

total_deposits=$(python3 -c "print(float($deposits) + float($reserved))" 2>/dev/null || echo "0")

if $JSON_MODE; then
    python3 -c "
import json
print(json.dumps({
    'antseed': {
        'proxy_up': $proxy_up,
        'connected': '$conn_state' == 'connected',
        'wallet': '${wallet:0:10}...',
        'deposits_available': float('$deposits'),
        'deposits_reserved': float('$reserved'),
        'deposits_total': float('$total_deposits'),
        'channels': int('$channels'),
        'peer': '$pinned_peer...',
        'service': '$pinned_service',
        'model': '$current_model',
        'channel_status': '$channel_status',
        'requests_served': int('$requests'),
        'usd_signed': float('$signed_usd')
    }
}, indent=2))
"
else
    ICON=""
    $SHOW_ICON && ICON="\xF0\x9F\x90\x9D "  # 🐝 UTF-8 bytes
    
    if [ "$conn_state" = "connected" ] && $proxy_up; then
        C="\033[32m"  # green
    elif $proxy_up; then
        C="\033[33m"  # yellow
    else
        C="\033[31m"  # red
    fi
    R="\033[0m"
    
    printf "${C}${ICON}AntSeed${R} | \$%.2f | %s | req:%d ch:%d | %s... | %s\n" \
        "$total_deposits" "$current_model" "$requests" "$channels" "$pinned_peer" "$channel_status" >&2
fi
