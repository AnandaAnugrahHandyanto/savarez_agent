---
title: Production Deployment
description: Running Hermes Gateway in production with systemd, memory management, and monitoring.
---

# Production Deployment

This guide covers running Hermes Gateway as a long-lived systemd service, with attention to memory stability under sustained cron workloads.

## Systemd Service

The installer creates a user service at `~/.config/systemd/user/hermes-gateway.service`. For production use, consider these additions:

### Service Drop-in for Memory Stability

Create a drop-in override to preload jemalloc, a memory allocator that returns freed memory to the OS:

```bash
mkdir -p ~/.config/systemd/user/hermes-gateway.service.d
cat > ~/.config/systemd/user/hermes-gateway.service.d/memory.conf << 'EOF'
[Service]
# Preload jemalloc to prevent Python memory fragmentation.
# Without this, gateway RSS grows continuously under cron load
# because Python's pymalloc allocator never returns memory to the OS.
Environment="LD_PRELOAD=/usr/lib/x86_64-linux-gnu/libjemalloc.so.2"
EOF
systemctl --user daemon-reload
systemctl --user restart hermes-gateway
```

:::note
`LD_PRELOAD` and `Environment` are valid systemd unit keys. They are set directly in the unit file -- do not try to export them in `ExecStartPre` or wrapper scripts, as those are stripped by systemd's environment sanitization.
:::

### Verifying jemalloc is Active

After restart, confirm the allocator is loaded:

```bash
cat /proc/$(pgrep -f 'hermes_cli.main.*gateway' | head -1)/maps | grep jemalloc
```

You should see several lines mapping `libjemalloc.so.2`.

### Why jemalloc

Python's default allocator (pymalloc) manages memory in 4MB "arenas." When Python objects are freed, the memory is kept for reuse within the process but never returned to the operating system. The `VmRSS` of the process -- what the OS reports as resident memory -- only grows.

Under heavy cron workloads with many short-lived subagent sessions, this causes gateway RSS to climb from ~400MB toward several GB over hours. The gateway itself is not leaking memory in the traditional sense -- it is holding onto memory that Python's allocator has marked as "available for reuse" but cannot release.

jemalloc solves this by actively returning unused pages to the OS. With jemalloc loaded, gateway RSS stays flat under the same workload.

### Alternatives

- **tcmalloc** (Google's thread-caching malloc) also works: replace the `LD_PRELOAD` path with `/usr/lib/x86_64-linux-gnu/libtcmalloc.so.4` if available.
- **`malloc_trim`** via a preload hook calls `malloc_trim(0)` periodically to release glibc heap memory to the OS. This is a supplement to jemalloc, not a replacement.

## Memory Monitoring

### Watchdog Script

The gateway includes a memory watchdog that restarts the service if RSS exceeds a threshold. Install it as a cron job:

```bash
cat > ~/.hermes/scripts/gateway_mem_watchdog.py << 'PYEOF'
#!/usr/bin/env python3
"""Restart gateway if RSS exceeds threshold."""
import subprocess, sys

LIMIT_MB = 4096  # 4 GB
GATEWAY_SERVICE = "hermes-gateway"
PROC_PATTERN = "hermes_cli.main"

def get_rss_mb(pid):
    try:
        with open(f"/proc/{pid}/status") as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    return int(line.split()[1]) / 1024
    except (FileNotFoundError, ValueError):
        pass
    return 0

def main():
    result = subprocess.run(["pgrep", "-f", PROC_PATTERN],
                          capture_output=True, text=True)
    if result.returncode != 0:
        sys.exit(0)
    pids = [int(p) for p in result.stdout.strip().split("\n") if p]
    total = sum(get_rss_mb(p) for p in pids)
    if total >= LIMIT_MB:
        subprocess.run(["systemctl", "--user", "restart", f"{GATEWAY_SERVICE}.service"],
                      capture_output=True, timeout=30)
    sys.exit(0)

main()
PYEOF
chmod +x ~/.hermes/scripts/gateway_mem_watchdog.py
```

Add to crontab:

```bash
# Check gateway memory every 2 minutes
*/2 * * * * /usr/bin/python3 /root/.hermes/scripts/gateway_mem_watchdog.py
```

:::tip
With jemalloc loaded, the 4GB threshold is generous. Gateway RSS typically stays under 1GB even under heavy load. If the watchdog triggers, something unusual is happening.
:::

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| RSS grows 1-2 MB/min steadily | Python allocator fragmentation | Install jemalloc via `LD_PRELOAD` |
| RSS spikes to 2+ GB then drops | Cron subagent burst | Normal -- jemalloc returns memory after tasks complete |
| RSS grows and never drops | Confirmed memory leak (upstream bug) | [File an issue](https://github.com/NousResearch/hermes-agent/issues) with `VmRSS` trace |
| `libjemalloc.so.2: cannot open` | Wrong library path | Find correct path: `find /usr -name 'libjemalloc*'` |
| systemd ignores `LD_PRELOAD` | Syntax error in drop-in | Run `systemctl --user daemon-reload` after editing |

## See Also

- [GitHub Issue #25315](https://github.com/NousResearch/hermes-agent/issues/25315) -- agent cache memory leak (fixed in current main)
- [GitHub Issue #29298](https://github.com/NousResearch/hermes-agent/issues/29298) -- aiohttp ClientSession leak (fixed in current main)
- [Cron Guide](./cron-troubleshooting.md)
