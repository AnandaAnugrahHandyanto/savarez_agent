---
name: x11-desktop-helpers-mizuki
description: Use preinstalled X11 helper scripts on this Ubuntu desktop for reliable GUI automation in the user's live session.
triggers:
  - Need to control the user's live Ubuntu Xorg desktop session from Hermes
  - Need more reliable typing/focus/search than raw xdotool commands
---

# X11 desktop helpers (Mizuki)

Use this when operating the user's live Ubuntu Xorg desktop. The environment already has a reachable session and several helper tools/scripts installed.

## Preconditions

- User is logged into the desktop via GDM on Xorg
- Session is reachable with:
  - `DISPLAY=:0`
  - `XAUTHORITY=/run/user/1000/gdm/Xauthority`
- The following packages are installed:
  - `xdotool`
  - `scrot`
  - `imagemagick`
  - `wmctrl`
  - `xprop`
  - `xwininfo`
  - `xclip`

## Helper scripts

Located in `~/.local/bin/`:

1. `mizuki-x11`
   - Wraps commands with the correct X11 environment.
   - Pattern:
     ```bash
     mizuki-x11 xdotool getwindowfocus getwindowname
     ```

2. `mizuki-type`
   - Types using clipboard paste instead of `xdotool type`.
   - Use this for browser search bars and text fields when raw keystrokes are flaky.

3. `mizuki-screenshot`
   - Captures a desktop screenshot quickly.

4. `mizuki-focus`
   - Focuses a window by class/title.

5. `mizuki-brave-search`
   - Safer Brave searching workflow using focus + address bar + paste.

## Recommended workflow

1. Confirm the session is reachable:
   ```bash
   DISPLAY=:0 XAUTHORITY=/run/user/1000/gdm/Xauthority xdotool getmouselocation
   ```
2. Focus the target app/window with `mizuki-focus` or `wmctrl`.
3. For text entry, prefer `mizuki-type` over `xdotool type`.
4. For Brave searches, prefer `mizuki-brave-search`.
5. Verify using window titles (`wmctrl -lx`, `xdotool getwindowfocus getwindowname`) and screenshots when available.

## Pitfalls

- Raw `xdotool type` may drop characters if focus changes or the app lags.
- Screenshot capture may sometimes return black images under GNOME/X11 even when control still works.
- Keep the screen unlocked and avoid user mouse/keyboard interference during automation.

## Verification

- Check active window title:
  ```bash
  mizuki-x11 xdotool getwindowfocus getwindowname
  ```
- Check open windows:
  ```bash
  DISPLAY=:0 XAUTHORITY=/run/user/1000/gdm/Xauthority wmctrl -lx
  ```
- Take and inspect a screenshot if visual validation is needed.

## Brave / Chrome Web Store installation notes

Reusable workflow validated in practice:

1. Launch Brave with the X11 environment explicitly set:
   ```bash
   DISPLAY=:0 XAUTHORITY=/run/user/1000/gdm/Xauthority nohup brave-browser 'https://chromewebstore.google.com/detail/<name>/<extension-id>' >/tmp/brave.log 2>&1 &
   ```
2. Verify the window exists with `wmctrl -lx | grep -i brave`.
3. If visual confirmation is needed, use `mizuki-screenshot` and vision to locate the **Add to Brave** button and then the **Add extension** confirmation button.
4. After clicking through, verify installation by checking one or both of:
   - the extension directory under:
     `~/.config/BraveSoftware/Brave-Browser/Default/Extensions/<extension-id>`
   - the Brave page:
     `brave://extensions`
5. On `brave://extensions`, treat a visible card with a **Remove** button and an enabled toggle as the strongest confirmation the extension is installed and active.

Pitfall discovered during real use:
- launching `brave-browser` without `DISPLAY` and `XAUTHORITY` set may fail with `Missing X server or $DISPLAY`, even if later X11 control commands work fine.
