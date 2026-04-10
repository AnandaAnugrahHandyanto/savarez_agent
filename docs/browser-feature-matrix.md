# Browser Feature Matrix: Hermes Agent vs Competitors

Generated: 2025-01-10 | Source: tools/browser_tool.py, tools/browser_camofox.py, tools/browser_providers/, tools/url_safety.py

Legend: ✅ Implemented | 🔶 Partial | ❌ Missing

## Competitors Reference

- **Claude Code** (Anthropic) — computer_use + browser via MCP
- **OpenAI Codex** — browser tool via ChatGPT Operator
- **Devin** (Cognition) — integrated browser in cloud sandbox
- **Manus** — cloud browser with vision-first approach
- **Browser Use** (open source) — Python Playwright agent library
- **Stagehand** (Browserbase) — TypeScript browser agent framework

---

## 1. CORE BROWSING

| Feature              | Hermes       | Claude Code | Codex/Operator | Devin  | Manus  | Browser Use | Stagehand |
|----------------------|--------------|-------------|----------------|--------|--------|-------------|-----------|
| Navigate to URL      | ✅           | ✅          | ✅             | ✅     | ✅     | ✅          | ✅        |
| Go back              | ✅           | ✅          | ✅             | ✅     | ✅     | ✅          | ✅        |
| Go forward           | ❌           | ✅          | ✅             | ✅     | 🔶     | ✅          | ✅        |
| Reload               | ❌           | ✅          | ✅             | ✅     | 🔶     | ✅          | ✅        |
| Multi-tab support    | ❌ (1)       | ❌          | ✅             | ✅     | ✅     | 🔶          | 🔶        |
| Frame/iframe support | 🔶 (2)      | ✅          | ✅             | ✅     | 🔶     | ✅          | ✅        |
| Scroll up/down       | ✅           | ✅          | ✅             | ✅     | ✅     | ✅          | ✅        |
| Scroll to element    | ❌           | ✅          | 🔶             | ✅     | 🔶     | ✅          | ✅        |

Notes:
(1) No browser_new_tab / browser_switch_tab tools. Camofox backend has tab management per-session but the tool layer exposes only one tab per task_id.
(2) agent-browser's accessibility tree may include iframe content depending on version; no explicit frame targeting tool.

---

## 2. INTERACTION

| Feature              | Hermes       | Claude Code | Codex/Operator | Devin  | Manus  | Browser Use | Stagehand |
|----------------------|--------------|-------------|----------------|--------|--------|-------------|-----------|
| Click by ref         | ✅           | ✅ (coord)  | ✅             | ✅     | ✅     | ✅          | ✅        |
| Type/fill text       | ✅           | ✅          | ✅             | ✅     | ✅     | ✅          | ✅        |
| Press keyboard key   | ✅           | ✅          | ✅             | ✅     | 🔶     | ✅          | ✅        |
| Hover                | ❌           | ✅ (coord)  | ✅             | ✅     | 🔶     | ✅          | ✅        |
| Select dropdown      | ❌ (3)       | ✅          | ✅             | ✅     | 🔶     | ✅          | ✅        |
| Drag & drop          | ❌           | ✅ (coord)  | ❌             | 🔶     | ❌     | ❌          | ❌        |
| File upload           | ❌           | 🔶          | ✅             | ✅     | ❌     | ✅          | 🔶        |
| File download         | ❌           | ❌          | ✅             | ✅     | ❌     | 🔶          | ❌        |
| Right-click          | ❌           | ✅ (coord)  | ❌             | 🔶     | ❌     | ❌          | ❌        |
| Double-click         | ❌           | ✅ (coord)  | ❌             | 🔶     | ❌     | ✅          | ❌        |

Notes:
(3) Can be worked around via browser_click on option refs or browser_press for arrow key navigation, but no dedicated select tool.

---

## 3. OBSERVATION

