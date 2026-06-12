---
title: "Hearthstone On Ubuntu — Install Battle"
sidebar_label: "Hearthstone On Ubuntu"
description: "Install Battle"
---

{/* This page is auto-generated from the skill's SKILL.md by website/scripts/generate-skill-docs.py. Edit the source SKILL.md, not this page. */}

# Hearthstone On Ubuntu

Install Battle.net and Hearthstone on Ubuntu using Wine/Lutris, including mirror troubleshooting and 32-bit Wine setup.

## Skill metadata

| | |
|---|---|
| Source | Bundled (installed by default) |
| Path | `skills/gaming/hearthstone-on-ubuntu` |

## Reference: full SKILL.md

:::info
The following is the complete skill definition that Hermes loads when this skill is triggered. This is what the agent sees as instructions when the skill is active.
:::

# Hearthstone on Ubuntu

Use this skill when:
- the user wants to play Hearthstone on a Linux/Ubuntu desktop
- Battle.net must be installed through Wine/Lutris
- apt mirrors are slow, flaky, or partially synced

## Goal

Get a working Battle.net installation path on Ubuntu so the user can install and launch Hearthstone.

## Key findings

1. **Hearthstone has no native Linux client**. Use **Battle.net via Wine/Lutris**.
2. On Ubuntu 24.04, Battle.net may fail under Wine with errors about `syswow64`, `wow64 mode`, or missing `ntdll.dll` unless **i386 multiarch + `wine32:i386`** are installed.
3. `lutris` may install its executable in **`/usr/games/lutris`**, which may not be on PATH in non-interactive sessions. If `command -v lutris` fails after install, check `/usr/games/lutris` or `dpkg -L lutris`.
4. If `apt-get update` appears hung on a regional mirror (example: `iq.archive.ubuntu.com`), switching to **`http://archive.ubuntu.com/ubuntu/`** can help.
5. `apt-get update` can fail transiently with **"File has unexpected size" / "Mirror sync in progress?"** on `dep11`/Components metadata. That does not always mean all package indexes are unusable; check `apt-cache policy` before assuming installs are impossible.
6. Even if a refresh partially fails, `apt-cache policy wine32:i386` may still show a valid candidate from existing indexes, and install can proceed.
7. A non-trivial failure mode on older Intel iGPU / Ubuntu 24.04 setups is **Battle.net Update Agent launch failure** even after Wine, Lutris, and `wine32:i386` are installed. The useful log signature is:
   - `Failed Caller authorization due to signature for 'Battle.net-Setup.exe'(32)`
   This showed up with both Ubuntu Wine and GE-Proton/Lutris Wine and correlates with the Battle.net popup *"We're having trouble launching the Battle.net Update Agent"*.
8. Installing **`winbind`** removes `ntlm_auth was not found` warnings, but it did **not** fix the Battle.net Update Agent signature/authorization failure in this environment.
9. On Ubuntu 24.04 desktop setups running **Wayland** (`XDG_SESSION_TYPE=wayland`), Lutris/Wine installer windows may fail to appear correctly even when the process is running. Symptoms include hidden or never-shown installer dialogs and Battle.net/Agent windows that technically exist but do not become usable.
10. Lutris-managed installation can also fail silently: X11 windows may exist but remain **unmapped** (`Map State: IsUnMapped`). In that case the user legitimately sees nothing even though Wine/Agent windows exist in X11.
11. To verify hidden-window behavior, `xwininfo -root -tree` is more useful than process checks alone. If you see windows like `"Agent"` or `"C:\\ProgramData\\Battle.net\\Agent\\Agent.9414\\Agent.exe"` with `Map State: IsUnMapped`, the problem is now GUI/window mapping, not missing packages.
12. A practical workaround is to switch the desktop session from **Wayland to Xorg** before retrying Lutris/Battle.net. On Ubuntu/GDM, the session chooser may be hidden when the user uses **PIN login**; they may need to switch to **password login** first before a gear/session selector appears.
13. On some Ubuntu 24.04 systems with **GDM auto-login enabled**, the login-screen gear/session chooser may never appear reliably. If `/usr/share/xsessions/ubuntu-xorg.desktop` exists, you can force Xorg for the next login by editing `/etc/gdm3/custom.conf` and uncommenting:
   - `WaylandEnable=false`
   Then log out/reboot and verify with `echo $XDG_SESSION_TYPE` expecting `x11`.
14. A Lutris Battle.net install may create a **broken Wine prefix** where `~/Games/battlenet/drive_c/windows/system32/kernel32.dll` and `syswow64/kernel32.dll` are missing. Symptom:
   - `wine: could not load kernel32.dll, status c0000135`
   In that case, delete the broken prefix, recreate it manually with the same GE/Lutris Wine runner using `wineboot --init`, verify both `kernel32.dll` files exist, then relaunch `Battle.net-Setup.exe` manually with that runner.
15. When recovering from the broken-prefix case, direct manual launch can work even if the Lutris scripted install failed. Use the GE runner’s `wine` binary with:
   - `DISPLAY=:0`
   - `XAUTHORITY=$HOME/.Xauthority`
   - `XDG_RUNTIME_DIR=/run/user/$(id -u)`
   - `WINEPREFIX=$HOME/Games/battlenet`
   Then confirm the setup window exists with `xwininfo -root -tree | grep -Ei 'Battle.net Setup|Installing Battle.net'`.
16. The temporary Lutris cache copy of the installer may disappear after a failed or canceled install. If `~/.cache/lutris/installer/battlenet/setup/Battle.net-Setup.exe` is missing, relaunch from the persistent download instead:
   - `~/Games/Installers/Battle.net-Setup.exe`
