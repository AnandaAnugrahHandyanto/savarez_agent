"""Fleet monitor — tracks Hermes agent fleet and mirrors to Telegram + CLI.

Hooks into existing AIAgent callbacks (thinking, tool_progress, status, step)
and delegate_tool lifecycle events to maintain a live fleet state, then pushes
formatted updates to a Telegram chat and CLI observers for full observability.

Telegram config is read from:
  1. ~/.hermes/config.yaml  gateway.platforms.telegram.token + home_channel.chat_id
  2. Env overrides: FLEET_TELEGRAM_TOKEN, FLEET_TELEGRAM_CHAT_ID

CLI observability is enabled via:
  display.subagent_observability: full | summary | off

Usage from cli.py (after agent creation):
    from agent.fleet_monitor import init_fleet_monitor, get_fleet_monitor
    init_fleet_monitor(config)
    monitor = get_fleet_monitor()
    agent.thinking_callback  = monitor.wrap_thinking(agent.thinking_callback)
    agent.tool_progress_callback = monitor.wrap_tool(agent.tool_progress_callback)
    agent.status_callback    = monitor.on_status
"""

import datetime
import logging
import os
import queue
import threading
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable

logger = logging.getLogger(__name__)


GOD_ICONS: Dict[str, str] = {
    "Hermes":     "~E~",
    "Athena":     ">O<",
    "Hephaestus": "[#]",
    "Poseidon":   "-Y-",
    "Artemis":    "->-",
    "Apollo":     "*O*",
    "Ares":       ">|<",
    "Zeus":       "/|\\",
    "Demeter":    "@.@",
    "Dionysus":   "<~>",
    "Hades":      "X.X",
}

GOD_ROLES: Dict[str, str] = {
    "Hermes":     "Orchestrator / Router",
    "Athena":     "Planner / Strategy",
    "Hephaestus": "Code Forge / Builder",
    "Poseidon":   "Tools / APIs / External",
    "Artemis":    "Search / Hunt / Retrieval",
    "Apollo":     "Oracle / Knowledge / RAG",
    "Ares":       "Executor / Task Runner",
    "Zeus":       "Critic / Validation",
    "Demeter":    "Memory / Storage",
    "Dionysus":   "Reflection / Improvement",
    "Hades":      "Failure Watch / Recovery",
}

STATUS_ICONS: Dict[str, str] = {
    "idle":        "...",
    "spawning":    ">>>",
    "thinking":    "???",
    "querying":    "<->",
    "processing":  "###",
    "responding":  ">>-",
    "complete":    "[x]",
    "failed":      "!!!",
    "interrupted": "/!\\",
    "retrying":    "<>",
}

