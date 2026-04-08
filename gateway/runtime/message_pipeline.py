"""Inbound message pipeline for GatewayRunner."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Optional

from gateway.platforms.base import MessageEvent, MessageType

from gateway.runtime.shared import (
    _AGENT_PENDING_SENTINEL,
    _check_unavailable_skill,
)
from hermes_constants import get_hermes_home

logger = logging.getLogger(__name__)
_hermes_home = get_hermes_home()


class GatewayMessagePipelineMixin:
    async def _handle_message(self, event: MessageEvent) -> Optional[str]:
        """
        Handle an incoming message from any platform.
        
        This is the core message processing pipeline:
        1. Check user authorization
        2. Check for commands (/new, /reset, etc.)
        3. Check for running agent and interrupt if needed
        4. Get or create session
        5. Build context for agent
        6. Run agent conversation
        7. Return response
        """
        source = event.source

        # Check if user is authorized
        if not self._is_user_authorized(source):
            logger.warning("Unauthorized user: %s (%s) on %s", source.user_id, source.user_name, source.platform.value)
            # In DMs: offer pairing code. In groups: silently ignore.
            if source.chat_type == "dm" and self._get_unauthorized_dm_behavior(source.platform) == "pair":
                platform_name = source.platform.value if source.platform else "unknown"
                # Rate-limit ALL pairing responses (code or rejection) to
                # prevent spamming the user with repeated messages when
                # multiple DMs arrive in quick succession.
                if self.pairing_store._is_rate_limited(platform_name, source.user_id):
                    return None
                code = self.pairing_store.generate_code(
                    platform_name, source.user_id, source.user_name or ""
                )
                if code:
                    adapter = self.adapters.get(source.platform)
                    if adapter:
                        await adapter.send(
                            source.chat_id,
                            f"Hi~ I don't recognize you yet!\n\n"
                            f"Here's your pairing code: `{code}`\n\n"
                            f"Ask the bot owner to run:\n"
                            f"`hermes pairing approve {platform_name} {code}`"
                        )
                else:
                    adapter = self.adapters.get(source.platform)
                    if adapter:
                        await adapter.send(
                            source.chat_id,
                            "Too many pairing requests right now~ "
                            "Please try again later!"
                        )
                    # Record rate limit so subsequent messages are silently ignored
                    self.pairing_store._record_rate_limit(platform_name, source.user_id)
            return None
        
        # Intercept messages that are responses to a pending /update prompt.
        # The update process (detached) wrote .update_prompt.json; the watcher
        # forwarded it to the user; now the user's reply goes back via
        # .update_response so the update process can continue.
        _quick_key = self._session_key_for_source(source)
        _update_prompts = getattr(self, "_update_prompt_pending", {})
        if _update_prompts.get(_quick_key):
            raw = (event.text or "").strip()
            # Accept /approve and /deny as shorthand for yes/no
            cmd = event.get_command()
            if cmd in ("approve", "yes"):
                response_text = "y"
            elif cmd in ("deny", "no"):
                response_text = "n"
            else:
                response_text = raw
            if response_text:
                response_path = _hermes_home / ".update_response"
                try:
                    tmp = response_path.with_suffix(".tmp")
                    tmp.write_text(response_text)
                    tmp.replace(response_path)
                except OSError as e:
                    logger.warning("Failed to write update response: %s", e)
                    return f"✗ Failed to send response to update process: {e}"
                _update_prompts.pop(_quick_key, None)
                label = response_text if len(response_text) <= 20 else response_text[:20] + "…"
                return f"✓ Sent `{label}` to the update process."

        # PRIORITY handling when an agent is already running for this session.
        # Default behavior is to interrupt immediately so user text/stop messages
        # are handled with minimal latency.
        #
        # Special case: Telegram/photo bursts often arrive as multiple near-
        # simultaneous updates. Do NOT interrupt for photo-only follow-ups here;
        # let the adapter-level batching/queueing logic absorb them.

        # Staleness eviction: detect leaked locks from hung/crashed handlers.
        # With inactivity-based timeout, active tasks can run for hours, so
        # wall-clock age alone isn't sufficient.  Evict only when the agent
        # has been *idle* beyond the inactivity threshold (or when the agent
        # object has no activity tracker and wall-clock age is extreme).
        _raw_stale_timeout = self._effective_agent_timeout_seconds()
        _stale_ts = self._running_agents_ts.get(_quick_key, 0)
        if _quick_key in self._running_agents and _stale_ts:
            _stale_age = time.time() - _stale_ts
            _stale_agent = self._running_agents.get(_quick_key)
            # Never evict the pending sentinel — it was just placed moments
            # ago during the async setup phase before the real agent is
            # created.  Sentinels have no get_activity_summary(), so the
            # idle check below would always evaluate to inf >= timeout and
            # immediately evict them, racing with the setup path.
            _stale_idle = float("inf")  # assume idle if we can't check
            _stale_detail = ""
            if _stale_agent and hasattr(_stale_agent, "get_activity_summary"):
                try:
                    _sa = _stale_agent.get_activity_summary()
                    _stale_idle = _sa.get("seconds_since_activity", float("inf"))
                    _stale_detail = (
                        f" | last_activity={_sa.get('last_activity_desc', 'unknown')} "
                        f"({_stale_idle:.0f}s ago) "
                        f"| iteration={_sa.get('api_call_count', 0)}/{_sa.get('max_iterations', 0)}"
                    )
                except Exception:
                    pass
            # Evict if: agent is idle beyond timeout, OR wall-clock age is
            # extreme (10x timeout or 2h, whichever is larger — catches
            # cases where the agent object was garbage-collected).
            _wall_ttl = max(_raw_stale_timeout * 10, 7200) if _raw_stale_timeout > 0 else float("inf")
            _should_evict = (
                _stale_agent is not _AGENT_PENDING_SENTINEL
                and (
                    (_raw_stale_timeout > 0 and _stale_idle >= _raw_stale_timeout)
                    or _stale_age > _wall_ttl
                )
            )
            if _should_evict:
                logger.warning(
                    "Evicting stale _running_agents entry for %s "
                    "(age: %.0fs, idle: %.0fs, timeout: %.0fs)%s",
                    _quick_key[:30], _stale_age, _stale_idle,
                    _raw_stale_timeout, _stale_detail,
                )
                del self._running_agents[_quick_key]
                self._running_agents_ts.pop(_quick_key, None)

        if _quick_key in self._running_agents:
            if event.get_command() == "status":
                return await self._handle_status_command(event)

            # Resolve the command once for all early-intercept checks below.
            from hermes_cli.commands import resolve_command as _resolve_cmd_inner
            _evt_cmd = event.get_command()
            _cmd_def_inner = _resolve_cmd_inner(_evt_cmd) if _evt_cmd else None

            # /stop must hard-kill the session when an agent is running.
            # A soft interrupt (agent.interrupt()) doesn't help when the agent
            # is truly hung — the executor thread is blocked and never checks
            # _interrupt_requested.  Force-clean _running_agents so the session
            # is unlocked and subsequent messages are processed normally.
            if _cmd_def_inner and _cmd_def_inner.name == "stop":
                running_agent = self._running_agents.get(_quick_key)
                if running_agent and running_agent is not _AGENT_PENDING_SENTINEL:
                    running_agent.interrupt("Stop requested")
                # Force-clean: remove the session lock regardless of agent state
                adapter = self.adapters.get(source.platform)
                if adapter and hasattr(adapter, 'get_pending_message'):
                    adapter.get_pending_message(_quick_key)  # consume and discard
                self._pending_messages.pop(_quick_key, None)
                if _quick_key in self._running_agents:
                    del self._running_agents[_quick_key]
                logger.info("HARD STOP for session %s — session lock released", _quick_key[:20])
                return "⚡ Force-stopped. The session is unlocked — you can send a new message."

            # /reset and /new must bypass the running-agent guard so they
            # actually dispatch as commands instead of being queued as user
            # text (which would be fed back to the agent with the same
            # broken history — #2170).  Interrupt the agent first, then
            # clear the adapter's pending queue so the stale "/reset" text
            # doesn't get re-processed as a user message after the
            # interrupt completes.
            if _cmd_def_inner and _cmd_def_inner.name == "new":
                running_agent = self._running_agents.get(_quick_key)
                if running_agent and running_agent is not _AGENT_PENDING_SENTINEL:
                    running_agent.interrupt("Session reset requested")
                # Clear any pending messages so the old text doesn't replay
                adapter = self.adapters.get(source.platform)
                if adapter and hasattr(adapter, 'get_pending_message'):
                    adapter.get_pending_message(_quick_key)  # consume and discard
                self._pending_messages.pop(_quick_key, None)
                # Clean up the running agent entry so the reset handler
                # doesn't think an agent is still active.
                if _quick_key in self._running_agents:
                    del self._running_agents[_quick_key]
                return await self._handle_reset_command(event)

            # /queue <prompt> — queue without interrupting
            if event.get_command() in ("queue", "q"):
                queued_text = event.get_command_args().strip()
                if not queued_text:
                    return "Usage: /queue <prompt>"
                adapter = self.adapters.get(source.platform)
                if adapter:
                    from gateway.platforms.base import MessageEvent as _ME, MessageType as _MT
                    queued_event = _ME(
                        text=queued_text,
                        message_type=_MT.TEXT,
                        source=event.source,
                        message_id=event.message_id,
                    )
                    adapter._pending_messages[_quick_key] = queued_event
                return "Queued for the next turn."

            # /model must not be used while the agent is running.
            if _cmd_def_inner and _cmd_def_inner.name == "model":
                return "Agent is running — wait or /stop first, then switch models."

            # /approve and /deny must bypass the running-agent interrupt path.
            # The agent thread is blocked on a threading.Event inside
            # tools/approval.py — sending an interrupt won't unblock it.
            # Route directly to the approval handler so the event is signalled.
            if _cmd_def_inner and _cmd_def_inner.name in ("approve", "deny"):
                if _cmd_def_inner.name == "approve":
                    return await self._handle_approve_command(event)
                return await self._handle_deny_command(event)

            if event.message_type == MessageType.PHOTO:
                logger.debug("PRIORITY photo follow-up for session %s — queueing without interrupt", _quick_key[:20])
                adapter = self.adapters.get(source.platform)
                if adapter:
                    # Reuse adapter queue semantics so photo bursts merge cleanly.
                    if _quick_key in adapter._pending_messages:
                        existing = adapter._pending_messages[_quick_key]
                        if getattr(existing, "message_type", None) == MessageType.PHOTO:
                            existing.media_urls.extend(event.media_urls)
                            existing.media_types.extend(event.media_types)
                            if event.text:
                                if not existing.text:
                                    existing.text = event.text
                                elif event.text not in existing.text:
                                    existing.text = f"{existing.text}\n\n{event.text}".strip()
                        else:
                            adapter._pending_messages[_quick_key] = event
                    else:
                        adapter._pending_messages[_quick_key] = event
                return None

            running_agent = self._running_agents.get(_quick_key)
            if running_agent is _AGENT_PENDING_SENTINEL:
                # Agent is being set up but not ready yet.
                if event.get_command() == "stop":
                    # Force-clean the sentinel so the session is unlocked.
                    if _quick_key in self._running_agents:
                        del self._running_agents[_quick_key]
                    logger.info("HARD STOP (pending) for session %s — sentinel cleared", _quick_key[:20])
                    return "⚡ Force-stopped. The agent was still starting — session unlocked."
                # Queue the message so it will be picked up after the
                # agent starts.
                adapter = self.adapters.get(source.platform)
                if adapter:
                    adapter._pending_messages[_quick_key] = event
                return None
            logger.debug("PRIORITY interrupt for session %s", _quick_key[:20])
            running_agent.interrupt(event.text)
            if _quick_key in self._pending_messages:
                self._pending_messages[_quick_key] += "\n" + event.text
            else:
                self._pending_messages[_quick_key] = event.text
            return None

        # Check for commands
        command = event.get_command()
        
        # Emit command:* hook for any recognized slash command.
        # GATEWAY_KNOWN_COMMANDS is derived from the central COMMAND_REGISTRY
        # in hermes_cli/commands.py — no hardcoded set to maintain here.
        from hermes_cli.commands import GATEWAY_KNOWN_COMMANDS, resolve_command as _resolve_cmd
        if command and command in GATEWAY_KNOWN_COMMANDS:
            await self.hooks.emit(f"command:{command}", {
                "platform": source.platform.value if source.platform else "",
                "user_id": source.user_id,
                "command": command,
                "args": event.get_command_args().strip(),
            })

        # Resolve aliases to canonical name so dispatch only checks canonicals.
        _cmd_def = _resolve_cmd(command) if command else None
        canonical = _cmd_def.name if _cmd_def else command

        if canonical == "new":
            return await self._handle_reset_command(event)
        
        if canonical == "help":
            return await self._handle_help_command(event)

        if canonical == "commands":
            return await self._handle_commands_command(event)
        
        if canonical == "profile":
            return await self._handle_profile_command(event)

        if canonical == "status":
            return await self._handle_status_command(event)
        
        if canonical == "stop":
            return await self._handle_stop_command(event)
        
        if canonical == "reasoning":
            return await self._handle_reasoning_command(event)

        if canonical == "verbose":
            return await self._handle_verbose_command(event)

        if canonical == "yolo":
            return await self._handle_yolo_command(event)

        if canonical == "model":
            return await self._handle_model_command(event)

        if canonical == "provider":
            return await self._handle_provider_command(event)
        
        if canonical == "personality":
            return await self._handle_personality_command(event)

        if canonical == "plan":
            try:
                from agent.skill_commands import build_plan_path, build_skill_invocation_message

                user_instruction = event.get_command_args().strip()
                plan_path = build_plan_path(user_instruction)
                event.text = build_skill_invocation_message(
                    "/plan",
                    user_instruction,
                    task_id=_quick_key,
                    runtime_note=(
                        "Save the markdown plan with write_file to this exact relative path "
                        f"inside the active workspace/backend cwd: {plan_path}"
                    ),
                )
                if not event.text:
                    return "Failed to load the bundled /plan skill."
                canonical = None
            except Exception as e:
                logger.exception("Failed to prepare /plan command")
                return f"Failed to enter plan mode: {e}"
        
        if canonical == "retry":
            return await self._handle_retry_command(event)
        
        if canonical == "undo":
            return await self._handle_undo_command(event)
        
        if canonical == "sethome":
            return await self._handle_set_home_command(event)

        if canonical == "compress":
            return await self._handle_compress_command(event)

        if canonical == "usage":
            return await self._handle_usage_command(event)

        if canonical == "insights":
            return await self._handle_insights_command(event)

        if canonical == "reload-mcp":
            return await self._handle_reload_mcp_command(event)

        if canonical == "approve":
            return await self._handle_approve_command(event)

        if canonical == "deny":
            return await self._handle_deny_command(event)

        if canonical == "update":
            return await self._handle_update_command(event)

        if canonical == "title":
            return await self._handle_title_command(event)

        if canonical == "resume":
            return await self._handle_resume_command(event)

        if canonical == "branch":
            return await self._handle_branch_command(event)

        if canonical == "rollback":
            return await self._handle_rollback_command(event)

        if canonical == "background":
            return await self._handle_background_command(event)

        if canonical == "btw":
            return await self._handle_btw_command(event)

        if canonical == "voice":
            return await self._handle_voice_command(event)

        # User-defined quick commands (bypass agent loop, no LLM call)
        if command:
            if isinstance(self.config, dict):
                quick_commands = self.config.get("quick_commands", {}) or {}
            else:
                quick_commands = getattr(self.config, "quick_commands", {}) or {}
            if not isinstance(quick_commands, dict):
                quick_commands = {}
            if command in quick_commands:
                qcmd = quick_commands[command]
                if qcmd.get("type") == "exec":
                    exec_cmd = qcmd.get("command", "")
                    if exec_cmd:
                        try:
                            proc = await asyncio.create_subprocess_shell(
                                exec_cmd,
                                stdout=asyncio.subprocess.PIPE,
                                stderr=asyncio.subprocess.PIPE,
                            )
                            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
                            output = (stdout or stderr).decode().strip()
                            return output if output else "Command returned no output."
                        except asyncio.TimeoutError:
                            return "Quick command timed out (30s)."
                        except Exception as e:
                            return f"Quick command error: {e}"
                    else:
                        return f"Quick command '/{command}' has no command defined."
                elif qcmd.get("type") == "alias":
                    target = qcmd.get("target", "").strip()
                    if target:
                        target = target if target.startswith("/") else f"/{target}"
                        target_command = target.lstrip("/")
                        user_args = event.get_command_args().strip()
                        event.text = f"{target} {user_args}".strip()
                        command = target_command
                        # Fall through to normal command dispatch below
                    else:
                        return f"Quick command '/{command}' has no target defined."
                else:
                    return f"Quick command '/{command}' has unsupported type (supported: 'exec', 'alias')."

        # Plugin-registered slash commands
        if command:
            try:
                from hermes_cli.plugins import get_plugin_command_handler
                # Normalize underscores to hyphens so Telegram's underscored
                # autocomplete form matches plugin commands registered with
                # hyphens. See hermes_cli/commands.py:_build_telegram_menu.
                plugin_handler = get_plugin_command_handler(command.replace("_", "-"))
                if plugin_handler:
                    user_args = event.get_command_args().strip()
                    import asyncio as _aio
                    result = plugin_handler(user_args)
                    if _aio.iscoroutine(result):
                        result = await result
                    return str(result) if result else None
            except Exception as e:
                logger.debug("Plugin command dispatch failed (non-fatal): %s", e)

        # Skill slash commands: /skill-name loads the skill and sends to agent.
        # resolve_skill_command_key() handles the Telegram underscore/hyphen
        # round-trip so /claude_code from Telegram autocomplete still resolves
        # to the claude-code skill.
        if command:
            try:
                from agent.skill_commands import (
                    get_skill_commands,
                    build_skill_invocation_message,
                    resolve_skill_command_key,
                )
                skill_cmds = get_skill_commands()
                cmd_key = resolve_skill_command_key(command)
                if cmd_key is not None:
                    # Check per-platform disabled status before executing.
                    # get_skill_commands() only applies the *global* disabled
                    # list at scan time; per-platform overrides need checking
                    # here because the cache is process-global across platforms.
                    _skill_name = skill_cmds[cmd_key].get("name", "")
                    _plat = source.platform.value if source.platform else None
                    if _plat and _skill_name:
                        from agent.skill_utils import get_disabled_skill_names as _get_plat_disabled
                        if _skill_name in _get_plat_disabled(platform=_plat):
                            return (
                                f"The **{_skill_name}** skill is disabled for {_plat}.\n"
                                f"Enable it with: `hermes skills config`"
                            )
                    user_instruction = event.get_command_args().strip()
                    msg = build_skill_invocation_message(
                        cmd_key, user_instruction, task_id=_quick_key
                    )
                    if msg:
                        event.text = msg
                        # Fall through to normal message processing with skill content
                else:
                    # Not an active skill — check if it's a known-but-disabled or
                    # uninstalled skill and give actionable guidance.
                    _unavail_msg = _check_unavailable_skill(command)
                    if _unavail_msg:
                        return _unavail_msg
                    # Genuinely unrecognized /command: not a built-in, not a
                    # plugin, not a skill, not a known-inactive skill. Warn
                    # the user instead of silently forwarding it to the LLM
                    # as free text (which leads to silent-failure behavior
                    # like the model inventing a delegate_task call).
                    # Normalize to hyphenated form before checking known
                    # built-ins (command may be an alias target set by the
                    # quick-command block above, so _cmd_def can be stale).
                    if command.replace("_", "-") not in GATEWAY_KNOWN_COMMANDS:
                        logger.warning(
                            "Unrecognized slash command /%s from %s — "
                            "replying with unknown-command notice",
                            command,
                            source.platform.value if source.platform else "?",
                        )
                        return (
                            f"Unknown command `/{command}`. "
                            f"Type /commands to see what's available, "
                            f"or resend without the leading slash to send "
                            f"as a regular message."
                        )
            except Exception as e:
                logger.debug("Skill command check failed (non-fatal): %s", e)
        
        # Pending exec approvals are handled by /approve and /deny commands above.
        # No bare text matching — "yes" in normal conversation must not trigger
        # execution of a dangerous command.

        # ── Claim this session before any await ───────────────────────
        # Between here and _run_agent registering the real AIAgent, there
        # are numerous await points (hooks, vision enrichment, STT,
        # session hygiene compression).  Without this sentinel a second
        # message arriving during any of those yields would pass the
        # "already running" guard and spin up a duplicate agent for the
        # same session — corrupting the transcript.
        self._running_agents[_quick_key] = _AGENT_PENDING_SENTINEL
        self._running_agents_ts[_quick_key] = time.time()

        try:
            return await self._handle_message_with_agent(event, source, _quick_key)
        finally:
            # If _run_agent replaced the sentinel with a real agent and
            # then cleaned it up, this is a no-op.  If we exited early
            # (exception, command fallthrough, etc.) the sentinel must
            # not linger or the session would be permanently locked out.
            if self._running_agents.get(_quick_key) is _AGENT_PENDING_SENTINEL:
                del self._running_agents[_quick_key]
            self._running_agents_ts.pop(_quick_key, None)

    

    

    
    

    

