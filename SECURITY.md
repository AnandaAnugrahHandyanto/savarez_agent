# Security Policy — Hermes Agent

## Reporting Vulnerabilities

If you discover a security vulnerability, please report it responsibly:

1. **Do NOT open a public issue.**
2. Email the maintainers directly or use GitHub's private vulnerability reporting.
3. Include steps to reproduce, impact assessment, and any suggested fix.

We aim to respond within 48 hours and provide a fix within 7 days for critical issues.

---

## Security Architecture

Hermes Agent implements defense-in-depth with multiple independent security layers:

### 1. Command Approval System (`tools/approval.py`)

All terminal commands pass through a multi-stage security pipeline:

- **Pattern-based detection**: 40+ regex patterns match dangerous operations (recursive delete, disk format, fork bomb, privilege escalation, shell bypass techniques).
- **Unicode normalization**: Commands are NFKC-normalized and ANSI-stripped before matching to defeat fullwidth character and escape sequence obfuscation.
- **Tirith deep scanning** (`tools/tirith_security.py`): Optional binary scanner for content-level threats (homograph URLs, pipe-to-interpreter, terminal injection).
- **Per-session approval state**: Thread-safe approval tracking with permanent allowlist persistence.
- **Smart approval**: Optional LLM-based risk assessment for borderline commands.

### 2. File Operation Guards (`tools/file_tools.py`)

- **Sensitive path protection**: Blocks writes to `/etc/`, `/boot/`, `/usr/lib/systemd/`, Docker socket.
- **Symlink traversal protection**: Resolves symlinks before write and re-validates against sensitive paths.
- **Hermes config protection**: Blocks direct writes to `~/.hermes/config.yaml` and `~/.hermes/.env` to prevent persistence attacks.
- **Device path blocklist**: Prevents reads from `/dev/zero`, `/dev/random`, etc. that would hang the process.
- **Binary file guard**: Blocks reads of binary files by extension.
- **Character count limit**: Prevents oversized reads from consuming the context window.
- **Secret redaction**: All file content is redacted via `agent/redact.py` before entering the conversation.

### 3. SSRF Protection (`tools/url_safety.py`)

- **Pre-flight DNS resolution**: All URLs are resolved to IP addresses before requests.
- **Private IP blocklist**: Blocks RFC 1918, loopback, link-local, CGNAT (100.64.0.0/10), multicast, and reserved ranges.
- **Cloud metadata blocking**: Explicit hostname blocklist for `metadata.google.internal`, `metadata.goog`.
- **Fail-closed**: DNS resolution failures and unexpected errors block the request.

**Known limitations** (documented in source):
- DNS rebinding (TOCTOU) is not fully mitigable at pre-flight level.
- Redirect-based bypass is mitigated by httpx event hooks in downstream tools.

### 4. Skills Guard (`tools/skills_guard.py`)

External skills pass through static analysis before installation:

- **80+ threat patterns**: Regex-based detection across 12 categories (exfiltration, injection, destructive, persistence, network, obfuscation, supply chain, privilege escalation, credential exposure, mining).
- **Trust-level policy**: `builtin` > `trusted` (openai/anthropics repos) > `community`. Community skills with any findings are blocked.
- **Structural checks**: File count limits, size limits, binary file detection, symlink escape detection, invisible Unicode character detection.
- **Quarantine**: Downloaded skills are scanned in a quarantine directory before moving to the active skills directory.

### 5. Environment Variable Isolation

- **Provider env stripping** (`tools/environments/local.py`): All API keys, tokens, and credentials are stripped from subprocess environments by default.
- **Passthrough blocklist** (`tools/env_passthrough.py`): Even when skills declare `required_environment_variables`, sensitive patterns (API keys, tokens, passwords) are blocked from passthrough registration.
- **Credential file containment** (`tools/credential_files.py`): Path traversal and absolute path injection are rejected for credential file mounts.

### 6. Sandbox Isolation (`tools/code_execution_tool.py`)

- **Tool allowlist**: Execute_code sandbox can only call 7 predefined tools.
- **Call limit**: Maximum tool calls per execution (default: 50).
- **Blocked terminal params**: `background`, `pty`, `watch_patterns` stripped from sandbox terminal calls.
- **Timeout**: 5-minute default execution timeout.
- **Output limits**: 50KB stdout, 10KB stderr.

### 7. Delegation Controls (`tools/delegate_tool.py`)

- **Depth limit**: Maximum delegation depth of 2 (no grandchild agents).
- **Tool restriction**: Blocked tools (`delegate_task`, `clarify`, `memory`, `send_message`, `execute_code`) cannot be inherited by children.
- **Toolset intersection**: Children can only access tools the parent has — never gain new ones.

### 8. Secret Redaction (`agent/redact.py`)

- **30+ prefix patterns**: API keys from OpenAI, Anthropic, GitHub, Slack, Google, AWS, Stripe, etc.
- **Structural patterns**: ENV assignments, JSON fields, Authorization headers, database connection strings, private key blocks.
- **Import-time lock**: Redaction enablement is snapshotted at import time — runtime env mutations cannot disable it.

---

## Configuration Hardening Checklist

1. **Never run with `HERMES_YOLO_MODE=true` in production** — it bypasses all command approval.
2. **Use remote backends (Docker/SSH)** for untrusted workloads — the agent cannot access host API keys.
3. **Set `GATEWAY_ALLOW_ALL_USERS=false`** (default) — require explicit user allowlists.
4. **Enable Tirith** (`security.tirith_enabled: true`) for deep command scanning.
5. **Review `terminal.env_passthrough`** — only list variables that genuinely need to reach sandboxes.
6. **Use profiles** for multi-bot deployments — each profile gets isolated state, keys, and sessions.
7. **Set `security.website_blocklist.enabled: true`** to restrict agent web access to approved domains.

---

## Dependency Security

- **YAML**: All config loading uses `yaml.safe_load()` — no arbitrary code execution via YAML.
- **No `eval()`** in production code paths.
- **No `pickle.loads()`** on untrusted data — the one usage (Matrix E2EE crypto store) is HMAC-verified and type-checked.
- **Tirith binary**: Auto-installed with SHA-256 checksum verification; cosign provenance when available.
