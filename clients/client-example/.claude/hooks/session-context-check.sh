#!/bin/bash
# SessionStart: Check context staleness + inject today's memory
PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"
CONTEXT=""

# Check business.md exists
if [ ! -f "$PROJECT_DIR/context/business.md" ]; then
  CONTEXT="${CONTEXT}context/business.md does not exist. Run /business-context to create it before proceeding.\n"
fi

# Check account-changelog.md staleness
CHANGELOG="$PROJECT_DIR/context/account-changelog.md"
if [ -f "$CHANGELOG" ]; then
  FILE_MOD=$(stat -f %m "$CHANGELOG")
  NOW=$(date +%s)
  DAYS_OLD=$(( (NOW - FILE_MOD) / 86400 ))
  if [ "$DAYS_OLD" -gt 5 ]; then
    LAST_UPDATED=$(date -r "$FILE_MOD" '+%Y-%m-%d')
    CONTEXT="${CONTEXT}account-changelog.md is ${DAYS_OLD} days old (last updated ${LAST_UPDATED}). Offer the user to refresh with /account-changelog before making recommendations.\n"
  fi
else
  CONTEXT="${CONTEXT}context/account-changelog.md does not exist. Offer the user to run /account-changelog.\n"
fi

# Check Google Ads data staleness
DATA_DIR="$PROJECT_DIR/context/google-ads/data"
if [ -d "$DATA_DIR" ]; then
  NEWEST_CSV=$(ls -t "$DATA_DIR"/*.csv 2>/dev/null | head -1)
  if [ -n "$NEWEST_CSV" ]; then
    CSV_MOD=$(stat -f %m "$NEWEST_CSV")
    NOW=$(date +%s)
    CSV_DAYS=$(( (NOW - CSV_MOD) / 86400 ))
    if [ "$CSV_DAYS" -ge 7 ]; then
      CSV_DATE=$(date -r "$CSV_MOD" '+%Y-%m-%d')
      CONTEXT="${CONTEXT}Google Ads data is ${CSV_DAYS} days old (last pull ${CSV_DATE}). Offer the user to refresh with /gads-context.\n"
    fi
  fi
fi

# Create session timestamp for Stop hook + ensure memory directory exists
mkdir -p "$PROJECT_DIR/context/memory"
touch "$PROJECT_DIR/.claude/hooks/.session-timestamp"

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
    CONTEXT="${CONTEXT}\n--- ${LABEL}'S WORK LOG (${DAY}) ---\n$(cat "$MEMORY_FILE")\n--- END WORK LOG ---\n"
  fi
done

# Add action directive if there are warnings
if [ -n "$CONTEXT" ]; then
  CONTEXT="${CONTEXT}\nACTION REQUIRED: Your FIRST message to the user MUST start by listing the stale context above and asking if they want you to run the refresh commands. Do not skip this — do not wait for the user to ask. Lead with the staleness warnings before anything else."
fi

# Output plain text (automatically added as context)
if [ -n "$CONTEXT" ]; then
  printf '%b' "$CONTEXT"
fi

exit 0
