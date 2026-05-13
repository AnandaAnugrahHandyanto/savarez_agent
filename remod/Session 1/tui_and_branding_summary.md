# TUI Analysis & Branding Strings Search

## STEP 5: TUI System Analysis

### Architecture
The TUI is a full-screen terminal UI built with `@hermes/ink` (a React-based Ink fork). It communicates with the Python backend via newline-delimited JSON-RPC over stdio (GatewayClient).

### Key Files

**entry.tsx** (88 lines) — TUI entry point:
- Checks for TTY availability
- Resets terminal modes (mouse/focus/paste)
- Creates GatewayClient and starts it
- Sets up graceful exit (cleanup, onError, onSignal callbacks)
- Starts memory monitor for OOM prevention
- Dynamically imports `@hermes/ink` and `<App>` component
- Renders `<App gw={gw} />` via `ink.render()` with `exitOnCtrlC: false`

**app.tsx** (25 lines) — Main app component:
- Uses `useMainApp(gw)` hook to extract: appActions, appComposer, appProgress, appStatus, appTranscript
- Wraps `<AppLayout>` in `<GatewayProvider>`
- AppLayout receives all sub-apps as props

**Components** (22 files in components/):
- `appLayout.tsx` — Layout orchestrator arranging all panels
- `branding.tsx` — Banner, session panel, skills, toolsets, update info
- `theme.ts` — Theme interface, DARK_THEME, LIGHT_THEME, fromSkin() bridge
- `appChrome.tsx` — Status bar, title bar, thinking indicator
- `appOverlays.tsx` — Overlay management
- `thinking.tsx` — Thinking/animation states
- `messageLine.tsx` — Message rendering
- `streamingAssistant.tsx` + `streamingMarkdown.tsx` — Streaming response display
- `sessionPicker.tsx` — Session resume UI
- `modelPicker.tsx` — Model switching UI
- `prompts.tsx` — User prompt/approval dialogs
- `maskedPrompt.tsx` — Password/secret input
- `textInput.tsx` — Text input component
- `helpHint.tsx` — Help hints
- `agentsOverlay.tsx` — Sub-agent overlay
- `fpsOverlay.tsx` — Performance overlay
- `todoPanel.tsx` — Todo list panel
- `queuedMessages.tsx` — Message queue display
- `skillsHub.tsx` — Skills hub UI
- `overlayControls.tsx` — Overlay control utilities
- `themed.tsx` — Themed text wrapper
- `markdown.tsx` — Markdown rendering

**theme.ts** (589 lines) — Theme system:
- `ThemeColors` interface: 34 color properties (primary, accent, border, text, muted, completion*, status*, diff*, shellDollar, etc.)
- `ThemeBrand` interface: name, icon, prompt, welcome, goodbye, tool, helpHeader
- `Theme` interface: color + brand + bannerLogo + bannerHero
- `DARK_THEME`: Gold/amber dark palette (default)
- `LIGHT_THEME`: Darker gold on light background
- `fromSkin()`: Converts Python skin engine values to TUI Theme, with 25+ skin→theme mappings
- `detectLightMode()`: Auto-detects light terminal via env vars, COLORFGBG, TERM_PROGRAM
- ANSI normalization for terminals without truecolor support

**banner.ts** (93 lines) — ASCII art:
- `LOGO_ART`: "HERMES AGENT" in 6-line ASCII block letters (98 chars wide)
- `CADUCEUS_ART`: 15-line caduceus symbol in Braille/Unicode characters
- `logo()`: Returns colorized logo lines (custom via skin or built-in)
- `caduceus()`: Returns colorized hero art lines
- Color gradients: 4-step progression through primary → accent → border → muted

---

## STEP 6: Branding Strings Search

### TUI-side Branding (theme.ts — BRAND constant):
```
name:       "Hermes Agent"          # Agent display name
icon:       "⚕"                     # Caduceus icon
prompt:     "❯"                     # Input prompt
welcome:    "Type your message or /help for commands."
goodbye:    "Goodbye! ⚕"
tool:       "┊"                     # Tool output prefix
helpHeader: "(^_^)? Commands"
```

### TUI-side User-facing Strings (branding.tsx):
```
Line 52: "{t.brand.icon} NOUS HERMES"               — Banner text
Line 56: "{t.brand.icon} Nous Research · Messenger of the Digital Gods"  — Tagline
Line 227: "· Nous Research"                          — Session panel attribution
```

