"""
/ratelimit subcommand handlers.

  /ratelimit status        — show state, rpm, per-provider limits
  /ratelimit enable        — re-enable (restores rpm from config default)
  /ratelimit disable       — set rpm=0 for this session
  /ratelimit set <rpm>     — set rpm immediately and persist to config.yaml (0–3600)
"""

from __future__ import annotations
import sys
from pathlib import Path


def _validate_rpm(rpm: any) -> int:
    """
    Validate and normalize RPM value.

    Handles invalid values gracefully:
    - Non-integer values → 0 (disabled)
    - Negative values → 0 (disabled)
    - Values > 3600 → 3600 (max allowed)
    - None/missing → 0 (disabled)

    Args:
        rpm: RPM value from config or env var

    Returns:
        Validated RPM value (0-3600)
    """
    try:
        rpm_int = int(rpm)
    except (TypeError, ValueError):
        return 0  # Invalid value → disabled

    if rpm_int < 0:
        return 0  # Negative → disabled
    if rpm_int > 3600:
        return 3600  # Cap at max

    return rpm_int


def _get_registry():
    """Get the rate limiter registry from the current agent instance."""
    try:
        # Try to get the agent from the global reference in cli.py
        import cli
        agent = getattr(cli, '_active_agent_ref', None)
        if agent and hasattr(agent, '_rl_registry'):
            return agent._rl_registry
    except Exception:
        pass
    # Fallback: create a new registry from config
    try:
        from hermes_cli.config import load_config
        # Try importing from agent.rate_limiter first
        try:
            from agent.rate_limiter import make_registry
        except ImportError:
            # Fallback to direct import if running as plugin
            import importlib.util
            # Try multiple possible locations for rate_limiter.py
            possible_paths = [
                Path(__file__).parent.parent.parent / 'agent' / 'rate_limiter.py',  # dev directory
                Path(__file__).parent.parent.parent.parent / 'agent' / 'rate_limiter.py',  # installed directory
            ]
            rate_limiter_module = None
            for path in possible_paths:
                if path.exists():
                    spec = importlib.util.spec_from_file_location('rate_limiter', path)
                    rate_limiter_module = importlib.util.module_from_spec(spec)
                    sys.modules['rate_limiter'] = rate_limiter_module
                    spec.loader.exec_module(rate_limiter_module)
                    break
            
            if rate_limiter_module is None:
                raise ImportError("Could not find rate_limiter.py")
            
            make_registry = rate_limiter_module.make_registry
        return make_registry(load_config())
    except Exception:
        # Last resort: create a minimal registry
        try:
            from agent.rate_limiter import ProviderRateLimiterRegistry
        except ImportError:
            import importlib.util
            # Try multiple possible locations for rate_limiter.py
            possible_paths = [
                Path(__file__).parent.parent.parent / 'agent' / 'rate_limiter.py',  # dev directory
                Path(__file__).parent.parent.parent.parent / 'agent' / 'rate_limiter.py',  # installed directory
            ]
            rate_limiter_module = None
            for path in possible_paths:
                if path.exists():
                    spec = importlib.util.spec_from_file_location('rate_limiter', path)
                    rate_limiter_module = importlib.util.module_from_spec(spec)
                    sys.modules['rate_limiter'] = rate_limiter_module
                    spec.loader.exec_module(rate_limiter_module)
                    break
            
            if rate_limiter_module is None:
                raise ImportError("Could not find rate_limiter.py")
            
            ProviderRateLimiterRegistry = rate_limiter_module.ProviderRateLimiterRegistry
        return ProviderRateLimiterRegistry(0, {})


def _save_rpm_to_config(rpm: int) -> bool:
    """Save RPM setting to config.yaml for persistence."""
    try:
        from hermes_constants import get_hermes_home
        import yaml

        config_path = get_hermes_home() / 'config.yaml'
        if not config_path.exists():
            return False

        with open(config_path, 'r') as f:
            config = yaml.safe_load(f) or {}

        # Ensure rate_limit section exists
        if 'rate_limit' not in config:
            config['rate_limit'] = {}

        # Update the requests_per_minute setting
        config['rate_limit']['requests_per_minute'] = rpm

        # Remove providers section to use only requests_per_minute
        if 'providers' in config['rate_limit']:
            del config['rate_limit']['providers']

        # Write back to config
        with open(config_path, 'w') as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)

        return True
    except Exception as e:
        # Log the error for debugging
        import sys
        print(f"Error saving config: {e}", file=sys.stderr)
        return False


def handle(raw_args: str) -> str:
    """
    Handle /ratelimit slash command.

    Args:
        raw_args: Raw command arguments as a string

    Returns:
        Response message
    """
    registry = _get_registry()
    parts = raw_args.strip().split()
    sub = parts[0].lower() if parts else "status"

    if sub == "status":
        return _status(registry)
    if sub == "enable":
        return _enable(registry)
    if sub == "disable":
        registry.set_default_rpm(0)
        return "🔴 Rate limiter disabled for this session. Edit config.yaml to persist."
    if sub == "set":
        if len(parts) < 2:
            return "Usage: /ratelimit set <rpm>  (e.g. /ratelimit set 40)"
        try:
            rpm = int(parts[1])
        except ValueError:
            return f"❌ '{parts[1]}' is not a valid number."
        if not 0 <= rpm <= 3600:
            return "❌ RPM must be 0–3600."
        registry.set_default_rpm(rpm)
        # Persist to config.yaml
        saved = _save_rpm_to_config(rpm)
        if saved:
            # Reload the registry from config to ensure consistency
            try:
                from hermes_cli.config import load_config
                registry.reload_from_config(load_config())
            except Exception:
                pass  # Silently fail on reload errors
            return f"✅ Rate limiter set to {rpm} rpm and saved to config.yaml."
        else:
            return f"✅ Rate limiter set to {rpm} rpm (config.yaml save failed)."
    return f"Unknown subcommand '{sub}'. Try: enable, disable, status, set <rpm>"


def _status(registry) -> str:
    """Generate status message."""
    rpm = registry.resolve(None).rpm
    state = f"🟢 enabled ({rpm} rpm)" if rpm > 0 else "🔴 disabled (rpm=0)"
    lines = [f"Rate limiter: {state}"]
    per_provider = [
        f"  {name}: {lim.rpm} rpm"
        for name, lim in registry._providers.items()
        if lim.rpm > 0
    ]
    if per_provider:
        lines.append("Per-provider:")
        lines.extend(per_provider)
    return "\n".join(lines)


def _enable(registry) -> str:
    """Enable rate limiter by restoring from config."""
    if registry.resolve(None).rpm > 0:
        return f"✅ Already enabled ({registry.resolve(None).rpm} rpm)."
    # Load the rate from config
    try:
        from hermes_cli.config import load_config
        config = load_config()
        rate_limit_config = config.get('rate_limit', {})
        rpm = _validate_rpm(rate_limit_config.get('requests_per_minute'))
    except Exception:
        rpm = 0  # Fallback to disabled on error
    registry.set_default_rpm(rpm)
    if rpm > 0:
        return f"✅ Rate limiter enabled ({rpm} rpm). Use /ratelimit set <rpm> to change."
    else:
        return "⚠️  Rate limiter enabled but config has no valid RPM. Use /ratelimit set <rpm> to set a value."
