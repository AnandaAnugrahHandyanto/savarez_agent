---
title: "Komorebi On Ubuntu 24 — Install and launch Komorebi live wallpaper engine on Ubuntu 24"
sidebar_label: "Komorebi On Ubuntu 24"
description: "Install and launch Komorebi live wallpaper engine on Ubuntu 24"
---

{/* This page is auto-generated from the skill's SKILL.md by website/scripts/generate-skill-docs.py. Edit the source SKILL.md, not this page. */}

# Komorebi On Ubuntu 24

Install and launch Komorebi live wallpaper engine on Ubuntu 24.04 by building from source, because old .deb releases depend on obsolete WebKitGTK 4.0 packages.

## Skill metadata

| | |
|---|---|
| Source | Bundled (installed by default) |
| Path | `skills/software-development/komorebi-on-ubuntu-24` |

## Reference: full SKILL.md

:::info
The following is the complete skill definition that Hermes loads when this skill is triggered. This is what the agent sees as instructions when the skill is active.
:::

# Komorebi on Ubuntu 24.04

Use this when:
- user wants Komorebi on Ubuntu 24.04 / Noble
- GitHub .deb install fails with `libwebkit2gtk-4.0-*` dependency errors
- you need to get Komorebi working on a modern Ubuntu desktop

## Why not use the old .deb
The `Komorebi-Fork` release `.deb` depends on:
- `libwebkit2gtk-4.0-37`
- `libwebkit2gtk-4.0-dev`

Those are not installable on Ubuntu 24.04, which ships WebKitGTK 4.1 instead.

## Working approach
Build from source from `https://github.com/Komorebi-Fork/komorebi`.

The current Meson source supports:
- `webkit2gtk-4.1` first
- falls back to `webkit2gtk-4.0`

## Steps

### 1) Install build/runtime dependencies
```bash
sudo apt-get install -y \
  gettext meson valac libgtk-3-dev libgee-0.8-dev \
  libclutter-gtk-1.0-dev libclutter-1.0-dev \
  libclutter-gst-3.0-dev libwebkit2gtk-4.1-dev
```

### 2) Clone source
```bash
git clone --depth 1 https://github.com/Komorebi-Fork/komorebi /tmp/komorebi-src
```

### 3) Build and install
```bash
cd /tmp/komorebi-src
meson setup build --prefix=/usr/local
# if build dir already exists:
meson setup build --reconfigure --prefix=/usr/local
ninja -C build
sudo ninja -C build install
```

### 4) Fix Python path issue after install
On Hermes/venv-driven shells, `/usr/bin/env python3` may resolve to a venv interpreter without GI bindings, and `/usr/bin/python3` may miss `/usr/local/lib/python3.11/site-packages`.

Patch both installed entrypoints so they inject the package path near the top:

```python
import sys
sys.path.insert(0, '/usr/local/lib/python3.11/site-packages')
```

Files:
- `/usr/local/bin/komorebi`
- `/usr/local/bin/komorebi-wallpaper-creator`

Ensure `import sys` comes before `sys.path.insert(...)`.

### 5) Verify
```bash
PATH=/usr/local/bin:/usr/bin:/bin /usr/local/bin/komorebi --help
PATH=/usr/local/bin:/usr/bin:/bin /usr/local/bin/komorebi-wallpaper-creator --help
```

Expected banners:
- `Welcome to komorebi`
- `Welcome to komorebi Wallpaper Creator`

### 6) Launch in the live X11 desktop session
For this environment:
- `DISPLAY=:0`
- `XAUTHORITY=/run/user/1000/gdm/Xauthority`

Launch:
```bash
export DISPLAY=:0 XAUTHORITY=/run/user/1000/gdm/Xauthority
export PATH=/usr/local/bin:/usr/bin:/bin
export PYTHONPATH=/usr/local/lib/python3.11/site-packages
nohup /usr/local/bin/komorebi >/tmp/komorebi.log 2>&1 &
nohup /usr/local/bin/komorebi-wallpaper-creator >/tmp/komorebi-creator.log 2>&1 &
```

Verify window exists:
```bash
DISPLAY=:0 XAUTHORITY=/run/user/1000/gdm/Xauthority wmctrl -lx | grep -i komorebi
```

## Notes for GIF wallpapers
Komorebi creator exposes `image`, `video`, and `web_page` wallpaper types. For an animated GIF workflow, convert the GIF to a video (for example MP4/WebM) and create a `video` wallpaper, or use the GUI creator to select an existing video file plus thumbnail.

## Pitfalls
- Old GitHub `.deb` releases fail on Ubuntu 24.04 due to WebKitGTK 4.0 dependency mismatch.
- Meson build also needs `gettext`; otherwise it fails at `Program 'msgfmt' not found`.
- In Hermes shells, entrypoint scripts may run under the wrong Python unless the package path is injected or PATH/PYTHONPATH are forced.
- GUI launch needs the real X11 session variables.
