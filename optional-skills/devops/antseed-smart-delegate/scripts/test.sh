#!/usr/bin/env bash
# antseed-smart-delegate/test.sh — validate skill structure, syntax, and secrets
set -euo pipefail

SKILL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PASS=0; FAIL=0

pass() { echo "  PASS $1"; PASS=$((PASS+1)); }
fail() { echo "  FAIL $1"; FAIL=$((FAIL+1)); }

echo "=== antseed-smart-delegate: skill validation ==="
echo ""

echo "[Structure]"
test -f "$SKILL_DIR/SKILL.md" && pass "SKILL.md exists" || fail "SKILL.md missing"
test -d "$SKILL_DIR/scripts" && pass "scripts/ dir exists" || fail "scripts/ missing"
for sh in preflight best-peer cost-report status-bar dashboard auto-delegate test; do
    test -f "$SKILL_DIR/scripts/${sh}.sh" && pass "${sh}.sh exists" || fail "${sh}.sh missing"
done

echo ""
echo "[Frontmatter]"
head -1 "$SKILL_DIR/SKILL.md" | grep -q "^---$" && pass "starts with ---" || fail "no --- opener"
for field in name description version author license; do
    grep -q "^${field}:" "$SKILL_DIR/SKILL.md" && pass "has ${field}" || fail "no ${field}"
done
grep -q "tags:" "$SKILL_DIR/SKILL.md" && pass "has tags" || fail "no tags"
grep -q "required_environment_variables" "$SKILL_DIR/SKILL.md" && pass "has required_env_vars" || fail "no required_env_vars"

echo ""
echo "[Size limits]"
python3 -c "
import re
t=open('$SKILL_DIR/SKILL.md').read()
m=re.search(r'^description: (.*)$', t, re.M)
assert m and len(m.group(1)) <= 1024, 'description too long'
assert len(t) <= 100000, 'skill too large'
" 2>/dev/null && pass "size OK" || fail "size FAIL"

echo ""
echo "[Scripts: executable + bash syntax]"
for sh in preflight best-peer cost-report status-bar dashboard auto-delegate test; do
    f="$SKILL_DIR/scripts/${sh}.sh"
    test -x "$f" && pass "${sh}.sh executable" || fail "${sh}.sh not executable"
    bash -n "$f" 2>/dev/null && pass "${sh}.sh syntax OK" || fail "${sh}.sh syntax FAIL"
done

echo ""
echo "[No secrets leaked in SKILL.md]"
(grep -rqE "0x[0-9a-f]{20,}" "$SKILL_DIR/SKILL.md") 2>/dev/null && fail "wallet addr leak" || pass "no wallet addrs"
(grep -rqE "89\.110|192\.168\." "$SKILL_DIR/SKILL.md") 2>/dev/null && fail "IP leak" || pass "no IPs"
(grep -rqE "ghp_|gho_|sk-[A-Za-z0-9]{20,}" "$SKILL_DIR/SKILL.md") 2>/dev/null && fail "token leak" || pass "no tokens"
(grep -rq "ryptotalent|sava" "$SKILL_DIR/SKILL.md") 2>/dev/null && fail "username leak" || pass "no usernames"

echo ""
echo "[No secrets leaked in scripts]"
(grep -rqE "0x[0-9a-f]{20,}" "$SKILL_DIR/scripts/") 2>/dev/null && fail "wallet in scripts" || pass "scripts clean"
(grep -rqE "89\.110|192\.168\." "$SKILL_DIR/scripts/") 2>/dev/null && fail "IPs in scripts" || pass "scripts no IPs"

echo ""
echo "[Documentation completeness]"
grep -q "status-bar" "$SKILL_DIR/SKILL.md" && pass "status-bar documented" || fail "status-bar missing from docs"
grep -q "dashboard" "$SKILL_DIR/SKILL.md" && pass "dashboard documented" || fail "dashboard missing from docs"
grep -q "auto-delegate" "$SKILL_DIR/SKILL.md" && pass "auto-delegate documented" || fail "auto-delegate missing from docs"
grep -q "Pitfalls" "$SKILL_DIR/SKILL.md" && pass "has Pitfalls section" || fail "no Pitfalls section"

echo ""
echo "=== Results: $PASS passed, $FAIL failed ==="
[ "$FAIL" -eq 0 ]
