#!/usr/bin/env bash
set -euo pipefail

SRC="${1:-$HOME/.hermes/plugins/episodic}"
DEST="${2:-$HOME/.hermes/hermes-agent/user-plugins/episodic}"

if [ ! -d "$SRC" ]; then
  echo "Source plugin directory not found: $SRC" >&2
  exit 1
fi

mkdir -p "$DEST"

rsync -a --delete \
  --exclude='__pycache__/' \
  --exclude='.pytest_cache/' \
  "$SRC/" "$DEST/"

echo "Mirrored episodic runtime plugin"
echo "  from: $SRC"
echo "    to: $DEST"

echo
echo "Tracked files:"
python3 - <<'PY' "$DEST"
from pathlib import Path
import sys
root = Path(sys.argv[1])
for p in sorted(root.rglob('*')):
    if p.is_dir():
        continue
    if '__pycache__' in p.parts or '.pytest_cache' in p.parts:
        continue
    print(p.relative_to(root))
PY

echo
echo "Next suggested steps:"
echo "  cd $HOME/.hermes/hermes-agent"
echo "  git diff --stat -- user-plugins/episodic"
echo "  git add user-plugins/episodic && git commit -m 'chore(memory): refresh episodic runtime mirror'"
