#!/usr/bin/env bash
# antseed-smart-delegate/scripts/dashboard.sh
# Full AntSeed dashboard: balance, models, peers, spending, health
# Usage: bash dashboard.sh [--json] [--compact]
set -euo pipefail

COMPACT=false; JSON_MODE=false
for arg in "$@"; do case "$arg" in --json) JSON_MODE=true;; --compact) COMPACT=true;; esac; done

PROXY_URL="http://127.0.0.1:8377"

parse_table() {
    python3 -c "
import sys
text = sys.stdin.read()
key = sys.argv[1]
for line in text.splitlines():
    if key.lower() in line.lower():
        parts = line.split('\u2502')
        if len(parts) >= 3:
            print(parts[2].strip())
            break
" "$1"
}

G="\033[32m"; Y="\033[33m"; R="\033[31m"; B="\033[1m"; D="\033[0m"; C="\033[36m"; M="\033[35m"

divider() { printf "${D}─────────────────────────────────────────────────────────────${D}\n"; }

STATUS=$(antseed buyer status 2>/dev/null || echo "")
METERING=$(antseed buyer metering 2>/dev/null || echo "")
MODELS=$(curl -s --max-time 5 "$PROXY_URL/v1/models" -H "Authorization: Bearer antseed-p2p" 2>/dev/null || echo "")

proxy_ok=false; [ -n "$MODELS" ] && proxy_ok=true
model_count=$(echo "$MODELS" | python3 -c "import json,sys; d=json.load(sys.stdin); print(len(d.get('data',[])))" 2>/dev/null || echo "0")

wallet=$(parse_table "Wallet address" "$STATUS" 2>/dev/null || echo "?")
deposits_avail=$(parse_table "Deposits available" "$STATUS" 2>/dev/null | grep -oP '[\d.]+' || echo "0")
deposits_resv=$(parse_table "Deposits reserved" "$STATUS" 2>/dev/null | grep -oP '[\d.]+' || echo "0")
channels=$(parse_table "Active channels" "$STATUS" 2>/dev/null | grep -oP '\d+' || echo "0")
peer=$(parse_table "Pinned peer" "$STATUS" 2>/dev/null | head -c 12 || echo "?")
service=$(parse_table "Pinned service" "$STATUS" 2>/dev/null || echo "?")
conn=$(parse_table "Connection state" "$STATUS" 2>/dev/null || echo "?")
signed=$(echo "$METERING" | grep -oiP 'Signed:\s*[\d.]+' | grep -oP '[\d.]+' || echo "0")
reqs=$(echo "$METERING" | grep -oiP 'Requests:\s*\d+' | grep -oP '\d+' || echo "0")

total_bal=$(python3 -c "print(f'{float($deposits_avail)+float($deposits_resv):.4f}')")

if $JSON_MODE; then
    python3 -c "
import json,datetime
print(json.dumps({
    'dashboard': {
        'timestamp': datetime.datetime.now().isoformat(),
        'health': { 'proxy_up': $proxy_ok, 'connection': '$conn', 'channels': int('$channels') },
        'wallet': { 'address': '${wallet:0:10}...', 'available': float('$deposits_avail'), 'reserved': float('$deposits_resv'), 'total': float('$total_bal') },
        'peer': { 'id': '$peer...', 'service': '$service' },
        'models': { 'available_via_proxy': int('$model_count') },
        'usage': { 'requests_served': int('$reqs'), 'usd_signed': float('$signed') }
    }
}, indent=2))
"
    exit 0
fi

if $COMPACT; then
    $proxy_ok && echo -e "${G}UP${D}" || echo -e "${R}DOWN${D}"
    echo "  Wallet:   ${C}${wallet}${D}"
    echo "  Balance:  ${B}\$${total_bal} USDC${D} (\$${deposits_avail} avail + \$${deposits_resv} resv)"
    echo "  Peer:     ${M}${peer}...${D} (${service})"
    echo "  Channel:  ${G}${channels} active${D} | ${reqs} requests | \$${signed} spent"
    echo "  Models:   ${Y}${model_count}${D} via proxy"
    exit 0
fi

clear 2>/dev/null || true
printf "\n"
printf "${B}  ╔═══════════════════════════════════════════════════════╗${D}\n"
printf "${B}  ║${D}           ${C}${B}ANTSEED P2P NETWORK DASHBOARD${D}${B}              ║${D}\n"
printf "${B}  ╚═══════════════════════════════════════════════════════╝${D}\n"
printf "\n"

printf "${B}  HEALTH${D}\n"; divider
$proxy_ok && printf "  Proxy:   ${G}* ONLINE${D}  (port 8377)\n" || printf "  Proxy:   ${R}* OFFLINE${D}\n"
[ "$conn" = "connected" ] && printf "  Network: ${G}* CONNECTED${D}\n" || printf "  Network: ${Y}o $conn${D}\n"
printf "\n"

printf "${B}  WALLET${D}\n"; divider
printf "  Address:  ${C}%s${D}\n" "$wallet"
printf "  Balance:  ${B}\$%s USDC${D}\n" "$total_bal"
printf "            ${G}+ \$%s available${D}  ${Y}+ \$%s reserved${D}\n" "$deposits_avail" "$deposits_resv"
printf "\n"

printf "${B}  PEER${D}\n"; divider
printf "  ID:       ${M}%s...${D}\n" "$peer"
printf "  Service:  %s\n" "$service"
printf "  Channels: ${G}%s active${D}\n" "$channels"
printf "\n"

printf "${B}  USAGE THIS SESSION${D}\n"; divider
printf "  Requests:    %s\n" "$reqs"
printf "  Signed:      ${Y}\$%s USDC${D}\n" "$signed"
printf "\n"

printf "${B}  MODELS VIA PROXY${D}\n"; divider
printf "  Count:       ${C}%s models${D}\n" "$model_count"
if [ "$model_count" -gt 0 ] && [ -n "$MODELS" ]; then
    echo "$MODELS" | python3 -c "
import json,sys
d=json.load(sys.stdin)
models=sorted([m['id'] for m in d.get('data',[])])
for m in models[:10]:
    sys.stdout.write(f'  - {m}\n')
if len(models)>10: sys.stdout.write(f'  ... and {len(models)-10} more\n')
" 2>/dev/null
fi
printf "\n"

printf "${B}  QUICK ACTIONS${D}\n"; divider
printf "  auto-delegate <type> <prompt>   one-command delegation\n"
printf "  best-peer <type>                find optimal model\n"
printf "  cost-report                     spending details\n"
printf "  preflight                       health check\n"
printf "  status-bar                      one-line status\n"
printf "\n"
