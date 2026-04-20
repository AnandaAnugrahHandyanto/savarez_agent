"""Helpers for bridging gateway.json and config.yaml into gateway config data."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from gateway.config_models import Platform, _normalize_unauthorized_dm_behavior

logger = logging.getLogger(__name__)


def load_legacy_gateway_json(_home: Path) -> dict:
    gw_data: dict = {}
    # Legacy fallback: gateway.json provides the base layer.
    # config.yaml keys always win when both specify the same setting.
    gateway_json_path = _home / "gateway.json"
    if gateway_json_path.exists():
        try:
            with open(gateway_json_path, "r", encoding="utf-8") as f:
                gw_data = json.load(f) or {}
            logger.info(
                "Loaded legacy %s — consider moving settings to config.yaml",
                gateway_json_path,
            )
        except Exception as e:
            logger.warning("Failed to load %s: %s", gateway_json_path, e)
    return gw_data


def apply_config_yaml_overrides(_home: Path, gw_data: dict) -> None:
    # Primary source: config.yaml
    try:
        import yaml
        config_yaml_path = _home / "config.yaml"
        if config_yaml_path.exists():
            with open(config_yaml_path, encoding="utf-8") as f:
                yaml_cfg = yaml.safe_load(f) or {}

            # Map config.yaml keys → GatewayConfig.from_dict() schema.
            # Each key overwrites whatever gateway.json may have set.
            sr = yaml_cfg.get("session_reset")
            if sr and isinstance(sr, dict):
                gw_data["default_reset_policy"] = sr

            qc = yaml_cfg.get("quick_commands")
            if qc is not None:
                if isinstance(qc, dict):
                    gw_data["quick_commands"] = qc
                else:
                    logger.warning(
                        "Ignoring invalid quick_commands in config.yaml "
                        "(expected mapping, got %s)",
                        type(qc).__name__,
                    )

            stt_cfg = yaml_cfg.get("stt")
            if isinstance(stt_cfg, dict):
                gw_data["stt"] = stt_cfg

            if "group_sessions_per_user" in yaml_cfg:
                gw_data["group_sessions_per_user"] = yaml_cfg["group_sessions_per_user"]

            if "thread_sessions_per_user" in yaml_cfg:
                gw_data["thread_sessions_per_user"] = yaml_cfg["thread_sessions_per_user"]

            streaming_cfg = yaml_cfg.get("streaming")
            if isinstance(streaming_cfg, dict):
                gw_data["streaming"] = streaming_cfg

            if "reset_triggers" in yaml_cfg:
                gw_data["reset_triggers"] = yaml_cfg["reset_triggers"]

            if "always_log_local" in yaml_cfg:
                gw_data["always_log_local"] = yaml_cfg["always_log_local"]

            if "unauthorized_dm_behavior" in yaml_cfg:
                gw_data["unauthorized_dm_behavior"] = _normalize_unauthorized_dm_behavior(
                    yaml_cfg.get("unauthorized_dm_behavior"),
                    "pair",
                )

            # Merge platforms section from config.yaml into gw_data so that
            # nested keys like platforms.webhook.extra.routes are loaded.
            yaml_platforms = yaml_cfg.get("platforms")
            platforms_data = gw_data.setdefault("platforms", {})
            if not isinstance(platforms_data, dict):
                platforms_data = {}
                gw_data["platforms"] = platforms_data
            if isinstance(yaml_platforms, dict):
                for plat_name, plat_block in yaml_platforms.items():
                    if not isinstance(plat_block, dict):
                        continue
                    existing = platforms_data.get(plat_name, {})
                    if not isinstance(existing, dict):
                        existing = {}
                    # Deep-merge extra dicts so gateway.json defaults survive
                    merged_extra = {**existing.get("extra", {}), **plat_block.get("extra", {})}
                    merged = {**existing, **plat_block}
                    if merged_extra:
                        merged["extra"] = merged_extra
                    platforms_data[plat_name] = merged
                gw_data["platforms"] = platforms_data
            for plat in Platform:
                if plat == Platform.LOCAL:
                    continue
                platform_cfg = yaml_cfg.get(plat.value)
                if not isinstance(platform_cfg, dict):
                    continue
                # Collect bridgeable keys from this platform section
                bridged = {}
                if "unauthorized_dm_behavior" in platform_cfg:
                    bridged["unauthorized_dm_behavior"] = _normalize_unauthorized_dm_behavior(
                        platform_cfg.get("unauthorized_dm_behavior"),
                        gw_data.get("unauthorized_dm_behavior", "pair"),
                    )
                if "reply_prefix" in platform_cfg:
                    bridged["reply_prefix"] = platform_cfg["reply_prefix"]
                if "require_mention" in platform_cfg:
                    bridged["require_mention"] = platform_cfg["require_mention"]
                if "free_response_channels" in platform_cfg:
                    bridged["free_response_channels"] = platform_cfg["free_response_channels"]
                if "mention_patterns" in platform_cfg:
                    bridged["mention_patterns"] = platform_cfg["mention_patterns"]
                if plat == Platform.DISCORD and "channel_skill_bindings" in platform_cfg:
                    bridged["channel_skill_bindings"] = platform_cfg["channel_skill_bindings"]
                if "channel_prompts" in platform_cfg:
                    channel_prompts = platform_cfg["channel_prompts"]
                    if isinstance(channel_prompts, dict):
                        bridged["channel_prompts"] = {str(k): v for k, v in channel_prompts.items()}
                    else:
                        bridged["channel_prompts"] = channel_prompts
                if not bridged:
                    continue
                plat_data = platforms_data.setdefault(plat.value, {})
                if not isinstance(plat_data, dict):
                    plat_data = {}
                    platforms_data[plat.value] = plat_data
                extra = plat_data.setdefault("extra", {})
                if not isinstance(extra, dict):
                    extra = {}
                    plat_data["extra"] = extra
                extra.update(bridged)

            # Slack settings → env vars (env vars take precedence)
            slack_cfg = yaml_cfg.get("slack", {})
            if isinstance(slack_cfg, dict):
                if "require_mention" in slack_cfg and not os.getenv("SLACK_REQUIRE_MENTION"):
                    os.environ["SLACK_REQUIRE_MENTION"] = str(slack_cfg["require_mention"]).lower()
                if "allow_bots" in slack_cfg and not os.getenv("SLACK_ALLOW_BOTS"):
                    os.environ["SLACK_ALLOW_BOTS"] = str(slack_cfg["allow_bots"]).lower()
                frc = slack_cfg.get("free_response_channels")
                if frc is not None and not os.getenv("SLACK_FREE_RESPONSE_CHANNELS"):
                    if isinstance(frc, list):
                        frc = ",".join(str(v) for v in frc)
                    os.environ["SLACK_FREE_RESPONSE_CHANNELS"] = str(frc)

            # Discord settings → env vars (env vars take precedence)
            discord_cfg = yaml_cfg.get("discord", {})
            if isinstance(discord_cfg, dict):
                if "require_mention" in discord_cfg and not os.getenv("DISCORD_REQUIRE_MENTION"):
                    os.environ["DISCORD_REQUIRE_MENTION"] = str(discord_cfg["require_mention"]).lower()
                frc = discord_cfg.get("free_response_channels")
                if frc is not None and not os.getenv("DISCORD_FREE_RESPONSE_CHANNELS"):
                    if isinstance(frc, list):
                        frc = ",".join(str(v) for v in frc)
                    os.environ["DISCORD_FREE_RESPONSE_CHANNELS"] = str(frc)
                if "auto_thread" in discord_cfg and not os.getenv("DISCORD_AUTO_THREAD"):
                    os.environ["DISCORD_AUTO_THREAD"] = str(discord_cfg["auto_thread"]).lower()
                if "reactions" in discord_cfg and not os.getenv("DISCORD_REACTIONS"):
                    os.environ["DISCORD_REACTIONS"] = str(discord_cfg["reactions"]).lower()
                # ignored_channels: channels where bot never responds (even when mentioned)
                ic = discord_cfg.get("ignored_channels")
                if ic is not None and not os.getenv("DISCORD_IGNORED_CHANNELS"):
                    if isinstance(ic, list):
                        ic = ",".join(str(v) for v in ic)
                    os.environ["DISCORD_IGNORED_CHANNELS"] = str(ic)
                # allowed_channels: if set, bot ONLY responds in these channels (whitelist)
                ac = discord_cfg.get("allowed_channels")
                if ac is not None and not os.getenv("DISCORD_ALLOWED_CHANNELS"):
                    if isinstance(ac, list):
                        ac = ",".join(str(v) for v in ac)
                    os.environ["DISCORD_ALLOWED_CHANNELS"] = str(ac)
                # no_thread_channels: channels where bot responds directly without creating thread
                ntc = discord_cfg.get("no_thread_channels")
                if ntc is not None and not os.getenv("DISCORD_NO_THREAD_CHANNELS"):
                    if isinstance(ntc, list):
                        ntc = ",".join(str(v) for v in ntc)
                    os.environ["DISCORD_NO_THREAD_CHANNELS"] = str(ntc)
                # allow_mentions: granular control over what the bot can ping.
                # Safe defaults (no @everyone/roles) are applied in the adapter;
                # these YAML keys only override when set and let users opt back
                # into unsafe modes (e.g. roles=true) if they actually want it.
                allow_mentions_cfg = discord_cfg.get("allow_mentions")
                if isinstance(allow_mentions_cfg, dict):
                    for yaml_key, env_key in (
                        ("everyone", "DISCORD_ALLOW_MENTION_EVERYONE"),
                        ("roles", "DISCORD_ALLOW_MENTION_ROLES"),
                        ("users", "DISCORD_ALLOW_MENTION_USERS"),
                        ("replied_user", "DISCORD_ALLOW_MENTION_REPLIED_USER"),
                    ):
                        if yaml_key in allow_mentions_cfg and not os.getenv(env_key):
                            os.environ[env_key] = str(allow_mentions_cfg[yaml_key]).lower()

            # Telegram settings → env vars (env vars take precedence)
            telegram_cfg = yaml_cfg.get("telegram", {})
            if isinstance(telegram_cfg, dict):
                if "require_mention" in telegram_cfg and not os.getenv("TELEGRAM_REQUIRE_MENTION"):
                    os.environ["TELEGRAM_REQUIRE_MENTION"] = str(telegram_cfg["require_mention"]).lower()
                if "mention_patterns" in telegram_cfg and not os.getenv("TELEGRAM_MENTION_PATTERNS"):
                    import json as _json
                    os.environ["TELEGRAM_MENTION_PATTERNS"] = _json.dumps(telegram_cfg["mention_patterns"])
                frc = telegram_cfg.get("free_response_chats")
                if frc is not None and not os.getenv("TELEGRAM_FREE_RESPONSE_CHATS"):
                    if isinstance(frc, list):
                        frc = ",".join(str(v) for v in frc)
                    os.environ["TELEGRAM_FREE_RESPONSE_CHATS"] = str(frc)
                ignored_threads = telegram_cfg.get("ignored_threads")
                if ignored_threads is not None and not os.getenv("TELEGRAM_IGNORED_THREADS"):
                    if isinstance(ignored_threads, list):
                        ignored_threads = ",".join(str(v) for v in ignored_threads)
                    os.environ["TELEGRAM_IGNORED_THREADS"] = str(ignored_threads)
                if "reactions" in telegram_cfg and not os.getenv("TELEGRAM_REACTIONS"):
                    os.environ["TELEGRAM_REACTIONS"] = str(telegram_cfg["reactions"]).lower()
                if "proxy_url" in telegram_cfg and not os.getenv("TELEGRAM_PROXY"):
                    os.environ["TELEGRAM_PROXY"] = str(telegram_cfg["proxy_url"]).strip()
                if "disable_link_previews" in telegram_cfg:
                    plat_data = platforms_data.setdefault(Platform.TELEGRAM.value, {})
                    if not isinstance(plat_data, dict):
                        plat_data = {}
                        platforms_data[Platform.TELEGRAM.value] = plat_data
                    extra = plat_data.setdefault("extra", {})
                    if not isinstance(extra, dict):
                        extra = {}
                        plat_data["extra"] = extra
                    extra["disable_link_previews"] = telegram_cfg["disable_link_previews"]

            whatsapp_cfg = yaml_cfg.get("whatsapp", {})
            if isinstance(whatsapp_cfg, dict):
                if "require_mention" in whatsapp_cfg and not os.getenv("WHATSAPP_REQUIRE_MENTION"):
                    os.environ["WHATSAPP_REQUIRE_MENTION"] = str(whatsapp_cfg["require_mention"]).lower()
                if "mention_patterns" in whatsapp_cfg and not os.getenv("WHATSAPP_MENTION_PATTERNS"):
                    os.environ["WHATSAPP_MENTION_PATTERNS"] = json.dumps(whatsapp_cfg["mention_patterns"])
                frc = whatsapp_cfg.get("free_response_chats")
                if frc is not None and not os.getenv("WHATSAPP_FREE_RESPONSE_CHATS"):
                    if isinstance(frc, list):
                        frc = ",".join(str(v) for v in frc)
                    os.environ["WHATSAPP_FREE_RESPONSE_CHATS"] = str(frc)

            # DingTalk settings → env vars (env vars take precedence)
            dingtalk_cfg = yaml_cfg.get("dingtalk", {})
            if isinstance(dingtalk_cfg, dict):
                if "require_mention" in dingtalk_cfg and not os.getenv("DINGTALK_REQUIRE_MENTION"):
                    os.environ["DINGTALK_REQUIRE_MENTION"] = str(dingtalk_cfg["require_mention"]).lower()
                if "mention_patterns" in dingtalk_cfg and not os.getenv("DINGTALK_MENTION_PATTERNS"):
                    os.environ["DINGTALK_MENTION_PATTERNS"] = json.dumps(dingtalk_cfg["mention_patterns"])
                frc = dingtalk_cfg.get("free_response_chats")
                if frc is not None and not os.getenv("DINGTALK_FREE_RESPONSE_CHATS"):
                    if isinstance(frc, list):
                        frc = ",".join(str(v) for v in frc)
                    os.environ["DINGTALK_FREE_RESPONSE_CHATS"] = str(frc)
                allowed = dingtalk_cfg.get("allowed_users")
                if allowed is not None and not os.getenv("DINGTALK_ALLOWED_USERS"):
                    if isinstance(allowed, list):
                        allowed = ",".join(str(v) for v in allowed)
                    os.environ["DINGTALK_ALLOWED_USERS"] = str(allowed)

            # Matrix settings → env vars (env vars take precedence)
            matrix_cfg = yaml_cfg.get("matrix", {})
            if isinstance(matrix_cfg, dict):
                if "require_mention" in matrix_cfg and not os.getenv("MATRIX_REQUIRE_MENTION"):
                    os.environ["MATRIX_REQUIRE_MENTION"] = str(matrix_cfg["require_mention"]).lower()
                frc = matrix_cfg.get("free_response_rooms")
                if frc is not None and not os.getenv("MATRIX_FREE_RESPONSE_ROOMS"):
                    if isinstance(frc, list):
                        frc = ",".join(str(v) for v in frc)
                    os.environ["MATRIX_FREE_RESPONSE_ROOMS"] = str(frc)
                if "auto_thread" in matrix_cfg and not os.getenv("MATRIX_AUTO_THREAD"):
                    os.environ["MATRIX_AUTO_THREAD"] = str(matrix_cfg["auto_thread"]).lower()
                if "dm_mention_threads" in matrix_cfg and not os.getenv("MATRIX_DM_MENTION_THREADS"):
                    os.environ["MATRIX_DM_MENTION_THREADS"] = str(matrix_cfg["dm_mention_threads"]).lower()

    except Exception as e:
        logger.warning(
            "Failed to process config.yaml — falling back to .env / gateway.json values. "
            "Check %s for syntax errors. Error: %s",
            _home / "config.yaml",
            e,
        )


__all__ = ["apply_config_yaml_overrides", "load_legacy_gateway_json"]
