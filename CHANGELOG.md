# Changelog

All notable changes are logged here — for humans **and** agents.
Format follows [Keep a Changelog](https://keepachangelog.com/). Newest first.

## [Unreleased]

### Added

### Changed

### Fixed

- Fallback chain activation now honors `api_key_env`/`key_env` on fallback
  provider entries in `run_agent.py`'s inline `_try_activate_fallback`, matching
  the documented behavior (`fallback-providers.md`) and the refactored runtime
  helper. Without it, a custom free-tier fallback (e.g. Gemini) that referenced
  its key by env-var name resolved to no key and was silently skipped, so a
  primary 429 could exhaust the chain and surface a raw `API call failed after 3
  retries: HTTP 429` instead of self-healing onto a live provider.
