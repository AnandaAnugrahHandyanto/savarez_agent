#!/usr/bin/env bash
set -euo pipefail

# ─── MemTensor Memory Plugin installer for hermes-agent ───
#
# Clones or updates the memos-local-plugin runtime, installs Node.js
# dependencies, and records the bridge path for runtime discovery.
#
# Usage:
#   bash plugins/memory/memtensor/install.sh

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BOLD='\033[1m'
NC='\033[0m'

info()    { echo -e "${BLUE}$1${NC}"; }
success() { echo -e "${GREEN}$1${NC}"; }
warn()    { echo -e "${YELLOW}$1${NC}"; }
error()   { echo -e "${RED}$1${NC}"; }

# ─── Node.js auto-install helpers ───

node_major_version() {
  if ! command -v node >/dev/null 2>&1; then
    echo "0"
    return 0
  fi
  local node_version
  node_version="$(node -v 2>/dev/null || true)"
  node_version="${node_version#v}"
  echo "${node_version%%.*}"
}

run_with_privilege() {
  if [[ "$(id -u)" -eq 0 ]]; then
    "$@"
  else
    sudo "$@"
  fi
}

download_to_file() {
  local url="$1"
  local output="$2"
  if command -v curl >/dev/null 2>&1; then
    curl -fsSL --proto '=https' --tlsv1.2 "$url" -o "$output"
    return 0
  fi
  if command -v wget >/dev/null 2>&1; then
    wget -q --https-only --secure-protocol=TLSv1_2 "$url" -O "$output"
    return 0
  fi
  return 1
}

install_node22() {
  local os_name
  os_name="$(uname -s)"

  if [[ "$os_name" == "Darwin" ]]; then
    if ! command -v brew >/dev/null 2>&1; then
      error "Homebrew is required to auto-install Node.js on macOS"
      error "Install Homebrew first: https://brew.sh"
      exit 1
    fi
    info "Auto-installing Node.js 22 via Homebrew..."
    brew install node@22 >/dev/null
    brew link node@22 --overwrite --force >/dev/null 2>&1 || true
    local brew_node_prefix
    brew_node_prefix="$(brew --prefix node@22 2>/dev/null || true)"
    if [[ -n "$brew_node_prefix" && -x "${brew_node_prefix}/bin/node" ]]; then
      export PATH="${brew_node_prefix}/bin:${PATH}"
    fi
    return 0
  fi

  if [[ "$os_name" == "Linux" ]]; then
    info "Auto-installing Node.js 22 on Linux..."
    local tmp_script
    tmp_script="$(mktemp)"
    if command -v apt-get >/dev/null 2>&1; then
      if ! download_to_file "https://deb.nodesource.com/setup_22.x" "$tmp_script"; then
        error "Failed to download NodeSource setup script"
        rm -f "$tmp_script"
        exit 1
      fi
      run_with_privilege bash "$tmp_script"
      run_with_privilege apt-get update -qq
      run_with_privilege apt-get install -y -qq nodejs
      rm -f "$tmp_script"
      return 0
    fi
    if command -v dnf >/dev/null 2>&1; then
      if ! download_to_file "https://rpm.nodesource.com/setup_22.x" "$tmp_script"; then
        error "Failed to download NodeSource setup script"
        rm -f "$tmp_script"
        exit 1
      fi
      run_with_privilege bash "$tmp_script"
      run_with_privilege dnf install -y -q nodejs
      rm -f "$tmp_script"
      return 0
    fi
    if command -v yum >/dev/null 2>&1; then
      if ! download_to_file "https://rpm.nodesource.com/setup_22.x" "$tmp_script"; then
        error "Failed to download NodeSource setup script"
        rm -f "$tmp_script"
        exit 1
      fi
      run_with_privilege bash "$tmp_script"
      run_with_privilege yum install -y -q nodejs
      rm -f "$tmp_script"
      return 0
    fi
    rm -f "$tmp_script"
  fi

  error "Unsupported platform for auto-install. Please install Node.js >= 18 manually."
  exit 1
}

ensure_node() {
  local required_major=18
  local current_major
  current_major="$(node_major_version)"

  if [[ "$current_major" =~ ^[0-9]+$ ]] && (( current_major >= required_major )); then
    success "✓ Node.js $(node -v)"
    return 0
  fi

  warn "Node.js >= ${required_major} is required but not found. Auto-installing..."
  install_node22

  current_major="$(node_major_version)"
  if [[ "$current_major" =~ ^[0-9]+$ ]] && (( current_major >= required_major )); then
    success "✓ Node.js installed: $(node -v)"
    return 0
  fi

  error "Node.js installation failed — still below >= ${required_major}."
  exit 1
}

