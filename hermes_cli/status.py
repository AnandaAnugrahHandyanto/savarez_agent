"""
Status command for hermes CLI.

Shows the status of all Hermes Agent components.
"""

import os
import sys
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.resolve()

from hermes_cli.auth import AuthError, resolve_provider
from hermes_cli.colors import Colors, color
from hermes_cli.config import get_env_path, get_env_value, get_hermes_home, load_config
from hermes_cli.models import provider_label
from hermes_cli.nous_subscription import get_nous_subscription_features
from hermes_cli.runtime_provider import resolve_requested_provider
from hermes_constants import OPENROUTER_MODELS_URL
from tools.tool_backend_helpers import managed_nous_tools_enabled


def _get_repo_context_capability_summary() -> list[dict[str, str]]:
    """Return read-only repo-context capability summaries for status output."""
    try:
        from tools.registry import discover_builtin_tools
        discover_builtin_tools()
        from agent.capability_catalog import summarize_repo_context_capabilities

        return summarize_repo_context_capabilities()
    except Exception:
        return []


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


def _effective_provider_state() -> tuple[str, bool, bool]:
    """Return provider label plus readiness/blocking flags."""
    requested = resolve_requested_provider()
    try:
        effective = resolve_provider(requested)
        blocked = False
        ready = True
    except AuthError:
        effective = requested or "auto"
        blocked = bool(requested and requested != "auto")
        ready = False

    if effective == "openrouter" and get_env_value("OPENAI_BASE_URL"):
        effective = "custom"

    return provider_label(effective), ready, blocked


def _count_configured_api_keys() -> int:
    env_vars = [
        "OPENROUTER_API_KEY",
        "OPENAI_API_KEY",
        "GLM_API_KEY",
        "KIMI_API_KEY",
        "MINIMAX_API_KEY",
        "MINIMAX_CN_API_KEY",
        "FIRECRAWL_API_KEY",
        "TAVILY_API_KEY",
        "BROWSER_USE_API_KEY",
        "BROWSERBASE_API_KEY",
        "FAL_KEY",
        "TINKER_API_KEY",
        "WANDB_API_KEY",
        "ELEVENLABS_API_KEY",
        "GITHUB_TOKEN",
    ]
    count = sum(1 for env_var in env_vars if get_env_value(env_var))
    from hermes_cli.auth import get_anthropic_key
    if get_anthropic_key():
        count += 1
    return count


def _count_configured_platforms() -> int:
    platform_envs = [
        "TELEGRAM_BOT_TOKEN",
        "DISCORD_BOT_TOKEN",
        "WHATSAPP_ENABLED",
        "SIGNAL_HTTP_URL",
        "SLACK_BOT_TOKEN",
        "EMAIL_ADDRESS",
        "TWILIO_ACCOUNT_SID",
        "DINGTALK_CLIENT_ID",
        "FEISHU_APP_ID",
        "WECOM_BOT_ID",
        "WECOM_CALLBACK_CORP_ID",
        "WEIXIN_ACCOUNT_ID",
        "BLUEBUBBLES_SERVER_URL",
        "QQ_APP_ID",
    ]
    return sum(1 for env_var in platform_envs if os.getenv(env_var, ""))


def _count_active_jobs() -> tuple[int, int]:
    jobs_file = get_hermes_home() / "cron" / "jobs.json"
    if not jobs_file.exists():
        return 0, 0
    import json
    try:
        with open(jobs_file, encoding="utf-8") as f:
            data = json.load(f)
        jobs = data.get("jobs", [])
        enabled_jobs = [j for j in jobs if j.get("enabled", True)]
        return len(enabled_jobs), len(jobs)
    except Exception:
        return 0, 0


def _health_grade_style(grade: str) -> tuple[str, str, str]:
    mapping = {
        "healthy": ("✓", "Healthy", Colors.GREEN),
        "degraded": ("⚠", "Degraded", Colors.YELLOW),
        "blocked": ("⛔", "Blocked", Colors.RED),
        "needs_setup": ("✗", "Needs setup", Colors.RED),
    }
    return mapping.get(grade, ("⚠", grade, Colors.YELLOW))