# ASCII art faces — shown in Telegram when a god is the active worker.
# Kept compact (≤8 lines, ≤28 chars wide) for mobile readability.
GOD_ART: Dict[str, str] = {
    "Hermes": (
        "   /\\  ~E~  /\\\n"
        "  (  \\____/  )\n"
        "  ( . o  o . )\n"
        "   \\ . -- . /\n"
        "  ~~|  --  |~~\n"
        "    |  /\\  |\n"
        "   /~~  ~~\\\n"
        "  ~ messenger ~"
    ),
    "Athena": (
        "   ^ ^ ^ ^ ^\n"
        "   /~~~~~~~\\\n"
        "  | o --- o |\n"
        "  |  ` ^ `  |\n"
        "  |  =====  |\n"
        "   \\_______/\n"
        "  -^--^--^--\n"
        "  [ strategy ]"
    ),
    "Hephaestus": (
        "  [#]  [#]  [#]\n"
        "  /~~------~~\\\n"
        " | o      o |\n"
        " |   ====   |\n"
        " |_/~~~~~~\\_|\n"
        " |   ####   |\n"
        " |__ #### __|\n"
        "  [  forge  ]"
    ),
    "Poseidon": (
        "  -Y-  -Y-  -Y-\n"
        "  /~~~~~~~~~~~\\\n"
        " | o ----- o |\n"
        " |   ` ~ `   |\n"
        "  \\~~~~~~~~~/\n"
        "  ~~~~~~~~~~~\n"
        "  ~ ~ ~ ~ ~ ~\n"
        "  [  depths  ]"
    ),
    "Artemis": (
        "    ->   ->\n"
        "   /--------\\\n"
        "  | o --- o |\n"
        "  |  ` ^ `  |\n"
        "   \\-------/\n"
        "   /|     |\\\n"
        "  -*----- -*-\n"
        "  [  hunter  ]"
    ),
    "Apollo": (
        "  *.*  *.*  *.*\n"
        "  /~~-------~~\\\n"
        " | o ----- o |\n"
        " |   ` O `   |\n"
        "  \\---------/\n"
        "  -|---------|--\n"
        "  -|---------|--\n"
        "  [  oracle  ]"
    ),
    "Ares": (
        "  >|<  >|<  >|<\n"
        "  /##########\\\n"
        " |o ------- o|\n"
        " |  `  #  `  |\n"
        " |  ========  |\n"
        "  \\##########/\n"
        "  /|        |\\\n"
        "  [ execute ]"
    ),
    "Zeus": (
        "  /|\\  /|\\  /|\\\n"
        "  /~~------~~\\\n"
        " |o ------- o|\n"
        " |   ` - `   |\n"
        " |  =======  |\n"
        "  \\---------/\n"
        "  ~-----------~\n"
        "  [  judge  ]"
    ),
    "Demeter": (
        "  -#-  -#-  -#-\n"
        "  /~~-------~~\\\n"
        " | o ----- o |\n"
        " |   ` w `   |\n"
        "  \\---------/\n"
        "  ~*-------*~\n"
        "  ~*-------*~\n"
        "  [  memory  ]"
    ),
    "Dionysus": (
        "  <~>  <~>  <~>\n"
        "  /~~-------~~\\\n"
        " | o ----- o |\n"
        " |   ` & `   |\n"
        "  \\---------/\n"
        "  ~~~~~~~~~~~\n"
        "  ~~~~~~~~~~~\n"
        "  [ reflect ]"
    ),
    "Hades": (
        "  X.X  X.X  X.X\n"
        "  /##-------##\\\n"
        " |o ------- o|\n"
        " |   ` v `   |\n"
        " |###########|\n"
        "  \\#########/\n"
        "  ...........\n"
        "  [ recovery ]"
    ),
}


@dataclass
class ToolCall:
    """Record of a single tool invocation."""
    name: str
    preview: str = ""
    start_time: float = field(default_factory=time.time)
    duration: float = 0.0
    status: str = "running"  # running, success, error


@dataclass
class AgentState:
    name: str
    role: str = ""
    status: str = "thinking"
    current_tool: str = ""
    tool_preview: str = ""
    step: int = 0
    max_iterations: int = 50
    start_time: float = field(default_factory=time.time)
    last_activity: float = field(default_factory=time.time)
    parent: str = "Hermes"
    last_event: str = ""
    goal: str = ""
    thinking_snippet: str = ""
    tool_history: List[ToolCall] = field(default_factory=list)
    tokens_in: int = 0
    tokens_out: int = 0
    api_calls: int = 0

    @property
    def progress_pct(self) -> float:
        """Estimated progress as percentage (0-100)."""
        if self.max_iterations <= 0:
            return 0.0
        return min(100.0, (self.step / self.max_iterations) * 100)

    @property
    def elapsed_seconds(self) -> float:
        """Seconds since agent started."""
        return time.time() - self.start_time


@dataclass
class FleetState:
    task: str = ""
    start_time: float = field(default_factory=time.time)
    agents: Dict[str, AgentState] = field(default_factory=dict)
    events: List[str] = field(default_factory=list)


