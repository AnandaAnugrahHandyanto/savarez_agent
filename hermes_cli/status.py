"""
Status command for hermes CLI.

Shows the status of all Hermes Agent components.
"""

import io
import json
import os
import sys
import subprocess
from contextlib import redirect_stdout
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.resolve()

from hermes_cli.auth import AuthError, resolve_provider
from hermes_cli.bootstrap_contract import build_bootstrap_summary, collect_provider_readiness
from hermes_cli.colors import Colors, color
from hermes_cli.config import get_env_path, get_env_value, get_hermes_home, load_config
from hermes_cli.models import provider_label
from hermes_cli.nous_subscription import get_nous_subscription_features
from hermes_cli.runtime_provider import resolve_requested_provider
from hermes_constants import OPENROUTER_MODELS_URL
from tools.tool_backend_helpers import managed_nous_tools_enabled

def check_mark(ok: bool) -> str:
    if ok:
        return color("✓", Colors.GREEN)
    return color("✗", Colors.RED)

def redact_key(key: str) -> str:
    """Redact an API key for display."""
    if not key:
        return "(not set)"
    if len(key) < 12:
        return "***"
    return key[:4] + "..." + key[-4:]


def _format_iso_timestamp(value) -> str:
    """Format ISO timestamps for status output, converting to local timezone."""
    if not value or not isinstance(value, str):
        return "(unknown)"
    from datetime import datetime, timezone
    text = value.strip()
    if not text:
        return "(unknown)"
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
    except Exception:
        return value
    return parsed.astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")


def _configured_model_label(config: dict) -> str:
    """Return the configured default model from config.yaml."""
    model_cfg = config.get("model")
    if isinstance(model_cfg, dict):
        model = (model_cfg.get("default") or model_cfg.get("name") or "").strip()
    elif isinstance(model_cfg, str):
        model = model_cfg.strip()
    else:
        model = ""
    return model or "(not set)"


def _effective_provider_label() -> str:
    """Return the provider label matching current CLI runtime resolution."""
    requested = resolve_requested_provider()
    try:
        effective = resolve_provider(requested)
    except AuthError:
        effective = requested or "auto"

    if effective == "openrouter" and get_env_value("OPENAI_BASE_URL"):
        effective = "custom"

    return provider_label(effective)


def _platform_config_snapshot(name: str, token_var: str, home_var: str | None) -> dict:
    token = os.getenv(token_var, "")
    configured = bool(token)
    home_channel = os.getenv(home_var, "") if home_var else ""
    return {
        "name": name,
        "configured": configured,
        "home_channel": home_channel or None,
    }


def _gateway_service_snapshot() -> dict:
    manager = "unsupported"
    service_running = False
    runtime_state = None
    exit_reason = None
    running_pid = None
    platforms = {}

    try:
        from gateway.status import get_running_pid, read_runtime_status

        running_pid = get_running_pid()
        runtime = read_runtime_status() or {}
        runtime_state = runtime.get("gateway_state")
        exit_reason = runtime.get("exit_reason")
        platforms = runtime.get("platforms") or {}
    except Exception:
        runtime = {}

    if sys.platform.startswith("linux"):
        manager = "systemd-user"
        try:
            from hermes_cli.gateway import get_service_name

            result = subprocess.run(
                ["systemctl", "--user", "is-active", get_service_name()],
                capture_output=True,
                text=True,
                timeout=5,
            )
            service_running = result.stdout.strip() == "active"
        except Exception:
            service_running = bool(running_pid)
    elif sys.platform == "darwin":
        manager = "launchd"
        try:
            from hermes_cli.gateway import get_launchd_label

            result = subprocess.run(
                ["launchctl", "list", get_launchd_label()],
                capture_output=True,
                text=True,
                timeout=5,
            )
            service_running = result.returncode == 0
        except Exception:
            service_running = bool(running_pid)

    return {
        "manager": manager,
        "service_running": service_running,
        "running_pid": running_pid,
        "runtime_state": runtime_state,
        "exit_reason": exit_reason,
        "platforms": platforms,
    }


