#!/usr/bin/env bash
# antseed-smart-delegate/scripts/auto-delegate.sh
# One-command delegation: preflight -> best-peer -> execute (with retry+fallback) -> report
#
# Usage:
#   bash auto-delegate.sh code "Refactor auth module"
#   bash auto-delegate.sh research "Summarize RLHF papers" --model deepseek-v4-flash
#   bash auto-delegate.sh vision "Describe this screenshot" --dry-run
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TASK_TYPE="${1:-code}"
shift; PROMPT="${*:-hello}"

MODEL_OVERRIDE=""
DRY_RUN=false
MAX_RETRIES=3

PROXY_URL="http://127.0.0.1:8377"
AUTH_HDR="Authorization: Bearer antseed-p2p"

G="\033[32m"; Y="\033[33m"; R="\033[31m"; B="\033[1m"; D="\033[0m"; C="\033[36m"

log()  { printf "${C}[antseed]${D} %s\n" "$1" >&2; }
ok()   { printf "${G}[OK]${D} %s\n" "$1" >&2; }
warn() { printf "${C}[..]${D} %s\n" "$1" >&2; }
fail() { printf "${R}[FAIL]${D} %s\n" "$1" >&2; }

# Parse flags from PROMPT
for arg in $PROMPT; do
    case "$arg" in
        --model)     MODEL_OVERRIDE="${PROMPT##*--model }"; MODEL_OVERRIDE="${MODEL_OVERRIDE%% *}" ;;
        --dry-run)   DRY_RUN=true ;;
    esac
done

# Strip flags from prompt for clean message
CLEAN_PROMPT=$(echo "$PROMPT" | sed 's/--model [^ ]*//g; s/--dry-run//g' | xargs)

# === STEP 1: PREFLIGHT ===
log "Step 1/4: Preflight..."
PF_JSON=$("$SCRIPT_DIR/preflight.sh" --json 2>/dev/null || echo "{}")
PF_OK=$(echo "$PF_JSON" | python3 -c "import json,sys; print(json.load(sys.stdin).get('ok',False))" 2>/dev/null || echo "false")

if [ "$PF_OK" != "True" ]; then
    fail "Preflight failed:"
    echo "$PF_JSON" | python3 -m json.tool 2>/dev/null >/dev/null 2>&1 || true
    fail "Run: bash $SCRIPT_DIR/preflight.sh for details"
    exit 1
fi
ok "Preflight: proxy up, peer pinned, wallet ready"

# === STEP 2: BEST PEER SELECTION ===
log "Step 2/4: Selecting best model for '$TASK_TYPE'..."
BP_JSON=$("$SCRIPT_DIR/best-peer.sh" "$TASK_TYPE" --json 2>/dev/null || echo "{}")

BEST_MODEL=$(echo "$BP_JSON" | python3 -c "import json,sys; print(json.load(sys.stdin).get('best',{}).get('model',''))" 2>/dev/null || echo "")
BEST_PEER_ID=$(echo "$BP_JSON" | python3 -c "import json,sys; print(json.load(sys.stdin).get('best',{}).get('peer_id',''))" 2>/dev/null || echo "")
PRICE_IN=$(echo "$BP_JSON" | python3 -c "import json,sys; print(json.load(sys.stdin).get('best',{}).get('price_in','?'))" 2>/dev/null || echo "?")
N_FALLBACKS=$(echo "$BP_JSON" | python3 -c "import json,sys; d=json.load(sys.stdin); print(len(d.get('fallbacks',[])))" 2>/dev/null || echo "0")

[ -n "$MODEL_OVERRIDE" ] && BEST_MODEL="$MODEL_OVERRIDE"

ok "Model: $BEST_MODEL (\$${PRICE_IN}/1M tokens)"
ok "Peer: ${BEST_PEER_ID:0:10}... ($N_FALLBACKS fallbacks available)"

if $DRY_RUN; then
    log "--- DRY RUN (no request sent) ---"
    log "Task:   $TASK_TYPE"
    log "Model:  $BEST_MODEL"
    log "Prompt: ${CLEAN_PROMPT:0:100}"
    exit 0
