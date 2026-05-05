#!/usr/bin/env bash
# Bootstrap a fresh Ubuntu VPS for Hermes Agent.
# Idempotent: safe to run repeatedly. Installs Docker Engine + compose plugin,
# enables the daemon, and adds the invoking user to the docker group.

set -euo pipefail

log() { printf '\033[0;36m[bootstrap]\033[0m %s\n' "$*"; }
err() { printf '\033[0;31m[bootstrap]\033[0m %s\n' "$*" >&2; }

if [ "$(id -u)" -eq 0 ]; then
    SUDO=""
else
    SUDO="sudo"
    if ! command -v sudo >/dev/null 2>&1; then
        err "Not running as root and sudo is not installed. Re-run as root or install sudo."
        exit 1
    fi
fi

if ! grep -qiE 'ubuntu|debian' /etc/os-release 2>/dev/null; then
    err "This bootstrap targets Ubuntu/Debian. Detected: $(. /etc/os-release && echo "$PRETTY_NAME")"
    exit 1
fi

. /etc/os-release
DISTRO_ID="${ID:-ubuntu}"
DISTRO_CODENAME="${VERSION_CODENAME:-}"

if [ -z "$DISTRO_CODENAME" ]; then
    if command -v lsb_release >/dev/null 2>&1; then
        DISTRO_CODENAME="$(lsb_release -cs)"
    fi
fi

log "Updating apt index"
export DEBIAN_FRONTEND=noninteractive
$SUDO apt-get update -y

log "Installing base packages"
$SUDO apt-get install -y --no-install-recommends \
    ca-certificates curl gnupg rsync git ufw

if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
    log "Docker + compose plugin already present ($(docker --version))"
else
    log "Installing Docker Engine from docker.com"
    $SUDO install -m 0755 -d /etc/apt/keyrings
    if [ ! -f /etc/apt/keyrings/docker.gpg ]; then
        curl -fsSL "https://download.docker.com/linux/${DISTRO_ID}/gpg" \
            | $SUDO gpg --dearmor -o /etc/apt/keyrings/docker.gpg
        $SUDO chmod a+r /etc/apt/keyrings/docker.gpg
    fi

    arch="$(dpkg --print-architecture)"
    repo="deb [arch=${arch} signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/${DISTRO_ID} ${DISTRO_CODENAME} stable"
    echo "$repo" | $SUDO tee /etc/apt/sources.list.d/docker.list >/dev/null

    $SUDO apt-get update -y
    $SUDO apt-get install -y \
        docker-ce docker-ce-cli containerd.io \
        docker-buildx-plugin docker-compose-plugin
fi

log "Enabling docker service"
$SUDO systemctl enable --now docker

# Add the invoking (non-root) user to the docker group so subsequent sessions
# can run docker without sudo. Effective on next login, not in the current
# session — the deploy script falls back to sudo where needed.
TARGET_USER="${SUDO_USER:-$(id -un)}"
if [ "$TARGET_USER" != "root" ] && ! id -nG "$TARGET_USER" | grep -qw docker; then
    log "Adding $TARGET_USER to docker group"
    $SUDO usermod -aG docker "$TARGET_USER"
fi

log "Docker version: $(docker --version 2>/dev/null || echo unavailable)"
log "Compose version: $(docker compose version 2>/dev/null || echo unavailable)"
log "Bootstrap complete."
