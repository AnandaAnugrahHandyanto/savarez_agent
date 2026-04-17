# Disaster Recovery Runbook — jaxmind.xyz Lab Infra

> **Ticket:** PAB-13  
> **Last Updated:** 2026-04-13  
> **Owner:** Pablo Torres (@pablots99)  
> **Purpose:** Complete step-by-step runbook to rebuild the `jax-mind` VPS lab from scratch after total server loss.

---

## Overview

This runbook covers the full rebuild path: provision a new Hetzner VPS → bootstrap Docker → restore secrets → deploy all stacks → verify services.

**Target state after recovery:**
- All services running behind Traefik at `jaxmind.xyz`
- Metrics flowing to Grafana Cloud
- Uptime Kuma monitoring all endpoints
- GitOps pipeline (Woodpecker CI) operational

---

## Section 1: Prerequisites

Before touching any server, gather the following. Nothing works without these.

### 1.1 age Private Key (Critical)

The age private key is used by SOPS to decrypt all `.env.enc` secret files. Without it, secrets cannot be recovered from the repo.

- **Location on old server (if accessible):** `/root/.config/sops/age/keys.txt`
- **Should also be stored in:** your password manager (Bitwarden, 1Password, etc.) — this is the backup
- **Public key (safe to store anywhere):** `age1snttkxsjte460xkh5v6cl0u0t7umuu4q0m7za8vpgzm9yx46zdvs8sdtfz`

**Action:** Before proceeding, confirm you have the private key contents. It looks like:
```
# created: 2024-...
# public key: age1snttkxsj...
AGE-SECRET-KEY-1...
```

> ⚠️ **If the age private key is lost,** all `.env.enc` secrets must be manually recreated from other sources (password manager, GitHub OAuth app settings, etc.). See Section 5 for fallback.

### 1.2 GitHub Access

Required to clone the `lab-infra` repo and for Woodpecker CI OAuth.

- GitHub account: `pablots99`
- Repo: `https://github.com/pablots99/lab-infra`
- Either a **deploy key** (SSH) or a **Personal Access Token** with `repo` scope
- **Woodpecker OAuth App** credentials (Client ID + Secret) — stored in password manager

### 1.3 Cloudflare Access

Required to point DNS to the new VPS IP once provisioned.

- Log into Cloudflare dashboard: https://dash.cloudflare.com
- Zone: `jaxmind.xyz`
- You will need to update the `A` record to point to the new VPS IP

**Note on Cloudflare API token:** Currently, Traefik uses Cloudflare edge SSL in Flexible mode (Cloudflare terminates TLS, sends plain HTTP to VPS on port 80). A Cloudflare API token is only needed if you want Let's Encrypt DNS-01 challenge — not required for the current setup.

### 1.4 Hetzner Account

- Login: https://console.hetzner.cloud
- Project: your lab project
- You will provision a new CX22 server and a 50 GB volume

### 1.5 Grafana Cloud Credentials

- Grafana Cloud URL: `pablots99.grafana.net`
- Used to verify metrics/logs reach Grafana after recovery
- VictoriaMetrics remote read UID: `efiwad0exm5tsf`
- Loki datasource UID: `afiwd6p9kej28e`

---

## Section 2: Provision New VPS

### 2.1 Create the Server in Hetzner Cloud

1. Log into https://console.hetzner.cloud
2. Navigate to your lab project → **Servers** → **Add Server**
3. Configure:
   - **Location:** Choose your preferred region (e.g., Falkenstein or Helsinki)
   - **Image:** Ubuntu 24.04 LTS
   - **Type:** CX22 — 4 vCPU, 8 GB RAM, 80 GB NVMe disk  
     *(Note: architecture docs show 16 GB RAM — select CX32 if 16 GB is required)*
   - **SSH Key:** Add your public SSH key
   - **Hostname:** `jax-mind`
4. Click **Create & Buy Now**
5. Note the new public IP address (referred to as `<NEW_IP>` below)

### 2.2 Create and Attach the Extra Volume

1. In Hetzner Console → **Volumes** → **Add Volume**
2. Configure:
   - **Size:** 50 GB
   - **Location:** Same as server
   - **Name:** e.g., `jax-mind-data`
3. Click **Create Volume**
4. Attach it to the `jax-mind` server

### 2.3 SSH Into the New Server

```bash
ssh root@<NEW_IP>
```

### 2.4 Initial System Setup

```bash
# Update and upgrade packages
apt update && apt upgrade -y

# Set hostname
hostnamectl set-hostname jax-mind

# Verify hostname
hostname
```