def _overall_health_grade(*, inference_ready: bool, inference_blocked: bool, api_key_count: int, platform_count: int, active_jobs: int) -> str:
    if inference_ready and (platform_count > 0 or active_jobs > 0):
        return "healthy"
    if inference_blocked:
        return "blocked"
    if inference_ready or api_key_count > 0 or platform_count > 0 or active_jobs > 0:
        return "degraded"
    return "needs_setup"


def _health_reason(*, grade: str, inference_ready: bool, inference_blocked: bool, api_key_count: int, platform_count: int, active_jobs: int) -> str:
    if grade == "healthy":
        if active_jobs > 0 and platform_count > 0:
            return "inference OK, messaging configured, and automation running"
        if active_jobs > 0:
            return "inference OK and automation running"
        return "inference OK and at least one delivery surface is configured"
    if grade == "blocked":
        return "configured inference path exists, but auth/runtime access is unavailable"
    if grade == "degraded":
        reasons = []
        if inference_ready:
            reasons.append("inference OK")
        if api_key_count == 0:
            reasons.append("no API keys configured")
        if platform_count == 0:
            reasons.append("no messaging platforms configured")
        if active_jobs == 0:
            reasons.append("no active automation")
        return ", ".join(reasons[:3]) if reasons else "partial capability only"
    return "missing usable inference setup and no active delivery/automation surfaces"


def _print_quick_summary(config: dict) -> None:
    model_label = _configured_model_label(config)
    provider_label_text, provider_ready, provider_blocked = _effective_provider_state()
    api_key_count = _count_configured_api_keys()
    platform_count = _count_configured_platforms()
    active_jobs, total_jobs = _count_active_jobs()
    inference_ready = bool(model_label != "(not set)" and provider_ready)
    inference_blocked = bool(model_label != "(not set)" and provider_blocked)
    overall_grade = _overall_health_grade(
        inference_ready=inference_ready,
        inference_blocked=inference_blocked,
        api_key_count=api_key_count,
        platform_count=platform_count,
        active_jobs=active_jobs,
    )
    overall_reason = _health_reason(
        grade=overall_grade,
        inference_ready=inference_ready,
        inference_blocked=inference_blocked,
        api_key_count=api_key_count,
        platform_count=platform_count,
        active_jobs=active_jobs,
    )
    grade_icon, grade_label, grade_color = _health_grade_style(overall_grade)

    print()
    print(color("◆ Quick Summary", Colors.CYAN, Colors.BOLD))
    print(f"  Health:       {color(grade_icon, grade_color)} {color(grade_label, grade_color)}")
    print(f"  Reason:       {overall_reason}")
    print(f"  Inference:    {check_mark(inference_ready)} {provider_label_text} · {model_label}")
    print(f"  API Access:   {check_mark(api_key_count > 0)} {api_key_count} API key source(s) configured")
    print(f"  Messaging:    {check_mark(platform_count > 0)} {platform_count} platform(s) configured")
    jobs_text = f"{active_jobs} active / {total_jobs} total" if total_jobs else "0 active"
    print(f"  Automation:   {check_mark(active_jobs > 0)} {jobs_text}")


from hermes_constants import is_termux as _is_termux