| Feature                  | Hermes       | Claude Code | Codex/Operator | Devin  | Manus  | Browser Use | Stagehand |
|--------------------------|--------------|-------------|----------------|--------|--------|-------------|-----------|
| Accessibility tree       | ✅           | ❌ (4)      | ❌             | ❌     | ❌     | ✅          | ✅        |
| DOM/HTML access          | 🔶 (5)      | ✅          | ✅             | ✅     | 🔶     | ✅          | ✅        |
| Screenshot               | ✅           | ✅          | ✅             | ✅     | ✅     | ✅          | ✅        |
| Full-page screenshot     | ✅           | 🔶          | ✅             | ✅     | 🔶     | ✅          | 🔶        |
| Annotated screenshot     | ✅ (6)       | ❌          | ❌             | ❌     | ❌     | ✅          | ❌        |
| Console output capture   | ✅           | ❌          | ❌             | 🔶     | ❌     | ❌          | ❌        |
| JS error capture         | ✅           | ❌          | ❌             | 🔶     | ❌     | ❌          | ❌        |
| JS evaluation (eval)     | ✅           | ❌          | ❌             | ✅     | ❌     | ✅          | ✅        |
| Network request capture  | ❌           | ❌          | ❌             | ✅     | ❌     | ❌          | ❌        |
| Image extraction         | ✅ (7)       | ❌          | ❌             | 🔶     | ❌     | ❌          | ❌        |

Notes:
(4) Claude uses vision (screenshots + coordinates) not accessibility tree.
(5) Via browser_console with expression param — can run arbitrary JS including document.querySelector(), document.body.innerHTML, etc.
(6) browser_vision --annotate overlays [N] labels on interactive elements mapping to @eN refs.
(7) browser_get_images extracts all page images via JS eval.

---

## 4. INTELLIGENCE

| Feature                        | Hermes       | Claude Code | Codex/Operator | Devin  | Manus  | Browser Use | Stagehand |
|--------------------------------|--------------|-------------|----------------|--------|--------|-------------|-----------|
| Snapshot truncation            | ✅           | N/A         | N/A            | N/A    | N/A    | ✅          | 🔶        |
| LLM-powered summarization     | ✅ (8)       | N/A         | N/A            | ✅     | ✅     | ❌          | ❌        |
| Task-aware content extraction  | ✅ (9)       | N/A         | N/A            | 🔶     | ✅     | ❌          | ❌        |
| Element ref system (@eN)      | ✅           | ❌ (coord)  | ❌             | ❌     | ❌     | ✅          | ✅        |
| Vision AI analysis             | ✅           | ✅ (native) | ✅ (native)    | ✅     | ✅     | ✅          | 🔶        |
| Bot detection warnings         | ✅ (10)      | ❌          | ❌             | ✅     | ✅     | 🔶          | ❌        |
| Compact vs full snapshot modes | ✅           | N/A         | N/A            | N/A    | N/A    | 🔶          | ❌        |
| Auto-snapshot after navigate   | ✅ (11)      | N/A         | N/A            | N/A    | N/A    | ❌          | ❌        |
| Secret redaction in snapshots  | ✅ (12)      | ❌          | ❌             | ❌     | ❌     | ❌          | ❌        |

Notes:
(8) Uses auxiliary LLM (configurable model via AUXILIARY_WEB_EXTRACT_MODEL) to summarize snapshots > 8000 chars.
(9) _extract_relevant_content() accepts user_task param for task-focused extraction.
(10) Detects common blocked-page patterns in title ("captcha", "cloudflare", etc.) and adds bot_detection_warning to response.
(11) browser_navigate returns a compact snapshot inline, saving one tool call.
(12) agent.redact.redact_sensitive_text applied to snapshot text before sending to auxiliary LLMs and in vision analysis output.

---

## 5. SESSION & BACKENDS

