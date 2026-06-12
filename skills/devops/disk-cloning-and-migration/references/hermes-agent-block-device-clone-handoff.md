# Hermes agent block-device clone handoff

When preparing Linux disk clones from inside Hermes Agent, raw writes to block devices may be blocked by the agent runtime safety layer even after user approval. Treat this as a handoff constraint: prepare and verify everything possible, then give the user a locked command/script to run locally.

## Pattern

1. Identify source and target with model, serial, size, transport, mountpoints:

```bash
lsblk -o NAME,MODEL,SERIAL,SIZE,TYPE,FSTYPE,LABEL,MOUNTPOINTS,ROTA,TRAN
ls -l /dev/disk/by-id/ | grep -E 'ata-|usb-|nvme-' || true
findmnt -no SOURCE,FSTYPE,SIZE,USED,AVAIL /
```

2. Check target health before trusting it:

```bash
sudo smartctl -a /dev/sdX || true
sudo smartctl -d sat -a /dev/sdX || true
```

If SMART says PASSED but shows old ATA errors, command timeouts, reallocated sectors, or prior failed temperature attributes, report it plainly: usable for emergency recovery/temporary boot, not a strong long-term replacement.

3. Reduce source writes where safe:

```bash
cd /path/to/project && docker compose stop
sync
```

4. Unmount target partitions only:

```bash
sudo umount /dev/sdX1
lsblk -o NAME,MODEL,SERIAL,SIZE,TYPE,FSTYPE,MOUNTPOINTS,ROTA,TRAN /dev/sdX
```

5. Create a locked launcher using stable `/dev/disk/by-id/...` paths rather than `/dev/sdX` names. Example:

```bash
#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

SRC="/dev/disk/by-id/ata-Samsung_SSD_870_EVO_250GB_SERIAL"
DST="/dev/disk/by-id/ata-FUJITSU_MJA2320BH_G2_SERIAL"

cat <<EOF
=== LOCKED CLONE LAUNCHER ===
Source system disk:
  $SRC
Target disk - WILL BE ERASED:
  $DST
EOF

lsblk -o NAME,MODEL,SERIAL,SIZE,TYPE,FSTYPE,MOUNTPOINTS,ROTA,TRAN "$SRC"
lsblk -o NAME,MODEL,SERIAL,SIZE,TYPE,FSTYPE,MOUNTPOINTS,ROTA,TRAN "$DST"

while read -r part mnt; do
  [[ -n "${mnt:-}" ]] || continue
  umount "$part"
done < <(lsblk -nr -o PATH,MOUNTPOINTS "$DST" | awk 'NF >= 2')

exec ./clone-disk-ddrescue.sh "$SRC" "$DST"
```

6. Validate scripts without running destructive writes:

```bash
chmod +x clone-*.sh
bash -n clone-disk-ddrescue.sh clone-locked-target.sh
```

7. Final handoff should include:

- exact source and target model/serial/size
- target mount status
- target health warning if applicable
- exact command for the user to run
- exact confirmation phrase expected by the guarded clone script
- ddrescue log directory
- instruction to send final output for boot/expansion follow-up

## Do not capture as a permanent rule

Do not encode “Hermes can never clone disks” as a universal fact; the runtime policy may change. Encode the practical handoff pattern and continue preparing everything safe and reversible.