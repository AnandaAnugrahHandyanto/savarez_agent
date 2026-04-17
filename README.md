# Hermes Agent Installation Notes

## Summary
This document captures the installation fixes that were applied and the remaining manual configuration steps required for full Hermes functionality.

## Installation Fixes Performed
- Updated Hermes to latest available upstream commit:
  - `hermes update`
- Verified Hermes startup crash path is resolved:
  - Interactive launch/exit completed without traceback.
- Applied dependency remediation:
  - `npm audit fix --prefix ~/.hermes/hermes-agent`
  - `npm audit fix --prefix ~/.hermes/hermes-agent/scripts/whatsapp-bridge` (partial only; see open issues below)
- Initialized missing project components:
  - `git submodule update --init --recursive`
  - `hermes skills list` (initialized Skills Hub state)
- Installed missing dependency needed for submodule/backend setup:
  - `brew install git-lfs`
  - `git lfs install`
  - `~/.local/bin/uv pip install -e ~/.hermes/hermes-agent/tinker-atropos --python ~/.hermes/hermes-agent/venv/bin/python`
- Committed remediation lockfile changes:
  - Commit: `181af81f`
  - Files: `package-lock.json`, `scripts/whatsapp-bridge/package-lock.json`

## Final Verified State
- Hermes is installed and up to date.
- Core `hermes doctor` checks pass for install/runtime.
- `hermes` resolves correctly in login shells.
- Remaining warnings are configuration- or upstream-related (not core install blockers).

## Remaining Configuration Steps

### 1) Ensure `hermes` is available in new shells
Run:
```bash
source ~/.zshrc
command -v hermes
```
Expected:
```bash
~/.local/bin/hermes
```

### 2) Configure providers and API keys for full tool access
Run guided setup:
```bash
hermes setup
```
Or focused tools setup:
```bash
hermes setup tools
```
Add required keys in `~/.hermes/.env` as needed (example categories):
- OpenRouter/provider keys
- Web tool keys (Exa / Tavily / Firecrawl / Parallel)
- Any other provider keys required by your enabled toolsets

### 3) Optional authentication integrations
Configure only if needed:
- Nous Portal auth
- Google Gemini OAuth
- Codex CLI (only if you specifically need codex-cli-dependent flows)

### 4) WhatsApp bridge vulnerabilities (open upstream)
Current status:
- `scripts/whatsapp-bridge` still reports 3 critical advisories with no upstream-resolvable fix in the current dependency chain.

Recommended handling:
- Keep WhatsApp bridge disabled until upstream patches are released.
- Recheck periodically:
```bash
npm audit --prefix ~/.hermes/hermes-agent/scripts/whatsapp-bridge
npm audit fix --prefix ~/.hermes/hermes-agent/scripts/whatsapp-bridge
```

### 5) Optional GitHub token for Skills Hub rate limits
To avoid low API rate limits, set:
- `GITHUB_TOKEN` in `~/.hermes/.env`

## Post-Configuration Verification
After completing setup, run:
```bash
hermes --version
hermes doctor
```
If desired, perform a quick smoke test:
```bash
hermes
```
(then exit cleanly)
