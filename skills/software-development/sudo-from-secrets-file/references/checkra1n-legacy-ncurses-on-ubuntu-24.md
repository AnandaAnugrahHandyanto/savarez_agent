# checkra1n / Apple tooling on Ubuntu 24.04 with removed legacy libs

Use this when a third-party Apple/mobiledevice package repo still targets older Ubuntu/Debian runtimes and `apt-get install` fails on Ubuntu 24.04 (noble) because legacy libraries were removed from the standard repo.

## Symptoms

Typical failures:
- `checkra1n : Depends: libncurses5 (>= 6.0) but it is not installable`
- `irecovery : Depends: libreadline7 (>= 6.0) but it is not installable`
- `E: Unable to correct problems, you have held broken packages.`

## Root cause

Ubuntu 24.04 no longer ships some older runtime packages in the normal repo, but some third-party packages still declare hard dependencies on them.

For the checkra1n repo observed here:
- `checkra1n` required `libncurses5`
- `libncurses5` in turn required `libtinfo5`
- `irecovery` required `libreadline7`

These packages can still be fetched as compatibility `.deb` files from the Ubuntu archive pool.

## Working pattern

Do NOT use `dpkg -i` first unless you want recovery work afterward.

Prefer one apt transaction that includes the local compatibility packages and the target package together:

1. Download the exact compatibility `.deb` files to a temp dir.
2. Run one command like:

```bash
apt-get install -y ./libtinfo5_*.deb ./libncurses5_*.deb checkra1n
```

or:

```bash
apt-get install -y ./libreadline7_*.deb irecovery
```

This lets apt resolve the whole dependency graph cleanly in one pass.

## Versions used successfully in this session

From Ubuntu archive pool:
- `libtinfo5_6.3-2ubuntu0.1_amd64.deb`
- `libncurses5_6.3-2ubuntu0.1_amd64.deb`
- `libreadline7_7.0-3_amd64.deb`

Installed successfully with:
- `checkra1n 0.12.4`
- `irecovery 1.0.1-1`
- `libimobiledevice-utils` from noble repo for `idevice_id` / `ideviceinfo`

## Verification steps

After install, verify the actual tools instead of only package state:

```bash
command -v checkra1n
checkra1n --help | sed -n '1,20p'
command -v idevice_id
idevice_id -l
ideviceinfo -s
irecovery -q
```

Interpretation:
- `idevice_id -l` works when the phone is in normal mode and trusted / reachable.
- `ideviceinfo -s` gives a quick hardware + iOS identity snapshot.
- `irecovery -q` is mainly for recovery/DFU mode; `Unable to connect to device` usually just means the phone is not in recovery/DFU right now.

Also useful:

```bash
lsusb | grep -i apple
systemctl status usbmuxd --no-pager -l | sed -n '1,20p'
```

## Notes

- `python` is not the apt package name on Ubuntu 24.04; the normal package is `python3`, and `python-is-python3` adds the `python` command alias when an old script expects it.
- Existing clone directories causing `fatal: destination path ... already exists and is not an empty directory` are a separate cleanup problem, not a dependency-resolution problem.
- Missing `libtoolize`, `aclocal`, `automake`, `autoconf`, or `configure` indicates missing build tooling, not a broken sudo flow.
