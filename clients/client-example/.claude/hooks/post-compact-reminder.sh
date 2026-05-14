#!/bin/bash
# PostCompact: Re-inject critical context after compaction
PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"
CONTEXT=""

CONTEXT="Re-read these files to restore context:\n1. context/business.md — KPI targets, CPA/ROAS goals, constraints\n2. context/account-changelog.md — if making budget/bid recommendations"

# Inject last 3 days of memory logs
for OFFSET in 0 1 2; do
  DAY=$(date -v-${OFFSET}d '+%Y-%m-%d')
  MEMORY_FILE="$PROJECT_DIR/context/memory/${DAY}.md"
  if [ -f "$MEMORY_FILE" ]; then
    if [ "$OFFSET" -eq 0 ]; then
      LABEL="TODAY"
    elif [ "$OFFSET" -eq 1 ]; then
      LABEL="YESTERDAY"
    else
      LABEL="2 DAYS AGO"
    fi
    CONTEXT="${CONTEXT}\n\n--- ${LABEL}'S WORK LOG (${DAY}) ---\n$(cat "$MEMORY_FILE")\n--- END WORK LOG ---"
  fi
done

# Check changelog staleness
CHANGELOG="$PROJECT_DIR/context/account-changelog.md"
if [ -f "$CHANGELOG" ]; then
  FILE_MOD=$(stat -f %m "$CHANGELOG")
  NOW=$(date +%s)
  DAYS_OLD=$(( (NOW - FILE_MOD) / 86400 ))
  if [ "$DAYS_OLD" -gt 5 ]; then
    CONTEXT="${CONTEXT}\n\naccount-changelog.md is ${DAYS_OLD} days old. Offer the user to refresh with /account-changelog."
  fi
fi

# Output plain text (automatically added as context)
printf '%b' "$CONTEXT"
exit 0
