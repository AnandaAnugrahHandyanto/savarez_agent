---
title: "X11 Desktop Automation"
sidebar_label: "X11 Desktop Automation"
description: "Discover and use a live Ubuntu Xorg desktop session for GUI automation with xdotool, screenshots, and Xauthority wiring"
---

{/* This page is auto-generated from the skill's SKILL.md by website/scripts/generate-skill-docs.py. Edit the source SKILL.md, not this page. */}

# X11 Desktop Automation

Discover and use a live Ubuntu Xorg desktop session for GUI automation with xdotool, screenshots, and Xauthority wiring.

## Skill metadata

| | |
|---|---|
| Source | Bundled (installed by default) |
| Path | `skills/software-development/x11-desktop-automation` |

## Reference: full SKILL.md

:::info
The following is the complete skill definition that Hermes loads when this skill is triggered. This is what the agent sees as instructions when the skill is active.
:::

# X11 desktop automation on Ubuntu

Use this skill when:
- the user wants Hermes to control the real desktop GUI with mouse/keyboard actions
- browser automation is insufficient and you need access to the live local X11 session
- DISPLAY/XAUTHORITY are missing from the current shell and GUI commands fail until the session is discovered

## Goal

Attach Hermes terminal commands to the user's active Xorg desktop session, install basic GUI automation tooling, and verify that mouse/keyboard/screenshot operations work.

## Prerequisites

- Ubuntu or similar Linux desktop using **X11/Xorg** (Wayland is much more restrictive)
- local sudo available, preferably via `~/.config/mizuki/secrets.env` with `SUDO_PASSWORD`
- user is logged into an unlocked desktop session

## Core workflow

### 1) Detect the active graphical session

Use `loginctl` first:

```bash
loginctl list-sessions --no-legend
loginctl show-session <session_id> -p Name -p User -p Type -p State -p Active -p Remote -p Display -p Leader
```

Look for:
- `Type=x11`
- `Active=yes`
- the session `Leader` PID

### 2) Inspect the Xorg and session processes

When the current shell lacks `DISPLAY`, inspect processes to recover the correct Xauthority path:

```bash
ps -ef | grep -E 'Xorg|Xwayland|gdm|gnome-session' | grep -v grep
```

On Ubuntu/GDM, a reliable pattern is:
- Xorg process contains `-auth /run/user/1000/gdm/Xauthority`
- X socket exists as `/tmp/.X11-unix/X0`
- display is therefore typically `:0`

Example seen working:
- `DISPLAY=:0`
- `XAUTHORITY=/run/user/1000/gdm/Xauthority`

### 3) Install GUI automation tools

If missing, install:
- `xdotool` for mouse/keyboard/window control
- `xclip` for clipboard-based paste (more reliable than raw key-by-key typing)
- `scrot` for screenshots
- `imagemagick` for image conversion / `import`

Use the sudo-from-secrets-file workflow if needed.

### 4) Prefer clipboard paste over `xdotool type`

Raw `xdotool type` can drop characters when focus is unstable. In practice, browser automation was noticeably more reliable when using clipboard paste.

Recommended pattern:

```bash
DISPLAY=:0 XAUTHORITY=/run/user/1000/gdm/Xauthority bash -lc '
wid=$(xdotool search --onlyvisible --class brave-browser | head -n 1)
xdotool windowactivate --sync "$wid"
sleep 0.8
xdotool key --window "$wid" ctrl+l
sleep 0.3
printf %s "balatro" | xclip -selection clipboard
xdotool key --window "$wid" ctrl+v
sleep 0.3
xdotool key --window "$wid" Return
'
```

This worked better than `xdotool type --delay ...`, which previously turned an intended `balatro` search into `ba` due to focus/input timing issues.

### 5) Run commands against the desktop session explicitly

Prefix GUI commands with the discovered session variables:

```bash
DISPLAY=:0 XAUTHORITY=/run/user/1000/gdm/Xauthority xdotool getmouselocation --shell
DISPLAY=:0 XAUTHORITY=/run/user/1000/gdm/Xauthority xdotool getwindowfocus getwindowname
DISPLAY=:0 XAUTHORITY=/run/user/1000/gdm/Xauthority scrot -q 60 /tmp/mizuki-screen.png
```

