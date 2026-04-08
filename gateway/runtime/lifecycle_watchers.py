"""Lifecycle Watchers methods for GatewayRunner."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import shlex
import signal
import sys
import tempfile
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from gateway.config import Platform
from gateway.platforms.base import BasePlatformAdapter, MessageEvent, MessageType
from gateway.session import SessionContext, SessionSource, build_session_context, build_session_context_prompt, build_session_key
from hermes_constants import get_hermes_home
from utils import atomic_yaml_write

logger = logging.getLogger(__name__)
_hermes_home = get_hermes_home()


def _run():
    import gateway.run as run_module
    return run_module


class GatewayLifecycleWatchersMixin:
    async def _handle_adapter_fatal_error(self, adapter: BasePlatformAdapter) -> None:
        """React to an adapter failure after startup.

        If the error is retryable (e.g. network blip, DNS failure), queue the
        platform for background reconnection instead of giving up permanently.
        """
        logger.error(
            "Fatal %s adapter error (%s): %s",
            adapter.platform.value,
            adapter.fatal_error_code or "unknown",
            adapter.fatal_error_message or "unknown error",
        )
        self._self_improver.record_event(
            "adapter_fatal_error",
            platform=adapter.platform.value,
            code=adapter.fatal_error_code or "unknown",
            retryable=bool(adapter.fatal_error_retryable),
            message=adapter.fatal_error_message or "unknown error",
        )
        self._self_improver.record_failure_signature(
            "adapter_fatal_error",
            adapter.fatal_error_message or "unknown error",
            platform=adapter.platform.value,
        )

        existing = self.adapters.get(adapter.platform)
        if existing is adapter:
            try:
                await adapter.disconnect()
            finally:
                self.adapters.pop(adapter.platform, None)
                self.delivery_router.adapters = self.adapters

        # Queue retryable failures for background reconnection
        if adapter.fatal_error_retryable:
            platform_config = self.config.platforms.get(adapter.platform)
            if platform_config and adapter.platform not in self._failed_platforms:
                self._failed_platforms[adapter.platform] = {
                    "config": platform_config,
                    "attempts": 0,
                    "next_retry": time.monotonic() + 30,
                }
                logger.info(
                    "%s queued for background reconnection",
                    adapter.platform.value,
                )

        if not self.adapters and not self._failed_platforms:
            self._exit_reason = adapter.fatal_error_message or "All messaging adapters disconnected"
            if adapter.fatal_error_retryable:
                self._exit_with_failure = True
                logger.error("No connected messaging platforms remain. Shutting down gateway for service restart.")
            else:
                logger.error("No connected messaging platforms remain. Shutting down gateway cleanly.")
            await self.stop()
        elif not self.adapters and self._failed_platforms:
            # All platforms are down and queued for background reconnection.
            # If the error is retryable, exit with failure so systemd Restart=on-failure
            # can restart the process. Otherwise stay alive and keep retrying in background.
            if adapter.fatal_error_retryable:
                self._exit_reason = adapter.fatal_error_message or "All messaging platforms failed with retryable errors"
                self._exit_with_failure = True
                logger.error(
                    "All messaging platforms failed with retryable errors. "
                    "Shutting down gateway for service restart (systemd will retry)."
                )
                await self.stop()
            else:
                logger.warning(
                    "No connected messaging platforms remain, but %d platform(s) queued for reconnection",
                    len(self._failed_platforms),
                )

    def _request_clean_exit(self, reason: str) -> None:
        self._exit_cleanly = True
        self._exit_reason = reason
        self._shutdown_event.set()

    def _publish_runtime_observability(self) -> None:
        """Persist a compact runtime observability snapshot for CLI diagnostics."""
        try:
            self.session_store._ensure_loaded()
            entries = list(self.session_store._entries.values())
            total_sessions = len(entries)
            active_sessions = sum(1 for entry in entries if not self.session_store._is_session_expired(entry))
            expired_unflushed = sum(
                1
                for entry in entries
                if self.session_store._is_session_expired(entry) and not getattr(entry, "memory_flushed", False)
            )
        except Exception:
            total_sessions = 0
            active_sessions = 0
            expired_unflushed = 0

        reconnect_queue: list[dict[str, Any]] = []
        now_mono = time.monotonic()
        for platform, info in (self._failed_platforms or {}).items():
            try:
                reconnect_queue.append({
                    "platform": platform.value,
                    "attempts": int(info.get("attempts", 0)),
                    "next_retry_in_s": max(0, int(info.get("next_retry", now_mono) - now_mono)),
                })
            except Exception:
                continue

        payload = {
            "adapters_connected": sorted(p.value for p in self.adapters.keys()),
            "reconnect_queue": reconnect_queue,
            "session_store": {
                "total": total_sessions,
                "active": active_sessions,
                "expired_unflushed": expired_unflushed,
            },
            "status_update": {
                "running_agents": len(getattr(self, "_running_agents", {}) or {}),
                "pending_approvals": len(getattr(self, "_pending_approvals", {}) or {}),
                "voice_mode_chats": len(getattr(self, "_voice_mode", {}) or {}),
            },
            "adaptive_policy": {
                "agent_timeout_s": float(getattr(self, "_adaptive_agent_timeout_s", 1800.0)),
                "reconnect_max_attempts": int(getattr(self, "_adaptive_reconnect_max_attempts", 20)),
                "reconnect_backoff_cap_s": int(getattr(self, "_adaptive_reconnect_backoff_cap_s", 300)),
                "history_hygiene_threshold": float(getattr(self, "_adaptive_history_hygiene_threshold", 0.85)),
            },
        }

        try:
            from gateway.status import update_runtime_observability
            update_runtime_observability("gateway", payload)
        except Exception:
            pass

    async def start(self) -> bool:
        """
        Start the gateway and all configured platform adapters.
        
        Returns True if at least one adapter connected successfully.
        """
        logger.info("Starting Hermes Gateway...")
        logger.info("Session storage: %s", self.config.sessions_dir)
        try:
            from hermes_cli.profiles import get_active_profile_name
            _profile = get_active_profile_name()
            if _profile and _profile != "default":
                logger.info("Active profile: %s", _profile)
        except Exception:
            pass
        try:
            from gateway.status import write_runtime_status
            write_runtime_status(gateway_state="starting", exit_reason=None)
        except Exception:
            pass
        
        # Warn if no user allowlists are configured and open access is not opted in
        _any_allowlist = any(
            os.getenv(v)
            for v in ("TELEGRAM_ALLOWED_USERS", "DISCORD_ALLOWED_USERS",
                       "WHATSAPP_ALLOWED_USERS", "SLACK_ALLOWED_USERS",
                       "SIGNAL_ALLOWED_USERS", "SIGNAL_GROUP_ALLOWED_USERS",
                       "EMAIL_ALLOWED_USERS",
                       "SMS_ALLOWED_USERS", "MATTERMOST_ALLOWED_USERS",
                       "MATRIX_ALLOWED_USERS", "DINGTALK_ALLOWED_USERS",
                       "FEISHU_ALLOWED_USERS",
                       "WECOM_ALLOWED_USERS",
                       "GATEWAY_ALLOWED_USERS")
        )
        _allow_all = os.getenv("GATEWAY_ALLOW_ALL_USERS", "").lower() in ("true", "1", "yes") or any(
            os.getenv(v, "").lower() in ("true", "1", "yes")
            for v in ("TELEGRAM_ALLOW_ALL_USERS", "DISCORD_ALLOW_ALL_USERS",
                       "WHATSAPP_ALLOW_ALL_USERS", "SLACK_ALLOW_ALL_USERS",
                       "SIGNAL_ALLOW_ALL_USERS", "EMAIL_ALLOW_ALL_USERS",
                       "SMS_ALLOW_ALL_USERS", "MATTERMOST_ALLOW_ALL_USERS",
                       "MATRIX_ALLOW_ALL_USERS", "DINGTALK_ALLOW_ALL_USERS",
                       "FEISHU_ALLOW_ALL_USERS",
                       "WECOM_ALLOW_ALL_USERS")
        )
        if not _any_allowlist and not _allow_all:
            logger.warning(
                "No user allowlists configured. All unauthorized users will be denied. "
                "Set GATEWAY_ALLOW_ALL_USERS=true in ~/.hermes/.env to allow open access, "
                "or configure platform allowlists (e.g., TELEGRAM_ALLOWED_USERS=your_id)."
            )
        
        # Discover and load event hooks
        self.hooks.discover_and_load()
        
        # Recover background processes from checkpoint (crash recovery)
        try:
            from tools.process_registry import process_registry
            recovered = process_registry.recover_from_checkpoint()
            if recovered:
                logger.info("Recovered %s background process(es) from previous run", recovered)
        except Exception as e:
            logger.warning("Process checkpoint recovery: %s", e)
        
        connected_count = 0
        enabled_platform_count = 0
        startup_nonretryable_errors: list[str] = []
        startup_retryable_errors: list[str] = []
        
        # Initialize and connect each configured platform
        for platform, platform_config in self.config.platforms.items():
            if not platform_config.enabled:
                continue
            enabled_platform_count += 1
            
            adapter = self._create_adapter(platform, platform_config)
            if not adapter:
                logger.warning("No adapter available for %s", platform.value)
                continue
            
            # Set up message + fatal error handlers
            adapter.set_message_handler(self._handle_message)
            adapter.set_fatal_error_handler(self._handle_adapter_fatal_error)
            adapter.set_session_store(self.session_store)
            
            # Try to connect
            logger.info("Connecting to %s...", platform.value)
            try:
                success = await adapter.connect()
                if success:
                    self.adapters[platform] = adapter
                    self._sync_voice_mode_state_to_adapter(adapter)
                    connected_count += 1
                    logger.info("✓ %s connected", platform.value)
                else:
                    logger.warning("✗ %s failed to connect", platform.value)
                    if adapter.has_fatal_error:
                        target = (
                            startup_retryable_errors
                            if adapter.fatal_error_retryable
                            else startup_nonretryable_errors
                        )
                        target.append(
                            f"{platform.value}: {adapter.fatal_error_message}"
                        )
                        # Queue for reconnection if the error is retryable
                        if adapter.fatal_error_retryable:
                            self._failed_platforms[platform] = {
                                "config": platform_config,
                                "attempts": 1,
                                "next_retry": time.monotonic() + 30,
                            }
                    else:
                        startup_retryable_errors.append(
                            f"{platform.value}: failed to connect"
                        )
                        # No fatal error info means likely a transient issue — queue for retry
                        self._failed_platforms[platform] = {
                            "config": platform_config,
                            "attempts": 1,
                            "next_retry": time.monotonic() + 30,
                        }
            except Exception as e:
                logger.error("✗ %s error: %s", platform.value, e)
                startup_retryable_errors.append(f"{platform.value}: {e}")
                # Unexpected exceptions are typically transient — queue for retry
                self._failed_platforms[platform] = {
                    "config": platform_config,
                    "attempts": 1,
                    "next_retry": time.monotonic() + 30,
                }
        
        if connected_count == 0:
            if startup_nonretryable_errors:
                reason = "; ".join(startup_nonretryable_errors)
                logger.error("Gateway hit a non-retryable startup conflict: %s", reason)
                try:
                    from gateway.status import write_runtime_status
                    write_runtime_status(gateway_state="startup_failed", exit_reason=reason)
                except Exception:
                    pass
                self._request_clean_exit(reason)
                return True
            if enabled_platform_count > 0:
                reason = "; ".join(startup_retryable_errors) or "all configured messaging platforms failed to connect"
                logger.error("Gateway failed to connect any configured messaging platform: %s", reason)
                try:
                    from gateway.status import write_runtime_status
                    write_runtime_status(gateway_state="startup_failed", exit_reason=reason)
                except Exception:
                    pass
                return False
            logger.warning("No messaging platforms enabled.")
            logger.info("Gateway will continue running for cron job execution.")
        
        # Update delivery router with adapters
        self.delivery_router.adapters = self.adapters
        
        self._running = True
        self._self_improver.record_event(
            "gateway_start",
            connected_platforms=[p.value for p in self.adapters.keys()],
            failed_platforms=[p.value for p in self._failed_platforms.keys()],
        )
        try:
            from gateway.status import write_runtime_status
            write_runtime_status(gateway_state="running", exit_reason=None)
        except Exception:
            pass
        self._publish_runtime_observability()

        # Emit gateway:startup hook
        hook_count = len(self.hooks.loaded_hooks)
        if hook_count:
            logger.info("%s hook(s) loaded", hook_count)
        await self.hooks.emit("gateway:startup", {
            "platforms": [p.value for p in self.adapters.keys()],
        })
        
        if connected_count > 0:
            logger.info("Gateway running with %s platform(s)", connected_count)
        
        # Build initial channel directory for send_message name resolution
        try:
            from gateway.channel_directory import build_channel_directory
            directory = build_channel_directory(self.adapters)
            ch_count = sum(len(chs) for chs in directory.get("platforms", {}).values())
            logger.info("Channel directory built: %d target(s)", ch_count)
        except Exception as e:
            logger.warning("Channel directory build failed: %s", e)
        
        # Check if we're restarting after a /update command. If the update is
        # still running, keep watching so we notify once it actually finishes.
        notified = await self._send_update_notification()
        if not notified and any(
            path.exists()
            for path in (
                _hermes_home / ".update_pending.json",
                _hermes_home / ".update_pending.claimed.json",
            )
        ):
            self._schedule_update_notification_watch()

        # Drain any recovered process watchers (from crash recovery checkpoint)
        try:
            from tools.process_registry import process_registry
            while process_registry.pending_watchers:
                watcher = process_registry.pending_watchers.pop(0)
                asyncio.create_task(self._run_process_watcher(watcher))
                logger.info("Resumed watcher for recovered process %s", watcher.get("session_id"))
        except Exception as e:
            logger.error("Recovered watcher setup error: %s", e)

        # Start background session expiry watcher for proactive memory flushing
        asyncio.create_task(self._session_expiry_watcher())

        # Start background reconnection watcher for platforms that failed at startup
        if self._failed_platforms:
            logger.info(
                "Starting reconnection watcher for %d failed platform(s): %s",
                len(self._failed_platforms),
                ", ".join(p.value for p in self._failed_platforms),
            )
        asyncio.create_task(self._platform_reconnect_watcher())

        # Start adaptive policy evaluator (safe bounded threshold tuning)
        asyncio.create_task(self._self_improvement_evaluator())

        logger.info("Press Ctrl+C to stop")
        
        return True

    async def _session_expiry_watcher(self, interval: int = 300):
        """Background task that proactively flushes memories for expired sessions.
        
        Runs every `interval` seconds (default 5 min).  For each session that
        has expired according to its reset policy, flushes memories in a thread
        pool and marks the session so it won't be flushed again.

        This means memories are already saved by the time the user sends their
        next message, so there's no blocking delay.
        """
        await asyncio.sleep(60)  # initial delay — let the gateway fully start
        _flush_failures: dict[str, int] = {}  # session_id -> consecutive failure count
        _MAX_FLUSH_RETRIES = 3
        while self._running:
            try:
                self.session_store._ensure_loaded()
                # Collect expired sessions first, then log a single summary.
                _expired_entries = []
                for key, entry in list(self.session_store._entries.items()):
                    if entry.memory_flushed:
                        continue
                    if not self.session_store._is_session_expired(entry):
                        continue
                    _expired_entries.append((key, entry))

                if _expired_entries:
                    # Extract platform names from session keys for a compact summary.
                    # Keys look like "agent:main:telegram:dm:12345" — platform is field [2].
                    _platforms: dict[str, int] = {}
                    for _k, _e in _expired_entries:
                        _parts = _k.split(":")
                        _plat = _parts[2] if len(_parts) > 2 else "unknown"
                        _platforms[_plat] = _platforms.get(_plat, 0) + 1
                    _plat_summary = ", ".join(
                        f"{p}:{c}" for p, c in sorted(_platforms.items())
                    )
                    logger.info(
                        "Session expiry: %d sessions to flush (%s)",
                        len(_expired_entries), _plat_summary,
                    )

                for key, entry in _expired_entries:
                    try:
                        await self._async_flush_memories(entry.session_id)
                        # Shut down memory provider on the cached agent
                        cached_agent = self._running_agents.get(key)
                        if cached_agent and cached_agent is not _run()._AGENT_PENDING_SENTINEL:
                            try:
                                if hasattr(cached_agent, 'shutdown_memory_provider'):
                                    cached_agent.shutdown_memory_provider()
                            except Exception:
                                pass
                        # Mark as flushed and persist to disk so the flag
                        # survives gateway restarts.
                        with self.session_store._lock:
                            entry.memory_flushed = True
                            self.session_store._save()
                        logger.debug(
                            "Memory flush completed for session %s",
                            entry.session_id,
                        )
                        _flush_failures.pop(entry.session_id, None)
                    except Exception as e:
                        failures = _flush_failures.get(entry.session_id, 0) + 1
                        _flush_failures[entry.session_id] = failures
                        if failures >= _MAX_FLUSH_RETRIES:
                            logger.warning(
                                "Memory flush gave up after %d attempts for %s: %s. "
                                "Marking as flushed to prevent infinite retry loop.",
                                failures, entry.session_id, e,
                            )
                            with self.session_store._lock:
                                entry.memory_flushed = True
                                self.session_store._save()
                            _flush_failures.pop(entry.session_id, None)
                        else:
                            logger.debug(
                                "Memory flush failed (%d/%d) for %s: %s",
                                failures, _MAX_FLUSH_RETRIES, entry.session_id, e,
                            )

                if _expired_entries:
                    _flushed = sum(
                        1 for _, e in _expired_entries if e.memory_flushed
                    )
                    _failed = len(_expired_entries) - _flushed
                    if _failed:
                        logger.info(
                            "Session expiry done: %d flushed, %d pending retry",
                            _flushed, _failed,
                        )
                    else:
                        logger.info(
                            "Session expiry done: %d flushed", _flushed,
                        )
            except Exception as e:
                logger.debug("Session expiry watcher error: %s", e)

            self._publish_runtime_observability()

            # Sleep in small increments so we can stop quickly
            for _ in range(interval):
                if not self._running:
                    break
                await asyncio.sleep(1)

    async def _self_improvement_evaluator(self, interval: int = 900) -> None:
        """Periodic evaluator that updates bounded adaptive thresholds."""
        await asyncio.sleep(120)
        while self._running:
            try:
                result = self._self_improver.evaluate_and_update()
                if result.get("updated"):
                    policy = result.get("policy", {})
                    self._adaptive_agent_timeout_s = float(policy.get("agent_timeout_s", self._adaptive_agent_timeout_s))
                    self._adaptive_reconnect_max_attempts = int(policy.get("reconnect_max_attempts", self._adaptive_reconnect_max_attempts))
                    self._adaptive_reconnect_backoff_cap_s = int(policy.get("reconnect_backoff_cap_s", self._adaptive_reconnect_backoff_cap_s))
                    self._adaptive_history_hygiene_threshold = float(
                        policy.get("history_hygiene_threshold", self._adaptive_history_hygiene_threshold)
                    )
                    logger.info(
                        "Adaptive policy updated: timeout=%ss reconnect_attempts=%s reconnect_backoff_cap=%ss hygiene=%.2f",
                        int(self._adaptive_agent_timeout_s),
                        self._adaptive_reconnect_max_attempts,
                        self._adaptive_reconnect_backoff_cap_s,
                        self._adaptive_history_hygiene_threshold,
                    )
            except Exception as e:
                logger.debug("Self-improvement evaluator error: %s", e)

            for _ in range(interval):
                if not self._running:
                    return
                await asyncio.sleep(1)

    async def _platform_reconnect_watcher(self) -> None:
        """Background task that periodically retries connecting failed platforms.

        Uses exponential backoff: 30s → 60s → 120s → 240s → 300s (cap).
        Stops retrying a platform after 20 failed attempts or if the error
        is non-retryable (e.g. bad auth token).
        """
        _MAX_ATTEMPTS = max(1, int(self._adaptive_reconnect_max_attempts))
        _BACKOFF_CAP = max(30, int(self._adaptive_reconnect_backoff_cap_s))

        await asyncio.sleep(10)  # initial delay — let startup finish
        while self._running:
            if not self._failed_platforms:
                # Nothing to reconnect — sleep and check again
                for _ in range(30):
                    if not self._running:
                        return
                    await asyncio.sleep(1)
                continue

            _MAX_ATTEMPTS = max(1, int(self._adaptive_reconnect_max_attempts))
            _BACKOFF_CAP = max(30, int(self._adaptive_reconnect_backoff_cap_s))
            now = time.monotonic()
            for platform in list(self._failed_platforms.keys()):
                if not self._running:
                    return
                info = self._failed_platforms[platform]
                if now < info["next_retry"]:
                    continue  # not time yet

                if info["attempts"] >= _MAX_ATTEMPTS:
                    logger.warning(
                        "Giving up reconnecting %s after %d attempts",
                        platform.value, info["attempts"],
                    )
                    del self._failed_platforms[platform]
                    continue

                platform_config = info["config"]
                attempt = info["attempts"] + 1
                logger.info(
                    "Reconnecting %s (attempt %d/%d)...",
                    platform.value, attempt, _MAX_ATTEMPTS,
                )

                try:
                    adapter = self._create_adapter(platform, platform_config)
                    if not adapter:
                        logger.warning(
                            "Reconnect %s: adapter creation returned None, removing from retry queue",
                            platform.value,
                        )
                        del self._failed_platforms[platform]
                        continue

                    adapter.set_message_handler(self._handle_message)
                    adapter.set_fatal_error_handler(self._handle_adapter_fatal_error)
                    adapter.set_session_store(self.session_store)

                    success = await adapter.connect()
                    if success:
                        self.adapters[platform] = adapter
                        self._sync_voice_mode_state_to_adapter(adapter)
                        self.delivery_router.adapters = self.adapters
                        del self._failed_platforms[platform]
                        logger.info("✓ %s reconnected successfully", platform.value)
                        self._self_improver.record_event(
                            "reconnect_result",
                            platform=platform.value,
                            attempt=attempt,
                            success=True,
                        )

                        # Rebuild channel directory with the new adapter
                        try:
                            from gateway.channel_directory import build_channel_directory
                            build_channel_directory(self.adapters)
                        except Exception:
                            pass
                    else:
                        # Check if the failure is non-retryable
                        if adapter.has_fatal_error and not adapter.fatal_error_retryable:
                            logger.warning(
                                "Reconnect %s: non-retryable error (%s), removing from retry queue",
                                platform.value, adapter.fatal_error_message,
                            )
                            self._self_improver.record_event(
                                "reconnect_result",
                                platform=platform.value,
                                attempt=attempt,
                                success=False,
                                retryable=False,
                                error=adapter.fatal_error_message or "non-retryable",
                            )
                            self._self_improver.record_failure_signature(
                                "adapter_reconnect",
                                adapter.fatal_error_message or "non-retryable",
                                platform=platform.value,
                            )
                            del self._failed_platforms[platform]
                        else:
                            backoff = min(30 * (2 ** (attempt - 1)), _BACKOFF_CAP)
                            info["attempts"] = attempt
                            info["next_retry"] = time.monotonic() + backoff
                            self._self_improver.record_event(
                                "reconnect_result",
                                platform=platform.value,
                                attempt=attempt,
                                success=False,
                                retryable=True,
                                backoff_s=backoff,
                                error=adapter.fatal_error_message or "connect() returned false",
                            )
                            logger.info(
                                "Reconnect %s failed, next retry in %ds",
                                platform.value, backoff,
                            )
                except Exception as e:
                    backoff = min(30 * (2 ** (attempt - 1)), _BACKOFF_CAP)
                    info["attempts"] = attempt
                    info["next_retry"] = time.monotonic() + backoff
                    self._self_improver.record_event(
                        "reconnect_result",
                        platform=platform.value,
                        attempt=attempt,
                        success=False,
                        retryable=True,
                        backoff_s=backoff,
                        error=str(e),
                    )
                    self._self_improver.record_failure_signature(
                        "adapter_reconnect_exception",
                        str(e),
                        platform=platform.value,
                    )
                    logger.warning(
                        "Reconnect %s error: %s, next retry in %ds",
                        platform.value, e, backoff,
                    )

            self._publish_runtime_observability()

            # Check every 10 seconds for platforms that need reconnection
            for _ in range(10):
                if not self._running:
                    return
                await asyncio.sleep(1)

    async def stop(self) -> None:
        """Stop the gateway and disconnect all adapters."""
        logger.info("Stopping gateway...")
        self._running = False

        for session_key, agent in list(self._running_agents.items()):
            if agent is _run()._AGENT_PENDING_SENTINEL:
                continue
            try:
                agent.interrupt("Gateway shutting down")
                logger.debug("Interrupted running agent for session %s during shutdown", session_key[:20])
            except Exception as e:
                logger.debug("Failed interrupting agent during shutdown: %s", e)
            # Shut down memory provider at actual session boundary
            try:
                if hasattr(agent, 'shutdown_memory_provider'):
                    agent.shutdown_memory_provider()
            except Exception:
                pass

        for platform, adapter in list(self.adapters.items()):
            try:
                await adapter.cancel_background_tasks()
            except Exception as e:
                logger.debug("✗ %s background-task cancel error: %s", platform.value, e)
            try:
                await adapter.disconnect()
                logger.info("✓ %s disconnected", platform.value)
            except Exception as e:
                logger.error("✗ %s disconnect error: %s", platform.value, e)

        # Cancel any pending background tasks
        for _task in list(self._background_tasks):
            _task.cancel()
        self._background_tasks.clear()

        self.adapters.clear()
        self._running_agents.clear()
        self._pending_messages.clear()
        self._pending_approvals.clear()
        self._shutdown_event.set()

        self._publish_runtime_observability()

        from gateway.status import remove_pid_file, write_runtime_status
        remove_pid_file()
        try:
            write_runtime_status(gateway_state="stopped", exit_reason=self._exit_reason)
        except Exception:
            pass
        
        logger.info("Gateway stopped")

    async def wait_for_shutdown(self) -> None:
        """Wait for shutdown signal."""
        await self._shutdown_event.wait()

    def _create_adapter(
        self, 
        platform: Platform, 
        config: Any
    ) -> Optional[BasePlatformAdapter]:
        """Create the appropriate adapter for a platform."""
        if hasattr(config, "extra") and isinstance(config.extra, dict):
            config.extra.setdefault(
                "group_sessions_per_user",
                self.config.group_sessions_per_user,
            )
            config.extra.setdefault(
                "thread_sessions_per_user",
                getattr(self.config, "thread_sessions_per_user", False),
            )

        if platform == Platform.TELEGRAM:
            from gateway.platforms.telegram import TelegramAdapter, check_telegram_requirements
            if not check_telegram_requirements():
                logger.warning("Telegram: python-telegram-bot not installed")
                return None
            return TelegramAdapter(config)
        
        elif platform == Platform.DISCORD:
            from gateway.platforms.discord import DiscordAdapter, check_discord_requirements
            if not check_discord_requirements():
                logger.warning("Discord: discord.py not installed")
                return None
            return DiscordAdapter(config)
        
        elif platform == Platform.WHATSAPP:
            from gateway.platforms.whatsapp import WhatsAppAdapter, check_whatsapp_requirements
            if not check_whatsapp_requirements():
                logger.warning("WhatsApp: Node.js not installed or bridge not configured")
                return None
            return WhatsAppAdapter(config)
        
        elif platform == Platform.SLACK:
            from gateway.platforms.slack import SlackAdapter, check_slack_requirements
            if not check_slack_requirements():
                logger.warning("Slack: slack-bolt not installed. Run: pip install 'hermes-agent[slack]'")
                return None
            return SlackAdapter(config)

        elif platform == Platform.SIGNAL:
            from gateway.platforms.signal import SignalAdapter, check_signal_requirements
            if not check_signal_requirements():
                logger.warning("Signal: SIGNAL_HTTP_URL or SIGNAL_ACCOUNT not configured")
                return None
            return SignalAdapter(config)

        elif platform == Platform.HOMEASSISTANT:
            from gateway.platforms.homeassistant import HomeAssistantAdapter, check_ha_requirements
            if not check_ha_requirements():
                logger.warning("HomeAssistant: aiohttp not installed or HASS_TOKEN not set")
                return None
            return HomeAssistantAdapter(config)

        elif platform == Platform.EMAIL:
            from gateway.platforms.email import EmailAdapter, check_email_requirements
            if not check_email_requirements():
                logger.warning("Email: EMAIL_ADDRESS, EMAIL_PASSWORD, EMAIL_IMAP_HOST, or EMAIL_SMTP_HOST not set")
                return None
            return EmailAdapter(config)

        elif platform == Platform.SMS:
            from gateway.platforms.sms import SmsAdapter, check_sms_requirements
            if not check_sms_requirements():
                logger.warning("SMS: aiohttp not installed or TWILIO_ACCOUNT_SID/TWILIO_AUTH_TOKEN not set")
                return None
            return SmsAdapter(config)

        elif platform == Platform.DINGTALK:
            from gateway.platforms.dingtalk import DingTalkAdapter, check_dingtalk_requirements
            if not check_dingtalk_requirements():
                logger.warning("DingTalk: dingtalk-stream not installed or DINGTALK_CLIENT_ID/SECRET not set")
                return None
            return DingTalkAdapter(config)

        elif platform == Platform.FEISHU:
            from gateway.platforms.feishu import FeishuAdapter, check_feishu_requirements
            if not check_feishu_requirements():
                logger.warning("Feishu: lark-oapi not installed or FEISHU_APP_ID/SECRET not set")
                return None
            return FeishuAdapter(config)

        elif platform == Platform.WECOM:
            from gateway.platforms.wecom import WeComAdapter, check_wecom_requirements
            if not check_wecom_requirements():
                logger.warning("WeCom: aiohttp not installed or WECOM_BOT_ID/SECRET not set")
                return None
            return WeComAdapter(config)

        elif platform == Platform.MATTERMOST:
            from gateway.platforms.mattermost import MattermostAdapter, check_mattermost_requirements
            if not check_mattermost_requirements():
                logger.warning("Mattermost: MATTERMOST_TOKEN or MATTERMOST_URL not set, or aiohttp missing")
                return None
            return MattermostAdapter(config)

        elif platform == Platform.MATRIX:
            from gateway.platforms.matrix import MatrixAdapter, check_matrix_requirements
            if not check_matrix_requirements():
                logger.warning("Matrix: matrix-nio not installed or credentials not set. Run: pip install 'matrix-nio[e2e]'")
                return None
            return MatrixAdapter(config)

        elif platform == Platform.API_SERVER:
            from gateway.platforms.api_server import APIServerAdapter, check_api_server_requirements
            if not check_api_server_requirements():
                logger.warning("API Server: aiohttp not installed")
                return None
            return APIServerAdapter(config)

        elif platform == Platform.WEBHOOK:
            from gateway.platforms.webhook import WebhookAdapter, check_webhook_requirements
            if not check_webhook_requirements():
                logger.warning("Webhook: aiohttp not installed")
                return None
            adapter = WebhookAdapter(config)
            adapter.gateway_runner = self  # For cross-platform delivery
            return adapter

        return None

