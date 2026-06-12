# Guarded ddrescue Clone Toolkit Pattern

This reference captures a safe local-prep pattern for cloning a Linux system SSD to an HDD.

## Toolkit layout

Create a small directory such as:

```text
~/ssd-clone-toolkit/
  identify-disks.sh
  check-disk-health.sh
  clone-disk-ddrescue.sh
  README.md
```

## `identify-disks.sh`

```bash
#!/usr/bin/env bash
set -euo pipefail

lsblk -o NAME,MODEL,SERIAL,SIZE,TYPE,FSTYPE,MOUNTPOINTS,ROTA,TRAN

df -hT

ls -l /dev/disk/by-id/ | grep -E 'ata-|usb-|nvme-' || true

findmnt -no SOURCE,FSTYPE,SIZE,USED,AVAIL / || true
```

## `check-disk-health.sh`

```bash
#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "Usage: $0 /dev/DISK" >&2
  exit 2
fi

DISK="$1"
[[ -b "$DISK" ]] || { echo "ERROR: not a block device: $DISK" >&2; exit 1; }

lsblk -o NAME,MODEL,SERIAL,SIZE,TYPE,FSTYPE,MOUNTPOINTS,ROTA,TRAN "$DISK"

smartctl -a "$DISK" || smartctl -d sat -a "$DISK"
```

## `clone-disk-ddrescue.sh` guardrails

The clone script should:

- require root/sudo
- require exactly two args: source disk and target disk
- reject non-block devices
- reject same source/target
- check `blockdev --getsize64` target >= source
- reject mounted target partitions with `lsblk -nr -o MOUNTPOINTS "$DST"`
- print source and target with `lsblk`
- require exact typed confirmation, e.g. `CLONE /dev/sda TO /dev/sdb`
- save logs under `./logs/`
- run:

```bash
ddrescue -f -n "$SRC" "$DST" "$log"
ddrescue -f -d -r3 "$SRC" "$DST" "$log"
sync
partprobe "$DST" || true
```

## User-facing prep response

Report clearly:

- current root/source candidate by model, size, serial, partition
- any connected target candidates and whether mounted
- tools installed/available
- exact command to run later, but do not start clone
- live USB recommendation for cleaner system disk clone

## Sudo credential pitfall

If using a local secrets file, do not source the whole file. It may contain raw tokens or notes that are not valid shell assignments. Parse only `SUDO_PASSWORD` with Python, then pass it to `/usr/bin/sudo -S -p ''` via subprocess.