Do **not** rely on the shell already having the right environment.

This applies to **launching GUI apps too**, not just controlling them after launch. A plain terminal launch like:

```bash
nohup brave-browser 'https://chromewebstore.google.com/...' >/tmp/brave.log 2>&1 &
```

can fail with errors like:

```text
Missing X server or $DISPLAY
The platform failed to initialize. Exiting.
```

Use:

```bash
DISPLAY=:0 XAUTHORITY=/run/user/1000/gdm/Xauthority nohup brave-browser 'https://chromewebstore.google.com/...' >/tmp/brave.log 2>&1 &
```

and verify the window appears with `wmctrl -lx | grep -i brave`.

### 6) Verify before claiming control works

Minimum verification checklist:
- `xdotool getmouselocation --shell` returns coordinates
- `xdotool getwindowfocus getwindowname` returns a real window title
- `scrot` successfully captures the desktop at least once

If all three succeed, Hermes has working X11 GUI automation.

### 7) Expect focus and screenshot quirks under GNOME/X11

Experiential findings from real use:
- `xdotool` may emit `XGetWindowProperty[_NET_ACTIVE_WINDOW] failed (code=1)` while actions still partially succeed.
- `xdotool getwindowfocus getwindowname` may return `gnome-shell` even when an app window exists.
- `scrot` can sometimes produce an all-black screenshot even though the session is unlocked and X11 control still works.
- `wmctrl -lx` and `xdotool search --class ...` are often more reliable than active-window queries for finding an app.

Because of this, do not rely on a single focus query or a single screenshot. Cross-check with:

```bash
DISPLAY=:0 XAUTHORITY=/run/user/1000/gdm/Xauthority wmctrl -lx | grep -i brave || true
DISPLAY=:0 XAUTHORITY=/run/user/1000/gdm/Xauthority xdotool search --class brave-browser || true
loginctl show-session <session_id> -p LockedHint
```

If interactive typing/search keeps failing inside an existing browser tab, a strong fallback is to open the target URL directly, e.g.:

```bash
DISPLAY=:0 XAUTHORITY=/run/user/1000/gdm/Xauthority nohup brave-browser "https://search.brave.com/search?q=balatro+soundtrack" >/tmp/mizuki-brave.log 2>&1 &
```

## Recommended helper commands

Mouse move and click:

```bash
DISPLAY=:0 XAUTHORITY=/run/user/1000/gdm/Xauthority xdotool mousemove 500 400 click 1
```

Type text:

```bash
DISPLAY=:0 XAUTHORITY=/run/user/1000/gdm/Xauthority xdotool type --delay 25 'hello world'
```

Send keys:

```bash
DISPLAY=:0 XAUTHORITY=/run/user/1000/gdm/Xauthority xdotool key ctrl+l
DISPLAY=:0 XAUTHORITY=/run/user/1000/gdm/Xauthority xdotool key super
```

Window inspection:

```bash
DISPLAY=:0 XAUTHORITY=/run/user/1000/gdm/Xauthority xwininfo -root -tree
DISPLAY=:0 XAUTHORITY=/run/user/1000/gdm/Xauthority xprop -root
```

## Pitfalls

- If the user is on **Wayland**, many xdotool flows will fail or be incomplete.
- `loginctl` may show blank `Display=` even when X11 is active; inspect Xorg processes and `/tmp/.X11-unix/`.
- The current shell may have `DISPLAY` unset even though the GUI session is alive; explicitly set `DISPLAY` and `XAUTHORITY` per command.
- Under GDM autologin on Ubuntu, `XAUTHORITY` may live at `/run/user/<uid>/gdm/Xauthority` rather than `~/.Xauthority`.
- Screen lock can block practical interaction even if screenshots and xdotool technically work.

## When to stop and ask the user

Ask the user to intervene if:
- they are not on X11/Xorg yet
- the screen is locked
- a target application requires human login or 2FA
- an action is destructive or irreversible

## Outcome

Once this skill is working, Hermes can combine:
- desktop mouse/keyboard control via X11
- screenshots and visual inspection
- terminal/file/sudo operations
- browser automation

for near full local-PC operator mode.