| Feature                      | Hermes       | Claude Code | Codex/Operator | Devin  | Manus  | Browser Use | Stagehand |
|------------------------------|--------------|-------------|----------------|--------|--------|-------------|-----------|
| Local headless Chromium      | ✅           | ❌          | ❌             | ❌     | ❌     | ✅          | ✅        |
| Browserbase cloud            | ✅           | ❌          | ❌             | ❌     | ❌     | ❌          | ✅ (native)|
| Browser Use cloud            | ✅           | ❌          | ❌             | ❌     | ❌     | ✅ (native) | ❌        |
| Firecrawl cloud              | ✅           | ❌          | ❌             | ❌     | ❌     | ❌          | ❌        |
| Camofox anti-detection (FF)  | ✅ (13)      | ❌          | ❌             | ❌     | ❌     | ❌          | ❌        |
| Custom CDP endpoint          | ✅ (14)      | ❌          | ❌             | ❌     | ❌     | ✅          | ✅        |
| Task-scoped session isolation| ✅           | ✅          | ✅             | ✅     | ✅     | ✅          | ✅        |
| Session persistence/reuse    | 🔶 (15)     | ❌          | ✅             | ✅     | ✅     | ❌          | 🔶        |
| Session recording (WebM)     | ✅ (16)      | ❌          | ❌             | ✅     | ✅     | ❌          | ✅ (BB)   |
| VNC live view                | 🔶 (17)     | ❌          | ❌             | ✅     | ✅     | ❌          | ❌        |
| Residential proxies          | ✅ (18)      | ❌          | ❌             | ✅     | ✅     | ✅          | ✅        |
| Advanced stealth mode        | ✅ (19)      | ❌          | ❌             | ✅     | ✅     | 🔶          | ✅        |
| Managed Nous gateway         | ✅           | N/A         | N/A            | N/A    | N/A    | N/A         | N/A       |
| KeepAlive reconnection       | ✅           | ❌          | ❌             | ✅     | ❌     | ❌          | ✅        |
| Configurable session timeout | ✅           | ❌          | ❌             | ✅     | 🔶     | 🔶          | ✅        |

Notes:
(13) Camofox = Firefox fork (Camoufox) with C++ fingerprint spoofing. Self-hosted via npm/Docker. REST API backend with full tool parity.
(14) BROWSER_CDP_URL env var or /browser connect command. Auto-discovers websocket via /json/version if given HTTP endpoint.
(15) Camofox managed_persistence preserves browser profiles (cookies, storage) across tasks. Standard mode sessions are ephemeral per-task.
(16) browser.record_sessions config flag auto-records to ~/.hermes/browser_recordings/ as WebM, with 72h auto-cleanup.
(17) VNC available only with Camofox backend when it exposes a VNC port. URL returned in navigate response.
(18) Via Browserbase (BROWSERBASE_PROXIES) and Browser Use (proxyCountryCode). Falls back gracefully on free plans (402 handling).
(19) Via Browserbase BROWSERBASE_ADVANCED_STEALTH (custom Chromium, Scale plan required).

---

## 6. SECURITY

| Feature                        | Hermes       | Claude Code | Codex/Operator | Devin  | Manus  | Browser Use | Stagehand |
|--------------------------------|--------------|-------------|----------------|--------|--------|-------------|-----------|
| SSRF protection (private IPs)  | ✅ (20)      | ✅          | ✅             | ✅     | 🔶     | ❌          | ❌        |
| Post-redirect SSRF check       | ✅           | 🔶          | 🔶             | 🔶     | ❌     | ❌          | ❌        |
| URL validation                 | ✅           | ✅          | ✅             | ✅     | 🔶     | ❌          | ❌        |
| Cloud metadata blocking        | ✅ (21)      | ✅          | ✅             | ✅     | 🔶     | ❌          | ❌        |
| CGNAT range blocking           | ✅           | 🔶          | 🔶             | 🔶     | ❌     | ❌          | ❌        |
| Secret exfiltration prevention | ✅ (22)      | ❌          | ❌             | ❌     | ❌     | ❌          | ❌        |
| Secret redaction in output     | ✅ (23)      | ❌          | ❌             | ❌     | ❌     | ❌          | ❌        |
| Website blocklist policy       | ✅ (24)      | ❌          | ❌             | ❌     | ❌     | ❌          | ❌        |
| Configurable private URL allow | ✅           | ❌          | ❌             | ❌     | ❌     | ❌          | ❌        |
| Local-backend SSRF bypass      | ✅ (25)      | N/A         | N/A            | N/A    | N/A    | N/A         | N/A       |
| DNS resolution fail-closed     | ✅           | 🔶          | 🔶             | 🔶     | ❌     | ❌          | ❌        |
| Sandboxed execution            | 🔶 (26)     | ✅          | ✅             | ✅     | ✅     | ❌          | ❌        |

