# Scott Hermes Desktop source-of-truth capture â€” 20260609T115108Z

This folder records the laptop-installed Hermes Desktop baseline and Scott-specific restoration materials.

## Installed Desktop

- Desktop package version: $desktopVersion
- Repo HEAD at capture: $(git rev-parse --short HEAD)
- Branch: $(git branch --show-current)
- Packaged executable: `apps/desktop/release/win-unpacked/Hermes.exe`
- Executable SHA-256: `f89e2a2b437f44027dcbfb644812b0463cc40f256191b74e7141fd5ffe1bb139`
- Executable mtime UTC: `2026-06-08T00:29:47.9609778Z`

## Scott-specific behavior that must survive restore/update

1. Apollo custom provider keeps current Microsoft Teams session headers merged into OpenAI client requests for bidirectional session sharing.
2. Desktop session/model hot-swap preserves named provider slugs (custom:apollo, custom:omega) and resolves provider base URLs without blanking model.base_url.
3. Desktop home/profile is locked to scott-omega-profile with only that profile exposed in the Desktop UI when present.
4. scott-omega-profile is seeded with Scott-specific SOUL, USER/MEMORY files, README, SCOTT_PROFILE_CONTEXT, FACTS, and holographic memory_store.db.
5. Holographic memory is enabled via profile config; database evidence is summarized without dumping private fact text.

## Files

- manifest.json â€” machine-readable capture manifest.
- custom-source.patch â€” replayable source patch for the relevant custom code changes.
- config.redacted.yaml â€” redacted profile config proving provider/header/memory shape without secrets.
- profile-config-summary.json â€” parsed non-secret config summary.
- holographic-memory-db-summary.json â€” table/count summary only.
- profile-* â€” restore source files copied from scott-omega-profile.
- git-*, diff-* â€” git evidence at capture time.

Do not commit raw API keys, session keys, auth files, or unredacted state.db content.