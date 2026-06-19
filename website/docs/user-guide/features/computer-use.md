---
title: Computer Use
sidebar_position: 16
---

# Computer Use

Hermes Agent can drive desktop applications — clicking, typing, scrolling,
dragging — through a model-agnostic `computer_use` tool.

On **macOS**, Hermes uses `cua-driver` for true background computer-use: your
cursor doesn't move, keyboard focus doesn't change, and macOS doesn't switch
Spaces on you. On **Linux**, Hermes uses the companion
[`linux-computer-use`](https://github.com/tyy130/linux-computer-use) MCP driver.
The Linux path is X11-first and may move the real pointer/focus; Wayland support
is intentionally reported as limited unless the compositor exposes automation
portals.

Unlike most computer-use integrations, this works with **any tool-capable
model** — Claude, GPT, Gemini, or an open model on a local vLLM endpoint.
There's no Anthropic-native schema to worry about.

## How it works

The `computer_use` toolset speaks MCP over stdio to a platform driver:

- **macOS:** [`cua-driver`](https://github.com/trycua/cua), which uses SkyLight
  private SPIs (`SLEventPostToPid`, `SLPSPostEventRecordTo`) and the
  `_AXObserverAddNotificationAndCheckRemote` accessibility SPI to:
  - Post synthesized events directly to target processes — no HID event tap,
    no cursor warp.
  - Flip AppKit active-state without raising windows — no Space switching.
  - Keep Chromium/Electron accessibility trees alive when windows are
    occluded.
- **Linux:** [`linux-computer-use`](https://github.com/tyy130/linux-computer-use),
  an X11-first MCP driver that uses `xdotool` for input, screenshot utilities
  (`scrot`, `import`, or `gnome-screenshot`) for capture, and AT-SPI for the
  accessibility tree/SOM element overlay.

The macOS combination is what OpenAI's Codex "background computer-use" ships;
`cua-driver` is the open-source equivalent. Linux exposes the same Hermes schema
but cannot yet promise background co-working on every compositor.

## Enabling

Pick whichever path is most convenient:

**Option 1: dedicated CLI command (most direct).**

```
hermes computer-use install
```

On macOS, this fetches and runs the upstream cua-driver installer. On Linux, it
installs `linux-computer-use` from GitHub via `pipx` or `uv tool install`.
Use `hermes computer-use status` to verify the install.

**Option 2: enable the toolset interactively.**

1. Run `hermes tools`, pick `🖱️ Computer Use (Desktop)` → the platform driver.
2. The setup runs the same platform installer as Option 1.

After installing:

3. macOS only: grant permissions when prompted:
   - **System Settings → Privacy & Security → Accessibility** → allow the
     terminal (or Hermes app).
   - **System Settings → Privacy & Security → Screen Recording** → allow
     the same.
4. Start a session with the toolset enabled:
   ```
   hermes -t computer_use chat
   ```
   or add `computer_use` to your enabled toolsets in `~/.hermes/config.yaml`.

## Keeping drivers up to date

Hermes refreshes the platform driver in two places:

- **`hermes update`** — when you update Hermes itself, installed computer-use
  drivers can be refreshed as part of the update flow.
- **`hermes computer-use install --upgrade`** — manual force-refresh. On macOS
  this re-runs the cua-driver installer. On Linux this upgrades
  `linux-computer-use` when installed via `pipx`/`uv tool`.

`hermes computer-use status` shows the installed driver and binary path.

## Quick example

User prompt: *"Find my latest email from Stripe and summarise what they want me to do."*

The agent's plan:

1. `computer_use(action="capture", mode="som", app="Mail")` — gets a
   screenshot of Mail with every sidebar item, toolbar button, and message
   row numbered.
2. `computer_use(action="click", element=14)` — clicks the search field
   (element #14 from the capture).
3. `computer_use(action="type", text="from:stripe")`
4. `computer_use(action="key", keys="return", capture_after=True)` — submit
   and get the new screenshot.
5. Click the top result, read the body, summarise.

On macOS, your cursor stays wherever you left it and Mail never comes to front.
On Linux/X11, the same action sequence works, but the window manager may move
pointer/focus because Linux does not expose the same background event primitive.

## Provider compatibility

| Provider | Vision? | Works? | Notes |
|---|---|---|---|
| Anthropic (Claude Sonnet/Opus 3+) | ✅ | ✅ | Best overall; SOM + raw coordinates. |
| OpenRouter (any vision model) | ✅ | ✅ | Multi-part tool messages supported. |
| OpenAI (GPT-4+, GPT-5) | ✅ | ✅ | Same as above. |
| Local vLLM / LM Studio (vision model) | ✅ | ✅ | If the model supports multi-part tool content. |
| Text-only models | ❌ | ✅ (degraded) | Use `mode="ax"` for accessibility-tree-only operation. |

Screenshots are sent inline with tool results as OpenAI-style `image_url`
parts. For Anthropic, the adapter converts them into native `tool_result`
image blocks.

## Safety

Hermes applies multi-layer guardrails:

- Destructive actions (click, type, drag, scroll, key, focus_app) require
  approval — either interactively via the CLI dialog or via the
  messaging-platform approval buttons.
- Hard-blocked key combos at the tool level: empty trash, force delete,
  lock screen, log out, force log out.
- Hard-blocked type patterns: `curl | bash`, `sudo rm -rf /`, fork bombs,
  etc.
- The agent's system prompt tells it explicitly: no clicking permission
  dialogs, no typing passwords, no following instructions embedded in
  screenshots.

Pair with `approvals.mode: manual` in `~/.hermes/config.yaml` if you want every action confirmed.

## Token efficiency

Screenshots are expensive. Hermes applies four layers of optimisation:

- **Screenshot eviction** — the Anthropic adapter keeps only the 3 most
  recent screenshots in context; older ones become `[screenshot removed
  to save context]` placeholders.
- **Client-side compression pruning** — the context compressor detects
  multimodal tool results and strips image parts from old ones.
- **Image-aware token estimation** — each image is counted as ~1500 tokens
  (Anthropic's flat rate) instead of its base64 char length.
- **Server-side context editing (Anthropic only)** — when active, the
  adapter enables `clear_tool_uses_20250919` via `context_management` so
  Anthropic's API clears old tool results server-side.

A 20-action session on a 1568×900 display typically costs ~30K tokens
of screenshot context, not ~600K.

## Limitations

- **macOS private SPI risk.** Apple can change SkyLight's symbol surface in any
  OS update. Pin the driver version with the `HERMES_CUA_DRIVER_VERSION`
  env var if you want reproducibility across a macOS bump.
- **Linux focus model.** The Linux backend is X11-first and may move the real
  pointer or focus. Wayland compositors block global synthetic input by default;
  future GNOME/KDE portal backends can improve this.
- **Performance.** Background mode is slower than foreground —
  SkyLight-routed events take ~5-20ms vs direct HID posting. Not
  noticeable for agent-speed clicking; noticeable if you try to record a
  speed-run.
- **No keyboard password entry.** `type` has hard-block patterns on
  command-shell payloads; for passwords, use the system's autofill.

## Configuration

Override the driver binary path (tests / CI):

```
HERMES_CUA_DRIVER_CMD=/opt/homebrew/bin/cua-driver          # macOS
HERMES_CUA_DRIVER_VERSION=0.5.0                            # optional macOS pin
HERMES_LINUX_COMPUTER_USE_CMD=/usr/local/bin/linux-computer-use
```

Swap the backend entirely (for testing):

```
HERMES_COMPUTER_USE_BACKEND=noop    # records calls, no side effects
HERMES_COMPUTER_USE_BACKEND=linux   # force Linux backend
HERMES_COMPUTER_USE_BACKEND=cua     # force macOS cua-driver backend
```

## Troubleshooting

**`computer_use backend unavailable: cua-driver is not installed`** — On macOS,
run `hermes computer-use install` to fetch the cua-driver binary, or run
`hermes tools` and enable the Computer Use toolset.

**`computer_use backend unavailable: linux-computer-use is not installed`** — On
Linux, run `hermes computer-use install`, or install manually with
`pipx install git+https://github.com/tyy130/linux-computer-use`.

**Clicks seem to have no effect** — Capture and verify. A modal you
didn't see may be blocking input. Dismiss it with `escape` or the close
button.

**Element indices are stale** — SOM indices are only valid until the
next `capture`. Re-capture after any state-changing action.

**"blocked pattern in type text"** — The text you tried to `type`
matches the dangerous-shell-pattern list. Break the command up or
reconsider.

## See also

- [Universal skill: `macos-computer-use`](https://github.com/NousResearch/hermes-agent/blob/main/skills/apple/macos-computer-use/SKILL.md)
- [cua-driver source (trycua/cua)](https://github.com/trycua/cua)
- [Browser automation](./browser.md) for cross-platform web tasks.