### 2.5 Format and Mount the Extra Volume

The Hetzner volume will appear as a block device (typically `/dev/sdb` or `/dev/disk/by-id/scsi-...`). Verify the device name first:

```bash
# List block devices to identify the volume
lsblk
```

The volume should appear as an unformatted disk (no partition, no filesystem). Hetzner also shows the device path in the console UI.

```bash
# Format the volume as ext4 (replace /dev/sdb with your device)
mkfs.ext4 /dev/sdb

# Create the mount point
mkdir -p /mnt/data

# Mount the volume
mount /dev/sdb /mnt/data

# Make the mount persistent across reboots
echo "/dev/sdb /mnt/data ext4 defaults 0 2" >> /etc/fstab

# Create a symlink matching the original storage layout
# (original was /mnt/HC_Volume_105131034 → /mnt/data)
ln -s /mnt/data /mnt/HC_Volume_$(basename /dev/sdb)

# Verify mount
df -h /mnt/data
```

> **Expected:** `/mnt/data` shows ~50 GB available.

---

## Section 3: Bootstrap Docker

### 3.1 Install Docker Engine and Docker Compose Plugin

```bash
# Install prerequisites
apt install -y ca-certificates curl gnupg lsb-release

# Add Docker's official GPG key
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
  -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc

# Add Docker repository
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] \
  https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
  | tee /etc/apt/sources.list.d/docker.list > /dev/null

# Install Docker Engine + Compose plugin
apt update
apt install -y docker-ce docker-ce-cli containerd.io \
  docker-buildx-plugin docker-compose-plugin

# Verify installation
docker --version
docker compose version
```

### 3.2 Configure Docker to Use the Data Volume

By default Docker stores all image/volume data under `/var/lib/docker` (root disk). Redirect it to `/mnt/data/docker` to use the larger data volume.

```bash
# Create the Docker data directory on the volume
mkdir -p /mnt/data/docker

# Create the Docker daemon configuration
cat > /etc/docker/daemon.json <<'EOF'
{
  "data-root": "/mnt/data/docker"
}
EOF

# Restart Docker to apply the new data-root
systemctl restart docker

# Verify Docker is using the new path
docker info | grep "Docker Root Dir"
```

> **Expected output:** `Docker Root Dir: /mnt/data/docker`

### 3.3 Create Required Docker Networks

Traefik and all services communicate over two shared external networks. These must exist before any stack is deployed.

```bash
docker network create proxy
docker network create monitoring
```

---

## Section 4: Clone the Repository

### 4.1 Create the Lab Directory Structure

```bash
mkdir -p /lab
```

### 4.2 Clone the Repo

**Option A — HTTPS with PAT (simpler):**

```bash
# Replace <YOUR_PAT> with your GitHub Personal Access Token
git clone https://<YOUR_PAT>@github.com/pablots99/lab-infra.git /lab/infra
```

**Option B — SSH:**

```bash
# Set up SSH key for GitHub (if not already on the server)
ssh-keygen -t ed25519 -C "root@jax-mind" -f /root/.ssh/id_ed25519 -N ""
cat /root/.ssh/id_ed25519.pub
# Add the public key to GitHub: Settings → SSH and GPG keys → New SSH key

# Clone via SSH
git clone git@github.com:pablots99/lab-infra.git /lab/infra
```

### 4.3 Create Required Directories

```bash
# Obsidian vault directory — used by the obsidian-sync stack (CouchDB bind mount)
mkdir -p /lab/obsidian_vault

# Live stacks directory — where .env files and deployed configs live
mkdir -p /lab/stacks
```

---

## Section 5: Restore Secrets

> **Status check:** `.env.enc` files exist in the repo for: `traefik`, `monitoring`, `homepage`, `woodpecker`. The stacks `obsidian-sync` and `uptime-kuma` have no encrypted env files and require no secrets from SOPS.

### 5.1 Install SOPS

```bash
# Download the latest SOPS binary
SOPS_VERSION=$(curl -s https://api.github.com/repos/getsops/sops/releases/latest \
  | grep '"tag_name"' | cut -d'"' -f4)

curl -fsSL "https://github.com/getsops/sops/releases/download/${SOPS_VERSION}/sops-${SOPS_VERSION}.linux.amd64" \
  -o /usr/local/bin/sops

chmod +x /usr/local/bin/sops

# Verify
sops --version
```

### 5.2 Restore the age Private Key

