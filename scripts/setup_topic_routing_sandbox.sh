#!/usr/bin/env bash
# Create a disposable Hermes topic-routing sandbox.
#
# This script never writes into ~/.hermes. It prepares a gateway home plus two
# profile homes with non-sensitive marker data so forum-topic routing can be
# tested against isolated SOUL/config/memory/session trees.

set -euo pipefail

GATEWAY_HOME="${HERMES_TOPIC_ROUTING_GATEWAY_HOME:-/tmp/hermes-topic-routing-gateway}"
PROFILES_ROOT="${HERMES_TOPIC_ROUTING_PROFILES_ROOT:-/tmp/hermes-topic-routing-profiles}"
ALPHA_HOME="$PROFILES_ROOT/alpha-test"
BETA_HOME="$PROFILES_ROOT/beta-test"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

case "$GATEWAY_HOME:$PROFILES_ROOT" in
  *"$HOME/.hermes"*|*"~/.hermes"*)
    echo "Refusing to use ~/.hermes for a sandbox." >&2
    exit 1
    ;;
esac

for path in "$GATEWAY_HOME" "$ALPHA_HOME" "$BETA_HOME"; do
  if [ -L "$path" ]; then
    echo "Refusing symlink sandbox path: $path" >&2
    exit 1
  fi
done

if [ "${1:-}" = "--clean" ]; then
  if command -v trash >/dev/null 2>&1; then
    [ ! -e "$GATEWAY_HOME" ] || trash "$GATEWAY_HOME"
    [ ! -e "$PROFILES_ROOT" ] || trash "$PROFILES_ROOT"
  else
    echo "Refusing to delete without the 'trash' command installed." >&2
    exit 1
  fi
fi

mkdir -p \
  "$GATEWAY_HOME/sessions" \
  "$ALPHA_HOME/memories" "$ALPHA_HOME/sessions" "$ALPHA_HOME/logs" \
  "$BETA_HOME/memories" "$BETA_HOME/sessions" "$BETA_HOME/logs"

cat > "$GATEWAY_HOME/config.yaml" <<EOF
model:
  provider: openai-compatible
  default: sandbox-fake-model
  base_url: http://127.0.0.1:18099/v1
telegram:
  enabled: true
  topic_profiles_safe_root: "$PROFILES_ROOT"
  topic_profiles:
    - match:
        chat_id: "-1000000000000"
        thread_id: 101
      profile: alpha-test
      profile_home: "$ALPHA_HOME"
    - match:
        chat_id: "-1000000000000"
        thread_id: 202
      profile: beta-test
      profile_home: "$BETA_HOME"
EOF

cat > "$GATEWAY_HOME/.env" <<'EOF'
# Sandbox only. Do not put production tokens here.
OPENAI_API_KEY=test-key-only
TELEGRAM_BOT_TOKEN=
EOF

cat > "$ALPHA_HOME/config.yaml" <<'EOF'
model:
  provider: openai-compatible
  default: sandbox-alpha-model
  base_url: http://127.0.0.1:18099/v1
EOF
cat > "$ALPHA_HOME/.env" <<'EOF'
OPENAI_API_KEY=test-key-only
EOF
cat > "$ALPHA_HOME/SOUL.md" <<'EOF'
# Alpha Test Soul

SANDBOX_PROFILE_MARKER=alpha-test
EOF
cat > "$ALPHA_HOME/memories/MEMORY.md" <<'EOF'
SANDBOX_MEMORY_MARKER=alpha-test
EOF

cat > "$BETA_HOME/config.yaml" <<'EOF'
model:
  provider: openai-compatible
  default: sandbox-beta-model
  base_url: http://127.0.0.1:18099/v1
EOF
cat > "$BETA_HOME/.env" <<'EOF'
OPENAI_API_KEY=test-key-only
EOF
cat > "$BETA_HOME/SOUL.md" <<'EOF'
# Beta Test Soul

SANDBOX_PROFILE_MARKER=beta-test
EOF
cat > "$BETA_HOME/memories/MEMORY.md" <<'EOF'
SANDBOX_MEMORY_MARKER=beta-test
EOF

cat <<EOF
Sandbox ready:
  Gateway home: $GATEWAY_HOME
  Alpha profile: $ALPHA_HOME
  Beta profile: $BETA_HOME

Offline tests:
  HERMES_HOME=$GATEWAY_HOME PYTHONPATH=$REPO_ROOT scripts/run_tests.sh tests/gateway/test_topic_profile_routing.py

Manual gateway sandbox:
  HERMES_HOME=$GATEWAY_HOME PYTHONPATH=$REPO_ROOT python -m hermes_cli.main gateway run
EOF
