#!/usr/bin/env bash
# Thin PR validation wrapper. It selects a repo-local validation command and
# delegates all pytest execution to scripts/run_tests.sh.

set -euo pipefail

usage() {
  cat <<'EOF'
Usage: scripts/validate_pr.sh [--scope auto|docs|scripts|tests|full] [--base REF] [--dry-run]

Scopes:
  auto     Infer the smallest validation scope from files changed against REF.
  docs     Syntax-check this wrapper for docs-only changes.
  scripts  Syntax-check this wrapper and run its contract tests.
  tests    Run this wrapper's contract tests.
  full     Run the full hermetic pytest suite through scripts/run_tests.sh.

Options:
  --base REF   Ref used for auto scope detection. Default: origin/main.
  --dry-run    Print commands without executing them.
  -h, --help   Show this help.

This wrapper is intentionally small. scripts/run_tests.sh owns virtualenv
selection, credential scrubbing, timezone/locale pins, and xdist worker count.
EOF
}

BASE_REF="origin/main"
SCOPE="auto"
DRY_RUN=0

while [ "$#" -gt 0 ]; do
  case "$1" in
    --base)
      if [ "$#" -lt 2 ]; then
        echo "error: --base requires a ref" >&2
        exit 2
      fi
      BASE_REF="$2"
      shift 2
      ;;
    --scope)
      if [ "$#" -lt 2 ]; then
        echo "error: --scope requires a value" >&2
        exit 2
      fi
      SCOPE="$2"
      shift 2
      ;;
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "error: unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

is_docs_file() {
  case "$1" in
    AGENTS.md|README.md|README.*.md|CONTRIBUTING.md|SECURITY.md|LICENSE|RELEASE*.md|docs/*|website/docs/*|website/sidebars.ts)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

infer_scope() {
  local base="$1"
  local merge_base
  local inferred="docs"
  if ! git rev-parse --verify "$base" >/dev/null 2>&1; then
    echo "full"
    return
  fi

  merge_base="$(git merge-base HEAD "$base")"
  changed=()
  while IFS= read -r file; do
    [ -n "$file" ] && changed+=("$file")
  done < <(git diff --name-only "$merge_base"...HEAD)
  while IFS= read -r file; do
    [ -n "$file" ] && changed+=("$file")
  done < <(git diff --name-only)
  while IFS= read -r file; do
    [ -n "$file" ] && changed+=("$file")
  done < <(git diff --name-only --cached)
  while IFS= read -r file; do
    [ -n "$file" ] && changed+=("$file")
  done < <(git ls-files --others --exclude-standard)

  if [ "${#changed[@]}" -eq 0 ]; then
    echo "docs"
    return
  fi

  local file
  for file in "${changed[@]}"; do
    case "$file" in
      scripts/validate_pr.sh|scripts/run_tests.sh)
        if [ "$inferred" != "full" ]; then
          inferred="scripts"
        fi
        ;;
      tests/test_validation_contract.py)
        if [ "$inferred" = "docs" ]; then
          inferred="tests"
        fi
        ;;
      *.py)
        inferred="full"
        ;;
      *)
        if ! is_docs_file "$file"; then
          inferred="full"
        fi
        ;;
    esac
  done

  echo "$inferred"
}

if [ "$SCOPE" = "auto" ]; then
  SCOPE="$(infer_scope "$BASE_REF")"
fi

case "$SCOPE" in
  docs)
    COMMANDS=("bash -n scripts/validate_pr.sh")
    ;;
  scripts)
    COMMANDS=(
      "bash -n scripts/validate_pr.sh"
      "bash -n scripts/run_tests.sh"
      "scripts/run_tests.sh tests/test_validation_contract.py"
    )
    ;;
  tests)
    COMMANDS=("scripts/run_tests.sh tests/test_validation_contract.py")
    ;;
  full)
    COMMANDS=("scripts/run_tests.sh")
    ;;
  *)
    echo "error: unknown scope: $SCOPE" >&2
    usage >&2
    exit 2
    ;;
esac

echo "Validation scope: $SCOPE"
for command in "${COMMANDS[@]}"; do
  if [ "$DRY_RUN" -eq 1 ]; then
    echo "+ $command"
  else
    echo "+ $command"
    bash -c "$command"
  fi
done
