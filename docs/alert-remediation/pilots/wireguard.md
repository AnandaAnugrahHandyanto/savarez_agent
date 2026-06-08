# WireGuard Alert Remediation Pilot

This pilot exercises the alert-remediation pipeline for the safest initial Hippo Host class: a stale WireGuard peer handshake. The goal is to prove routing, policy selection, escalation shape, and dry-run behavior before enabling any live mutation.

**No live mutation is enabled by this document.** The pilot starts in dry-run. Live auto-remediation requires a separate operational decision after the dry-run output and verification checklist are reviewed.

## Scope

Pilot alert class:

- Source: `wireguard-watchdog`
- Service: `wireguard`
- Symptom: `peer handshake stale > 15m`
- Policy rule: `wireguard_stale_handshake`
- Allowed runbook: `wireguard_restart_and_verify`
- Critical route: `telegram:-1003939486586:7`
- Synthetic fixture: `docs/alert-remediation/fixtures/wireguard-stale.json`

The policy currently routes this fixture to `auto_remediate`, but the cron wrapper still runs in `--dry-run` during the pilot.

## Dry-run command

Use the profile-local policy when testing the operational path:

```bash
python scripts/alert_remediation_router.py \
  --policy ~/.hermes/profiles/sysadmin/alert-remediation/hippo-host-policy.yaml \
  --dry-run \
  --emit-decision-json \
  < docs/alert-remediation/fixtures/wireguard-stale.json
```

Expected decision:

- `action`: `auto_remediate`
- `matched_rule`: `wireguard_stale_handshake`
- `runbooks`: `wireguard_restart_and_verify`
- `should_spawn_triage`: `false`
- `should_create_kanban`: `false`
- no Kanban card is created during `--dry-run`

## Read-only pre-checks

Before any live restart is considered, collect current state from the affected hub/exit path.

Hub checks:

```bash
wg show
wg show interfaces
wg show <interface> latest-handshakes
systemctl status wg-quick@<interface> --no-pager
systemctl is-active wg-quick@<interface>
ip rule show
ip route show table 500
ip route show table 600
ip route show table 700
ip route get 8.8.8.8 from 192.168.98.34 iif client22-ais
ip route get 8.8.8.8 from 192.168.98.38 iif client22-3bb
ip route get 8.8.8.8 from 192.168.98.42 iif client22-true
journalctl -u wg-quick@<interface> -n 80 --no-pager
```

Exit-node checks where applicable:

```bash
wg show hop1
wg show hop1 latest-handshakes
systemctl status wg-quick@hop1 --no-pager
systemctl is-active wg-quick@hop1
ip route get 139.59.122.102
tailscale status --json
```

Required observations:

- identify which interface has stale `latest-handshakes`
- verify whether `wg-quick@<interface>` is active
- verify policy rules are present and not `[detached]`
- verify route tables have expected defaults
- verify `ip route get 8.8.8.8 ... iif <client-interface>` selects the expected table/interface
- verify the selected exit interface itself has a fresh peer or stale peer

## Approved remediation command class

The only restart class in this pilot is WireGuard systemd unit restart:

```bash
sudo systemctl restart wg-quick@<interface>
```

Use `systemctl restart wg-quick@`; not raw wg-quick down/up, not `ip link del`, and not `systemctl enable --now` as a substitute for restart. Systemd must run the unit's stop/start paths so PostDown/PostUp policy routing is reapplied consistently.

Do not reboot the host for this pilot. Do not change DNS, LVS routing, firewall rules, package versions, or unrelated services.

## Post-remediation verification

After any future approved restart, verify:

```bash
systemctl is-active wg-quick@<interface>
wg show <interface>
wg show <interface> latest-handshakes
ip rule show
ip route show table <table>
ip route get 8.8.8.8 from <peer-tunnel-ip> iif <client-interface>
journalctl -u wg-quick@<interface> -n 80 --no-pager
```

Success criteria:

- service active
- peer reachable where a ping/check is configured
- latest-handshakes fresh on both relevant sides
- RX/TX counters advance where expected
- policy routing selects the expected exit interface
- no new failed `wg-quick@*.service` unit relevant to the production tunnel

If verification fails, create/reuse a Kanban card with the alert dedupe key and include the pre-check and post-check evidence.

## Central monitor expectations

The existing WireGuard monitor should remain quiet when healthy and concise when unhealthy. A live alert should include:

- affected host
- affected interface/path
- stale-handshake age
- policy route simulation result
- whether hub and exit sides agree
- proposed runbook
- dedupe key

Repeated identical failures should not spam Telegram. Recovery should emit a single concise recovery message.

## Pilot enablement checklist

Before enabling live auto-remediation for this class:

- profile-local policy copy exists at `~/.hermes/profiles/sysadmin/alert-remediation/hippo-host-policy.yaml`
- dry-run with `wireguard-stale.json` returns `auto_remediate`
- dry-run does not create Kanban cards
- read-only pre-check command list reviewed
- approved restart command is limited to `sudo systemctl restart wg-quick@<interface>`
- post-remediation checks are documented
- critical routing remains `telegram:-1003939486586:7`
- local/on-node watchdog remains in place for cases where central SSH cannot reach the node

## Current pilot status

Prepared for dry-run. Live mutation remains disabled until explicitly enabled after review.
