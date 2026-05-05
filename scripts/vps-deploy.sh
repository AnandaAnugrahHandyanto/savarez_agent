#!/usr/bin/env bash
# Build (or refresh) and start the Hermes Agent stack on the VPS.
# Invoked by .github/workflows/deploy-vps.yml after rsync uploads the source.
#
# Usage: vps-deploy.sh <install_dir>
# Env:
#   FORCE_RESTART=true  -> docker compose up -d --force-recreate
#   DEPLOY_REF=...      -> recorded in $INSTALL_DIR/.deployed_ref for traceability

set -euo pipefail

INSTALL_DIR="${1:-/opt/hermes-agent}"
FORCE_RESTART="${FORCE_RESTART:-false}"
DEPLOY_REF="${DEPLOY_REF:-unknown}"

log() { printf '\033[0;36m[deploy]\033[0m %s\n' "$*"; }
err() { printf '\033[0;31m[deploy]\033[0m %s\n' "$*" >&2; }

if [ ! -f "$INSTALL_DIR/docker-compose.yml" ]; then
    err "docker-compose.yml not found in $INSTALL_DIR. Did rsync run?"
    exit 1
fi

cd "$INSTALL_DIR"

# Run docker as the invoking user when possible; fall back to sudo on the
# first deploy (group membership only takes effect on the next login).
if docker info >/dev/null 2>&1; then
    DOCKER="docker"
elif command -v sudo >/dev/null 2>&1 && sudo -n docker info >/dev/null 2>&1; then
    DOCKER="sudo docker"
else
    err "Cannot reach the docker daemon. Is bootstrap complete?"
    exit 1
fi

# .env handling. The workflow may have written a fresh one from VPS_HERMES_ENV.
# Otherwise, seed from .env.example on first deploy and leave existing files alone.
if [ ! -f .env ]; then
    if [ -f .env.example ]; then
        log "No .env present; seeding from .env.example (edit on the VPS to fill in keys)"
        cp .env.example .env
        chmod 600 .env
    else
        log "No .env or .env.example; continuing without one"
    fi
fi

# Pin file ownership inside the data volume to the host user so the entrypoint's
# usermod/gosu remap matches.
HERMES_UID="$(id -u)"
HERMES_GID="$(id -g)"
export HERMES_UID HERMES_GID

# Record the deployed git ref for operators inspecting the VPS later.
printf '%s\n' "$DEPLOY_REF" > .deployed_ref

log "Building image (this can take several minutes on a fresh VPS)"
$DOCKER compose build

up_args=("-d")
if [ "$FORCE_RESTART" = "true" ]; then
    up_args+=("--force-recreate")
fi

log "Starting stack (HERMES_UID=$HERMES_UID HERMES_GID=$HERMES_GID)"
$DOCKER compose up "${up_args[@]}"

log "Waiting briefly for containers to settle"
sleep 5

log "Container status:"
$DOCKER compose ps

# Surface logs from any service that exited so failures are visible in the
# GitHub Actions output instead of silently rolled back.
unhealthy="$($DOCKER compose ps --status=exited --quiet || true)"
if [ -n "$unhealthy" ]; then
    err "One or more services exited. Recent logs:"
    $DOCKER compose logs --tail=80
    exit 1
fi

log "Deploy complete (ref: $DEPLOY_REF)."
