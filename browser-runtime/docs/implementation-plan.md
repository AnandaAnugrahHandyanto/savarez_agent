# Hermes Browser Runtime MVP Implementation Plan

**Goal:** локальный self-hosted browser runtime для одного пользователя и Hermes-агентов: API создаёт Chrome-сессию, отдаёт `cdp_ws_url`, сохраняет persistent profiles, поддерживает human takeover и артефакты.

**Architecture:** Rust binary with an `axum` HTTP API and a `clap` CLI. Core browser lifecycle is hidden behind `BrowserBackend`; MVP ships `LocalChromeBackend`, which starts a local Chrome/Chromium process with a dedicated `--user-data-dir` and discovers CDP via `/json/version`. Session state, profile locks, takeover tokens, artifacts and redacted event logs live locally under `~/.local/share/hermes-browser-runtime` by default.

**Tech stack:** `axum`, `tokio`, `serde`, `clap`, `tracing`, `reqwest`, `tokio-tungstenite`, `uuid`.

## Commit-like implementation steps

1. **Scaffold crate and contracts**
   - Create standalone Rust app in `browser-runtime/`.
   - Add API/request/response types, config defaults, redaction helpers.
   - Tests: serialization defaults, redaction, profile path safety.

2. **LocalChrome backend**
   - Implement `BrowserBackend` trait and `LocalChromeBackend`.
   - Launch Chrome/Chromium subprocess with `--remote-debugging-port`, `--user-data-dir`, headless/headful, viewport, and timeout.
   - Poll `/json/version` for `cdp_ws_url`.
   - Safe close on DELETE/drop.

3. **Profiles and locks**
   - Store profiles outside repo under mode `0700`.
   - Implement persistent vs ephemeral profile copy.
   - Prevent concurrent write sessions for the same persistent profile.

4. **HTTP API**
   - Implement sessions/profiles/artifacts endpoints.
   - Add optional bearer token auth.
   - Add safe JSON errors.

5. **Human takeover MVP**
   - Generate TTL takeover tokens.
   - Serve takeover web page with screenshot polling and release button.
   - Add CDP Input fallback endpoints for click/type/scroll.

6. **Artifacts and screenshots**
   - Implement CDP screenshot capture.
   - Persist screenshots, metadata, event JSONL and downloads dir.
   - Return artifact listing.

7. **CLI and docs**
   - Add `server`, `sessions`, and `profiles` CLI subcommands.
   - Document Hermes/Playwright flow, OAuth/login/payment/3DS takeover, SSH tunnel and troubleshooting.

8. **Quality gates**
   - `cargo fmt`
   - `cargo clippy -- -D warnings`
   - `cargo test`
   - Integration tests are present and run automatically when Chrome and Node Playwright are installed; otherwise they skip cleanly with a message.
