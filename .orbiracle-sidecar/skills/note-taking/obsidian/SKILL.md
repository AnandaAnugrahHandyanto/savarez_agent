---
name: obsidian
description: Read, search, and create notes in the Obsidian vault.
---

# Obsidian Vault

**Location:** Set via `OBSIDIAN_VAULT_PATH` environment variable (e.g. in `~/.hermes/.env`).

If unset, defaults to `~/Documents/Obsidian Vault`.

Note: Vault paths may contain spaces - always quote them.

## Read a note

```bash
VAULT="${OBSIDIAN_VAULT_PATH:-$HOME/Documents/Obsidian Vault}"
cat "$VAULT/Note Name.md"
```

## List notes

```bash
VAULT="${OBSIDIAN_VAULT_PATH:-$HOME/Documents/Obsidian Vault}"

# All notes
find "$VAULT" -name "*.md" -type f

# In a specific folder
ls "$VAULT/Subfolder/"
```

## Search

```bash
VAULT="${OBSIDIAN_VAULT_PATH:-$HOME/Documents/Obsidian Vault}"

# By filename
find "$VAULT" -name "*.md" -iname "*keyword*"

# By content
grep -rli "keyword" "$VAULT" --include="*.md"
```

## Create a note

```bash
VAULT="${OBSIDIAN_VAULT_PATH:-$HOME/Documents/Obsidian Vault}"
cat > "$VAULT/New Note.md" << 'ENDNOTE'
# Title

Content here.
ENDNOTE
```

## Append to a note

```bash
VAULT="${OBSIDIAN_VAULT_PATH:-$HOME/Documents/Obsidian Vault}"
echo "
New content here." >> "$VAULT/Existing Note.md"
```

## Wikilinks

Obsidian links notes with `[[Note Name]]` syntax. When creating notes, use these to link related content.

## Installing Obsidian on constrained Ubuntu/Linux environments

When the user asks to "set up Obsidian" rather than just read/write vault files, do prerequisite checks first:

1. Check OS/package situation: `uname -a`, `/etc/os-release`, `command -v apt snap flatpak`, `whoami`, `id`, `sudo -n true`
2. Check whether a GUI session exists: inspect `DISPLAY`, `WAYLAND_DISPLAY`, `XDG_CURRENT_DESKTOP`
3. Check whether the target vault already exists and whether `OBSIDIAN_VAULT_PATH` is set

### Preferred normal route

If sudo/admin access exists and desktop packages are available, install Obsidian with the system's standard package route.

### Fallback route for no-sudo / headless / missing FUSE

On Ubuntu boxes where:
- sudo is unavailable,
- AppImage fails with `dlopen(): error loading libfuse.so.2`, or
- Electron/GTK libs are missing,

use this user-space workaround:

1. Download latest Obsidian AppImage into `~/Applications/`
2. Extract it with `--appimage-extract` into `~/Applications/obsidian-extracted/`
3. Use `apt download <pkg>` (no sudo required) plus `dpkg-deb -x` to unpack missing runtime libraries into a user-owned root such as `~/Applications/obsidian-libs/root`
4. Verify missing libs with:
   ```bash
   LD_LIBRARY_PATH="$LIBROOT/usr/lib/x86_64-linux-gnu:$LIBROOT/lib/x86_64-linux-gnu" ldd "$APPDIR/obsidian" | grep 'not found'
   ```
5. Create a wrapper at `~/.local/bin/obsidian` that sets:
   - `APPDIR`
   - `LD_LIBRARY_PATH`
   - `OBSIDIAN_VAULT_PATH`
   and launches:
   ```bash
   "$APPDIR/obsidian" --no-sandbox "$@"
   ```
6. Create `~/.local/share/applications/obsidian.desktop` pointing to the wrapper
7. If the vault is a generated wiki, precreate `.obsidian/app.json` and set `attachmentFolderPath` (for example `raw/assets`)

### Important findings

- AppImage may be downloaded successfully but still be unusable directly because FUSE is absent.
- Extracted Obsidian can still fail until GTK/ATK/Pango/Cairo/ASound-related shared libraries are bundled.
- `ldd ... | grep 'not found'` is the fastest way to iteratively close dependency gaps.
- `chrome-sandbox` will fail without root ownership/setuid; `--no-sandbox` is required in this no-sudo fallback route.
- In a headless shell, you can verify files, wrapper, desktop entry, env vars, and resolved dependencies, but you cannot fully verify the GUI window without a real desktop session.

### Vault defaulting

If the user has an existing canonical wiki/vault, export `OBSIDIAN_VAULT_PATH` in their shell env helper rather than relying on manual selection each launch.
