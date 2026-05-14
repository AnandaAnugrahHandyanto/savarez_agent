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

install_hint() {
  cat <<EOF
[error] cargo-llvm-cov is not installed for this toolchain.
Install it with:
  PATH="${CARGO_HOME}/bin:\$PATH" CARGO_HOME="${CARGO_HOME}" RUSTUP_HOME="${RUSTUP_HOME}" rustup component add llvm-tools-preview
  PATH="${CARGO_HOME}/bin:\$PATH" CARGO_HOME="${CARGO_HOME}" RUSTUP_HOME="${RUSTUP_HOME}" cargo install cargo-llvm-cov --locked
EOF
}

if ! command -v cargo >/dev/null 2>&1; then
  echo "[error] cargo is not available on PATH=${PATH}" >&2
  exit 1
fi

if ! cargo llvm-cov --version >/dev/null 2>&1; then
  install_hint >&2
  exit 1
fi

cargo llvm-cov \
  --manifest-path "$manifest_path" \
  --all-features \
  --summary-only \
  --fail-under-lines 97 \
  "$@"
