# Hermes Agent — Roadmap

> This document outlines the project direction, active development areas, and planned milestones.
> Last updated: 2026-05-28

---

## Current Release: v0.14.0 (2026.5.16)

**The Foundation Release** — Hermes installs and runs anywhere. This release established cross-platform stability, supply-chain hardening, and the plugin architecture.

### v0.14.0 Highlights

- Native Windows support (early beta)
- PyPI wheel distribution
- Supply-chain hardening (OSV scanning, tirith pre-exec checks)
- OpenAI-compatible local proxy for OAuth providers
- Cross-session Claude prompt cache
- 2 new platforms (LINE + SimpleX)
- Microsoft Graph foundation
- `/handoff` live
- `x_search`, `vision_analyze` passthrough
- LSP diagnostics
- `video_generate` plugin surface
- `computer_use` CUA driver
- 9 new skills, 12 P0 fixes, 50 P1 closures

---

## Active Development Areas

These are currently in progress or recently shipped with ongoing iteration.

### 🔌 Plugin Ecosystem

**Status:** Active development

The plugin system is the biggest architectural addition since the gateway. Recent milestones:

- `register_command()` on plugin context for slash commands
- Namespaced skill bundles from plugins
- Lifecycle hooks (`pre_llm`, `post_llm`, `session_start`, `session_end`)
- Plugin enable/disable commands

**Next steps:**
- [ ] Stabilize plugin API surface (no breaking changes for v1.0)
- [ ] Document plugin development guide
- [ ] Memory provider SDK standardization
- [ ] Plugin marketplace / registry

### 🧠 Honcho Integration

**Status:** Active development

Deep integration with Honcho for persistent, contextual memory:

- 5-tool surface (memory store, recall, search, context injection, session isolation)
- Cost safety guards
- Cross-profile observability
- Configurable observation mode

**Next steps:**
- [ ] Production memory provider certification
- [ ] Memory deduplication and relevance scoring
- [ ] Cross-session memory consolidation

### 🌐 Provider Expansion

**Status:** Rapid iteration

We've added native support for:

AWS Bedrock, Arcee AI, Xiaomi MiMo, z.ai/GLM, Kimi/Moonshot, MiniMax, xAI/Grok, Hugging Face, OpenCode, Kilo Code, Alibaba Cloud

**Next steps:**
- [ ] Unified provider testing framework
- [ ] Provider health monitoring dashboard
- [ ] Cost estimation accuracy (see [pricing accuracy architecture](docs/plans/2026-03-16-pricing-accuracy-architecture-design.md))

### 🛡️ Security Hardening

**Status:** Ongoing, enterprise-readiness focus

Recent investments:
- PKCE state/verifier separation for OAuth flows
- OSV malware checking for MCP
- JWT token and Discord mention redaction
- Supply-chain audit workflow

**Next steps:**
- [ ] Comprehensive audit logging
- [ ] SOC 2 alignment
- [ ] Role-based access control in gateway

### 🎤 Voice Mode

**Status:** Active development

- Continuous voice mode with VAD silence detection
- Push-to-talk support
- Groq STT, MiniMax TTS, Voxtral integration
- Real-time voice interaction pipeline

**Next steps:**
- [ ] Voice activity detection improvements
- [ ] Multi-language STT
- [ ] Custom wake word support

### 📊 Web Dashboard

**Status:** Maturing

- i18n (English + Chinese)
- Context window configuration
- Responsive mobile layout
- Health probes
- OAuth provider management

---

## Upcoming Milestones

### v0.15.0 — Plugin API Stabilization

_Planned: June 2026_

- Plugin API v1.0 (frozen interface, backwards compatibility guarantees)
- Memory provider SDK documentation
- Comprehensive test coverage for plugin lifecycle
- Developer onboarding documentation (this DEVELOPERS.md, API docs)
- Gateway platform adapter development guide

### v0.16.0 — Observability & Cost Transparency