Notes:
(20) url_safety.py: resolves hostname → IP, checks is_private/is_loopback/is_link_local/is_reserved/is_multicast/is_unspecified + CGNAT 100.64.0.0/10. Fail-closed on DNS errors.
(21) Blocks metadata.google.internal and metadata.goog by hostname. RFC 1918, link-local (169.254.x.x) blocked by IP check.
(22) browser_navigate checks URLs against _PREFIX_RE pattern for API key prefixes (sk-ant-, ghp_, etc.) + URL-decoded variants to catch %2D encoding tricks.
(23) redact_sensitive_text() applied to: snapshot text before auxiliary LLM summarization, vision LLM output, annotation context.
(24) website_policy.py: user-managed domain blocklist in config.yaml + shared list files. Glob pattern matching. Cached with 30s TTL.
(25) SSRF checks skipped for local backends (Camofox, headless Chromium without cloud provider) since user already has full local network access via terminal.
(26) Cloud providers run in isolated cloud VMs. Local mode runs on user's machine — no additional sandboxing beyond OS-level process isolation.

---

## 7. PERFORMANCE

| Feature                      | Hermes       | Claude Code | Codex/Operator | Devin  | Manus  | Browser Use | Stagehand |
|------------------------------|--------------|-------------|----------------|--------|--------|-------------|-----------|
| Snapshot caching             | ❌           | N/A         | N/A            | 🔶     | 🔶     | ❌          | ❌        |
| Command batching             | ❌           | ❌          | ❌             | 🔶     | ❌     | ❌          | ❌        |
| Parallel sessions            | ✅ (27)      | ❌          | ❌             | ✅     | ✅     | ✅          | ✅        |
| Engine choice (Chromium/FF)  | ✅ (28)      | ❌          | ❌             | ❌     | ❌     | ✅          | ❌        |
| Pixel-based scroll (1 call)  | ✅ (29)      | N/A         | N/A            | N/A    | N/A    | N/A         | N/A       |
| Per-task socket isolation    | ✅           | N/A         | N/A            | N/A    | N/A    | N/A         | N/A       |
| Screenshot auto-cleanup      | ✅ (30)      | ❌          | ❌             | 🔶     | 🔶     | ❌          | ❌        |
| Recording auto-cleanup       | ✅           | N/A         | N/A            | 🔶     | 🔶     | N/A         | N/A       |
| Config-driven timeout        | ✅           | ❌          | ❌             | 🔶     | 🔶     | 🔶          | 🔶        |

Notes:
(27) Thread-safe: _cleanup_lock protects session state. Subagents run concurrent browser tasks via ThreadPoolExecutor with per-task socket directories.
(28) Local Chromium via agent-browser, Firefox via Camofox backend. Configurable per deployment.
(29) browser_scroll sends a single 500px scroll command instead of 5 subprocess calls.
(30) Screenshots cleaned after 24h (throttled to 1 scan/hour). Recordings cleaned after 72h.

---

## 8. ERROR HANDLING

