#!/usr/bin/env bash
# ============================================================================
# run.sh — Hermes Agent headless launcher (WebUI / CLI / gateway)
# ============================================================================
# Boots Hermes on a headless VPS with logs streamed live to the terminal.
#
#   Usage:
#     ./run.sh up                 # default: headless WebUI (hermes dashboard)
#     ./run.sh up --public        # WebUI bound to 0.0.0.0 (reachable by IP) — see SECURITY
#     ./run.sh up --port 9119      # override WebUI port (default 9119)
#     ./run.sh up --cli           # interactive terminal UI (needs a TTY)
#     ./run.sh up --gateway       # messaging gateway service (Telegram/Discord/…)
#     ./run.sh up --setup-only    # provision the uv env, then exit
#     ./run.sh status             # list running hermes dashboard processes
#     ./run.sh down               # stop running hermes dashboard processes
#     ./run.sh doctor             # print what the launcher detected, change nothing
#     ./run.sh help
#
# Architecture note (why there is NO custom web server here):
#   The Electron desktop app was only ever a thin browser shell. It spawns the
#   Python backend as `python -m hermes_cli.main dashboard --no-open --host
#   127.0.0.1 --port 0`; that backend (hermes_cli/web_server.py) is a FastAPI +
#   uvicorn server which builds the web/ frontend into hermes_cli/web_dist and
#   serves the agent API + WebSocket + UI. Going headless therefore means
#   running that SAME server directly and binding it to a network interface —
#   no parallel server, no forked agent logic, no GUI process.
#
#   SECURITY: `hermes dashboard` refuses any non-loopback bind unless --insecure
#   is passed, because a public bind disables the auth layer and exposes your
#   API keys to anyone who can reach the port. `--public` opts into that. The
#   safer production pattern is to keep the default 127.0.0.1 bind and reach it
#   over an SSH tunnel  (ssh -L 9119:127.0.0.1:9119 user@vps)  or place it
#   behind a TLS reverse proxy that enforces authentication.
#
# Idempotency: an existing ./venv and ./hermes_cli/web_dist are reused, never
#   rebuilt unless missing. `status`/`down` use the backend's own process
#   management. Re-running `./run.sh up` is safe.
# ============================================================================

set -Eeuo pipefail

# --- Resolve project root so the script works from any CWD -------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

export UV_NO_CONFIG="${UV_NO_CONFIG:-1}"   # don't read uv config from a foreign HOME under sudo (#21269)

VENV_DIR="$SCRIPT_DIR/venv"
HERMES_BIN="$VENV_DIR/bin/hermes"
WEB_DIST="$SCRIPT_DIR/hermes_cli/web_dist"
LOG_DIR="$SCRIPT_DIR/logs"
PYTHON_VERSION="3.11"
DEFAULT_PORT=9119

# --- Logging -----------------------------------------------------------------
if [ -t 1 ]; then
  C_INFO=$'\033[0;36m'; C_OK=$'\033[0;32m'; C_WARN=$'\033[0;33m'
  C_ERR=$'\033[0;31m';  C_DIM=$'\033[0;90m'; C_OFF=$'\033[0m'
else
  C_INFO=""; C_OK=""; C_WARN=""; C_ERR=""; C_DIM=""; C_OFF=""
fi
log()  { printf '%s[hermes-run]%s %s\n'  "$C_INFO" "$C_OFF" "$*"; }
ok()   { printf '%s[hermes-run]%s %s\n'  "$C_OK"   "$C_OFF" "$*"; }
warn() { printf '%s[hermes-run]%s %s\n'  "$C_WARN" "$C_OFF" "$*" >&2; }
die()  { printf '%s[hermes-run] ERROR:%s %s\n' "$C_ERR" "$C_OFF" "$*" >&2; exit 1; }
trap 'die "failed at line $LINENO (command: $BASH_COMMAND)"' ERR

have() { command -v "$1" >/dev/null 2>&1; }

# ============================================================================
# Environment provisioning — uv only (no pip / requirements.txt), reused if present
# ============================================================================