class FleetMonitor:
    """Central fleet state tracker with Telegram push and CLI observer support."""

    MAX_EVENTS = 30
    MAX_TOOL_HISTORY = 20  # per agent
    DEBOUNCE_NORMAL = 4.0   # seconds between routine pushes
    DEBOUNCE_URGENT = 0.8   # seconds between urgent pushes

    THINKING_SNIPPET_LEN = 60
    TOOL_PREVIEW_LEN = 50
    TASK_DISPLAY_LEN = 80
    TASK_DISPLAY_SHORT_LEN = 60
    TELEGRAM_HTTP_TIMEOUT = 6
    TELEGRAM_ERROR_SLEEP = 5
    QUEUE_GET_TIMEOUT = 60
    FLEET_SNAPSHOT_TOOLS = 5
    FLEET_SNAPSHOT_EVENTS = 10
    RESET_DELAY_SECONDS = 8.0

    def __init__(self):
        self._state = FleetState()
        self._lock = threading.Lock()
        self._push_queue: queue.Queue = queue.Queue(maxsize=50)
        self._tg_token: Optional[str] = None
        self._tg_chat_id: Optional[str] = None
        self._enabled = False
        self._verbose_mode = "normal"   # quiet / normal / god
        self._observability = "summary"  # off / summary / full
        self._push_thread: Optional[threading.Thread] = None
        # CLI observers — callbacks that receive real-time fleet updates
        self._cli_observers: List[Callable[[str, Dict[str, Any]], None]] = []

    # ------------------------------------------------------------------
    # Init
    # ------------------------------------------------------------------

    def init(self, config: dict) -> None:
        """Load Telegram config and start push thread."""
        try:
            gw = config.get("gateway", {})
            plats = gw.get("platforms", {})
            tg = plats.get("telegram", {})
            self._tg_token = (
                os.getenv("FLEET_TELEGRAM_TOKEN")
                or tg.get("token")
                or os.getenv("TELEGRAM_BOT_TOKEN")
            )
            home = tg.get("home_channel", {})
            chat_id = ""
            if isinstance(home, dict):
                chat_id = str(home.get("chat_id", ""))
            self._tg_chat_id = os.getenv("FLEET_TELEGRAM_CHAT_ID") or chat_id
        except Exception as e:
            logger.debug("Fleet monitor config error: %s", e)

        self._enabled = bool(self._tg_token and self._tg_chat_id)
        if self._enabled:
            self._push_thread = threading.Thread(
                target=self._push_worker, daemon=True, name="fleet-tg"
            )
            self._push_thread.start()
            logger.info("Fleet monitor: Telegram mirror active → chat %s", self._tg_chat_id)
        else:
            logger.debug("Fleet monitor: Telegram not configured (set FLEET_TELEGRAM_TOKEN + FLEET_TELEGRAM_CHAT_ID)")

        # Always register Hermes as root
        with self._lock:
            self._state.agents["Hermes"] = AgentState(
                name="Hermes", role=GOD_ROLES["Hermes"]
            )

    def set_verbose_mode(self, mode: str) -> None:
        """Set verbosity: quiet / normal / god."""
        self._verbose_mode = mode.lower().strip()
        with self._lock:
            self._log(f"Verbose mode: {self._verbose_mode.upper()}")
        self._push(urgent=True)

    def set_observability(self, level: str) -> None:
        """Set CLI observability level: off / summary / full."""
        self._observability = level.lower().strip()

    # ------------------------------------------------------------------
    # CLI Observer API
    # ------------------------------------------------------------------

    def register_observer(self, callback: Callable[[str, Dict[str, Any]], None]) -> None:
        """Register a CLI observer callback.
        
        Callback receives (event_type, data) where event_type is one of:
          - "god_spawned": data = {name, role, goal, parent}
          - "god_thinking": data = {name, snippet}
          - "god_tool_start": data = {name, tool, preview}
          - "god_tool_complete": data = {name, tool, duration, status}
          - "god_progress": data = {name, step, max_iterations, api_calls}
          - "god_complete": data = {name, result_preview, duration, api_calls}
          - "god_failed": data = {name, error}
          - "fleet_update": data = {agents: Dict[name, AgentState]}
        """
        if callback not in self._cli_observers:
            self._cli_observers.append(callback)

    def unregister_observer(self, callback: Callable) -> None:
        """Remove a CLI observer callback."""
        if callback in self._cli_observers:
            self._cli_observers.remove(callback)

    def _notify_observers(self, event_type: str, data: Dict[str, Any]) -> None:
        """Notify all registered CLI observers of an event."""
        if self._observability == "off":
            return
        for cb in self._cli_observers:
            try:
                cb(event_type, data)
            except Exception as e:
                logger.debug("Observer callback error: %s", e)

    def get_fleet_snapshot(self) -> Dict[str, Any]:
        """Return a snapshot of current fleet state for dashboard rendering."""
        with self._lock:
            return {
                "task": self._state.task,
                "start_time": self._state.start_time,
                "elapsed": time.time() - self._state.start_time,
                "agents": {
                    name: {
                        "name": a.name,
                        "role": a.role,
                        "status": a.status,
                        "goal": a.goal,
                        "current_tool": a.current_tool,
                        "tool_preview": a.tool_preview,
                        "thinking_snippet": a.thinking_snippet,
                        "step": a.step,
                        "max_iterations": a.max_iterations,
                        "progress_pct": a.progress_pct,
                        "elapsed": a.elapsed_seconds,
                        "api_calls": a.api_calls,
                        "tokens_in": a.tokens_in,
                        "tokens_out": a.tokens_out,
                        "tool_history": [
                            {"name": t.name, "preview": t.preview, "duration": t.duration, "status": t.status}
                            for t in a.tool_history[-self.FLEET_SNAPSHOT_TOOLS:]
                        ],
                        "parent": a.parent,
                    }
                    for name, a in self._state.agents.items()
                },
                "events": list(self._state.events[-self.FLEET_SNAPSHOT_EVENTS:]),
            }

    # ------------------------------------------------------------------
    # Callback wrappers (wrap existing cli.py callbacks)
    # ------------------------------------------------------------------

    def wrap_thinking(self, original: Optional[Callable]) -> Callable:
        """Return a thinking_callback that notifies the monitor then calls original."""
        monitor = self

        def _thinking(text: str) -> None:
            if text and not text.startswith("_"):
                with monitor._lock:
                    agent = monitor._get_or_create("Hermes")
                    agent.status = "thinking"
                    agent.last_event = (text[:monitor.THINKING_SNIPPET_LEN] if text else "")
                    agent.last_activity = time.time()
                    if monitor._verbose_mode == "god":
                        monitor._log(f"Hermes thinking: {text[:monitor.THINKING_SNIPPET_LEN]}")
                if monitor._verbose_mode == "god":
                    monitor._push(urgent=False)
            if original:
                original(text)

        return _thinking

    def wrap_tool(self, original: Optional[Callable]) -> Callable:
        """Return a tool_progress_callback that notifies the monitor then calls original."""
        monitor = self

        def _tool(function_name: str, preview: str, function_args: dict) -> None:
            if function_name and not function_name.startswith("_"):
                with monitor._lock:
                    agent = monitor._get_or_create("Hermes")
                    agent.status = "querying"
                    agent.current_tool = function_name
                    agent.tool_preview = (preview or "")[:monitor.TOOL_PREVIEW_LEN]
                    agent.last_activity = time.time()
                    short = f" → {agent.tool_preview}" if agent.tool_preview else ""
                    agent.last_event = f"{function_name}{short}"
                    monitor._log(f"Hermes: {function_name}{short}")
                monitor._push(urgent=False)
            if original:
                original(function_name, preview, function_args)

        return _tool

    def on_status(self, category: str, message: str) -> None:
        """status_callback — lifecycle events from AIAgent."""
        with self._lock:
            self._log(f"[{category}] {message}")
            if any(kw in message.lower() for kw in ("error", "fail", "interrupt", "retry")):
                agent = self._get_or_create("Hermes")
                agent.status = "interrupted"
                agent.last_event = message[:self.THINKING_SNIPPET_LEN]
        is_critical = any(kw in message.lower() for kw in ("error", "fail", "interrupt"))
        self._push(urgent=is_critical)

    # ------------------------------------------------------------------
    # God lifecycle (called from delegate_tool.py)
    # ------------------------------------------------------------------

    def on_task_start(self, task: str) -> None:
        with self._lock:
            self._state.task = task[:self.TASK_DISPLAY_LEN]
            self._state.start_time = time.time()
            self._state.events.clear()
            agent = self._get_or_create("Hermes")
            agent.status = "thinking"
            agent.step = 0
            self._log(f"Task received: {task[:self.TASK_DISPLAY_SHORT_LEN]}")
        self._push(urgent=True)

    def on_god_spawned(
        self, name: str, role: str = "", goal: str = "", parent: str = "Hermes",
        max_iterations: int = 50,
    ) -> None:
        with self._lock:
            resolved_role = role or GOD_ROLES.get(name, "Subagent")
            self._state.agents[name] = AgentState(
                name=name, role=resolved_role, status="spawning", parent=parent,
                goal=goal, max_iterations=max_iterations,
            )
            hermes = self._get_or_create("Hermes")
            hermes.status = "processing"
            goal_short = goal[:self.TOOL_PREVIEW_LEN] if goal else resolved_role
            self._log(f"Hermes → {name}: {goal_short}")
        self._push(urgent=True)
        self._notify_observers("god_spawned", {
            "name": name, "role": resolved_role, "goal": goal, "parent": parent,
        })

    def on_god_thinking(self, name: str, snippet: str) -> None:
        """Called when a subagent emits thinking/reasoning content."""
        with self._lock:
            agent = self._get_or_create(name)
            agent.status = "thinking"
            agent.thinking_snippet = (snippet[:self.TASK_DISPLAY_LEN] if snippet else "")
            agent.last_activity = time.time()
            if self._verbose_mode == "god":
                self._log(f"{name} 💭 {snippet[:40]}")
        if self._observability == "full":
            self._notify_observers("god_thinking", {"name": name, "snippet": snippet})

    def on_god_tool_start(self, name: str, tool: str, preview: str = "") -> None:
        """Called when a subagent starts a tool call."""
        with self._lock:
            agent = self._get_or_create(name)
            agent.status = "querying"
            agent.current_tool = tool
            agent.tool_preview = (preview or "")[:self.TOOL_PREVIEW_LEN]
            agent.last_activity = time.time()
            agent.tool_history.append(ToolCall(name=tool, preview=preview[:self.TOOL_PREVIEW_LEN]))
            if len(agent.tool_history) > self.MAX_TOOL_HISTORY:
                agent.tool_history.pop(0)
            self._log(f"{name}: {tool} → {preview[:30]}" if preview else f"{name}: {tool}")
        self._push(urgent=False)
        self._notify_observers("god_tool_start", {"name": name, "tool": tool, "preview": preview})

    def on_god_tool_complete(self, name: str, tool: str, duration: float, status: str = "success") -> None:
        """Called when a subagent completes a tool call."""
        with self._lock:
            agent = self._get_or_create(name)
            agent.current_tool = ""
            agent.last_activity = time.time()
            if agent.tool_history and agent.tool_history[-1].name == tool:
                agent.tool_history[-1].duration = duration
                agent.tool_history[-1].status = status
        if self._observability == "full":
            self._notify_observers("god_tool_complete", {
                "name": name, "tool": tool, "duration": duration, "status": status,
            })

    def on_god_progress(self, name: str, step: int, api_calls: int = 0, tokens_in: int = 0, tokens_out: int = 0) -> None:
        """Called to update subagent progress metrics."""
        with self._lock:
            agent = self._get_or_create(name)
            agent.step = step
            agent.api_calls = api_calls
            agent.tokens_in = tokens_in
            agent.tokens_out = tokens_out
            agent.last_activity = time.time()
        self._notify_observers("god_progress", {
            "name": name, "step": step, "max_iterations": agent.max_iterations,
            "api_calls": api_calls, "tokens_in": tokens_in, "tokens_out": tokens_out,
        })

    def on_god_complete(self, name: str, result_preview: str = "", api_calls: int = 0) -> None:
        with self._lock:
            agent = self._get_or_create(name)
            agent.status = "complete"
            agent.current_tool = ""
            agent.last_activity = time.time()
            agent.api_calls = api_calls
            short = result_preview[:self.TOOL_PREVIEW_LEN] if result_preview else "done"
            agent.last_event = short
            duration = agent.elapsed_seconds
            self._log(f"{name} ✓ {short}")
        self._push(urgent=True)
        self._notify_observers("god_complete", {
            "name": name, "result_preview": result_preview, "duration": duration, "api_calls": api_calls,
        })

    def on_god_failed(self, name: str, error: str = "") -> None:
        with self._lock:
            agent = self._get_or_create(name)
            agent.status = "failed"
            agent.last_activity = time.time()
            agent.last_event = error[:self.THINKING_SNIPPET_LEN] if error else "failed"
            self._log(f"⚠ {name} failed: {error[:50]}")
        self._push(urgent=True)
        self._notify_observers("god_failed", {"name": name, "error": error})

    def on_response_complete(self) -> None:
        with self._lock:
            agent = self._get_or_create("Hermes")
            agent.status = "complete"
            agent.current_tool = ""
            self._log("Response delivered ✓")
        self._push(urgent=True)
        threading.Timer(self.RESET_DELAY_SECONDS, self._reset_subagents).start()

    # ------------------------------------------------------------------
    # Telegram formatting
    # ------------------------------------------------------------------

    def _format_message(self) -> str:
        state = self._state
        now = time.time()
        elapsed = int(now - state.start_time)
        mins, secs = divmod(elapsed, 60)
        elapsed_str = f"{mins}:{secs:02d}"

        lines: List[str] = []
        lines.append(f"⚡ <b>OLYMPUS FLEET</b>  ·  ⏱ {elapsed_str}")

        if state.task:
            task_display = state.task if len(state.task) <= 70 else state.task[:67] + "..."
            lines.append(f"<i>{task_display}</i>")

        lines.append("──────────────────────")

        hermes = state.agents.get("Hermes")
        if hermes:
            lines.append(self._format_agent(hermes))

        children = [a for n, a in state.agents.items() if n != "Hermes"]
        for agent in children:
            lines.append(self._format_agent(agent, child=True))

        # Active god ASCII art — show the god currently doing work
        active_god = None
        active_statuses = ("spawning", "thinking", "querying", "processing")
        for name, agent in state.agents.items():
            if name != "Hermes" and agent.status in active_statuses:
                active_god = agent
                break
        # Fall back to Hermes if no child is active
        if active_god is None and hermes and hermes.status in active_statuses:
            active_god = hermes

        if active_god and active_god.name in GOD_ART:
            art = GOD_ART[active_god.name]
            lines.append("")
            lines.append(f"<code>{art}</code>")

        if state.events and self._verbose_mode != "quiet":
            count = 8 if self._verbose_mode == "god" else 4
            lines.append("")
            lines.append("<b>Events</b>")
            for evt in state.events[-count:]:
                lines.append(f"  {evt}")

        lines.append("──────────────────────")
        mode_label = f"👁 GOD MODE" if self._verbose_mode == "god" else f"mode: {self._verbose_mode}"
        lines.append(f"<code>{mode_label}</code>  ·  reply /abort /mode /status")

        return "\n".join(lines)

    def _format_agent(self, agent: AgentState, child: bool = False) -> str:
        icon = GOD_ICONS.get(agent.name, "◈")
        s_icon = STATUS_ICONS.get(agent.status, "◈")
        prefix = "  └ " if child else ""
        name_part = f"<b>{agent.name}</b>"

        detail = ""
        if agent.current_tool and agent.status not in ("complete", "failed", "idle"):
            preview = f" → {agent.tool_preview}" if agent.tool_preview else ""
            detail = f"  <code>{agent.current_tool}{preview}</code>"
        elif agent.last_event and agent.status in ("complete", "failed"):
            detail = f"  <i>{agent.last_event}</i>"
        elif agent.role and agent.status in ("spawning", "thinking"):
            detail = f"  <i>{agent.role}</i>"

        return f"{prefix}{icon} {name_part} {s_icon}{detail}"

    # ------------------------------------------------------------------
    # Telegram push (background thread)
    # ------------------------------------------------------------------

    def _push(self, urgent: bool = False) -> None:
        if not self._enabled:
            return
        try:
            self._push_queue.put_nowait(urgent)
        except queue.Full:
            pass

    def _push_worker(self) -> None:
        import requests

        last_push = 0.0
        last_msg_id: Optional[int] = None

        while True:
            try:
                urgent = self._push_queue.get(timeout=self.QUEUE_GET_TIMEOUT)

                while not self._push_queue.empty():
                    try:
                        latest = self._push_queue.get_nowait()
                        urgent = urgent or latest
                    except queue.Empty:
                        break

                now = time.time()
                debounce = self.DEBOUNCE_URGENT if urgent else self.DEBOUNCE_NORMAL
                wait = debounce - (now - last_push)
                if wait > 0:
                    time.sleep(wait)

                text = self._format_message()
                base = f"https://api.telegram.org/bot{self._tg_token}"

                edited = False
                if last_msg_id:
                    r = requests.post(
                        f"{base}/editMessageText",
                        json={
                            "chat_id": self._tg_chat_id,
                            "message_id": last_msg_id,
                            "text": text,
                            "parse_mode": "HTML",
                        },
                        timeout=self.TELEGRAM_HTTP_TIMEOUT,
                    )
                    edited = r.ok

                if not edited:
                    r = requests.post(
                        f"{base}/sendMessage",
                        json={
                            "chat_id": self._tg_chat_id,
                            "text": text,
                            "parse_mode": "HTML",
                        },
                        timeout=self.TELEGRAM_HTTP_TIMEOUT,
                    )
                    if r.ok:
                        last_msg_id = r.json().get("result", {}).get("message_id")
                    else:
                        logger.debug("Fleet TG push failed: %s", r.text[:200])

                last_push = time.time()

            except queue.Empty:
                pass
            except Exception as e:
                logger.debug("Fleet monitor push error: %s", e)
                time.sleep(self.TELEGRAM_ERROR_SLEEP)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_or_create(self, name: str) -> AgentState:
        """Get or create agent state. Call with self._lock held."""
        if name not in self._state.agents:
            self._state.agents[name] = AgentState(
                name=name, role=GOD_ROLES.get(name, "Subagent")
            )
        return self._state.agents[name]

    def _log(self, message: str) -> None:
        """Append timestamped event. Call with self._lock held."""
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        self._state.events.append(f"[{ts}] {message}")
        if len(self._state.events) > self.MAX_EVENTS:
            self._state.events.pop(0)

    def _reset_subagents(self) -> None:
        with self._lock:
            hermes = self._state.agents.get("Hermes")
            self._state.agents.clear()
            if hermes:
                hermes.status = "idle"
                hermes.current_tool = ""
                hermes.last_event = ""
                self._state.agents["Hermes"] = hermes


_monitor: Optional[FleetMonitor] = None


def get_fleet_monitor() -> FleetMonitor:
    global _monitor
    if _monitor is None:
        _monitor = FleetMonitor()
    return _monitor


def init_fleet_monitor(config: dict) -> FleetMonitor:
    monitor = get_fleet_monitor()
    monitor.init(config)
    return monitor