### Python-side Skin Engine (skin_engine.py):
- **6 built-in skins**: default, ares, mono, slate, daylight, warm-lightmode
- **Default branding**:
  - agent_name: "Hermes Agent"
  - welcome: "Welcome to Hermes Agent! Type your message or /help for commands."
  - goodbye: "Goodbye! ⚕"
  - response_label: " ⚕ Hermes "
  - prompt_symbol: "❯"
  - help_header: "(^_^)? Available Commands"
- Each skin can override all branding strings + colors + spinner faces/verbs/wings + tool prefix + logo/hero art
- `SkinConfig` dataclass with: name, description, colors dict, spinner dict, branding dict, tool_prefix, tool_emojis, banner_logo, banner_hero

### Python-side Default Soul (default_soul.py):
```
"You are Hermes Agent, an intelligent AI assistant created by Nous Research. "
```

### Python-side Banner (banner.py):
```
Line 130: _UPSTREAM_REPO_URL = "https://github.com/NousResearch/hermes-agent.git"
Line 287: _RELEASE_URL_BASE = "https://github.com/NousResearch/hermes-agent/releases/tag"
Line 472: "Nous Research" tag in banner
```

### Other Python-side "Hermes" References (95+ total matches):
- `hermes_cli/status.py:97` — "⚕ Hermes Agent Status"
- `hermes_cli/setup.py:180` — "⚕ Hermes Setup"
- `hermes_cli/setup.py:3133` — "⚕ Hermes Agent Setup Wizard"
- `hermes_cli/tools_config.py:2393` — "⚕ Hermes Tool Configuration"
- `hermes_cli/uninstall.py:455` — "⚕ Hermes Agent Uninstaller"
- `hermes_cli/gateway.py:3171` — "⚕ Hermes Gateway Starting..."
- `hermes_cli/gateway.py:4776` — "⚕ Gateway Setup"
- `hermes_cli/config.py:4707` — "⚕ Hermes Configuration"
- `hermes_cli/main.py:7340` — "⚕ Updating Hermes Agent..."
- `hermes_cli/claw.py:351/577` — "⚕ Hermes — OpenClaw Migration/Cleanup"
- `hermes_cli/slack_cli.py:112-117` — Default bot name "Hermes"
- `hermes_cli/main.py:9629` — Bot display name default "Hermes"
- `hermes_cli/providers.py:453` — source="hermes" for provider profiles
- `hermes_cli/models.py:906` — "Nous Portal (Nous Research subscription)"
- `hermes_cli/model_switch.py:54-66` — Nous Research Hermes model detection logic
- `hermes_cli/skills_hub.py:356/574` — "Nous Research" attribution for skills
- `hermes_cli/tips.py:335` — "Skills from trusted repos (NousResearch)"
- `hermes_cli/auth.py:3249` — "hermes" check in model names
- `hermes_cli/_parser.py:90` — prog="hermes"

### Key Branding Locations Summary for Customization to "Jade":
1. **TUI Theme**: `theme.ts` — BRAND constant (lines 239-247), DARK_THEME (lines 257-305), LIGHT_THEME (lines 310-350)
2. **TUI Banner**: `branding.tsx` — lines 52, 56, 227
3. **TUI ASCII Art**: `banner.ts` — LOGO_ART (lines 46-53), CADUCEUS_ART (lines 55-71)
4. **Skin Engine**: `skin_engine.py` — _BUILTIN_SKINS (lines 164-436), SkinConfig dataclass, fromSkin() → TUI bridge
5. **Default Soul**: `default_soul.py` — DEFAULT_SOUL_MD (line 4)
6. **Python Banner**: `banner.py` — Nous Research references, HTTPS github URLs
7. **CLI Outputs**: status.py, setup.py, tools_config.py, uninstall.py, gateway.py, config.py, main.py, claw.py, slack_cli.py, skills_hub.py, model_switch.py
8. **Provider Registration**: providers.py, models.py — Nous Research provider entries
9. **Auth/Update URLs**: auth.py, main.py — github.com/NousResearch/hermes-agent references
10. **CLI Parser**: _parser.py — prog="hermes"

### Next Steps Required
With permission, proceed to:
- STEP 7: Read gateway structure and Discord platform adapter (gateway/ directory)
- STEP 8: Compile final summary with all findings for Jade customization