resolve_uv() {
  if have uv; then echo "uv"; return 0; fi
  for c in "$HOME/.local/bin/uv" "$HOME/.cargo/bin/uv"; do
    [ -x "$c" ] && { echo "$c"; return 0; }
  done
  return 1
}

ensure_python_env() {
  if [ -x "$HERMES_BIN" ]; then
    ok "Python env present (venv/bin/hermes) — reusing, not reinstalling."
    return 0
  fi

  local UV; UV="$(resolve_uv)" || die \
    "'uv' is not installed and no venv exists. Install uv (https://docs.astral.sh/uv/) \
or run ./setup-hermes.sh, then retry."

  log "Provisioning uv environment into ./venv (first run only; 1-5 min) ..."
  [ -d "$VENV_DIR" ] || "$UV" venv "$VENV_DIR" --python "$PYTHON_VERSION"

  # Hash-verified install straight from pyproject.toml + uv.lock.
  if ! UV_PROJECT_ENVIRONMENT="$VENV_DIR" "$UV" sync --extra all --locked; then
    warn "'uv sync --locked' failed (stale lockfile?) — retrying without --locked."
    UV_PROJECT_ENVIRONMENT="$VENV_DIR" "$UV" sync --extra all
  fi

  [ -x "$HERMES_BIN" ] || die "Provisioning finished but $HERMES_BIN is missing."
  ok "Environment provisioned."
}

# ============================================================================
# Runtime helpers
# ============================================================================

# Warn (don't fail) if the chosen port is already bound.
port_busy() {
  local port="$1"
  if have lsof; then
    [ -n "$(lsof -nP -iTCP:"$port" -sTCP:LISTEN -t 2>/dev/null || true)" ]
  elif have ss; then
    ss -ltn 2>/dev/null | grep -Eq "[:.]$port[[:space:]]"
  else
    return 1
  fi
}

# Foreground-exec with its own process group; tee logs live; tear down the whole
# group on Ctrl-C / TERM so no child is orphaned.
run_foreground() {
  local name="$1"; shift
  mkdir -p "$LOG_DIR"
  local logfile="$LOG_DIR/${name}.log"
  log "Streaming '${name}' logs to terminal and ${C_DIM}${logfile}${C_OFF} — Ctrl-C to stop."
  set -m
  "$@" > >(tee -a "$logfile") 2>&1 &
  local child=$!
  trap 'warn "Stopping ${name} ..."; kill -- -"$child" 2>/dev/null || kill "$child" 2>/dev/null || true' INT TERM
  local rc=0
  wait "$child" || rc=$?
  trap - INT TERM
  if [ "$rc" -ne 0 ]; then
    warn "'${name}' exited with code ${rc} (see ${logfile})."
    return "$rc"
  fi
  ok "'${name}' exited cleanly."
}

# ============================================================================
# Service launchers
# ============================================================================

launch_webui() {
  local public="$1" port="$2"
  local host="127.0.0.1"
  local args=(dashboard --no-open --port "$port")

  if [ "$public" -eq 1 ]; then
    host="0.0.0.0"
    args+=(--host "$host" --insecure)
    warn "──────────────────────────────────────────────────────────────────────"
    warn " SECURITY: --public binds 0.0.0.0 with --insecure. This DISABLES the"
    warn " dashboard auth layer and exposes your configured API keys to anyone"
    warn " who can reach this port. Only do this behind a firewall/VPN, or"
    warn " prefer an SSH tunnel:  ssh -L ${port}:127.0.0.1:${port} user@<vps>"
    warn "──────────────────────────────────────────────────────────────────────"
  else
    args+=(--host "$host")
  fi

  # Reuse a prebuilt frontend when present (VPS-friendly: no redundant rebuild,
  # and no Node needed on restart). First run builds web_dist automatically.
  if [ -f "$WEB_DIST/index.html" ]; then
    args+=(--skip-build)
    ok "Reusing prebuilt WebUI (hermes_cli/web_dist) — skipping frontend build."
  else
    if ! have node; then
      warn "Node.js not found and hermes_cli/web_dist is absent — the first-run"
      warn "frontend build needs Node >= 20. Install Node, or copy a prebuilt"
      warn "web_dist into hermes_cli/ and re-run."
    fi
    log "First run: the WebUI frontend will be built into hermes_cli/web_dist."
  fi

  if port_busy "$port"; then
    warn "Port ${port} is already in use. A dashboard may already be running:"
    warn "  check: ./run.sh status     stop: ./run.sh down     other port: ./run.sh up --port <N>"
  fi

  log "WebUI will listen on ${C_OK}http://${host}:${port}${C_OFF}"
  if [ "$public" -eq 1 ]; then
    log "Reachable at ${C_OK}http://<VPS-PUBLIC-IP>:${port}${C_OFF} (substitute this host's public IP)."
  else
    log "Bound to loopback. From your laptop:  ssh -L ${port}:127.0.0.1:${port} user@<vps>  then open http://localhost:${port}"
  fi

  run_foreground "webui" "$HERMES_BIN" "${args[@]}"
}

