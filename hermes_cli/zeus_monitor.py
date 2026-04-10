"""Zeus Monitor — Autonomous supervisor that drives Hermes.

Run in a separate terminal to supervise your Hermes session:
    hermes zeus              # Watch mode (read-only)
    hermes zeus --drive      # Drive mode (Zeus responds when Hermes stops)
    hermes zeus --auto       # Full auto mode (Zeus runs autonomously all day)

In drive/auto mode, Zeus:
- Watches for when Hermes completes a turn
- Evaluates if the task is done
- Sends follow-up instructions to keep Hermes working
- Can run your business autonomously
"""

import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

try:
    from rich.console import Console
    from rich.live import Live
    from rich.panel import Panel
    from rich.table import Table
    from rich.layout import Layout
    from rich.text import Text
    from rich import box
except ImportError:
    print("Zeus Monitor requires 'rich'. Install with: pip install rich")
    sys.exit(1)


MIN_TURNS_BETWEEN_NUDGES = 3
SESSION_NOTES_TAIL = 3000
STUCK_TURN_THRESHOLD = 4
PROGRESS_RESPONSE_MIN_LEN = 100
MONITOR_POLL_INTERVAL = 2
MAX_TURNS_DISPLAYED = 8
USER_MSG_TRUNCATE = 40
RESPONSE_TRUNCATE = 35
MAX_EVALUATIONS_SHOWN = 3


from hermes_constants import get_hermes_home


ZEUS_QUEUE_FILE = "zeus_queue.json"


def get_queue_path() -> Path:
    """Get the Zeus message queue file path."""
    return get_hermes_home() / ZEUS_QUEUE_FILE


def queue_message_for_hermes(message: str, priority: str = "normal") -> bool:
    """Queue a message for Hermes to pick up.
    
    Args:
        message: The message/instruction for Hermes
        priority: "normal", "high", or "urgent"
        
    Returns:
        True if queued successfully
    """
    queue_path = get_queue_path()
    
    try:
        # Load existing queue
        if queue_path.exists():
            queue = json.loads(queue_path.read_text(encoding="utf-8"))
        else:
            queue = {"messages": [], "last_updated": None}
        
        # Add new message
        queue["messages"].append({
            "id": f"zeus_{int(time.time() * 1000)}",
            "message": message,
            "priority": priority,
            "timestamp": datetime.now().isoformat(),
            "source": "zeus_monitor",
        })
        queue["last_updated"] = datetime.now().isoformat()
        
        # Write atomically
        tmp_path = queue_path.with_suffix(".tmp")
        tmp_path.write_text(json.dumps(queue, indent=2), encoding="utf-8")
        tmp_path.rename(queue_path)
        
        return True
    except Exception as e:
        print(f"Failed to queue message: {e}")
        return False


def get_queued_messages() -> list:
    """Get all queued messages (for Hermes to consume)."""
    queue_path = get_queue_path()
    
    if not queue_path.exists():
        return []
    
    try:
        queue = json.loads(queue_path.read_text(encoding="utf-8"))
        return queue.get("messages", [])
    except Exception:
        return []


def pop_queued_message() -> Optional[dict]:
    """Pop the next message from the queue (FIFO)."""
    queue_path = get_queue_path()
    
    if not queue_path.exists():
        return None
    
    try:
        queue = json.loads(queue_path.read_text(encoding="utf-8"))
        messages = queue.get("messages", [])
        
        if not messages:
            return None
        
        # Pop first message (FIFO)
        msg = messages.pop(0)
        queue["messages"] = messages
        queue["last_updated"] = datetime.now().isoformat()
        
        # Write back
        tmp_path = queue_path.with_suffix(".tmp")
        tmp_path.write_text(json.dumps(queue, indent=2), encoding="utf-8")
        tmp_path.rename(queue_path)
        
        return msg
    except Exception:
        return None


