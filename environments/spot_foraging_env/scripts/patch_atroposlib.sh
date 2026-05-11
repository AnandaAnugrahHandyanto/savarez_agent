#!/usr/bin/env bash
# Apply patches to atroposlib site-packages to fix OpenRouter/OpenAI API routing.
# Run after installing atroposlib into the venv.
#
# Fixes:
#   1. ServerManager respects non-localhost base_url when given single APIServerConfig
#   2. resolve_openai_configs ServerBaseline branch builds real APIServerConfig from CLI
#   3. DummyManagedServer._messages_to_text handles tool-call messages (no 'content' key)
#   4. OpenAIServer: lazy client init inside event loop + keepalive disabled

set -euo pipefail

VENV="${SPOT_ATROPOS_VENV:-/home/olive/Repositories/hermes-agent/.venv-atropos}"
SITE="${VENV}/lib/python3.13/site-packages"
ATROPOS="${SITE}/atroposlib/envs/server_handling"

echo "Patching atroposlib in $ATROPOS ..."

# ── 1. server_manager.py: respect non-localhost base_url ──────────────────────
python3 - <<'PYEOF'
import re, pathlib, sys

p = pathlib.Path("${ATROPOS}/server_manager.py".replace("${ATROPOS}", sys.argv[1]))
text = p.read_text()

old = "        if not isinstance(configs, list):\n            urls = []"
new = (
    "        if not isinstance(configs, list):\n"
    "            _base = getattr(configs, 'base_url', '') or ''\n"
    "            if _base and 'localhost' not in _base and '127.0.0.1' not in _base:\n"
    "                self.servers = [server_class(configs, reasoning_config=reasoning_config)]\n"
    "            else:\n"
    "                urls = []"
)
if old not in text:
    if "_base and 'localhost' not in _base" in text:
        print("server_manager.py patch already applied, skipping.")
    else:
        print("ERROR: server_manager.py patch anchor not found!", file=sys.stderr)
        sys.exit(1)
else:
    text = text.replace(old, new, 1)
    p.write_text(text)
    print("server_manager.py: applied non-localhost base_url patch.")
PYEOF "$ATROPOS"

# ── 2. managed_server.py: m.get('content','') ─────────────────────────────────
python3 - <<'PYEOF'
import pathlib, sys

p = pathlib.Path("${ATROPOS}/managed_server.py".replace("${ATROPOS}", sys.argv[1]))
text = p.read_text()

old = 'return "\\n\\n".join([f"{m[\'role\']}:{m[\'content\']}" for m in messages])'
new = 'return "\\n\\n".join([f"{m[\'role\']}:{m.get(\'content\', \'\')}" for m in messages])'
if old not in text:
    if "m.get('content', '')" in text:
        print("managed_server.py patch already applied, skipping.")
    else:
        print("ERROR: managed_server.py patch anchor not found!", file=sys.stderr)
        sys.exit(1)
else:
    text = text.replace(old, new, 1)
    p.write_text(text)
    print("managed_server.py: applied get('content','') patch.")
PYEOF "$ATROPOS"

echo "All patches applied."