_Planned: July 2026_

- Pricing accuracy architecture implementation (see design doc)
- Provider cost dashboard improvements
- Token usage analytics
- Audit logging framework
- Context compression improvements (smart collapse, anti-thrashing)

### v1.0.0 — API Stability & Documentation

_Planned: Q3 2026_

The v1.0 release signals that:
- All public APIs are stable and backwards-compatible
- Documentation is comprehensive and accurate
- Test coverage meets production standards
- Security review is complete
- Deployment guides exist for all supported platforms

**v1.0 blockers:**
- [ ] Complete plugin API documentation
- [ ] Comprehensive test coverage (>80% for core, >60% for gateway)
- [ ] Security audit pass
- [ ] CHANGELOG.md maintenance established
- [ ] All deprecated APIs removed or migrated
- [ ] Windows support out of beta

### v1.6.0 — Extensibility & Community

This milestone focuses on making Hermes the most extensible self-hosted AI agent:

- **Skill Marketplace** — Browse, install, and manage community skills
- **Plugin Registry** — Discover and install memory providers, tool integrations
- **Multi-tenant Isolation** — Application-level profile separation (beyond HERMES_HOME)
- **Hosted Deployment** — Docker Compose and Kubernetes manifests for production
- **Voice Pipeline v2** — Low-latency real-time voice with interruption support

---

## Long-Term Vision

### Autonomous Agents

Hermes is evolving from a chat-based assistant toward a **self-improving agent** that:
- Creates skills from experience during use
- Improves existing skills based on outcomes
- Runs reliably on any platform (CLI, gateway, embedded, hosted)
- Maintains persistent, contextual memory across sessions

### Skill Intelligence

The skill system will become increasingly intelligent:
- Automatic skill selection based on task analysis
- Skill composition (chaining skills for complex workflows)
- Skill quality scoring based on success/failure rates
- Community skill validation and certification

### Multi-Agent Coordination

Building on the existing `delegate_task` infrastructure:
- Agent-to-agent communication protocols
- Orchestrated multi-agent workflows
- Specialized agent spawning for domain tasks
- Shared memory and context between agents

---

## Contributing to the Roadmap

This roadmap is a living document. To propose changes:

1. **Open a GitHub Issue** with the `roadmap` label
2. **Start a GitHub Discussion** for architectural proposals
3. **Join Discord** at [discord.gg/NousResearch](https://discord.gg/NousResearch) for real-time discussion

### Priority Framework

We value contributions in this order:

1. **Bug fixes** — crashes, data loss, incorrect behavior
2. **Cross-platform compatibility** — Windows, macOS, different Linux distros
3. **Security hardening** — injection prevention, auth, sandboxing
4. **Performance & robustness** — retry logic, graceful degradation
5. **New skills** — broadly useful capabilities
6. **New tools** — only when skills can't do the job
7. **Documentation** — fixes, clarifications, guides

---

## Release Cadence

We target bi-weekly releases with patch releases as needed for critical fixes.

| Release | Date | Focus |
|---------|------|-------|
| v0.14.0 | 2026-05-16 | Foundation: cross-platform, plugin API, supply-chain |
| v0.13.0 | 2026-05-07 | Gateway fixes, empty-response loop fix |
| v0.12.0 | 2026-04-30 | Curator status, DeepSeek thinking |
| v0.11.0 | 2026-04-23 | Dashboard theming, cron toolsets |
| v0.10.0 | 2026-04-16 | Tool Gateway ungate |
| v0.9.0 | Earlier | Initial stable baseline |

---

## Metrics & Health

| Metric | Current | Target (v1.0) |
|--------|---------|---------------|
| Test coverage | ~40% | >80% core, >60% gateway |
| Platform adapters | 11+ | 15+ |
| Memory providers | 9 | 12+ |
| Bundled skills | 40+ | 50+ |
| Supported providers | 25+ | 30+ |
| Response time (p50) | — | <2s cold start |