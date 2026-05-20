#!/usr/bin/env bash
# Basic host health check for disk and memory pressure.
#
# Environment overrides:
#   DISK_USAGE_THRESHOLD=90    # fail if any checked filesystem is >= this % used
#   MEMORY_USAGE_THRESHOLD=90  # fail if memory usage is >= this % used

set -euo pipefail

DISK_USAGE_THRESHOLD="${DISK_USAGE_THRESHOLD:-90}"
MEMORY_USAGE_THRESHOLD="${MEMORY_USAGE_THRESHOLD:-90}"

failures=0

is_integer() {
  [[ "$1" =~ ^[0-9]+$ ]]
}

validate_threshold() {
  local name="$1"
  local value="$2"

  if ! is_integer "$value" || (( value < 1 || value > 100 )); then
    echo "ERROR: $name must be an integer between 1 and 100 (got '$value')" >&2
    exit 2
  fi
}

check_disk_space() {
  echo "Disk space:"

  local df_output
  if ! df_output="$(df -P -x tmpfs -x devtmpfs -x squashfs)"; then
    echo "  FAIL unable to read filesystem usage"
    failures=$((failures + 1))
    return
  fi

  # Skip pseudo/temporary filesystems so the signal is focused on real mounted
  # storage. Parse from the right so mount points with spaces are preserved.
  while IFS= read -r line; do
    [[ "$line" == Filesystem* ]] && continue
    [[ -z "$line" ]] && continue

    local source used_pct target used
    target="${line##* }"
    line="${line% "$target"}"
    used_pct="${line##* }"
    line="${line% "$used_pct"}"
    source="${line%% *}"
    used="${used_pct%%%}"

    if (( used >= DISK_USAGE_THRESHOLD )); then
      echo "  FAIL ${target}: ${used}% used (${source})"
      failures=$((failures + 1))
    else
      echo "  OK   ${target}: ${used}% used (${source})"
    fi
  done <<< "$df_output"
}

check_memory() {
  echo "Memory:"

  local mem_total_kb mem_available_kb mem_used_pct
  mem_total_kb="$(awk '/^MemTotal:/ {print $2}' /proc/meminfo)"
  mem_available_kb="$(awk '/^MemAvailable:/ {print $2}' /proc/meminfo)"

  if [[ -z "$mem_total_kb" || -z "$mem_available_kb" || "$mem_total_kb" -eq 0 ]]; then
    echo "  FAIL unable to read memory information from /proc/meminfo"
    failures=$((failures + 1))
    return
  fi

  mem_used_pct=$(( (mem_total_kb - mem_available_kb) * 100 / mem_total_kb ))

  if (( mem_used_pct >= MEMORY_USAGE_THRESHOLD )); then
    echo "  FAIL ${mem_used_pct}% used (threshold: ${MEMORY_USAGE_THRESHOLD}%)"
    failures=$((failures + 1))
  else
    echo "  OK   ${mem_used_pct}% used (threshold: ${MEMORY_USAGE_THRESHOLD}%)"
  fi
}

main() {
  validate_threshold "DISK_USAGE_THRESHOLD" "$DISK_USAGE_THRESHOLD"
  validate_threshold "MEMORY_USAGE_THRESHOLD" "$MEMORY_USAGE_THRESHOLD"

  echo "Healthcheck thresholds: disk >= ${DISK_USAGE_THRESHOLD}%, memory >= ${MEMORY_USAGE_THRESHOLD}%"
  check_disk_space
  check_memory

  if (( failures > 0 )); then
    echo "Healthcheck failed: ${failures} issue(s) found"
    exit 1
  fi

  echo "Healthcheck passed"
}

main "$@"
