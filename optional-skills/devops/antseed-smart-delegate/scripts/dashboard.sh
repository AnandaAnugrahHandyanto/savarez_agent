#!/usr/bin/env bash
set -euo pipefail
COMPACT=false; JSON_MODE=false
for arg in "$@"; do case "$arg" in --json) JSON_MODE=true;; --compact) COMPACT=true;; esac; done
PROXY_URL="http://127.0.0.1:8377"

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

G=$'\033[32m'; Y=$'\033[33m'; R=$'\033[31m'; B=$'\033[1m'; D=$'\033[0m'; C=$'\033[36m'; M=$'\033[35m'
div() { printf "${D}-------------------------------------------------------------${D}\n"; }

STATUS=$(antseed buyer status 2>/dev/null || true)
METER=$(antseed buyer metering 2>/dev/null || true)
MODELS=$(curl -s --max-time 5 "$PROXY_URL/v1/models" -H "Authorization: Bearer antseed-p2p" 2>/dev/null || true)

proxy_ok=false; [ -n "$MODELS" ] && proxy_ok=true
mcnt=$(python3 -c "import json,sys; d=json.load(sys.stdin); print(len(d.get('data',[])))" 2>/dev/null <<< "$MODELS" || echo "0")

wallet=$(tbl_val "Wallet address" <<< "$STATUS" 2>/dev/null || echo "?")
da=$(tbl_val "Deposits available" <<< "$STATUS" 2>/dev/null | grep -oP '[\d.]+' || echo "0")
dr=$(tbl_val "Deposits reserved" <<< "$STATUS" 2>/dev/null | grep -oP '[\d.]+' || echo "0")
ch=$(tbl_val "Active channels" <<< "$STATUS" 2>/dev/null | grep -oP '\d+' || echo "0")
peer=$(tbl_val "Pinned peer" <<< "$STATUS" 2>/dev/null | cut -c1-12 || echo "?")
svc=$(tbl_val "Pinned service" <<< "$STATUS" 2>/dev/null || echo "?")
cn=$(tbl_val "Connection state" <<< "$STATUS" 2>/dev/null || echo "?")
signed=$(grep -oiP 'Signed:\s*[\d.]+' <<< "$METER" 2>/dev/null | grep -oP '[\d.]+' || echo "0")
reqs_raw=$(grep -oiP 'Requests:\s*\d+' <<< "$METER" 2>/dev/null | grep -oP '\d+' || echo "0")
reqs=$(echo "$reqs_raw" | tr -d '\n')
total=$(python3 -c "print(f'{float($da)+float($dr):.4f}')")

if $JSON_MODE; then
    python3 <<PYEOF
import json,datetime
print(json.dumps({
    "dashboard": {
        "timestamp": datetime.datetime.now().isoformat(),
        "health": {"proxy_up": $proxy_ok, "connection": "$cn", "channels": int("${ch:-0}")},
        "wallet": {"address": "${wallet:0:10}...", "available": float("$da"), "reserved": float("$dr"), "total": float("$total")},
        "peer": {"id": "${peer:0:12}...", "service": "$svc"},
        "models": {"available_via_proxy": int("$mcnt")},
        "usage": {"requests_served": int("${reqs:-0}"), "usd_signed": float("$signed")}
    }
}, indent=2))
PYEOF
    exit 0
fi

if $COMPACT; then
    $proxy_ok && printf "Status: ${G}ONLINE${D}\n" || printf "Status: ${R}OFFLINE${D}\n"
    printf "Wallet:   %s\n" "${wallet:0:20}..."
    printf "Balance:  \$%s USDC (%s avail + %s resv)\n" "$total" "$da" "$dr"
    printf "Peer:     %s... (%s)\n" "${peer:0:10}" "$svc"
    printf "Channel:  %s active | %s requests | \$%s spent\n" "$ch" "${reqs:-0}" "$signed"
    printf "Models:   %s via proxy\n" "$mcnt"
    exit 0
fi

clear 2>/dev/null || true
printf "\n"
printf "${B}  +======================================================+${D}\n"
printf "${B}  |${D}       ${C}${B}ANTSEED P2P NETWORK DASHBOARD${D}${B}              |${D}\n"
printf "${B}  +======================================================+${D}\n\n"

printf "${B}  HEALTH${D}\n"; div
$proxy_ok && printf "  Proxy:   ${G}* ONLINE${D}  (port 8377)\n" || printf "  Proxy:   ${R}* OFFLINE${D}\n"
[ "$cn" = "connected" ] && printf "  Network: ${G}* CONNECTED${D}\n" || printf "  Network: ${Y}o %s${D}\n" "$cn"
printf "\n"

printf "${B}  WALLET${D}\n"; div
printf "  Address:  ${C}%s${D}\n" "${wallet:0:20}..."
printf "  Balance:  ${B}\$%s USDC${D}\n" "$total"
printf "            ${G}+ \$%s available${D}  ${Y}+ \$%s reserved${D}\n" "$da" "$dr"
printf "\n"

printf "${B}  PEER${D}\n"; div
printf "  ID:       ${M}%s...${D}\n" "${peer:0:12}"
printf "  Service:  %s\n" "$svc"
printf "  Channels: ${G}%s active${D}\n" "$ch"
printf "\n"

printf "${B}  USAGE THIS SESSION${D}\n"; div
printf "  Requests:   %s\n" "${reqs:-0}"
printf "  Signed:     ${Y}\$%s USDC${D}\n" "$signed"
printf "\n"

printf "${B}  MODELS VIA PROXY${D}\n"; div
printf "  Count:      ${C}%s models${D}\n" "$mcnt"
if [ "$mcnt" -gt 0 ] && [ -n "$MODELS" ]; then
    python3 -c "
import json,sys
d=json.load(sys.stdin)
models=sorted([m['id'] for m in d.get('data',[])])
for m in models[:10]: sys.stdout.write('  - '+m+'\n')
if len(models)>10: sys.stdout.write('  ... and '+str(len(models)-10)+' more\n')
" 2>/dev/null <<< "$MODELS"
fi
printf "\n"

printf "${B}  QUICK ACTIONS${D}\n"; div
printf "  auto-delegate <type> <prompt>   one-command delegation\n"
printf "  best-peer <type>                find optimal model\n"
printf "  status-bar [--icon]              one-line status\n"
printf "  cost-report                     spending details\n"
printf "  preflight                       health check\n"
printf "\n"