def show_status(args):
    """Show status of all Hermes Agent components."""
    show_all = getattr(args, 'all', False)
    deep = getattr(args, 'deep', False)
    
    print()
    print(color("┌─────────────────────────────────────────────────────────┐", Colors.CYAN))
    print(color("│                 ⚕ Hermes Agent Status                  │", Colors.CYAN))
    print(color("└─────────────────────────────────────────────────────────┘", Colors.CYAN))

    try:
        config = load_config()
    except Exception:
        config = {}

    _print_quick_summary(config)

    repo_context_capabilities = _get_repo_context_capability_summary()
    if repo_context_capabilities:
        print()
        print(color("◆ Repo Context", Colors.CYAN, Colors.BOLD))
        for item in repo_context_capabilities[:4]:
            print(
                "  "
                f"{item['name']} · {item['group']} · {item['readiness_status']}"
            )
            print(
                "    "
                f"identity={item['identity_scope']} · workflow={item['workflow']} · results={item['result_mode']}"
            )
    
    # =========================================================================
    # Environment
    # =========================================================================
    print()
    print(color("◆ Environment", Colors.CYAN, Colors.BOLD))
    print(f"  Project:      {PROJECT_ROOT}")
    print(f"  Python:       {sys.version.split()[0]}")
    
    env_path = get_env_path()
    print(f"  .env file:    {check_mark(env_path.exists())} {'exists' if env_path.exists() else 'not found'}")

    print(f"  Model:        {_configured_model_label(config)}")
    provider_label_text, _, _ = _effective_provider_state()
    print(f"  Provider:     {provider_label_text}")
    
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
        "StepFun Step Plan": "STEPFUN_API_KEY",
        "MiniMax": "MINIMAX_API_KEY",
        "MiniMax-CN": "MINIMAX_CN_API_KEY",
        "Firecrawl": "FIRECRAWL_API_KEY",
        "Tavily": "TAVILY_API_KEY",
        "Browser Use": "BROWSER_USE_API_KEY",  # Optional — local browser works without this
        "Browserbase": "BROWSERBASE_API_KEY",  # Optional — direct credentials only
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

    from hermes_cli.auth import get_anthropic_key
    anthropic_value = get_anthropic_key()
    anthropic_display = redact_key(anthropic_value) if not show_all else anthropic_value
    print(f"  {'Anthropic':<12}  {check_mark(bool(anthropic_value))} {anthropic_display}")

    # =========================================================================
    # Auth Providers (OAuth)
    # =========================================================================
    print()
    print(color("◆ Auth Providers", Colors.CYAN, Colors.BOLD))

    try:
        from hermes_cli.auth import get_nous_auth_status, get_codex_auth_status, get_qwen_auth_status
        nous_status = get_nous_auth_status()
        codex_status = get_codex_auth_status()
        qwen_status = get_qwen_auth_status()
    except Exception:
        nous_status = {}
        codex_status = {}
        qwen_status = {}

    nous_logged_in = bool(nous_status.get("logged_in"))
    nous_error = nous_status.get("error")
    nous_label = "logged in" if nous_logged_in else "not logged in (run: hermes auth add nous --type oauth)"
    print(
        f"  {'Nous Portal':<12}  {check_mark(nous_logged_in)} "
        f"{nous_label}"
    )
    portal_url = nous_status.get("portal_base_url") or "(unknown)"
    access_exp = _format_iso_timestamp(nous_status.get("access_expires_at"))
    key_exp = _format_iso_timestamp(nous_status.get("agent_key_expires_at"))
    refresh_label = "yes" if nous_status.get("has_refresh_token") else "no"
    if nous_logged_in or portal_url != "(unknown)" or nous_error:
        print(f"    Portal URL: {portal_url}")
    if nous_logged_in or nous_status.get("access_expires_at"):
        print(f"    Access exp: {access_exp}")
    if nous_logged_in or nous_status.get("agent_key_expires_at"):
        print(f"    Key exp:    {key_exp}")
    if nous_logged_in or nous_status.get("has_refresh_token"):
        print(f"    Refresh:    {refresh_label}")
    if nous_error and not nous_logged_in:
        print(f"    Error:      {nous_error}")

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

    qwen_logged_in = bool(qwen_status.get("logged_in"))
    print(
        f"  {'Qwen OAuth':<12}  {check_mark(qwen_logged_in)} "
        f"{'logged in' if qwen_logged_in else 'not logged in (run: qwen auth qwen-oauth)'}"
    )
    qwen_auth_file = qwen_status.get("auth_file")
    if qwen_auth_file:
        print(f"    Auth file:  {qwen_auth_file}")
    qwen_exp = qwen_status.get("expires_at_ms")
    if qwen_exp:
        from datetime import datetime, timezone
        print(f"    Access exp: {datetime.fromtimestamp(int(qwen_exp) / 1000, tz=timezone.utc).isoformat()}")
    if qwen_status.get("error") and not qwen_logged_in:
        print(f"    Error:      {qwen_status.get('error')}")

    # =========================================================================
    # Nous Subscription Features
    # =========================================================================
    if managed_nous_tools_enabled():
        features = get_nous_subscription_features(config)
        print()
        print(color("◆ Nous Tool Gateway", Colors.CYAN, Colors.BOLD))
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
    elif nous_logged_in:
        # Logged into Nous but on the free tier — show upgrade nudge
        print()
        print(color("◆ Nous Tool Gateway", Colors.CYAN, Colors.BOLD))
        print("  Your free-tier Nous account does not include Tool Gateway access.")
        print("  Upgrade your subscription to unlock managed web, image, TTS, and browser tools.")
        try:
            portal_url = nous_status.get("portal_base_url", "").rstrip("/")
            if portal_url:
                print(f"  Upgrade: {portal_url}")
        except Exception:
            pass

    # =========================================================================
    # API-Key Providers
    # =========================================================================
    print()
    print(color("◆ API-Key Providers", Colors.CYAN, Colors.BOLD))

    apikey_providers = {
        "Z.AI / GLM":       ("GLM_API_KEY", "ZAI_API_KEY", "Z_AI_API_KEY"),
        "Kimi / Moonshot":  ("KIMI_API_KEY",),
        "StepFun Step Plan": ("STEPFUN_API_KEY",),
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
        "WeCom Callback": ("WECOM_CALLBACK_CORP_ID", None),
        "Weixin": ("WEIXIN_ACCOUNT_ID", "WEIXIN_HOME_CHANNEL"),
        "BlueBubbles": ("BLUEBUBBLES_SERVER_URL", "BLUEBUBBLES_HOME_CHANNEL"),
        "QQBot": ("QQ_APP_ID", "QQ_HOME_CHANNEL"),
        "Yuanbao": ("YUANBAO_APP_ID", "YUANBAO_HOME_CHANNEL"),
    }
    
    for name, (token_var, home_var) in platforms.items():
        token = os.getenv(token_var, "")
        has_token = bool(token)
        
        home_channel = ""
        if home_var:
            home_channel = os.getenv(home_var, "")
        # Back-compat: QQBot home channel was renamed from QQ_HOME_CHANNEL to QQBOT_HOME_CHANNEL
        if not home_channel and home_var == "QQBOT_HOME_CHANNEL":
            home_channel = os.getenv("QQ_HOME_CHANNEL", "")
        
        status = "configured" if has_token else "not configured"
        if home_channel:
            status += f" (home: {home_channel})"
        
        print(f"  {name:<12}  {check_mark(has_token)} {status}")
    
    # =========================================================================
    # Gateway Status
    # =========================================================================
    print()
    print(color("◆ Gateway Service", Colors.CYAN, Colors.BOLD))

    try:
        from hermes_cli.gateway import get_gateway_runtime_snapshot, _format_gateway_pids

        snapshot = get_gateway_runtime_snapshot()
        is_running = snapshot.running
        print(f"  Status:       {check_mark(is_running)} {'running' if is_running else 'stopped'}")
        print(f"  Manager:      {snapshot.manager}")
        if snapshot.gateway_pids:
            print(f"  PID(s):       {_format_gateway_pids(snapshot.gateway_pids)}")
        if snapshot.has_process_service_mismatch:
            print("  Service:      installed but not managing the current running gateway")
        elif _is_termux() and not snapshot.gateway_pids:
            print("  Start with:   hermes gateway")
            print("  Note:         Android may stop background jobs when Termux is suspended")
        elif snapshot.service_installed and not snapshot.service_running:
            print("  Service:      installed but stopped")
    except Exception:
        if _is_termux():
            print(f"  Status:       {color('unknown', Colors.DIM)}")
            print("  Manager:      Termux / manual process")
        elif sys.platform.startswith('linux'):
            print(f"  Status:       {color('unknown', Colors.DIM)}")
            print("  Manager:      systemd/manual")
        elif sys.platform == 'darwin':
            print(f"  Status:       {color('unknown', Colors.DIM)}")
            print("  Manager:      launchd")
        else:
            print(f"  Status:       {color('N/A', Colors.DIM)}")
            print("  Manager:      (not supported on this platform)")
    
    # =========================================================================
    # Cron Jobs
    # =========================================================================
    print()
    print(color("◆ Scheduled Jobs", Colors.CYAN, Colors.BOLD))
    
    active_jobs, total_jobs = _count_active_jobs()
    if total_jobs:
        print(f"  Jobs:         {active_jobs} active, {total_jobs} total")
    else:
        print("  Jobs:         0")
    
    # =========================================================================
    # Sessions
    # =========================================================================
    print()
    print(color("◆ Sessions", Colors.CYAN, Colors.BOLD))
    
    sessions_file = get_hermes_home() / "sessions" / "sessions.json"
    if sessions_file.exists():
        import json
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
