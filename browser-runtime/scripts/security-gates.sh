#!/usr/bin/env bash
set -euo pipefail

real_home="$(getent passwd "$(id -un)" | cut -d: -f6)"
export CARGO_HOME="${CARGO_HOME:-${real_home}/.cargo}"
export RUSTUP_HOME="${RUSTUP_HOME:-${real_home}/.rustup}"
export RUSTUP_TOOLCHAIN="${RUSTUP_TOOLCHAIN:-stable}"
export PATH="${CARGO_HOME}/bin:${PATH}"

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
crate_dir="$(cd "$script_dir/.." && pwd)"
manifest_path="$crate_dir/Cargo.toml"
lock_path="$crate_dir/Cargo.lock"
deny_config="$crate_dir/deny.toml"

run_or_skip() {
  local binary="$1"
  local install_hint="$2"
  shift 2

  if command -v "$binary" >/dev/null 2>&1; then
    "$@"
  else
    echo "[skip] $binary is not installed"
    echo "       install with: $install_hint"
  fi
}

run_or_skip cargo-audit "cargo install cargo-audit" \
  cargo-audit audit --file "$lock_path"

run_or_skip cargo-deny "cargo install cargo-deny" \
  cargo-deny --manifest-path "$manifest_path" check --config "$deny_config"
