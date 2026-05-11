#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR=$(cd $(dirname "$0") && pwd)
TASK_TYPE="${1:-chat}"
shift; PROMPT="$*"
MODEL_OVERRIDE=""
DRY_RUN=false
PROXY_URL="http://127.0.0.1:8377"
AUTH='Authorization: Bearer antseed-p2p'
G='[32m'
R='[31m'
D='[0m'
C='[36m'

log() { printf "${C}[antseed]${D} %s\n" "$1" >&2; }
ok()  { printf "${G}[OK]${D} %s\n" "$1" >&2; }
warn(){ printf "${C}[..]${D} %s\n" "$1" >&2; }
fail(){ printf "${R}[FAIL]${D} %s\n" "$1" >&2; }

for arg in $PROMPT; do
    case "$arg" in --model) MODEL_OVERRIDE="${PROMPT##*--model }"; MODEL_OVERRIDE="${MODEL_OVERRIDE%% *}" ;; --dry-run) DRY_RUN=true ;; esac
done
CLEAN_PROMPT=$(echo "$PROMPT" | sed 's/--model [^ ]*//g; s/--dry-run//g' | xargs)

log "Step 1/4: Preflight..."
PF=$(bash "$SCRIPT_DIR/preflight.sh" --json 2>/dev/null || echo '{}')
PF_OK=$(echo "$PF" | python3 -c "import json,sys;print(json.load(sys.stdin).get('ok',False))" 2>/dev/null || echo false)
if [ "$PF_OK" != True ]; then fail "Preflight failed"; exit 1; fi
ok "Proxy up, peer pinned, wallet ready"

log "Step 2/4: Selecting model..."
case "$TASK_TYPE" in
    code|coding|debug|refactor) MODEL_LIST=(minimaxai/minimax-m2.5 glm-5v-turbo glm-5.1) ;;
    research|analysis) MODEL_LIST=(glm-5v-turbo glm-5.1 minimaxai/minimax-m2.5) ;;
    vision|image) MODEL_LIST=(glm-5v-turbo minimaxai/minimax-m2.5) ;;
    *) MODEL_LIST=(minimaxai/minimax-m2.5 glm-5v-turbo glm-5.1) ;;
esac
[ -n "$MODEL_OVERRIDE" ] && MODEL_LIST=("$MODEL_OVERRIDE")
BEST_MODEL="${MODEL_LIST[0]}"
ok "Primary: $BEST_MODEL (${#MODEL_LIST[@]} fallbacks)"
$DRY_RUN && log "DRY RUN" && exit 0

log "Step 3/4: Delegating..."
RESP_RAW=""
HTTP_CODE="000"
USED_MODEL=""
for MODEL in "${MODEL_LIST[@]}"; do
    warn "Trying: $MODEL ..."
    PAYLOAD=$(echo "$CLEAN_PROMPT" | python3 "$SCRIPT_DIR/_build_payload.py" "$MODEL")
    RESP_RAW=$(curl -s --max-time 60 -w "__HTTP__%{http_code}" "$PROXY_URL/v1/chat/completions" -H "$AUTH" -H "Content-Type: application/json" -d "$PAYLOAD" 2>/dev/null || true)
    HTTP_CODE=$(echo "$RESP_RAW" | tail -1 | sed "s/.*__HTTP__//" || echo 000)
    if [ "$HTTP_CODE" -ge 200 ] && [ "$HTTP_CODE" -lt 300 ]; then
        USED_MODEL="$MODEL"
        ok "Success! HTTP $HTTP_CODE via $MODEL"
        break
    else
        fail "HTTP $HTTP_CODE from $MODEL"
    fi
done
if [ -z "$USED_MODEL" ]; then fail "All models failed"; echo "$RESP_RAW" | head -5 >&2; exit 1; fi

log "Step 4/4: Extracting result..."
OUTPUT=$(echo "$RESP_RAW" | python3 "$SCRIPT_DIR/_extract.py" 2>&1)
CONTENT=$(echo "$OUTPUT" | grep -v '^TOKENS:' | head -1)
TOKEN_INFO=$(echo "$OUTPUT" | grep '^TOKENS:' | sed 's/TOKENS://')

bash "$SCRIPT_DIR/cost-report.sh" >/dev/null 2>&1 || true

printf "
${D}--- ANTSEED RESULT ---${D}
" >&2
printf "%s
" "$CONTENT" >&2
printf "
${D}Model: ${C}%s${D} | Tokens: %s
" "$USED_MODEL" "$TOKEN_INFO" >&2
