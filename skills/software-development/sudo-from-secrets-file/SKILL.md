---
name: sudo-from-secrets-file
description: Use a local secrets file to supply sudo or other credentials during Hermes terminal tasks, with a Python subprocess fallback when shell piping to sudo behaves unexpectedly.
---

# Sudo from local secrets file

Use this skill when:
- a user wants Hermes to read local credentials from disk during PC tasks
- a task needs `sudo` and the user has approved the destructive/risky action
- shell-based `printf ... | sudo -S ...` behaves unexpectedly in the Hermes terminal environment

## Goal

Use credentials from a local file without saving secrets to long-term memory, and reliably execute `sudo` commands even if shell piping fails.

## Local secrets file convention

Default path used in this workflow:

```bash
~/.config/mizuki/secrets.env
```

Typical contents:

```env
SUDO_PASSWORD=
API_KEY=
TOKEN=
EMAIL=
NOTES=
```

Guidelines:
1. Never save secrets into Hermes memory.
2. Keep the file local-only and chmod it to `600`.
3. Read from the file only when the active task needs a credential.
4. For destructive actions (uninstalling software, deleting data, etc.), still get explicit confirmation first.

## Creating the secrets file

Use `write_file` to create the file and `terminal` to lock permissions:

```bash
chmod 600 ~/.config/mizuki/secrets.env
```

## Preferred sudo execution flow

### 1) Check the secret exists

Use a shell or Python read to confirm `SUDO_PASSWORD` is present and non-empty.

**Do not assume the whole secrets file is safe to `source`.** The local file may contain notes, raw tokens, or other non-shell-safe lines. Prefer parsing only the specific key needed instead of running `. ~/.config/mizuki/secrets.env`.

Safe Python parse pattern:

```python
from pathlib import Path

key = 'SUDO_' + 'PASSWORD'
pw = None
for line in (Path.home() / '.config/mizuki/secrets.env').read_text(errors='ignore').splitlines():
    if line.startswith(key + '='):
        pw = line.split('=', 1)[1].strip().strip('"').strip("'")
        break
if not pw:
    raise SystemExit('Missing sudo password')
```

### 2) Try direct shell sudo only if simple and the secret is already safely parsed

A common attempt is:

```bash
printf '%s\n' "$SUDO_PASSWORD" | sudo -S -p '' <command>
```

### 3) If sudo prints usage, the secrets file fails to source, or the shell approach otherwise misbehaves, switch immediately to Python subprocess

In some Hermes terminal contexts, the shell pipeline can fail even when `sudo` itself works. The reliable fallback is to invoke `/usr/bin/sudo` directly from Python and pass the password via `subprocess.run(..., input=...)`.

Pattern:

```python
import subprocess

pw = "..."
p = subprocess.run(
    ['/usr/bin/sudo', '-S', '-p', '', 'true'],
    input=(pw + '\n').encode(),
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
)
print(p.stdout.decode())
print(p.returncode)
```

For a real privileged command:

```python
import subprocess

def run_sudo(cmd, pw):
    p = subprocess.run(
        ['/usr/bin/sudo', '-S', '-p', ''] + cmd,
        input=(pw + '\n').encode(),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    print(p.stdout.decode(), end='')
    if p.returncode != 0:
        raise SystemExit(p.returncode)

run_sudo(['apt-get', 'purge', '-y', 'firefox'], pw)
```

## Additional references

- `references/checkra1n-legacy-ncurses-on-ubuntu-24.md` — workaround for Ubuntu 24.04 when the checkra1n repo still depends on removed legacy libraries (`libncurses5` / `libtinfo5`) and `irecovery` still depends on `libreadline7`, plus Apple device verification steps after install.

## Example: install a package with local compatibility .debs in the same apt transaction

When a third-party package depends on an old library that is no longer present in the current Ubuntu release, prefer this pattern:
1. Download the exact compatibility `.deb` packages from the Ubuntu archive pool.
2. Use the Python subprocess sudo fallback.
3. Run one `apt-get install -y <local1.deb> <local2.deb> target-package` command so apt resolves everything together.
4. Verify with the actual executable (`command -v`, `--help`, or version output), not package state alone.

This avoids a messier `dpkg -i` followed by `apt -f install` recovery path.

## Example: uninstall Firefox and remove user data

Workflow used successfully:
1. Detect package manager and whether Firefox exists as apt transitional package and/or snap.
2. Read `SUDO_PASSWORD` from `~/.config/mizuki/secrets.env`.
3. If shell sudo fails unexpectedly, use Python subprocess fallback.
4. Run privileged removals:
   - `apt-get purge -y firefox` (if installed)
   - `snap remove --purge firefox` (if installed)
5. Remove user data:
   - `~/.mozilla`
   - `~/.cache/mozilla`
   - `~/.config/firefox`
6. Verify:
   - `which firefox` is absent
   - `snap list firefox` fails/not installed
   - data directories are gone

## Example: multi-app cleanup across snap, flatpak, and apt

When the user explicitly selects apps/tools to remove:
1. Treat the user's numbered selection as confirmation for those exact items only; do not broaden into unrelated system cleanup.
2. Remove snap apps with `snap remove --purge <name>` and verify with `snap list <name>` returning non-zero.
3. Remove Flatpak apps with `flatpak uninstall -y --delete-data <app-id>`, then run `flatpak uninstall -y --unused` to remove now-unused runtimes. A DBus warning after uninstall may still leave the app removed; verify with `flatpak info <app-id>`.
4. Before a large apt purge, run or be ready to run `dpkg --configure -a`; if apt reports `dpkg was interrupted`, fix that state immediately and retry the purge.
5. For apt removals, use `apt-get purge -y --autoremove <packages...>`, then `apt-get autoremove -y --purge` and `apt-get autoclean`.
6. Large apt purges may exceed foreground tool limits. If so, use a tracked background process with completion notification, then wait/poll and verify afterward.
7. Verify all selected packages explicitly:
   - `dpkg-query -W -f='${db:Status-Abbrev} ${binary:Package}\n' <pkg>` should be absent or `un`/`pn`/removed.
   - `dpkg --audit` should be clean after package work.
   - `snap list` and `flatpak list --app` should show expected remaining apps only.
8. Do not manually delete leftover service data directories unless the user specifically approved data deletion. It is okay to report small leftovers and their size.

## Verification checklist

Before finishing, verify all of:
- credential file exists
- `SUDO_PASSWORD` is non-empty
- privileged command exit code is 0
- target package/app is absent afterward
- user data paths requested for deletion are actually gone

## Pitfalls

- Do not store the password in Hermes memory.
- Do not skip confirmation for destructive actions just because a local secrets file exists.
- `sudo -S` via shell pipeline may emit usage text unexpectedly in this environment; if that happens, test `/usr/bin/sudo` directly with Python subprocess and proceed with that path.
- Snap and apt may both be involved for the same app on Ubuntu; check both.