```bash
# Create the directory
mkdir -p /root/.config/sops/age

# Paste the private key contents (from your password manager)
# The file should look like:
# # created: 2024-...
# # public key: age1snttkxsj...
# AGE-SECRET-KEY-1...

nano /root/.config/sops/age/keys.txt

# Set restrictive permissions
chmod 600 /root/.config/sops/age/keys.txt
```

### 5.3 Decrypt Secrets for Each Stack

For each stack that has a `.env.enc` file, decrypt it and place the result where the stack expects it:

```bash
export SOPS_AGE_KEY_FILE=/root/.config/sops/age/keys.txt

# Traefik
mkdir -p /lab/stacks/traefik
sops --decrypt /lab/infra/stacks/traefik/.env.enc \
  > /lab/stacks/traefik/.env

# Monitoring
mkdir -p /lab/stacks/monitoring
sops --decrypt /lab/infra/stacks/monitoring/.env.enc \
  > /lab/stacks/monitoring/.env

# Homepage
mkdir -p /lab/stacks/homepage
sops --decrypt /lab/infra/stacks/homepage/.env.enc \
  > /lab/stacks/homepage/.env

# Woodpecker
mkdir -p /lab/stacks/woodpecker
sops --decrypt /lab/infra/stacks/woodpecker/.env.enc \
  > /lab/stacks/woodpecker/.env
```

**Verify each file was created and is non-empty:**

```bash
for stack in traefik monitoring homepage woodpecker; do
  echo "=== $stack ==="
  wc -l /lab/stacks/$stack/.env
done
```

> ⚠️ **If decryption fails (key mismatch or key lost):** You must manually recreate each `.env` file. See Section 5.4.

### 5.4 Fallback: Manual Secret Reconstruction

If the age key is unavailable and `.env.enc` cannot be decrypted, recreate each `.env` from scratch:

**`/lab/stacks/traefik/.env`**
```bash
# Generate a bcrypt password hash: htpasswd -nB admin
# Then populate:
TRAEFIK_DASHBOARD_AUTH=admin:<bcrypt_hash>
```

**`/lab/stacks/homepage/.env`**
- Check `stacks/homepage/docker-compose.yml` for required variables
- Usually homepage bookmark/service configuration — may not be strictly required

**`/lab/stacks/monitoring/.env`**
- Contains credentials for VictoriaMetrics basic auth, Loki basic auth, Discord webhook URL for Alertmanager
- Retrieve Discord webhook URL from the Discord server channel settings
- Set basic auth hashes using `htpasswd -nB <username>`

**`/lab/stacks/woodpecker/.env`**
- Contains GitHub OAuth Client ID + Secret
- Recreate at: GitHub → Settings → Developer Settings → OAuth Apps
  - Homepage URL: `https://woodpecker.jaxmind.xyz`
  - Callback URL: `https://woodpecker.jaxmind.xyz/authorize`
- Also contains `WOODPECKER_AGENT_SECRET` (random string — generate a new one: `openssl rand -hex 32`)
- See `stacks/woodpecker/README.md` for full details

---

## Section 6: Deploy Stacks

> **Order matters.** Traefik must be running first — it owns port 80 and the `proxy` network. The monitoring stack should come second since other services emit metrics. Then remaining stacks in any order.

**Deploy order:** `traefik` → `monitoring` → `woodpecker` → `homepage` → `obsidian-sync` → `uptime-kuma`

Before deploying each stack, the Woodpecker GitOps pipeline uses `rsync` to copy stack configs from `/lab/infra/stacks/<name>/` to `/lab/stacks/<name>/` (excluding `.env` files). On a fresh restore, do this manually:

```bash
# Sync all stack configs to /lab/stacks/ (skip .env files which you already created)
for stack in traefik monitoring woodpecker homepage obsidian-sync uptime-kuma; do
  mkdir -p /lab/stacks/$stack
  rsync -av --exclude='.env' --exclude='.env.enc' \
    /lab/infra/stacks/$stack/ /lab/stacks/$stack/
done
```

### 6.1 Deploy Traefik

```bash
cd /lab/infra/stacks/traefik
docker compose --env-file /lab/stacks/traefik/.env up -d

# Verify
docker compose ps
```

> **Expected:** `traefik` container status `Up`, listening on port 80.

```bash
# Quick smoke test — Traefik should return a response
curl -si http://localhost/ping || curl -si http://localhost/ | head -5
```

### 6.2 Deploy Monitoring Stack

```bash
cd /lab/infra/stacks/monitoring
docker compose --env-file /lab/stacks/monitoring/.env up -d

# Verify all containers are healthy
docker compose ps
```

> **Expected:** `victoriametrics`, `loki`, `promtail`, `alertmanager`, `node-exporter`, `docker-stats-exporter`, and `vmalert` all showing `Up (healthy)`.