# ─── Main ───

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
HERMES_REPO="$(cd "$SCRIPT_DIR/../../.." && pwd)"
MEMOS_RUNTIME_DIR="${MEMOS_PLUGIN_ROOT:-$HOME/.hermes/memtensor-runtime}"
MEMOS_REPO_URL="https://github.com/MemTensor/MemOS.git"
MEMOS_PLUGIN_SUBDIR="apps/memos-local-plugin"

echo -e "${BOLD}=== MemTensor Memory Plugin Installer ===${NC}"
echo ""
info "Plugin dir:     $SCRIPT_DIR"
info "Hermes repo:    $HERMES_REPO"
info "Runtime dir:    $MEMOS_RUNTIME_DIR"
echo ""

# ─── Pre-flight checks ───

if [ ! -f "$HERMES_REPO/agent/memory_provider.py" ]; then
  error "ERROR: $HERMES_REPO does not look like a hermes-agent repository."
  exit 1
fi

ensure_node

# ─── Clone or update the memos-local-plugin runtime ───

echo ""
if [ -d "$MEMOS_RUNTIME_DIR/.git" ]; then
  info "Updating memos-local-plugin runtime..."
  cd "$MEMOS_RUNTIME_DIR"
  git pull --ff-only 2>/dev/null || warn "  git pull failed, using existing version"
elif [ -d "$MEMOS_RUNTIME_DIR/package.json" ]; then
  info "Runtime directory exists (non-git), skipping update."
else
  info "Cloning memos-local-plugin runtime..."
  git clone --depth 1 --filter=blob:none --sparse "$MEMOS_REPO_URL" "$MEMOS_RUNTIME_DIR"
  cd "$MEMOS_RUNTIME_DIR"
  git sparse-checkout set "$MEMOS_PLUGIN_SUBDIR" packages/memos-core packages/memos-schema packages/adapter-base
  # Move the plugin to the root for simpler paths
  if [ -d "$MEMOS_RUNTIME_DIR/$MEMOS_PLUGIN_SUBDIR" ]; then
    cp -r "$MEMOS_RUNTIME_DIR/$MEMOS_PLUGIN_SUBDIR/"* "$MEMOS_RUNTIME_DIR/" 2>/dev/null || true
  fi
fi

success "✓ Runtime available"

# ─── Install Node.js dependencies ───

echo ""
info "Installing Node.js dependencies..."
cd "$MEMOS_RUNTIME_DIR"

if command -v pnpm &>/dev/null; then
  pnpm install --frozen-lockfile 2>/dev/null || pnpm install
elif command -v npm &>/dev/null; then
  npm install
else
  error "ERROR: npm or pnpm is required."
  exit 1
fi

success "✓ Dependencies installed"

# ─── Record bridge path for runtime discovery ───

BRIDGE_CTS="$MEMOS_RUNTIME_DIR/bridge.cts"
echo "$BRIDGE_CTS" > "$SCRIPT_DIR/bridge_path.txt"

if [ -f "$BRIDGE_CTS" ]; then
  success "✓ Bridge script found: $BRIDGE_CTS"
else
  warn "WARNING: bridge.cts not found at $BRIDGE_CTS"
  warn "  Make sure it exists before using the plugin."
fi

# ─── Done ───

echo ""
echo -e "${BOLD}=== Installation complete ===${NC}"
echo ""
info "Activate the plugin by editing ~/.hermes/config.yaml:"
echo ""
echo "  memory:"
echo "    provider: memtensor"
echo ""
info "Or run:"
echo "  hermes config set memory.provider memtensor"
echo ""
info "Then start hermes normally. The bridge daemon and memory viewer"
info "will start automatically on first session."
echo ""
success "  Memory Viewer: http://127.0.0.1:${VIEWER_PORT:-18901}"
echo ""
info "Optional environment variables:"
echo "  MEMOS_PLUGIN_ROOT          - Override memos-local-plugin location"
echo "  MEMOS_STATE_DIR            - Override memory database location"
echo "  MEMOS_DAEMON_PORT          - Bridge daemon TCP port (default: 18992)"
echo "  MEMOS_VIEWER_PORT          - Memory viewer HTTP port (default: 18901)"
echo "  MEMOS_EMBEDDING_PROVIDER   - Embedding provider (default: local)"
echo "  MEMOS_EMBEDDING_API_KEY    - API key for embedding provider"
echo "  MEMOS_EMBEDDING_ENDPOINT   - Custom embedding endpoint"
