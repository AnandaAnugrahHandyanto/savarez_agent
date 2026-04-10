"""View 8: Zeus — Overseer Monitor dashboard view.

Mirrors the standalone ``hermes zeus`` Rich TUI inside the Olympus dashboard,
showing live session turns, overseer evaluations, queue status, and Zeus
configuration at a glance.

Features:
- Zeus hero art with thunderbolt motif
- Overseer status panel (enabled/model/endpoint)
- Session turns table (last N turns from session notes)
- Overseer evaluations timeline
- Message queue indicator
- Recent file activity
"""

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, ScrollableContainer
from textual.reactive import reactive
from textual.widgets import Static
from textual import work


ZEUS_HERO = """\
[dim #0A0A12]░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░[/]
[dim #1A1A38]░░[/][#2A2A50]╔════════════════════════════════════════════════════════════════════════════════════════════════════════════════╗[/][dim #1A1A38]░░[/]
[dim #1A1A38]░░[/][#2A2A50]║[/]                                                                                                              [#2A2A50]║[/][dim #1A1A38]░░[/]
[dim #1A1A38]░░[/][#2A2A50]║[/]      [dim #3A3A6A]⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣀⣀⣀⣀⣀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]       [bold #E0E0FF]╔═══════════════════════════════════════╗[/]      [#2A2A50]║[/][dim #1A1A38]░░[/]
[dim #1A1A38]░░[/][#2A2A50]║[/]      [dim #3A3A6A]⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣠⣴⣾⣿⣿⣿⣿⣿⣿⣿⣷⣦⣄⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]       [bold #E0E0FF]║[/]  [bold #F0F0FF]👁 ZEUS OVERSEER 👁[/]              [bold #E0E0FF]║[/]      [#2A2A50]║[/][dim #1A1A38]░░[/]
[dim #1A1A38]░░[/][#2A2A50]║[/]      [#C0C0FF]⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣠⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣦⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]       [bold #E0E0FF]║[/]  [dim #00D4FF]Divine Supervision & Judgment[/]       [bold #E0E0FF]║[/]      [#2A2A50]║[/][dim #1A1A38]░░[/]
[dim #1A1A38]░░[/][#2A2A50]║[/]      [#E0E0FF]⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣼⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣧⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]       [bold #E0E0FF]╠═══════════════════════════════════════╣[/]      [#2A2A50]║[/][dim #1A1A38]░░[/]
[dim #1A1A38]░░[/][#2A2A50]║[/]      [#F0F0FF]⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣾⣿⣿⣿⣿⣿⣿⣿[/][bold #FFFFFF]👁[/][#F0F0FF]⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡄⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]       [bold #E0E0FF]║[/]                                       [bold #E0E0FF]║[/]      [#2A2A50]║[/][dim #1A1A38]░░[/]
[dim #1A1A38]░░[/][#2A2A50]║[/]      [#FFFFFF]⠀⠀⠀⠀⠀⠀⠀⠀⠀⢸⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡇⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]       [bold #E0E0FF]║[/]  [#F0F0FF]👁[/] [dim #555577]ZEUS[/] — King of the Gods      [bold #E0E0FF]║[/]      [#2A2A50]║[/][dim #1A1A38]░░[/]
[dim #1A1A38]░░[/][#2A2A50]║[/]      [#E0E0FF]⠀⠀⠀⠀⠀⠀⠀⠀⠀⠘⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⠃⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]       [bold #E0E0FF]║[/]  [dim #00D4FF]oversee · judge · command[/]          [bold #E0E0FF]║[/]      [#2A2A50]║[/][dim #1A1A38]░░[/]
[dim #1A1A38]░░[/][#2A2A50]║[/]      [#C0C0FF]⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠹⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⠏⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]       [bold #E0E0FF]║[/]                                       [bold #E0E0FF]║[/]      [#2A2A50]║[/][dim #1A1A38]░░[/]
[dim #1A1A38]░░[/][#2A2A50]║[/]      [dim #3A3A6A]⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠙⢿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡿⠋⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]       [bold #E0E0FF]║[/]  [dim #555577]Session Turns • Evaluations[/]       [bold #E0E0FF]║[/]      [#2A2A50]║[/][dim #1A1A38]░░[/]
[dim #1A1A38]░░[/][#2A2A50]║[/]      [dim #3A3A6A]⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠉⠛⠻⠿⠿⠿⠿⠿⠿⠟⠛⠉⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]       [bold #E0E0FF]╚═══════════════════════════════════════╝[/]      [#2A2A50]║[/][dim #1A1A38]░░[/]
[dim #1A1A38]░░[/][#2A2A50]║[/]                                                                                                              [#2A2A50]║[/][dim #1A1A38]░░[/]
[dim #1A1A38]░░[/][#2A2A50]╚════════════════════════════════════════════════════════════════════════════════════════════════════════════════╝[/][dim #1A1A38]░░[/]
[dim #0A0A12]░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░[/]\
"""

