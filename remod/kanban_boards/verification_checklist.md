# Jade Rebranding - Final Verification Checklist

## Git & Repo Hygiene
- [ ] git diff shows only intended string changes
- [ ] No forbidden files (run_agent.py, cli.py, gateway/run.py, main.py) in diff
- [ ] No import statements changed
- [ ] No Python logic modified

## String Coverage
- [ ] grep -r "Hermes" --include="*.py" --include="*.ts" --include="*.tsx" . returns only acceptable matches
- [ ] grep -r "NousResearch" --include="*.py" --include="*.md" . returns only acceptable matches
- [ ] grep -r "Nous Research" --include="*.py" --include="*.ts" --include="*.tsx" . returns only acceptable matches
- [ ] Review any remaining matches:
  - [ ] Python package names (keep as-is)
  - [ ] GitHub URLs (update or keep)
  - [ ] Config comments (update or keep)

## File-by-File Verification
- [ ] README.md updated
- [ ] All skill description files updated
- [ ] ui-tui/src/banner.ts LOGO_ART updated (optional - requires ASCII art work)
- [ ] session/ directory removed (was Session 1 docs)

## Forbidden Items (Must NOT Appear Modified)
- [ ] run_agent.py - no changes
- [ ] cli.py - no changes
- [ ] gateway/run.py - no changes
- [ ] hermes_cli/main.py - no changes

## Final Output Required
- [ ] List of intentionally-kept strings with explanations
- [ ] List of reviewed-but-left-intact strings
- [ ] One-line summary per modified file