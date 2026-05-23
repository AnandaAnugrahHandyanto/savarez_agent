#!/usr/bin/env bash
# launchd wrapper for `hermes dashboard --no-open`.
#
# Why a wrapper instead of invoking hermes directly:
# the dashboard subcommand runs `npm run build` on every startup with
# fatal=True, and Vite 7 needs Node 20.19+.  Launchd's restricted PATH
# resolves /usr/local/bin/node (Node 18) before any fnm-managed Node,
# so the build fails and the dashboard exits 1.  This wrapper prepends
# the user's fnm-managed Node directory to PATH before exec'ing hermes.

set -eu

# Pick the newest fnm-installed Node version (alphanumerically sort
# descending so v22 beats v20, v22.22 beats v22.10, etc.).
FNM_NODE_DIR="$HOME/.local/share/fnm/node-versions"
if [ -d "$FNM_NODE_DIR" ]; then
    NEWEST_NODE=$(ls -1 "$FNM_NODE_DIR" 2>/dev/null | sort -rV | head -n1)
    if [ -n "$NEWEST_NODE" ] && [ -x "$FNM_NODE_DIR/$NEWEST_NODE/installation/bin/node" ]; then
        export PATH="$FNM_NODE_DIR/$NEWEST_NODE/installation/bin:$PATH"
    fi
fi

exec "$HOME/.hermes/hermes-agent/venv/bin/hermes" dashboard --no-open