def _collect_status_snapshot(*, show_all: bool, deep: bool) -> dict:
    try:
        config = load_config()
    except Exception:
        config = {}

    env_path = get_env_path()
    hermes_home = get_hermes_home()
    provider_readiness = collect_provider_readiness(config, quiet=True)

    keys = {
        "OpenRouter": "OPENROUTER_API_KEY",
        "OpenAI": "OPENAI_API_KEY",
        "Z.AI/GLM": "GLM_API_KEY",
        "Kimi": "KIMI_API_KEY",
        "MiniMax": "MINIMAX_API_KEY",
        "MiniMax-CN": "MINIMAX_CN_API_KEY",
        "Firecrawl": "FIRECRAWL_API_KEY",
        "Tavily": "TAVILY_API_KEY",
        "Browserbase": "BROWSERBASE_API_KEY",
        "FAL": "FAL_KEY",
        "Tinker": "TINKER_API_KEY",
        "WandB": "WANDB_API_KEY",
        "ElevenLabs": "ELEVENLABS_API_KEY",
        "GitHub": "GITHUB_TOKEN",
    }
    api_keys = {}
    for label, env_var in keys.items():
        value = get_env_value(env_var) or ""
        api_keys[label] = {
            "configured": bool(value),
            "value": value if show_all else redact_key(value),
        }

    anthropic_value = get_env_value("ANTHROPIC_TOKEN") or get_env_value("ANTHROPIC_API_KEY") or ""
    api_keys["Anthropic"] = {
        "configured": bool(anthropic_value),
        "value": anthropic_value if show_all else redact_key(anthropic_value),
    }

    oauth = {
        "nous_portal": {"logged_in": False},
        "openai_codex": {"logged_in": False},
    }
    try:
        from hermes_cli.auth import get_nous_auth_status, get_codex_auth_status

        with redirect_stdout(io.StringIO()):
            oauth["nous_portal"] = get_nous_auth_status() or {"logged_in": False}
            oauth["openai_codex"] = get_codex_auth_status() or {"logged_in": False}
    except Exception:
        pass

    terminal_env = os.getenv("TERMINAL_ENV", "")
    if not terminal_env:
        try:
            terminal_env = config.get("terminal", {}).get("backend", "local")
        except Exception:
            terminal_env = "local"

    platforms = {
        "Telegram": ("TELEGRAM_BOT_TOKEN", "TELEGRAM_HOME_CHANNEL"),
        "Discord": ("DISCORD_BOT_TOKEN", "DISCORD_HOME_CHANNEL"),
        "WhatsApp": ("WHATSAPP_ENABLED", None),
        "Signal": ("SIGNAL_HTTP_URL", "SIGNAL_HOME_CHANNEL"),
        "Slack": ("SLACK_BOT_TOKEN", None),
        "Email": ("EMAIL_ADDRESS", "EMAIL_HOME_ADDRESS"),
        "SMS": ("TWILIO_ACCOUNT_SID", "SMS_HOME_CHANNEL"),
        "DingTalk": ("DINGTALK_CLIENT_ID", None),
        "Feishu": ("FEISHU_APP_ID", "FEISHU_HOME_CHANNEL"),
        "WeCom": ("WECOM_BOT_ID", "WECOM_HOME_CHANNEL"),
    }
    messaging = [_platform_config_snapshot(name, token_var, home_var) for name, (token_var, home_var) in platforms.items()]

    gateway = _gateway_service_snapshot()

    jobs_total = 0
    jobs_active = 0
    jobs_file = hermes_home / "cron" / "jobs.json"
    if jobs_file.exists():
        try:
            with open(jobs_file, encoding="utf-8") as f:
                job_data = json.load(f)
            jobs = job_data.get("jobs", [])
            jobs_total = len(jobs)
            jobs_active = len([job for job in jobs if job.get("enabled", True)])
        except Exception:
            pass

    active_sessions = 0
    sessions_file = hermes_home / "sessions" / "sessions.json"
    if sessions_file.exists():
        try:
            with open(sessions_file, encoding="utf-8") as f:
                active_sessions = len(json.load(f))
        except Exception:
            pass

    deep_checks = {}
    if deep:
        openrouter_key = os.getenv("OPENROUTER_API_KEY", "")
        if openrouter_key:
            try:
                import httpx

                response = httpx.get(
                    OPENROUTER_MODELS_URL,
                    headers={"Authorization": f"Bearer {openrouter_key}"},
                    timeout=10,
                )
                deep_checks["openrouter"] = {
                    "ok": response.status_code == 200,
                    "status_code": response.status_code,
                }
            except Exception as exc:
                deep_checks["openrouter"] = {
                    "ok": False,
                    "error": str(exc),
                }
        try:
            import socket

            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex(("127.0.0.1", 18789))
            sock.close()
            deep_checks["gateway_port_18789"] = {"in_use": result == 0}
        except OSError:
            pass

    env_exists = env_path.exists()
    config_exists = (hermes_home / "config.yaml").exists() or (PROJECT_ROOT / "cli-config.yaml").exists()
    issues = []
    if gateway.get("runtime_state") in {"startup_failed", "stopped"} and gateway.get("exit_reason"):
        issues.append(gateway["exit_reason"])

    bootstrap = build_bootstrap_summary(
        env_exists=env_exists,
        config_exists=config_exists,
        provider_ready=provider_readiness["configured"],
        gateway_configured=any(item["configured"] for item in messaging),
        gateway_running=bool(gateway["service_running"] or gateway["running_pid"]),
        issues=issues,
    )

    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "environment": {
            "project_root": str(PROJECT_ROOT),
            "hermes_home": str(hermes_home),
            "python_version": sys.version.split()[0],
            "env_file_exists": env_exists,
            "config_file_exists": config_exists,
        },
        "model": {
            "configured_model": _configured_model_label(config),
            "effective_provider": _effective_provider_label(),
        },
        "providers": {
            "readiness": provider_readiness,
            "api_keys": api_keys,
            "oauth": oauth,
        },
        "terminal": {
            "backend": terminal_env,
            "sudo_enabled": bool(os.getenv("SUDO_PASSWORD", "")),
        },
        "messaging": {"platforms": messaging},
        "gateway": gateway,
        "cron": {
            "jobs_total": jobs_total,
            "jobs_active": jobs_active,
        },
        "sessions": {
            "active_count": active_sessions,
        },
        "deep_checks": deep_checks,
        "bootstrap": bootstrap,
    }