def clear_queue():
    """Clear all queued messages."""
    queue_path = get_queue_path()
    if queue_path.exists():
        queue_path.unlink()


def get_latest_session_notes() -> dict:
    """Load the most recent session notes file."""
    sessions_dir = get_hermes_home() / "sessions"
    if not sessions_dir.exists():
        return {}
    
    # Find the most recent notes file
    notes_files = sorted(sessions_dir.glob("notes_*.txt"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not notes_files:
        return {}
    
    latest_notes = notes_files[0]
    try:
        content = latest_notes.read_text(encoding="utf-8")
    except Exception:
        return {}
    
    # Parse the notes file
    session_id = ""
    model = ""
    turns = []
    overseer_evals = []
    
    # Extract session ID from header
    session_match = re.search(r"SESSION NOTES: (\S+)", content)
    if session_match:
        session_id = session_match.group(1)
    
    # Extract model
    model_match = re.search(r"Model: (.+)", content)
    if model_match:
        model = model_match.group(1).strip()
    
    # Parse turns
    turn_blocks = re.split(r"-{50,}", content)
    for block in turn_blocks:
        turn_match = re.search(r"TURN (\d+) \| (\d+:\d+:\d+)", block)
        if turn_match:
            turn_num = int(turn_match.group(1))
            timestamp = turn_match.group(2)
            
            user_match = re.search(r"USER: (.+?)(?:\n|$)", block)
            user_msg = user_match.group(1).strip() if user_match else ""
            
            tools = re.findall(r"→ (\w+)", block)
            files = re.findall(r"• (.+\.(?:py|js|ts|yaml|json|md|txt))", block)
            
            response_match = re.search(r"RESPONSE: (.+?)(?:\n|$)", block)
            response = response_match.group(1).strip() if response_match else ""
            
            stats_match = re.search(r"STATS: (.+?)(?:\n|$)", block)
            stats = stats_match.group(1).strip() if stats_match else ""
            
            turns.append({
                "turn": turn_num,
                "timestamp": timestamp,
                "user": user_msg,
                "tools": tools[:6],
                "files": files[:5],
                "response": response,
                "stats": stats,
            })
        
        # Parse Zeus Overseer evaluations
        zeus_match = re.search(r"\[(\d+:\d+:\d+)\] ZEUS_OVERSEER: (.+)", block)
        if zeus_match:
            overseer_evals.append({
                "timestamp": zeus_match.group(1),
                "message": zeus_match.group(2),
            })
    
    return {
        "session_id": session_id,
        "model": model,
        "turns": turns,
        "overseer_evals": overseer_evals,
        "file_path": str(latest_notes),
        "file_mtime": latest_notes.stat().st_mtime,
        "raw_content": content,
    }


def get_overseer_config() -> dict:
    """Load overseer config."""
    try:
        from hermes_cli.config import load_config
        config = load_config()
        return config.get("overseer", {})
    except Exception:
        return {}


class ZeusBrain:
    """Zeus's decision-making engine for autonomous operation.
    
    Philosophy: Zeus watches silently and only intervenes when necessary.
    - If Hermes is making progress → stay quiet
    - If Hermes seems stuck (same errors, no progress) → nudge
    - If Hermes finished but task incomplete → nudge
    - If task complete → assign next task (auto mode) or stay quiet (drive mode)
    """
    
    def __init__(self):
        self._overseer = None
        self._last_turn_count = 0
        self._consecutive_incomplete = 0
        self._consecutive_no_progress = 0
        self._tasks_completed = 0
        self._session_goal = ""
        self._auto_mode = False
        self._last_error_count = 0
        self._last_nudge_turn = 0  # Don't nudge too frequently
        self._min_turns_between_nudges = MIN_TURNS_BETWEEN_NUDGES
        
    def get_overseer(self):
        """Get or create the Zeus Overseer instance."""
        if self._overseer is None:
            try:
                from agent.zeus_overseer import get_overseer
                self._overseer = get_overseer()
            except Exception:
                pass
        return self._overseer
    
    def set_session_goal(self, goal: str):
        """Set the high-level goal for this session."""
        self._session_goal = goal
    
    def should_intervene(self, data: dict) -> bool:
        """Check if Zeus should intervene (new turn completed)."""
        turns = data.get("turns", [])
        current_count = len(turns)
        
        if current_count > self._last_turn_count:
            self._last_turn_count = current_count
            return True
        return False
    
    def evaluate_and_respond(self, data: dict) -> Optional[str]:
        """Evaluate the session and decide if intervention is needed.
        
        Zeus watches silently most of the time. Only intervenes when:
        1. Task is complete → assign next task (auto mode only)
        2. Hermes seems stuck (errors, no progress for multiple turns)
        3. Hermes stopped but task isn't done (and enough turns have passed)
        
        Returns:
            A message to send to Hermes, or None if no action needed
        """
        overseer = self.get_overseer()
        if not overseer or not overseer.enabled:
            return None
        
        turns = data.get("turns", [])
        if not turns:
            return None
        
        current_turn = len(turns)
        
        # Don't nudge too frequently — let Hermes work
        turns_since_last_nudge = current_turn - self._last_nudge_turn
        if turns_since_last_nudge < self._min_turns_between_nudges and self._last_nudge_turn > 0:
            return None  # Too soon, stay quiet
        
        # Get the last turn info
        last_turn = turns[-1]
        last_response = last_turn.get("response", "")
        tools_used = len(last_turn.get("tools", []))
        
        # Count errors in session notes
        session_notes = data.get("raw_content", "")
        error_count = session_notes.count("⚠") + session_notes.count("BLOCKED") + session_notes.count("failed")
        
        # Check if Hermes is making progress
        is_making_progress = tools_used > 0 or len(last_response) > PROGRESS_RESPONSE_MIN_LEN
        errors_increasing = error_count > self._last_error_count + 2
        
        self._last_error_count = error_count
        
        # If making progress and no major errors, stay quiet
        if is_making_progress and not errors_increasing:
            self._consecutive_no_progress = 0
            # Only evaluate completion, don't nudge if incomplete
            # Let Hermes keep working
            return None
        
        # Not making progress — track it
        self._consecutive_no_progress += 1
        
        # Only intervene if stuck for multiple turns
        if self._consecutive_no_progress < 2:
            return None  # Give Hermes more time
        
        # Hermes seems stuck — evaluate and potentially nudge
        task = self._session_goal
        if not task:
            for turn in reversed(turns):
                user_msg = turn.get("user", "")
                if user_msg and not user_msg.startswith("[Zeus"):
                    task = user_msg
                    break
        
        if not task:
            task = "Continue working on the current task"
        
        # Evaluate with Zeus
        try:
            result = overseer.evaluate(
                task=task,
                session_notes=session_notes[-SESSION_NOTES_TAIL:],
                last_response=last_response,
            )
        except Exception as e:
            return None  # Evaluation failed, stay quiet
        
        # Task complete?
        if result.complete:
            self._consecutive_incomplete = 0
            self._consecutive_no_progress = 0
            self._tasks_completed += 1
            
            if self._auto_mode:
                # In auto mode, generate the next task from briefing/goals
                next_task = self._generate_next_task(data)
                if next_task:
                    self._last_nudge_turn = current_turn
                    return next_task
            # Task complete, stay quiet
            return None
        
        # Task not complete and Hermes seems stuck
        self._consecutive_incomplete += 1
        
        # Only nudge if we have something useful to say
        if result.nudge and result.confidence > 0.5:
            self._last_nudge_turn = current_turn
            self._consecutive_no_progress = 0
            return f"[⚡ Zeus: {result.nudge}]"
        
        # Stuck for a while with no good suggestion
        if self._consecutive_no_progress >= STUCK_TURN_THRESHOLD:
            self._last_nudge_turn = current_turn
            self._consecutive_no_progress = 0
            return "[⚡ Zeus: You seem stuck. Try a different approach, check for errors, or simplify the task.]"
        
        # No intervention needed
        return None
    
    def _generate_next_task(self, data: dict) -> Optional[str]:
        """Generate the next task for AUTO mode after current task completes.
        
        Uses Zeus's chat capability to determine what to work on next based on
        the briefing file and session history.
        """
        overseer = self.get_overseer()
        if not overseer or not overseer.enabled:
            return None
        
        session_notes = data.get("raw_content", "")[-1500:]
        
        prompt = f"""The current task is COMPLETE. Based on the briefing and what's been done, what should we work on next?

What has been done so far:
{session_notes}

Tasks completed this session: {self._tasks_completed}

Look at the BRIEFING priorities and determine the next most important task.
If all priorities are done, suggest maintenance, testing, or documentation tasks.
If truly nothing left to do, respond with exactly: NOTHING_LEFT

Respond with a clear, actionable task description (1-2 sentences max)."""

        try:
            response = overseer.chat(prompt, session_context=session_notes)
            if response and "NOTHING_LEFT" not in response.upper():
                return f"[⚡ Zeus assigns next task: {response}]"
        except Exception:
            pass
        
        return None
    
    def generate_autonomous_instruction(self, data: dict, business_context: str = "") -> Optional[str]:
        """Generate an autonomous instruction based on business context.
        
        Used in full auto mode to keep Hermes working on business tasks.
        """
        overseer = self.get_overseer()
        if not overseer or not overseer.enabled:
            return None
        
        # Use Zeus's chat capability to generate next steps
        session_notes = data.get("raw_content", "")[-2000:]
        
        prompt = f"""Based on the session so far, what should the agent work on next?

Session context:
{session_notes}

Business context:
{business_context if business_context else "General development and maintenance tasks."}

Provide a clear, actionable instruction for the agent. Be specific."""

        try:
            response = overseer.chat(prompt, session_context=session_notes)
            if response:
                return f"[⚡ Zeus commands: {response}]"
        except Exception:
            pass
        
        return None


def build_layout(data: dict, overseer_cfg: dict, zeus_brain: ZeusBrain, mode: str = "watch") -> Layout:
    """Build the dashboard layout."""
    layout = Layout()
    
    # Split into left (main) and right (overseer + input) panels
    layout.split_row(
        Layout(name="main", ratio=2),
        Layout(name="sidebar", ratio=1),
    )
    
    # Main panel: Session notes
    layout["main"].split_column(
        Layout(name="header", size=3),
        Layout(name="turns", ratio=3),
        Layout(name="activity", ratio=1),
    )
    
    # Sidebar: Overseer + mode info
    layout["sidebar"].split_column(
        Layout(name="overseer", ratio=2),
        Layout(name="mode", size=8),
    )
    
    # Header
    session_id = data.get("session_id", "No active session")[:40]
    model = data.get("model", "unknown")
    header_text = Text()
    header_text.append("⚡ ZEUS MONITOR", style="bold yellow")
    header_text.append(f"  │  Session: {session_id}", style="dim")
    layout["header"].update(Panel(header_text, box=box.SIMPLE))
    
    # Turns panel
    turns = data.get("turns", [])
    turns_table = Table(box=box.SIMPLE, expand=True, show_header=True)
    turns_table.add_column("#", style="yellow", width=4)
    turns_table.add_column("Time", style="dim", width=8)
    turns_table.add_column("User", style="white", ratio=2)
    turns_table.add_column("Tools", style="cyan", width=8)
    turns_table.add_column("Response", style="dim", ratio=2)
    
    for turn in turns[-MAX_TURNS_DISPLAYED:]:
        tools_count = len(turn.get("tools", []))
        tools_str = f"{tools_count} tools" if tools_count else "-"
        
        user_short = turn.get("user", "")[:USER_MSG_TRUNCATE]
        if len(turn.get("user", "")) > USER_MSG_TRUNCATE:
            user_short += "..."
        
        resp_short = turn.get("response", "")[:RESPONSE_TRUNCATE]
        if len(turn.get("response", "")) > RESPONSE_TRUNCATE:
            resp_short += "..."
        
        turns_table.add_row(
            str(turn.get("turn", "?")),
            turn.get("timestamp", ""),
            user_short,
            tools_str,
            resp_short,
        )
    
    if not turns:
        turns_table.add_row("-", "-", "No turns yet", "-", "-")
    
    layout["turns"].update(Panel(turns_table, title="[bold yellow]📜 Session Turns[/]", border_style="yellow"))
    
    # Activity panel (recent files + queue status)
    all_files = []
    for turn in turns[-5:]:
        all_files.extend(turn.get("files", []))
    unique_files = list(dict.fromkeys(all_files))[-4:]
    
    activity_text = Text()
    if unique_files:
        for f in unique_files:
            short = f.split("/")[-1] if "/" in f else f
            activity_text.append(f"  📝 {short}\n", style="green")
    else:
        activity_text.append("  No files modified yet\n", style="dim")
    
    # Show queue status
    queued = get_queued_messages()
    if queued:
        activity_text.append(f"\n  📬 {len(queued)} message(s) queued for Hermes\n", style="yellow")
    
    layout["activity"].update(Panel(activity_text, title="[bold green]Activity[/]", border_style="green"))
    
    # Overseer panel — show Zeus's current thinking
    overseer_content = Text()
    
    enabled = overseer_cfg.get("enabled", False)
    overseer_model = overseer_cfg.get("model", "unknown")
    
    if enabled:
        overseer_content.append("● ACTIVE\n", style="bold green")
        overseer_content.append(f"Model: {overseer_model}\n\n", style="dim")
    else:
        overseer_content.append("○ DISABLED\n", style="bold red")
        overseer_content.append("Enable in config.yaml\n\n", style="dim")
    
    # Show Zeus's current assessment
    if mode in ("drive", "auto") and turns:
        overseer_content.append("Current Status:\n", style="bold white")
        
        # Progress indicator
        no_progress = zeus_brain._consecutive_no_progress
        if no_progress == 0:
            overseer_content.append("  ✓ Hermes making progress\n", style="green")
        elif no_progress == 1:
            overseer_content.append("  ◐ Watching... (1 turn)\n", style="yellow")
        elif no_progress < 4:
            overseer_content.append(f"  ◑ Monitoring ({no_progress} turns)\n", style="yellow")
        else:
            overseer_content.append(f"  ⚠ May be stuck ({no_progress} turns)\n", style="red")
        
        # Tasks completed
        if zeus_brain._tasks_completed > 0:
            overseer_content.append(f"  📋 Tasks done: {zeus_brain._tasks_completed}\n", style="cyan")
        
        # Last nudge info
        if zeus_brain._last_nudge_turn > 0:
            turns_ago = len(turns) - zeus_brain._last_nudge_turn
            overseer_content.append(f"  💬 Last nudge: {turns_ago} turns ago\n", style="dim")
        
        overseer_content.append("\n", style="dim")
    
    # Show overseer evaluations from session notes
    evals = data.get("overseer_evals", [])
    if evals:
        overseer_content.append("Evaluations:\n", style="bold white")
        for ev in evals[-MAX_EVALUATIONS_SHOWN:]:
            msg = ev.get("message", "")
            ts = ev.get("timestamp", "")
            
            if "COMPLETE" in msg.upper():
                overseer_content.append(f"  ✓ ", style="green")
            else:
                overseer_content.append(f"  ⚡ ", style="yellow")
            
            overseer_content.append(f"{ts} ", style="dim")
            msg_short = msg[:30] + "..." if len(msg) > 30 else msg
            overseer_content.append(f"{msg_short}\n", style="white")
    elif mode in ("drive", "auto"):
        overseer_content.append("Watching silently...\n", style="dim")
        overseer_content.append("Will nudge if stuck.\n", style="dim")
    else:
        overseer_content.append("No evaluations yet.\n", style="dim")
    
    layout["overseer"].update(Panel(
        overseer_content, 
        title="[bold white]👁 ZEUS OVERSEER[/]", 
        border_style="white"
    ))
    
    # Mode panel
    mode_text = Text()
    if mode == "watch":
        mode_text.append("👁 WATCH MODE\n", style="bold cyan")
        mode_text.append("Read-only monitoring\n", style="dim")
        mode_text.append("Use --drive or --auto\n", style="dim")
        mode_text.append("to enable nudges", style="dim")
    elif mode == "drive":
        mode_text.append("🚗 DRIVE MODE\n", style="bold yellow")
        mode_text.append("Nudges when stuck\n", style="dim")
        mode_text.append("Stops when complete\n", style="dim")
        mode_text.append(f"Last nudge at turn: {zeus_brain._last_nudge_turn}", style="yellow")
    elif mode == "auto":
        mode_text.append("🤖 AUTO MODE\n", style="bold green")
        mode_text.append("Nudges when stuck\n", style="dim")
        mode_text.append("Assigns next task\n", style="dim")
        mode_text.append("when complete", style="green")
    
    mode_text.append("\n\nCtrl+C to quit", style="dim")
    
    layout["mode"].update(Panel(mode_text, title="[bold]Mode[/]", border_style="blue"))
    
    return layout


def run_monitor(mode: str = "watch", goal: str = ""):
    """Run the Zeus monitor dashboard.
    
    Args:
        mode: "watch" (read-only), "drive" (respond when Hermes stops), "auto" (fully autonomous)
        goal: High-level goal for the session (used in drive/auto mode)
    """
    console = Console()
    
    mode_labels = {
        "watch": "👁 WATCH",
        "drive": "🚗 DRIVE", 
        "auto": "🤖 AUTO",
    }
    
    console.print(f"\n[bold yellow]⚡ ZEUS MONITOR[/] — {mode_labels.get(mode, 'WATCH')} MODE")
    if mode == "watch":
        console.print("[dim]Watching Hermes activity (read-only)[/]")
    elif mode == "drive":
        console.print("[dim]Zeus will respond when Hermes stops[/]")
    elif mode == "auto":
        console.print("[bold green]Zeus is driving Hermes autonomously![/]")
    console.print("[dim]Press Ctrl+C to exit[/]\n")
    
    overseer_cfg = get_overseer_config()
    last_mtime = 0
    
    # Initialize Zeus brain
    zeus_brain = ZeusBrain()
    zeus_brain._auto_mode = (mode == "auto")
    if goal:
        zeus_brain.set_session_goal(goal)
    
    # Clear any old queued messages
    if mode in ("drive", "auto"):
        clear_queue()
    
    try:
        with Live(console=console, refresh_per_second=0.5, screen=True) as live:
            while True:
                data = get_latest_session_notes()
                
                # Check if file changed
                current_mtime = data.get("file_mtime", 0)
                if current_mtime != last_mtime:
                    last_mtime = current_mtime
                    # Reload overseer config in case it changed
                    overseer_cfg = get_overseer_config()
                    
                    # In drive/auto mode, check if we should intervene
                    if mode in ("drive", "auto") and zeus_brain.should_intervene(data):
                        response = zeus_brain.evaluate_and_respond(data)
                        if response:
                            queue_message_for_hermes(response)
                
                layout = build_layout(data, overseer_cfg, zeus_brain, mode)
                live.update(layout)
                
                time.sleep(MONITOR_POLL_INTERVAL)
                
    except KeyboardInterrupt:
        console.print("\n[dim]Zeus Monitor stopped.[/]")


def main():
    """Entry point for the zeus command."""
    run_monitor()


if __name__ == "__main__":
    main()