| Feature                        | Hermes       | Claude Code | Codex/Operator | Devin  | Manus  | Browser Use | Stagehand |
|--------------------------------|--------------|-------------|----------------|--------|--------|-------------|-----------|
| Command timeout management     | ✅ (31)      | ✅          | ✅             | ✅     | ✅     | 🔶          | 🔶        |
| Configurable command timeout   | ✅           | ❌          | ❌             | 🔶     | ❌     | 🔶          | 🔶        |
| Inactivity session cleanup     | ✅ (32)      | ❌          | ❌             | ✅     | ✅     | ❌          | ❌        |
| Emergency cleanup (atexit)     | ✅           | ❌          | ❌             | ✅     | 🔶     | ❌          | ❌        |
| 402 graceful fallback          | ✅ (33)      | N/A         | N/A            | N/A    | N/A    | N/A         | N/A       |
| Auto-retry on failure          | ❌           | ❌          | ❌             | ✅     | 🔶     | ❌          | ❌        |
| Fallback backend               | ❌ (34)      | ❌          | ❌             | ❌     | ❌     | ❌          | ❌        |
| Empty output detection         | ✅           | ❌          | ❌             | 🔶     | ❌     | ❌          | ❌        |
| Screenshot path recovery       | ✅ (35)      | ❌          | ❌             | ❌     | ❌     | ❌          | ❌        |
| Daemon PID cleanup             | ✅           | N/A         | N/A            | N/A    | N/A    | N/A         | N/A       |
| Interrupted task detection     | ✅           | ❌          | ❌             | 🔶     | ❌     | ❌          | ❌        |
| macOS socket path workaround   | ✅ (36)      | N/A         | N/A            | N/A    | N/A    | N/A         | N/A       |

Notes:
(31) DEFAULT_COMMAND_TIMEOUT=30s, configurable via browser.command_timeout in config.yaml. Floor at 5s. Navigate uses max(timeout, 60).
(32) Background thread checks every 30s, cleans sessions inactive > 5min (BROWSER_INACTIVITY_TIMEOUT env var).
(33) Browserbase 402 responses: retries without keepAlive first, then without proxies. Logs warnings about degraded capabilities.
(34) No automatic fallback from cloud to local or vice versa. Could be a future enhancement.
(35) _extract_screenshot_path_from_text recovers file path from non-JSON agent-browser output.
(36) macOS TMPDIR (/var/folders/...) exceeds 104-byte AF_UNIX limit; _socket_safe_tmpdir() redirects to /tmp on Darwin.

---

## HERMES STRENGTHS (Unique or Best-in-Class)

1. **Multi-backend architecture**: 5 backends (local Chromium, Browserbase, Browser Use, Firecrawl, Camofox) behind one tool interface — no other agent has this
2. **Accessibility-tree-first design**: Text-based page representation works with any LLM (no vision required), with vision as an upgrade path
3. **Secret exfiltration prevention**: Blocks API keys in URLs + redacts secrets in snapshot/vision outputs — unique among all competitors
4. **SSRF protection depth**: Pre-nav + post-redirect IP checks, CGNAT blocking, cloud metadata hostname blocking, fail-closed DNS
5. **Website policy system**: User-configurable domain blocklist with glob patterns and shared list files
6. **Auto-snapshot-after-navigate**: Saves one tool call per navigation (significant over multi-page workflows)
7. **Camofox anti-detection**: Firefox-based fingerprint spoofing alternative — unique among agent frameworks
8. **Console + JS eval**: browser_console gives DevTools-level access (log capture + arbitrary JS execution)

## HERMES GAPS (Missing Features to Address)

1. **No forward navigation** — browser_forward not implemented
2. **No reload** — browser_reload not implemented  
3. **No multi-tab management** — single tab per task, no tab switching/listing tools
4. **No hover tool** — no browser_hover for tooltip/dropdown trigger
5. **No dedicated select tool** — dropdown selection requires click/arrow workarounds
6. **No file upload/download** — cannot interact with file inputs or capture downloads
7. **No drag & drop** — cannot perform drag-and-drop operations
8. **No scroll-to-element** — can only scroll directionally, not to a specific element
9. **No network request interception** — cannot capture/modify HTTP requests
10. **No snapshot caching** — repeated snapshots re-invoke agent-browser subprocess
11. **No command batching** — each tool call is a separate subprocess invocation
12. **No auto-retry** — failed commands are not retried automatically
13. **No fallback backend** — if chosen backend fails, no automatic failover
