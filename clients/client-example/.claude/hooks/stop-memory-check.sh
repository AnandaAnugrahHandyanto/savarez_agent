#!/bin/bash
# Stop hook: Block if memory-worthy outputs were created but memory wasn't logged
PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"
TIMESTAMP_FILE="$PROJECT_DIR/.claude/hooks/.session-timestamp"

# If no session timestamp exists, allow stop
if [ ! -f "$TIMESTAMP_FILE" ]; then
  exit 0
fi

# Check if any output files were created/modified since session start
NEW_OUTPUTS=""

# Check created/ directory (RSAs, search-term CSVs, landing pages)
if [ -d "$PROJECT_DIR/created" ]; then
  CREATED_FILES=$(find "$PROJECT_DIR/created" -newer "$TIMESTAMP_FILE" -type f \
    -not -name '.DS_Store' -not -name '.gitkeep' 2>/dev/null)
  if [ -n "$CREATED_FILES" ]; then
    NEW_OUTPUTS="$CREATED_FILES"
  fi
fi

# Check context/analysis/ directory (analysis reports)
if [ -d "$PROJECT_DIR/context/analysis" ]; then
  ANALYSIS_FILES=$(find "$PROJECT_DIR/context/analysis" -newer "$TIMESTAMP_FILE" -type f \
    -not -name '.DS_Store' -not -name '.gitkeep' 2>/dev/null)
  if [ -n "$ANALYSIS_FILES" ]; then
    NEW_OUTPUTS="${NEW_OUTPUTS}${ANALYSIS_FILES}"
  fi
fi

# If no new outputs, allow stop
if [ -z "$NEW_OUTPUTS" ]; then
  exit 0
fi

# Outputs exist — check if today's memory file was updated this session
TODAY=$(date '+%Y-%m-%d')
MEMORY_FILE="$PROJECT_DIR/context/memory/${TODAY}.md"

if [ -f "$MEMORY_FILE" ] && [ "$MEMORY_FILE" -nt "$TIMESTAMP_FILE" ]; then
  # Memory was logged this session, allow stop
  exit 0
fi

# Count output files and build list
FILE_COUNT=$(echo "$NEW_OUTPUTS" | grep -c .)
FILE_LIST=$(echo "$NEW_OUTPUTS" | sed "s|$PROJECT_DIR/||g" | head -5)

# Block — memory not logged
jq -n --arg count "$FILE_COUNT" --arg today "$TODAY" --arg files "$FILE_LIST" '{
  decision: "block",
  reason: ("You created " + $count + " output file(s) this session but did not log to context/memory/" + $today + ".md. Per memory-logging rules, log the work before ending.\nFiles created:\n" + $files)
}'