### 6.3 Deploy Woodpecker CI

```bash
cd /lab/infra/stacks/woodpecker
docker compose --env-file /lab/stacks/woodpecker/.env up -d

docker compose ps
```

> **Expected:** `woodpecker-server` and `woodpecker-agent` both `Up`.

### 6.4 Deploy Homepage

```bash
cd /lab/infra/stacks/homepage
docker compose --env-file /lab/stacks/homepage/.env up -d

docker compose ps
```

### 6.5 Deploy Obsidian Sync (CouchDB)

No `.env.enc` — no secrets file needed. The `obsidian_vault` directory must exist (created in Section 4.3).

```bash
cd /lab/infra/stacks/obsidian-sync
docker compose up -d

docker compose ps
```

> **Expected:** `couchdb` container `Up (healthy)`.

### 6.6 Deploy Uptime Kuma

No `.env.enc` — no secrets file needed.

```bash
cd /lab/infra/stacks/uptime-kuma
docker compose up -d

docker compose ps
```

> **Expected:** `uptime-kuma` container `Up`.

> **Note:** Uptime Kuma stores its monitor configuration (URLs, intervals, notification settings) inside its Docker volume (`/mnt/data/docker/volumes/`). If the data volume was not backed up before the disaster, you will need to manually re-add all monitors through the Uptime Kuma UI at `https://status.jaxmind.xyz`.

---

## Section 7: Update DNS and Verify

### 7.1 Update Cloudflare DNS

Once the new VPS is running, update the DNS A record to point to the new IP:

1. Log into https://dash.cloudflare.com
2. Select zone: `jaxmind.xyz`
3. Go to **DNS** → find the `A` record for `jaxmind.xyz` (and the wildcard `*` or individual subdomains)
4. Update the IP to `<NEW_IP>`
5. Ensure **Proxy status** is set to **Proxied** (orange cloud)

DNS propagation through Cloudflare proxy is typically near-instant (seconds to a few minutes).

### 7.2 Verify All Containers Are Running

```bash
# Check each stack
for stack in traefik monitoring woodpecker homepage obsidian-sync uptime-kuma; do
  echo "====== $stack ======"
  cd /lab/infra/stacks/$stack && docker compose ps
done
```

> **Expected:** All containers show `Up` or `Up (healthy)`. No containers in `Exit`, `Restarting`, or `Created` state.

### 7.3 Verify Services Are Accessible via Traefik

Test each public-facing service. Wait a few minutes after DNS update for propagation.

```bash
# Homepage
curl -si https://home.jaxmind.xyz | head -3

# Woodpecker CI
curl -si https://woodpecker.jaxmind.xyz | head -3

# Traefik dashboard (requires basic auth)
curl -si https://traefik.jaxmind.xyz | head -3

# Uptime Kuma
curl -si https://status.jaxmind.xyz | head -3

# VictoriaMetrics (requires basic auth)
curl -si https://vm.jaxmind.xyz | head -3

# Loki (requires basic auth)
curl -si https://loki.jaxmind.xyz | head -3

# CouchDB
curl -si https://couchdb.jaxmind.xyz | head -3
```

> **Expected:** All return HTTP `200` or `301/302` redirects. A `404` from Traefik means routing is not configured. A connection refused means the container is down or Traefik is not running.

### 7.4 Verify Grafana Cloud Is Receiving Metrics

1. Log into https://pablots99.grafana.net
2. Navigate to **Explore** → select the **VictoriaMetrics** datasource (UID: `efiwad0exm5tsf`)
3. Run a simple query: `up` — should return results for `node-exporter`, `traefik`, `woodpecker`, etc.
4. Check the **Node Exporter Full** dashboard — should show CPU, RAM, disk for the new VPS
5. Navigate to **Explore** → select **Loki** datasource (UID: `afiwd6p9kej28e`)
6. Run `{job="varlogs"}` or `{container_name=~".+"}` — should show recent container logs

> **If Grafana Cloud shows no data:** Verify VictoriaMetrics is healthy, check `promtail` logs for Loki errors, and confirm the monitoring stack's `.env` has correct remote endpoints/credentials.

### 7.5 Verify Uptime Kuma Shows All Green

1. Open https://status.jaxmind.xyz
2. All 6 monitored endpoints should show **Up** (green) within ~2 minutes of services starting
3. If any endpoint is red: check the corresponding container with `docker logs <container_name>`

### 7.6 Verify GitOps Pipeline (Woodpecker)