launch_cli() {
  [ -t 0 ] && [ -t 1 ] || die "The interactive CLI needs a TTY. Use './run.sh up' (WebUI) or '--gateway' instead."
  log "Starting the Hermes interactive terminal UI."
  exec "$HERMES_BIN"
}

launch_gateway() {
  warn "Gateway mode assumes 'hermes gateway setup' has already configured a platform."
  run_foreground "gateway" "$HERMES_BIN" gateway start
}

# ============================================================================
# Diagnostics / process management (delegates to the backend's own commands)
# ============================================================================

doctor() {
  log "Hermes launcher diagnostics:"
  printf '  %-22s %s\n' "project root"     "$SCRIPT_DIR"
  printf '  %-22s %s\n' "os"               "$(uname -srm 2>/dev/null || echo unknown)"
  printf '  %-22s %s\n' "venv/bin/hermes"  "$([ -x "$HERMES_BIN" ] && echo present || echo MISSING)"
  printf '  %-22s %s\n' "uv"               "$(resolve_uv 2>/dev/null || echo 'not found')"
  printf '  %-22s %s\n' "node (web build)" "$(have node && node --version || echo 'not found')"
  printf '  %-22s %s\n' "web_dist (prebuilt)" "$([ -f "$WEB_DIST/index.html" ] && echo present || echo 'absent (built on first run)')"
  printf '  %-22s %s\n' "default WebUI port" "$DEFAULT_PORT"
  printf '  %-22s %s\n' "port $DEFAULT_PORT in use" "$(port_busy "$DEFAULT_PORT" && echo yes || echo no)"
  printf '  %-22s %s\n' "stdin/stdout TTY" "$([ -t 0 ] && [ -t 1 ] && echo yes || echo no)"
}

usage() { sed -n '5,17p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; }

# ============================================================================
# Entry point
# ============================================================================

main() {
  local cmd="${1:-help}"; shift || true
  case "$cmd" in
    up)
      local mode="webui" public=0 setup_only=0 port="${HERMES_WEB_PORT:-$DEFAULT_PORT}"
      while [ $# -gt 0 ]; do
        case "$1" in
          --public)     public=1 ;;
          --port)       shift; [ $# -gt 0 ] || die "--port needs a value"; port="$1" ;;
          --cli)        mode="cli" ;;
          --gateway)    mode="gateway" ;;
          --setup-only) setup_only=1 ;;
          *) die "Unknown option for 'up': $1 (see ./run.sh help)" ;;
        esac
        shift
      done

      ensure_python_env
      [ "$setup_only" -eq 1 ] && { ok "Setup complete (--setup-only); not launching."; return 0; }

      log "Run mode: ${C_OK}${mode}${C_OFF}"
      case "$mode" in
        webui)   launch_webui "$public" "$port" ;;
        cli)     launch_cli ;;
        gateway) launch_gateway ;;
      esac
      ;;
    status) ensure_python_env >/dev/null; "$HERMES_BIN" dashboard --status ;;
    down)   ensure_python_env >/dev/null; "$HERMES_BIN" dashboard --stop ;;
    doctor) doctor ;;
    help|-h|--help) usage ;;
    *) die "Unknown command: '$cmd'. Try: ./run.sh up | status | down | doctor | help" ;;
  esac
}

main "$@"