def show_status(args):
    """Show status of all Hermes Agent components."""
    show_all = getattr(args, 'all', False)
    deep = getattr(args, 'deep', False)
    json_mode = getattr(args, "json", False)

    if json_mode:
        snapshot = _collect_status_snapshot(show_all=show_all, deep=deep)
        print(json.dumps(snapshot, indent=2, ensure_ascii=False))
        return
    
    print()
    print(color("┌─────────────────────────────────────────────────────────┐", Colors.CYAN))
    print(color("│                 ⚕ Hermes Agent Status                  │", Colors.CYAN))
    print(color("└─────────────────────────────────────────────────────────┘", Colors.CYAN))
    
    # =========================================================================
    # Environment
    # =========================================================================
    print()
    print(color("◆ Environment", Colors.CYAN, Colors.BOLD))
    print(f"  Project:      {PROJECT_ROOT}")
    print(f"  Python:       {sys.version.split()[0]}")
    
    env_path = get_env_path()
    print(f"  .env file:    {check_mark(env_path.exists())} {'exists' if env_path.exists() else 'not found'}")

    try:
        config = load_config()
    except Exception:
        config = {}

    print(f"  Model:        {_configured_model_label(config)}")
    print(f"  Provider:     {_effective_provider_label()}")
    
    # =========================================================================
    # API Keys
    # =========================================================================
    print()
    print(color("◆ API Keys", Colors.CYAN, Colors.BOLD))
    
    keys = {
        "OpenRouter": "OPENROUTER_API_KEY",
        "OpenAI": "OPENAI_API_KEY",
        "Z.AI/GLM": "GLM_API_KEY",
        "Kimi": "KIMI_API_KEY",
        "MiniMax": "MINIMAX_API_KEY",
        "MiniMax-CN": "MINIMAX_CN_API_KEY",
        "Firecrawl": "FIRECRAWL_API_KEY",
        "Tavily": "TAVILY_API_KEY",
        "Browserbase": "BROWSERBASE_API_KEY",  # Optional — local browser works without this
        "FAL": "FAL_KEY",
        "Tinker": "TINKER_API_KEY",
        "WandB": "WANDB_API_KEY",
        "ElevenLabs": "ELEVENLABS_API_KEY",
        "GitHub": "GITHUB_TOKEN",
    }
    
    for name, env_var in keys.items():
        value = get_env_value(env_var) or ""
        has_key = bool(value)
        display = redact_key(value) if not show_all else value
        print(f"  {name:<12}  {check_mark(has_key)} {display}")

    anthropic_value = (
        get_env_value("ANTHROPIC_TOKEN")
        or get_env_value("ANTHROPIC_API_KEY")
        or ""
    )
    anthropic_display = redact_key(anthropic_value) if not show_all else anthropic_value
    print(f"  {'Anthropic':<12}  {check_mark(bool(anthropic_value))} {anthropic_display}")

    # =========================================================================
    # Auth Providers (OAuth)
    # =========================================================================
    print()
    print(color("◆ Auth Providers", Colors.CYAN, Colors.BOLD))

    try:
        from hermes_cli.auth import get_nous_auth_status, get_codex_auth_status
        nous_status = get_nous_auth_status()
        codex_status = get_codex_auth_status()
    except Exception:
        nous_status = {}
        codex_status = {}

    nous_logged_in = bool(nous_status.get("logged_in"))
    print(
        f"  {'Nous Portal':<12}  {check_mark(nous_logged_in)} "
        f"{'logged in' if nous_logged_in else 'not logged in (run: hermes model)'}"
    )
    if nous_logged_in:
        portal_url = nous_status.get("portal_base_url") or "(unknown)"
        access_exp = _format_iso_timestamp(nous_status.get("access_expires_at"))
        key_exp = _format_iso_timestamp(nous_status.get("agent_key_expires_at"))
        refresh_label = "yes" if nous_status.get("has_refresh_token") else "no"
        print(f"    Portal URL: {portal_url}")
        print(f"    Access exp: {access_exp}")
        print(f"    Key exp:    {key_exp}")
        print(f"    Refresh:    {refresh_label}")

    codex_logged_in = bool(codex_status.get("logged_in"))
    print(
        f"  {'OpenAI Codex':<12}  {check_mark(codex_logged_in)} "
        f"{'logged in' if codex_logged_in else 'not logged in (run: hermes model)'}"
    )
    codex_auth_file = codex_status.get("auth_store")
    if codex_auth_file:
        print(f"    Auth file:  {codex_auth_file}")
    codex_last_refresh = _format_iso_timestamp(codex_status.get("last_refresh"))
    if codex_status.get("last_refresh"):
        print(f"    Refreshed:  {codex_last_refresh}")
    if codex_status.get("error") and not codex_logged_in:
        print(f"    Error:      {codex_status.get('error')}")

    # =========================================================================
    # Nous Subscription Features
    # =========================================================================
    if managed_nous_tools_enabled():
        features = get_nous_subscription_features(config)
        print()
        print(color("◆ Nous Subscription Features", Colors.CYAN, Colors.BOLD))
        if not features.nous_auth_present:
            print("  Nous Portal   ✗ not logged in")
        else:
            print("  Nous Portal   ✓ managed tools available")
        for feature in features.items():
            if feature.managed_by_nous:
                state = "active via Nous subscription"
            elif feature.active:
                current = feature.current_provider or "configured provider"
                state = f"active via {current}"
            elif feature.included_by_default and features.nous_auth_present:
                state = "included by subscription, not currently selected"
            elif feature.key == "modal" and features.nous_auth_present:
                state = "available via subscription (optional)"
            else:
                state = "not configured"
            print(f"  {feature.label:<15} {check_mark(feature.available or feature.active or feature.managed_by_nous)} {state}")

    # =========================================================================
    # API-Key Providers
    # =========================================================================
    print()
    print(color("◆ API-Key Providers", Colors.CYAN, Colors.BOLD))

    apikey_providers = {
        "Z.AI / GLM":       ("GLM_API_KEY", "ZAI_API_KEY", "Z_AI_API_KEY"),
        "Kimi / Moonshot":  ("KIMI_API_KEY",),
        "MiniMax":          ("MINIMAX_API_KEY",),
        "MiniMax (China)":  ("MINIMAX_CN_API_KEY",),
    }
    for pname, env_vars in apikey_providers.items():
        key_val = ""
        for ev in env_vars:
            key_val = get_env_value(ev) or ""
            if key_val:
                break
        configured = bool(key_val)
        label = "configured" if configured else "not configured (run: hermes model)"
        print(f"  {pname:<16} {check_mark(configured)} {label}")

    # =========================================================================
    # Terminal Configuration
    # =========================================================================
    print()
    print(color("◆ Terminal Backend", Colors.CYAN, Colors.BOLD))
    
    terminal_env = os.getenv("TERMINAL_ENV", "")
    if not terminal_env:
        # Fall back to config file value when env var isn't set
        # (hermes status doesn't go through cli.py's config loading)
        try:
            _cfg = load_config()
            terminal_env = _cfg.get("terminal", {}).get("backend", "local")
        except Exception:
            terminal_env = "local"
    print(f"  Backend:      {terminal_env}")
    
    if terminal_env == "ssh":
        ssh_host = os.getenv("TERMINAL_SSH_HOST", "")
        ssh_user = os.getenv("TERMINAL_SSH_USER", "")
        print(f"  SSH Host:     {ssh_host or '(not set)'}")
        print(f"  SSH User:     {ssh_user or '(not set)'}")
    elif terminal_env == "docker":
        docker_image = os.getenv("TERMINAL_DOCKER_IMAGE", "python:3.11-slim")
        print(f"  Docker Image: {docker_image}")
    elif terminal_env == "daytona":
        daytona_image = os.getenv("TERMINAL_DAYTONA_IMAGE", "nikolaik/python-nodejs:python3.11-nodejs20")
        print(f"  Daytona Image: {daytona_image}")
    
    sudo_password = os.getenv("SUDO_PASSWORD", "")
    print(f"  Sudo:         {check_mark(bool(sudo_password))} {'enabled' if sudo_password else 'disabled'}")
    
    # =========================================================================
    # Messaging Platforms
    # =========================================================================
    print()
    print(color("◆ Messaging Platforms", Colors.CYAN, Colors.BOLD))
    
    platforms = {
        "Telegram": ("TELEGRAM_BOT_TOKEN", "TELEGRAM_HOME_CHANNEL"),
        "Discord": ("DISCORD_BOT_TOKEN", "DISCORD_HOME_CHANNEL"),
        "WhatsApp": ("WHATSAPP_ENABLED", None),
        "Signal": ("SIGNAL_HTTP_URL", "SIGNAL_HOME_CHANNEL"),
        "Slack": ("SLACK_BOT_TOKEN", None),
        "Email": ("EMAIL_ADDRESS", "EMAIL_HOME_ADDRESS"),
        "SMS": ("TWILIO_ACCOUNT_SID", "SMS_HOME_CHANNEL"),
        "DingTalk": ("DINGTALK_CLIENT_ID", None),
        "Feishu": ("FEISHU_APP_ID", "FEISHU_HOME_CHANNEL"),
        "WeCom": ("WECOM_BOT_ID", "WECOM_HOME_CHANNEL"),
    }
    
    for name, (token_var, home_var) in platforms.items():
        token = os.getenv(token_var, "")
        has_token = bool(token)
        
        home_channel = ""
        if home_var:
            home_channel = os.getenv(home_var, "")
        
        status = "configured" if has_token else "not configured"
        if home_channel:
            status += f" (home: {home_channel})"
        
        print(f"  {name:<12}  {check_mark(has_token)} {status}")
    
    # =========================================================================
    # Gateway Status
    # =========================================================================
    print()
    print(color("◆ Gateway Service", Colors.CYAN, Colors.BOLD))
    
    if sys.platform.startswith('linux'):
        try:
            from hermes_cli.gateway import get_service_name
            _gw_svc = get_service_name()
        except Exception:
            _gw_svc = "hermes-gateway"
        try:
            result = subprocess.run(
                ["systemctl", "--user", "is-active", _gw_svc],
                capture_output=True,
                text=True,
                timeout=5
            )
            is_active = result.stdout.strip() == "active"
        except subprocess.TimeoutExpired:
            is_active = False
        print(f"  Status:       {check_mark(is_active)} {'running' if is_active else 'stopped'}")
        print("  Manager:      systemd (user)")
        
    elif sys.platform == 'darwin':
        from hermes_cli.gateway import get_launchd_label
        try:
            result = subprocess.run(
                ["launchctl", "list", get_launchd_label()],
                capture_output=True,
                text=True,
                timeout=5
            )
            is_loaded = result.returncode == 0
        except subprocess.TimeoutExpired:
            is_loaded = False
        print(f"  Status:       {check_mark(is_loaded)} {'loaded' if is_loaded else 'not loaded'}")
        print("  Manager:      launchd")
    else:
        print(f"  Status:       {color('N/A', Colors.DIM)}")
        print("  Manager:      (not supported on this platform)")
    
    # =========================================================================
    # Cron Jobs
    # =========================================================================
    print()
    print(color("◆ Scheduled Jobs", Colors.CYAN, Colors.BOLD))
    
    jobs_file = get_hermes_home() / "cron" / "jobs.json"
    if jobs_file.exists():
        try:
            with open(jobs_file, encoding="utf-8") as f:
                data = json.load(f)
                jobs = data.get("jobs", [])
                enabled_jobs = [j for j in jobs if j.get("enabled", True)]
                print(f"  Jobs:         {len(enabled_jobs)} active, {len(jobs)} total")
        except Exception:
            print("  Jobs:         (error reading jobs file)")
    else:
        print("  Jobs:         0")
    
    # =========================================================================
    # Sessions
    # =========================================================================
    print()
    print(color("◆ Sessions", Colors.CYAN, Colors.BOLD))
    
    sessions_file = get_hermes_home() / "sessions" / "sessions.json"
    if sessions_file.exists():
        try:
            with open(sessions_file, encoding="utf-8") as f:
                data = json.load(f)
                print(f"  Active:       {len(data)} session(s)")
        except Exception:
            print("  Active:       (error reading sessions file)")
    else:
        print("  Active:       0")
    
    # =========================================================================
    # Deep checks
    # =========================================================================
    if deep:
        print()
        print(color("◆ Deep Checks", Colors.CYAN, Colors.BOLD))
        
        # Check OpenRouter connectivity
        openrouter_key = os.getenv("OPENROUTER_API_KEY", "")
        if openrouter_key:
            try:
                import httpx
                response = httpx.get(
                    OPENROUTER_MODELS_URL,
                    headers={"Authorization": f"Bearer {openrouter_key}"},
                    timeout=10
                )
                ok = response.status_code == 200
                print(f"  OpenRouter:   {check_mark(ok)} {'reachable' if ok else f'error ({response.status_code})'}")
            except Exception as e:
                print(f"  OpenRouter:   {check_mark(False)} error: {e}")
        
        # Check gateway port
        try:
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex(('127.0.0.1', 18789))
            sock.close()
            # Port in use = gateway likely running
            port_in_use = result == 0
            # This is informational, not necessarily bad
            print(f"  Port 18789:   {'in use' if port_in_use else 'available'}")
        except OSError:
            pass
    
    print()
    print(color("─" * 60, Colors.DIM))
    print(color("  Run 'hermes doctor' for detailed diagnostics", Colors.DIM))
    print(color("  Run 'hermes setup' to configure", Colors.DIM))
    print()