fi

# Build model list: best first, then fallbacks
MODEL_LIST=("$BEST_MODEL")
for i in $(seq 1 "$N_FALLBACKS"); do
    FB=$(echo "$BP_JSON" | python3 -c "import json,sys; print(json.load(sys.stdin)['fallbacks'][$i-1]['model'])" 2>/dev/null || true)
    [ -n "$FB" ] && MODEL_LIST+=("$FB")
done

# === STEP 3: EXECUTE WITH RETRY + FALLBACK ===
log "Step 3/4: Executing delegation..."
RESP_BODY=""
HTTP_CODE="000"
USED_MODEL=""

for MODEL in "${MODEL_LIST[@]}"; do
    warn "Trying: $MODEL ..."
    
    # Build JSON payload via Python to avoid shell quoting hell
    PAYLOAD=$(python3 -c "
import json
print(json.dumps({
    'model': '$MODEL',
    'messages': [{'role':'user','content':'''$(printf '%s' "$CLEAN_PROMPT" | python3 -c 'import sys,json;print(json.dumps(sys.stdin.read()))')'''}],
    'max_tokens': 4096,
    'temperature': 0.7
}))
")
    
    RAW_RESP=$(curl -s --max-time 60 -w "\n__HTTP__%{http_code}" \
        "$PROXY_URL/v1/chat/completions" \
        -H "$AUTH_HDR" \
        -H "Content-Type: application/json" \
        -d "$PAYLOAD" 2>/dev/null || true)
    
    HTTP_CODE=$(echo "$RAW_RESP" | tail -1 | grep -oP '\d+$' || echo "000")
    RESP_BODY=$(echo "$RAW_RESP" | grep -v "__HTTP__" || echo "{}")
    
    if [ "$HTTP_CODE" -ge 200 ] && [ "$HTTP_CODE" -lt 300 ]; then
        USED_MODEL="$MODEL"
        ok "Success! HTTP $HTTP_CODE via $MODEL"
        break
    else
        fail "HTTP $HTTP_CODE from $MODEL, trying next..."
    fi
done

if [ -z "$USED_MODEL" ]; then
    fail "All ${#MODEL_LIST[@]} models failed"
    echo "$RESP_BODY" | head -20 >&2
    exit 1
fi

# === STEP 4: EXTRACT RESULT + REPORT ===
log "Step 4/4: Extracting result..."

CONTENT=$(echo "$RESP_BODY" | python3 -c "
import json,sys
d=json.load(sys.stdin)
c=d.get('choices',[])
if c:
    m=c[0].get('message',{})
    print(m.get('content','') or m.get('reasoning','(empty)'))
else:
    print(json.dumps(d)[:300])
" 2>/dev/null || echo "(parse error)")

TOKEN_INFO=$(echo "$RESP_BODY" | python3 -c "
import json,sys
d=json.load(sys.stdin); u=d.get('usage',{})
print(f'{u.get(\"prompt_tokens\",0)} in / {u.get(\"completion_tokens\",0)} out')
" 2>/dev/null || echo "?/?")

# Update cost tracking
"$SCRIPT_DIR/cost-report.sh" >/dev/null 2>&1 || true

# === OUTPUT ===
printf "\n${B}--- ANTSEED DELEGATION RESULT ---${D}\n" >&2
printf "%s\n" "$CONTENT" >&2
printf "\n${D}Model: ${C}%s${D} | Tokens: %s\n" "$USED_MODEL" "$TOKEN_INFO" >&2

# JSON on stdout for piping
python3 -c "
import json
_content = '''$(printf '%s' "$CONTENT" | python3 -c 'import sys,json;print(json.dumps(sys.stdin.read()))')'''
print(json.dumps({
    'success': True,
    'model': '$USED_MODEL',
    'tokens': '$TOKEN_INFO',
    'task_type': '$TASK_TYPE',
    'content': _content
}, indent=2))
"
