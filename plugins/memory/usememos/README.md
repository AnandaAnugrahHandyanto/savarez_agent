# Memos Memory Provider

Self-hosted [Memos](https://usememos.com) integration for user-owned memory — lightweight note service, no pip dependencies.

## Requirements

- A running Memos instance (self-hosted or [demo](https://demo.usememos.com))
- An API access token from Memos → Settings → Access Tokens

## Setup

```bash
hermes memory setup    # select "usememos"
```

Or manually:
```bash
hermes config set memory.provider usememos
echo "MEMOS_API_URL=https://memos.example.com" >> ~/.hermes/.env
echo "MEMOS_ACCESS_TOKEN=your-token" >> ~/.hermes/.env
```

## Config

Config file: `$HERMES_HOME/usememos.json`

| Key | Default | Description |
|-----|---------|-------------|
| `api_url` | *(required)* | Memos instance URL |
| `access_token` | *(required)* | API access token |
| `default_visibility` | `PRIVATE` | Default visibility for new memos |

## Tools

| Tool | Description |
|------|-------------|
| `memos_list` | List recent memos from the instance |
| `memos_search` | Search memos by content keyword |
| `memos_add` | Store a new memo (Markdown supported) |
