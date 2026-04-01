# Changelog

All notable changes to Hermes Agent will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **MCP Authentication Command** - Unified authentication flow for MCP servers
  - `hermes mcp auth` CLI command for authenticating OAuth and API key servers
  - `/mcp` and `/mcp auth` gateway commands (Telegram, Discord, WhatsApp, Slack, etc.)
  - Automatic detection of servers needing authentication
  - OAuth 2.1 PKCE browser flow for OAuth-configured servers
  - Secure API key prompting and storage in `~/.hermes/.env`
  - Comprehensive test suite (`tests/hermes_cli/test_mcp_auth.py`)
  - Full documentation (`docs/mcp-authentication.md`)

### Changed

- Improved MCP server management with authentication status visibility
- Enhanced gateway command dispatcher to handle `/mcp` commands

### Technical Details

- Added `cmd_mcp_auth()` to `hermes_cli/mcp_config.py`
- Added `_handle_mcp_command()` to `gateway/run.py`
- Added `auth` subcommand to `hermes mcp` CLI
- Token storage in `~/.hermes/mcp-tokens/` with secure file permissions
- Environment variable interpolation support for API key headers

## [0.4.0] - Previous Release

See [RELEASE_v0.4.0.md](./RELEASE_v0.4.0.md) for details.