17. After relaunch, the visible installer may be a **very small** top-level window (example observed: about `408x108`) titled `Battle.net Setup`. The user can easily think it vanished. Use:
   - `wmctrl -ia <window_id>` to raise/focus it
   - `xwininfo -root -tree | grep -Ei 'Battle.net Setup|Agent'`
   to verify it still exists.
18. If the setup dialog disappears but `Agent.exe` remains, do not assume installation is over. Check whether the remaining `Agent` and `conhost.exe` windows are mapped or unmapped with `xwininfo -id <id>`, and guide the user to `Alt+Tab` specifically to `Battle.net Setup` before retrying more invasive fixes.
19. Battle.net's own logs under `~/Games/battlenet/drive_c/ProgramData/Battle.net/Setup/bna_2/Logs/` are worth reading directly. In this environment the visible popup *"We're having trouble launching the Battle.net Update Agent"* (`BLZBNTBTS0000005C`) corresponded to log lines like:
   - `Agent init returned status code=401`
   - `Failed to communicate with Agent after launch`
   - `Agent launch exception ... error=2`
   That means the failure is in Battle.net Agent startup/handshake, not just a generic Wine crash.
20. A concrete fix from Lutris' Battle.net troubleshooting docs helped here: ensure the machine hostname resolves to `127.0.0.1`, not only `127.0.1.1`. Verify with:
   - `hostname`
   - `getent hosts localhost $(hostname) $(hostname).localdomain`
   If needed, update `/etc/hosts` so the first line is effectively:
   - `127.0.0.1 localhost <hostname>.localdomain <hostname>`
   and remove the separate `127.0.1.1 <hostname>` line.
21. If the Update Agent error persists after fixing hostname resolution, back up and remove the Wine prefix's `C:\ProgramData\Battle.net` directory, then relaunch `Battle.net-Setup.exe`. This forces the Agent/Setup state to be rebuilt without deleting the whole prefix. On disk that is:
   - `~/Games/battlenet/drive_c/ProgramData/Battle.net`
22. Wine debug lines such as `err:ole:com_get_class_object apartment not initialised` are noisy but were **not** decisive in this workflow. Prefer Battle.net bootstrapper logs, window state (`xwininfo`), and live process state over raw Wine stderr when deciding next steps.

## Prerequisites

- Ubuntu desktop with GUI (`DISPLAY` available)
- `SUDO_PASSWORD` stored in `~/.config/mizuki/secrets.env`
- Internet access

Load and follow `sudo-from-secrets-file` for privileged commands.

## Recommended flow

### 1) Confirm environment

Check OS and GUI:

```bash
uname -a
cat /etc/os-release
printf 'DISPLAY=%s\nXDG_CURRENT_DESKTOP=%s\n' "$DISPLAY" "$XDG_CURRENT_DESKTOP"
```

### 2) Check what is already installed

```bash
command -v wine || true
command -v lutris || true
apt-cache policy wine64 winetricks p7zip-full lutris cabextract
```

If Lutris seems missing after installation, inspect:

```bash
dpkg -L lutris | head -50
```

Look specifically for `/usr/games/lutris`.

### 3) Fix slow Ubuntu mirror if needed

If `/etc/apt/sources.list.d/ubuntu.sources` points to a slow regional mirror, replace:

- from: `http://iq.archive.ubuntu.com/ubuntu/`
- to: `http://archive.ubuntu.com/ubuntu/`

Keep a backup before changing it.

If `noble-backports` or DEP-11 metadata is failing due to mirror sync issues, retry later or temporarily remove `noble-backports` from `Suites:` while troubleshooting.

### 4) Install base packages

Install:

```bash
apt-get install -y wine64 winetricks cabextract p7zip-full lutris
```

### 5) Enable 32-bit Wine support

Battle.net may fail without this. Run:

```bash
dpkg --add-architecture i386
apt-get update
apt-get install -y wine32:i386
```

This can pull hundreds of packages and over 1 GB of additional disk usage. Warn the user that it may take a while.

### 6) Download Battle.net installer

A working URL used successfully:

```bash
mkdir -p ~/Games/Installers
curl -L --fail -o ~/Games/Installers/Battle.net-Setup.exe \
  'https://www.battle.net/download/getInstallerForGame?os=win&gameProgram=BATTLENET_APP&version=Live'
file ~/Games/Installers/Battle.net-Setup.exe
```

### 7) Launch the installer

Direct Wine launch works for first test:

```bash
wine ~/Games/Installers/Battle.net-Setup.exe
```

If using Lutris and PATH misses `/usr/games`, run:

```bash
/usr/games/lutris
```

### 8) Interpret common Wine failure

If Wine outputs messages like:
- `multiarch needs to be enabled first`
- `apt-get install wine32:i386`
- `failed to open C:\windows\syswow64\rundll32.exe`
- `failed to load ... syswow64\ntdll.dll`

then stop and install `wine32:i386` before retrying.

## Verification checklist

Before saying it is ready, verify:

```bash
wine --version
apt-cache policy wine32:i386 | sed -n '1,20p'
test -f ~/Games/Installers/Battle.net-Setup.exe && echo installer_present
```

If GUI launching is possible, retry the installer and confirm Battle.net opens.

## Pitfalls

- **Do not stop at `wine64` only**; Battle.net commonly needs `wine32:i386`.
- **Do not trust PATH alone** for Lutris; it may live in `/usr/games/lutris`.
- **Do not assume apt is completely broken** after a mirror sync error; inspect `apt-cache policy` first.
- **Do not save passwords into memory**; read from `~/.config/mizuki/secrets.env` only when needed.
- Regional mirrors can be much slower than `archive.ubuntu.com`; switching mirrors can unblock installs.
