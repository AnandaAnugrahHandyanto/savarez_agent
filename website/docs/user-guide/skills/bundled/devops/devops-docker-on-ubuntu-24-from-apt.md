---
title: "Docker On Ubuntu 24 From Apt — Install Docker Engine, Compose v2, and Buildx on Ubuntu 24"
sidebar_label: "Docker On Ubuntu 24 From Apt"
description: "Install Docker Engine, Compose v2, and Buildx on Ubuntu 24"
---

{/* This page is auto-generated from the skill's SKILL.md by website/scripts/generate-skill-docs.py. Edit the source SKILL.md, not this page. */}

# Docker On Ubuntu 24 From Apt

Install Docker Engine, Compose v2, and Buildx on Ubuntu 24.04 using apt, with sudo credentials loaded from ~/.config/mizuki/secrets.env when needed.

## Skill metadata

| | |
|---|---|
| Source | Bundled (installed by default) |
| Path | `skills/devops/docker-on-ubuntu-24-from-apt` |

## Reference: full SKILL.md

:::info
The following is the complete skill definition that Hermes loads when this skill is triggered. This is what the agent sees as instructions when the skill is active.
:::

# Docker on Ubuntu 24.04 from apt

Use this skill when:
- Docker is needed on Ubuntu 24.04 / Noble
- `docker` is not installed yet
- local sudo credentials are stored in `~/.config/mizuki/secrets.env`
- you want the native Ubuntu apt packages rather than Docker's upstream repo

## Why this skill exists

On Ubuntu 24.04, installing `docker.io` plus `docker-compose-v2` is not always enough for a complete modern Docker toolchain.
A practical finding from real execution:
- `docker.io` installs Docker Engine
- `docker-compose-v2` installs `docker compose`
- but `docker buildx` may still be missing
- install `docker-buildx` explicitly

Also, after `usermod -aG docker <user>`, the current shell usually does **not** pick up the new group immediately. A new terminal or `newgrp docker` is needed.

## Prerequisites

- Ubuntu with `apt-get`
- sudo access
- if using local secrets workflow, `SUDO_PASSWORD` present in:
  - `~/.config/mizuki/secrets.env`

## Recommended package set

Install:
- `docker.io`
- `docker-compose-v2`
- `docker-buildx`

These bring in supporting packages like:
- `containerd`
- `runc`
- `bridge-utils`
- `pigz`

## Install workflow

### 1) Confirm OS and package candidates

```bash
. /etc/os-release
printf 'ID=%s\nVERSION_ID=%s\nPRETTY_NAME=%s\n' "$ID" "$VERSION_ID" "$PRETTY_NAME"
apt-cache policy docker.io docker-compose-v2 docker-buildx
```

### 2) Confirm sudo secret exists if using the secrets-file path

Check `~/.config/mizuki/secrets.env` for a non-empty `SUDO_PASSWORD`.
Do **not** store the password in memory.

### 3) Run install with reliable sudo

If plain shell piping to `sudo -S` is flaky, use Python subprocess as documented in the `sudo-from-secrets-file` skill.

Package install sequence:

```bash
sudo apt-get update
sudo apt-get install -y docker.io docker-compose-v2 docker-buildx
sudo systemctl enable --now docker
sudo usermod -aG docker "$USER"
```

If acting on behalf of the desktop user explicitly, replace `$USER` with that username, e.g. `h`.

## Verification

### 1) Check binaries and service

```bash
docker --version
docker compose version
docker buildx version
systemctl is-enabled docker
systemctl is-active docker
```

Expected service state:
- enabled
- active

### 2) Check whether current session can access the socket

```bash
docker ps
```

If you get:
- `permission denied while trying to connect to the docker API at unix:///var/run/docker.sock`

that usually means the shell has not picked up the new `docker` group yet.

### 3) Temporary same-session workaround

```bash
sg docker -c 'docker ps'
```

This is useful for immediate verification from automation.

### 4) End-to-end runtime test

```bash
sg docker -c 'docker pull hello-world && docker run --rm hello-world'
```

If Buildx is installed too, you can also verify:

```bash
sg docker -c 'docker buildx version'
```

Successful `hello-world` output confirms:
- Docker client works
- daemon is running
- image pull works
- container runtime works

## Post-install note for the user

Tell the user to do one of these before using Docker normally from their own shell:

```bash
newgrp docker
```

or simply open a new terminal window/tab.

Then re-test:

```bash
docker ps
docker --version
docker compose version
docker buildx version
```

## Pitfalls

- `docker.io` does **not** guarantee `docker buildx` is available on Ubuntu 24.04; install `docker-buildx` explicitly.
- `docker ps` may fail right after install even though setup is correct, because the current shell is missing the updated group membership.
- `debconf` warnings about dialog/readline in non-interactive terminal sessions are normal during apt installs here.
- Do not assume Podman is present as a fallback; check first.

## Good final summary

Report all of:
- installed packages
- Docker service enabled/running
- user added to `docker` group
- end-to-end `hello-world` verification succeeded
- user must open a new terminal or run `newgrp docker`
