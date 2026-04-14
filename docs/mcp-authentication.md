# MCP Authentication Command

## Overview

The `hermes mcp auth` command provides a unified authentication flow for MCP (Model Context Protocol) servers that require OAuth 2.1 PKCE or API key authentication. This command works across all Hermes channels: CLI, Telegram, Discord, WhatsApp, Slack, and more.

## Features

- **OAuth 2.1 PKCE Support**: Automatically initiates browser-based OAuth flows for servers configured with `auth: oauth`
- **API Key Management**: Prompts for and securely stores API keys in `~/.hermes/.env`
- **Multi-Channel Support**: Works identically in CLI and all gateway platforms
- **Intelligent Detection**: Automatically detects which servers need authentication
- **Secure Storage**: Uses file permissions (0600) for token files and masks sensitive values in output

## Usage

### CLI

```bash
# List MCP servers and see authentication status
hermes mcp auth

# Or use the quick command
hermes mcp
```

### Gateway (Telegram, Discord, etc.)

```
/mcp              # List servers with auth status
/mcp auth         # Authenticate all servers needing auth
```

## How It Works

### OAuth Authentication

For servers configured with `auth: oauth`:

1. Detects servers without stored OAuth tokens (`~/.hermes/mcp-tokens/<server>.json`)
2. Initiates the OAuth 2.1 PKCE flow using the MCP SDK's `OAuthClientProvider`
3. Opens a browser for user authorization
4. Exchanges authorization code for access and refresh tokens
5. Stores tokens securely for future use

### API Key Authentication

For servers with `Authorization` headers using environment variable interpolation:

1. Detects headers like `Authorization: Bearer ${MCP_SERVER_API_KEY}`
2. Checks if the environment variable is set
3. Prompts for the API key (hidden input)
4. Stores in `~/.hermes/.env` with the specified variable name

## Configuration Examples

### OAuth Server (Supabase MCP)

```yaml
mcp_servers:
  supabase:
    url: https://mcp.supabase.com/mcp
    auth: oauth
    timeout: 120
```

### API Key Server

```yaml
mcp_servers:
  my-api:
    url: https://api.example.com/mcp
    headers:
      Authorization: Bearer ${MCP_MY_API_API_KEY}
```

## Implementation Details

### File Structure

```
~/.hermes/
├── config.yaml          # MCP server configurations
├── .env                 # Environment variables (API keys)
└── mcp-tokens/          # OAuth tokens directory
    ├── server1.json     # OAuth tokens for server1
    ├── server1.client.json  # OAuth client registration
    └── ...
```

### Code Architecture

The implementation consists of three main components:

1. **CLI Command** (`hermes_cli/mcp_config.py`):
   - `cmd_mcp_auth()`: Main command dispatcher
   - `_do_oauth_auth()`: OAuth flow handler
   - `_do_header_auth()`: API key prompt handler

2. **Gateway Command** (`gateway/run.py`):
   - `_handle_mcp_command()`: Gateway dispatcher for `/mcp` and `/mcp auth`
   - Captures CLI command output for gateway response

3. **OAuth Infrastructure** (`tools/mcp_oauth.py`):
   - `build_oauth_auth()`: Builds httpx.Auth handler
   - `HermesTokenStorage`: File-backed token persistence
   - Browser callback handler for OAuth redirect

### Error Handling

- **Missing MCP SDK**: Graceful fallback with installation instructions
- **Network Errors**: Clear error messages for connection failures
- **User Cancellation**: Handles Ctrl+C and EOF gracefully
- **Invalid Config**: Validates server configuration before auth attempt

## Testing

The implementation includes comprehensive tests:

```bash
# Run all MCP auth tests
pytest tests/hermes_cli/test_mcp_auth.py -v

# Run integration tests
pytest tests/hermes_cli/test_mcp_auth.py -v -k "integration"

# Run edge case tests
pytest tests/hermes_cli/test_mcp_auth.py -v -k "edge"
```

## Security Considerations

1. **Token Storage**: OAuth tokens stored with 0600 permissions
2. **API Key Masking**: Sensitive values masked in output (e.g., `sk-***1234`)
3. **Environment Variables**: API keys stored in `.env` (not committed to git)
4. **Browser Security**: OAuth uses localhost callback (127.0.0.1)

## Troubleshooting

### OAuth Not Working

```bash
# Check if MCP SDK auth module is installed
python -c "from mcp.client.auth import OAuthClientProvider; print('OK')"

# If not, install it
pip install mcp[auth]
```

### API Key Not Being Prompted

The auth command only prompts for missing environment variables. If you've already set one, it won't ask again.

```bash
# Check current env vars
hermes mcp auth

# Clear an env var to re-prompt
unset MCP_MY_SERVER_API_KEY
# Or remove from ~/.hermes/.env
```

### Browser Not Opening

On headless/SSH environments, the OAuth URL is printed to console for manual opening.

## Future Enhancements

Potential improvements for future versions:

- [ ] Token refresh automation before expiry
- [ ] Support for additional OAuth providers (GitHub, Google, etc.)
- [ ] Interactive server selection (choose which to auth)
- [ ] Auth status in `hermes mcp list` output
- [ ] Token expiry warnings
- [ ] Bulk OAuth for multiple servers

## Related Documentation

- [MCP Server Management Skill](../skills/mcp/mcp-management/SKILL.md)
- [MCP OAuth Implementation](../tools/mcp_oauth.py)
- [MCP Tool Configuration](../hermes_cli/mcp_config.py)