MAX_TURNS_SHOWN = 12
USER_MSG_TRUNCATE = 50
RESPONSE_TRUNCATE = 45
MAX_EVALS_SHOWN = 6
MAX_FILES_SHOWN = 8
EVAL_MSG_TRUNCATE = 60


class ZeusHero(Static):
    """Zeus hero art banner."""

    def render(self) -> str:
        return ZEUS_HERO


class OverseerPanel(Static):
    """Shows Zeus Overseer configuration and live status."""

    overseer_data: reactive[dict] = reactive(dict, always_update=True)

    def render(self) -> str:
        data = self.overseer_data
        if not data:
            return "[dim #555577]Loading overseer status…[/]"

        cfg = data.get("overseer_config", {})
        enabled = cfg.get("enabled", False)
        model = cfg.get("model", "unknown")
        base_url = cfg.get("base_url", "")

        lines = ["[bold #F0F0FF]👁 ZEUS OVERSEER STATUS[/]", ""]

        if enabled:
            lines.append("[#00FF99]● ACTIVE[/]")
        else:
            lines.append("[#FF4444]○ DISABLED[/]  [dim #555577]enable in config.yaml → overseer.enabled: true[/]")

        lines.append(f"[dim #C9A227]Model:[/]    [#00D4FF]{model}[/]")
        if base_url:
            url_short = base_url.replace("http://", "").replace("https://", "")
            lines.append(f"[dim #C9A227]Endpoint:[/] [dim #888888]{url_short}[/]")

        queued = data.get("queued_messages", [])
        if queued:
            lines.append("")
            lines.append(f"[bold #FFD700]📬 {len(queued)} message(s) queued for Hermes[/]")
            for msg in queued[:3]:
                text = msg.get("message", "")[:40]
                pri = msg.get("priority", "normal")
                pri_color = "#FF4444" if pri == "urgent" else "#FFD700" if pri == "high" else "#555577"
                lines.append(f"  [{pri_color}]▸[/] {text}")
        else:
            lines.append("")
            lines.append("[dim #555577]📭 No messages queued[/]")

        return "\n".join(lines)


class TurnsPanel(Static):
    """Displays recent session turns in a table-like format."""

    turns_data: reactive[list] = reactive(list, always_update=True)
    session_id: reactive[str] = reactive("")
    model: reactive[str] = reactive("")

    def render(self) -> str:
        lines = []

        header = "[bold #F0F0FF]📜 SESSION TURNS[/]"
        if self.session_id:
            sid = self.session_id[:30]
            header += f"  [dim #555577]│[/]  [dim #888888]{sid}[/]"
        if self.model:
            header += f"  [dim #555577]│[/]  [dim #00D4FF]{self.model}[/]"
        lines.append(header)
        lines.append("")

        turns = self.turns_data or []
        if not turns:
            lines.append("[dim #555577]No session turns yet — start a conversation with Hermes.[/]")
            return "\n".join(lines)

        lines.append(
            f"  [dim #C9A227]{'#':>3}  {'Time':<8}  {'User':<{USER_MSG_TRUNCATE}}  {'Tools':>6}  Response[/]"
        )
        lines.append(f"  [dim #2A2A50]{'─' * 120}[/]")

        for turn in turns[-MAX_TURNS_SHOWN:]:
            num = str(turn.get("turn", "?"))
            ts = turn.get("timestamp", "")[:8]
            user = turn.get("user", "")
            if len(user) > USER_MSG_TRUNCATE:
                user = user[:USER_MSG_TRUNCATE - 3] + "..."
            tools = turn.get("tools", [])
            tools_str = f"{len(tools)} tool{'s' if len(tools) != 1 else ''}" if tools else "-"
            resp = turn.get("response", "")
            if len(resp) > RESPONSE_TRUNCATE:
                resp = resp[:RESPONSE_TRUNCATE - 3] + "..."

            lines.append(
                f"  [#FFD700]{num:>3}[/]  [dim #888888]{ts:<8}[/]  "
                f"[#E0E0FF]{user:<{USER_MSG_TRUNCATE}}[/]  "
                f"[#00D4FF]{tools_str:>6}[/]  "
                f"[dim #888888]{resp}[/]"
            )

        lines.append("")
        lines.append(f"  [dim #555577]{len(turns)} total turn{'s' if len(turns) != 1 else ''}[/]")
        return "\n".join(lines)


