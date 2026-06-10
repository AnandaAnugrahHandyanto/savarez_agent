#!/usr/bin/env bash
# Savarez Rebranding Script
set -euo pipefail

OLD_NAME="Savarez"
NEW_NAME="Savarez"
OLD_GITHUB="AnandaAnugrahHandyanto/savarez_agent"
NEW_GITHUB="AnandaAnugrahHandyanto/savarez_agent"

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$REPO_ROOT"

echo "=== Running branding: $OLD_NAME -> $NEW_NAME ==="

# List of all files to process
FILES=$(find . -type f \
  \( -name '*.py' -o -name '*.ts' -o -name '*.tsx' -o -name '*.js' \
     -o -name '*.cjs' -o -name '*.mjs' -o -name '*.md' -o -name '*.mdx' \
     -o -name '*.yaml' -o -name '*.yml' -o -name '*.nix' -o -name '*.sh' \
     -o -name '*.ps1' -o -name '*.toml' -o -name '*.json' \) \
  -not -path './.git/*' \
  -not -path '*/node_modules/*' \
  -not -path '*/.venv/*' \
  -not -path './hermes_cli/*' \
  -not -path './hermes_cli*' \
  -not -path './hermes_state.py' \
  -not -path './hermes_constants.py' \
  -not -path './hermes_logging.py' 2>/dev/null)

for f in $FILES; do
  # Replace GitHub URL
  sed -i "s|$OLD_GITHUB|$NEW_GITHUB|g" "$f"
  # Replace branding (word boundary to avoid internal names)
  sed -i "s|\b$OLD_NAME\b|$NEW_NAME|g" "$f"
done

echo "Branding complete. Check with: grep -rn '$OLD_NAME' --include='*.py' --include='*.md' . | grep -v 'hermes_cli'"