1. Make a trivial change to the repo (e.g., update a comment in `README.md`)
2. `git push origin main`
3. Open https://woodpecker.jaxmind.xyz — a new pipeline should appear and run successfully
4. This confirms Woodpecker is receiving GitHub webhooks and can deploy stacks

> **Note:** For Woodpecker to receive webhooks, the DNS must already be updated and Woodpecker GitHub OAuth must be configured. See `stacks/woodpecker/README.md`.

---

## Section 8: RTO Estimate

Estimated time to full recovery from scratch, assuming all prerequisites (age key, credentials) are immediately available.

| Phase | Task | Estimated Time |
|---|---|---|
| **0** | Gather prerequisites, locate age key + credentials | 10–20 min |
| **1** | Provision VPS + volume in Hetzner Console | 5–10 min |
| **2** | SSH in, apt update, set hostname, format + mount volume | 5–10 min |
| **3** | Install Docker, configure daemon.json, create networks | 10–15 min |
| **4** | Clone repo, create directories | 2–5 min |
| **5** | Install SOPS, restore age key, decrypt all `.env.enc` files | 5–10 min |
| **6** | Sync stack configs, deploy all 6 stacks | 10–20 min |
| **7** | Update Cloudflare DNS, verify all services | 10–15 min |
| **8** | Verify Grafana Cloud metrics + logs | 5–10 min |

**Total estimated RTO: ~60–115 minutes** (1 to 2 hours)

**RTO assumes:**
- age private key is available in password manager (no manual secret reconstruction)
- Hetzner account and billing are active
- No issues with Docker image pulls or container startup
- Cloudflare DNS propagates quickly (typically < 2 minutes with proxy)

**Extended RTO scenarios:**
- **age key lost → manual secret reconstruction:** +30–60 min
- **Docker image pull issues (rate limits, registry down):** +15–30 min
- **Data volume not backed up (Uptime Kuma monitor reconfiguration):** +15–30 min
- **Woodpecker OAuth app needs recreation:** +15 min

> **Recommendation:** Back up the age private key and all `.env` files from `/lab/stacks/` to an encrypted off-VPS location (e.g., encrypted export in password manager) at least monthly. This is the single largest risk to RTO.

---

## Appendix A: Quick Reference — Service URLs

| Service | URL | Notes |
|---|---|---|
| Homepage | https://home.jaxmind.xyz | Lab dashboard |
| Woodpecker CI | https://woodpecker.jaxmind.xyz | GitOps pipeline |
| Traefik Dashboard | https://traefik.jaxmind.xyz | Basic auth required |
| Uptime Kuma | https://status.jaxmind.xyz | Status page |
| VictoriaMetrics | https://vm.jaxmind.xyz | Basic auth required |
| Loki | https://loki.jaxmind.xyz | Basic auth required |
| CouchDB | https://couchdb.jaxmind.xyz | Obsidian LiveSync |

## Appendix B: Key File Locations on VPS

| File/Dir | Purpose |
|---|---|
| `/root/.config/sops/age/keys.txt` | age private key for SOPS decryption |
| `/lab/infra/` | Git clone of this repo |
| `/lab/stacks/<name>/.env` | Live secrets for each stack (not in git) |
| `/lab/stacks/<name>/` | Live stack configs (synced from repo by GitOps) |
| `/lab/obsidian_vault/` | Obsidian vault data (synced via CouchDB) |
| `/mnt/data/docker/` | All Docker volumes and image data |
| `/etc/docker/daemon.json` | Docker config (data-root redirect) |

## Appendix C: Stack Deployment Summary

| Stack | Has `.env.enc` | Networks | Deploy First? |
|---|---|---|---|
| `traefik` | ✅ Yes | `proxy` | **Yes — deploy first** |
| `monitoring` | ✅ Yes | `proxy`, `monitoring` | Second |
| `woodpecker` | ✅ Yes | `proxy`, `monitoring` | Third |
| `homepage` | ✅ Yes | `proxy` | Any order after traefik |
| `obsidian-sync` | ❌ No | `proxy` | Any order after traefik |
| `uptime-kuma` | ❌ No | `proxy` | Any order after traefik |

## Appendix D: Tailscale (Optional Alternative Access)

The original VPS was also accessible via Tailscale at `100.94.51.44` on mesh node `jax-mind`. On a fresh server, you can optionally reinstall Tailscale for private VPN access:

```bash
curl -fsSL https://tailscale.com/install.sh | sh
tailscale up
```

This gives direct access to the server at a Tailscale IP without going through Cloudflare, useful for maintenance when public DNS is broken.