class EvalsPanel(Static):
    """Displays Zeus Overseer evaluation history."""

    evals_data: reactive[list] = reactive(list, always_update=True)

    def render(self) -> str:
        lines = ["[bold #F0F0FF]⚡ OVERSEER EVALUATIONS[/]", ""]

        evals = self.evals_data or []
        if not evals:
            lines.append("[dim #555577]No evaluations yet.[/]")
            lines.append("[dim #555577]Zeus evaluates after each turn in drive/auto mode.[/]")
            return "\n".join(lines)

        for ev in evals[-MAX_EVALS_SHOWN:]:
            msg = ev.get("message", "")
            ts = ev.get("timestamp", "")

            if "COMPLETE" in msg.upper():
                icon = "[#00FF99]✓[/]"
            elif "NUDGE" in msg.upper() or "STUCK" in msg.upper():
                icon = "[#FFD700]⚡[/]"
            else:
                icon = "[#00D4FF]◈[/]"

            if len(msg) > EVAL_MSG_TRUNCATE:
                msg = msg[:EVAL_MSG_TRUNCATE - 3] + "..."

            lines.append(f"  {icon}  [dim #888888]{ts}[/]  [#E0E0FF]{msg}[/]")

        return "\n".join(lines)


class ActivityPanel(Static):
    """Shows recent file modifications from session turns."""

    activity_data: reactive[list] = reactive(list, always_update=True)

    def render(self) -> str:
        lines = ["[bold #F0F0FF]📝 RECENT FILE ACTIVITY[/]", ""]

        turns = self.activity_data or []
        all_files: list[str] = []
        for turn in turns[-8:]:
            all_files.extend(turn.get("files", []))

        seen: set[str] = set()
        unique: list[str] = []
        for f in reversed(all_files):
            if f not in seen:
                seen.add(f)
                unique.append(f)
        unique = list(reversed(unique))[-MAX_FILES_SHOWN:]

        if not unique:
            lines.append("[dim #555577]No files modified yet.[/]")
            return "\n".join(lines)

        for f in unique:
            short = f.split("/")[-1] if "/" in f else f
            ext = short.rsplit(".", 1)[-1] if "." in short else ""
            ext_colors = {
                "py": "#00D4FF", "js": "#FFD700", "ts": "#00D4FF",
                "yaml": "#C9A227", "json": "#C9A227", "md": "#00FF99",
                "txt": "#888888",
            }
            color = ext_colors.get(ext, "#888888")
            lines.append(f"  [{color}]●[/] [#E0E0FF]{short}[/]  [dim #555577]{f}[/]")

        return "\n".join(lines)


class ZeusPixelArt(Static):
    """Zeus pixel art portrait from the skin."""

    def render(self) -> str:
        try:
            from hermes_cli.dashboard.data import get_god_detail
            zeus = get_god_detail("Zeus")
            art = zeus.get("pixel_art", "")
            if art:
                return art
        except Exception:
            pass

        return (
            "[dim #2A2A50]┌────────────────────────┐[/]\n"
            "[dim #2A2A50]│[/]     [bold #F0F0FF]👁 ZEUS 👁[/]     [dim #2A2A50]│[/]\n"
            "[dim #2A2A50]│[/]  [dim #555577]King of the Gods[/]   [dim #2A2A50]│[/]\n"
            "[dim #2A2A50]└────────────────────────┘[/]"
        )


class ZeusView(ScrollableContainer):
    """View 8: Zeus — Overseer Monitor.

    Provides a dashboard-integrated version of ``hermes zeus``, showing
    live session turns, overseer evaluations, queue status, and Zeus
    configuration.
    """

    _refresh_timer = None

    def compose(self) -> ComposeResult:
        yield ZeusHero(id="zeus-hero", classes="hero-art")

        with Horizontal(classes="bento-row"):
            yield OverseerPanel(id="zeus-overseer", classes="divine-panel-gold")
            yield ZeusPixelArt(id="zeus-portrait", classes="divine-panel")

        yield TurnsPanel(id="zeus-turns", classes="divine-panel")

        with Horizontal(classes="bento-row"):
            yield EvalsPanel(id="zeus-evals", classes="divine-panel-gold")
            yield ActivityPanel(id="zeus-activity", classes="divine-panel")

    @work(thread=True)
    def load_data(self) -> None:
        """Load Zeus session data from the data layer."""
        from hermes_cli.dashboard.data import get_zeus_session_data

        data = get_zeus_session_data()
        if data:
            self.app.call_from_thread(self._apply_data, data)

    def _apply_data(self, data: dict) -> None:
        turns = data.get("turns", [])
        evals = data.get("overseer_evals", [])

        self.query_one("#zeus-overseer", OverseerPanel).overseer_data = data
        panel = self.query_one("#zeus-turns", TurnsPanel)
        panel.turns_data = turns
        panel.session_id = data.get("session_id", "")
        panel.model = data.get("model", "")
        self.query_one("#zeus-evals", EvalsPanel).evals_data = evals
        self.query_one("#zeus-activity", ActivityPanel).activity_data = turns

    def on_show(self) -> None:
        self.load_data()
        if self._refresh_timer is None:
            self._refresh_timer = self.set_interval(2.0, self._refresh)

    def on_hide(self) -> None:
        if self._refresh_timer is not None:
            self._refresh_timer.stop()
            self._refresh_timer = None

    def _refresh(self) -> None:
        """Periodic refresh of Zeus data."""
        try:
            self.load_data()
        except Exception:
            pass
