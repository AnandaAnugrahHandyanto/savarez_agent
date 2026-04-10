"""View 5: Session Deep Dive -- Epic Hephaestus forge art with tool chain inspector.

Features:
- Epic Hephaestus hero art (god of the forge/craftsmanship)
- Hephaestus braille pixel art portrait
- Tool-heavy sessions list with divine styling
- Session timeline with step-by-step tool chain visualization
- Divine forging statistics
"""

import json
import random
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, ScrollableContainer
from textual.reactive import reactive
from textual.widgets import Static, Input
from textual import work

FORGE_HERO_FRAME_1 = """\
[dim #0A0A12]░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░[/]
[dim #1A1A38]░░[/][#2A2A50]╔════════════════════════════════════════════════════════════════════════════════════════════════════════════════╗[/][dim #1A1A38]░░[/]
[dim #1A1A38]░░[/][#2A2A50]║[/]                                                                                                              [#2A2A50]║[/][dim #1A1A38]░░[/]
[dim #1A1A38]░░[/][#2A2A50]║[/]      [dim #3A3A6A]⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣀⣀⣀⣀⣀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]       [bold #FF8C00]╔═══════════════════════════════════════╗[/]      [#2A2A50]║[/][dim #1A1A38]░░[/]
[dim #1A1A38]░░[/][#2A2A50]║[/]      [dim #3A3A6A]⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣠⣴⣾⣿⣿⣿⣿⣿⣿⣿⣷⣦⣄⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]       [bold #FF8C00]║[/]  [bold #FFA500]🔨 THE FORGE 🔨[/]                 [bold #FF8C00]║[/]      [#2A2A50]║[/][dim #1A1A38]░░[/]
[dim #1A1A38]░░[/][#2A2A50]║[/]      [#555577]⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣠⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣦⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]       [bold #FF8C00]║[/]  [dim #00D4FF]Session Deep Dive Inspector[/]        [bold #FF8C00]║[/]      [#2A2A50]║[/][dim #1A1A38]░░[/]
[dim #1A1A38]░░[/][#2A2A50]║[/]      [#FF8C00]⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣼⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣧⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]       [bold #FF8C00]╠═══════════════════════════════════════╣[/]      [#2A2A50]║[/][dim #1A1A38]░░[/]
[dim #1A1A38]░░[/][#2A2A50]║[/]      [#FF8C00]⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣾⣿⣿⣿⣿[/][#FFA500]🔥[/][#FF8C00]⣿⣿⣿⣿⣿⣿⣿⣿[/][#FFA500]🔥[/][#FF8C00]⣿⣿⣿⣿⣿⡄⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]       [bold #FF8C00]║[/]                                       [bold #FF8C00]║[/]      [#2A2A50]║[/][dim #1A1A38]░░[/]
[dim #1A1A38]░░[/][#2A2A50]║[/]      [#FFA500]⠀⠀⠀⠀⠀⠀⠀⠀⠀⢸⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡇⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]       [bold #FF8C00]║[/]  [#FF8C00]🔨[/] [dim #555577]HEPHAESTUS[/] — Master Smith     [bold #FF8C00]║[/]      [#2A2A50]║[/][dim #1A1A38]░░[/]
[dim #1A1A38]░░[/][#2A2A50]║[/]      [#FFA500]⠀⠀⠀⠀⠀⠀⠀⠀⠀⢸⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡇⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]       [bold #FF8C00]║[/]  [dim #00D4FF]forge · strike · craft[/]            [bold #FF8C00]║[/]      [#2A2A50]║[/][dim #1A1A38]░░[/]
[dim #1A1A38]░░[/][#2A2A50]║[/]      [#FF8C00]⠀⠀⠀⠀⠀⠀⠀⠀⠀⠘⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⠃⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]       [bold #FF8C00]║[/]                                       [bold #FF8C00]║[/]      [#2A2A50]║[/][dim #1A1A38]░░[/]
[dim #1A1A38]░░[/][#2A2A50]║[/]      [#555577]⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠹⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⠏⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]       [bold #FF8C00]║[/]  [dim #555577]Tool Chain Visualization[/]          [bold #FF8C00]║[/]      [#2A2A50]║[/][dim #1A1A38]░░[/]
[dim #1A1A38]░░[/][#2A2A50]║[/]      [dim #3A3A6A]⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠙⢿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡿⠋⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]       [bold #FF8C00]╚═══════════════════════════════════════╝[/]      [#2A2A50]║[/][dim #1A1A38]░░[/]
[dim #1A1A38]░░[/][#2A2A50]║[/]      [dim #3A3A6A]⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠉⠛⠻⠿⠿⠿⠿⠿⠿⠟⠛⠉⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]                                                              [#2A2A50]║[/][dim #1A1A38]░░[/]
[dim #1A1A38]░░[/][#2A2A50]║[/]                                                                                                              [#2A2A50]║[/][dim #1A1A38]░░[/]
[dim #1A1A38]░░[/][#2A2A50]╚════════════════════════════════════════════════════════════════════════════════════════════════════════════════╝[/][dim #1A1A38]░░[/]
[dim #0A0A12]░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░[/]\
"""


def _truncate(text: str, maxlen: int = 120) -> str:
    """Truncate text to max length."""
    if not text:
        return ""
    text = text.replace("\n", " ").strip()
    if len(text) > maxlen:
        return text[:maxlen] + "..."
    return text


def _format_tool_call_args(tc: dict) -> str:
    """Format tool call arguments for display."""
    fn = tc.get("function", tc)
    args_raw = fn.get("arguments", "")
    if isinstance(args_raw, str):
        try:
            args_raw = json.loads(args_raw)
        except (json.JSONDecodeError, TypeError):
            return _truncate(str(args_raw), 80)
    if isinstance(args_raw, dict):
        parts = []
        for k, v in args_raw.items():
            val_str = _truncate(str(v), 50)
            parts.append(f"[dim #555577]{k}[/]=[#E0F7FF]{val_str}[/]")
        return "  ".join(parts)
    return _truncate(str(args_raw), 80)


class ForgeHero(Static):
    """Forge hero art widget."""
    
    def render(self) -> str:
        return FORGE_HERO_FRAME_1


class ForgeStats(Static):
    """Forge statistics bar."""
    
    stats: reactive[dict] = reactive(dict, always_update=True)
    
    def render(self) -> str:
        if not self.stats:
            return "[dim #555577]Heating the forge...[/]"
        
        total_strikes = self.stats.get("total_strikes", 0)
        heaviest = self.stats.get("heaviest_session", 0)
        avg_strikes = self.stats.get("avg_strikes", 0)
        
        return (
            f"[bold #FF8C00]🔨 Total Strikes[/]  [bold #FFA500]{total_strikes:,}[/]"
            f"     [bold #FF8C00]Heaviest Session[/]  [bold #FF4444]{heaviest}[/]"
            f"     [bold #FF8C00]Avg Strikes/Session[/]  [bold #00D4FF]{avg_strikes:.1f}[/]"
        )


class ToolHeavySessions(Static):
    """Tool-heavy sessions list with divine styling."""
    
    sessions: reactive[list] = reactive(list, always_update=True)

    def render(self) -> str:
        from hermes_cli.dashboard.data import format_timestamp
        
        header = "[bold #FF8C00]🔥 HEAVIEST FORGING SESSIONS[/]\n\n"
        header += "  [dim #FF8C00]HEAT   STRIKES  MSGS   TIME              TITLE" + " " * 20 + "MODEL              ID[/]\n"
        header += "  [dim #2A2A50]" + "─" * 100 + "[/]\n"
        
        if not self.sessions:
            return header + "[dim #555577]The forge is cold. No tool-calling sessions found.[/]"
        
        lines = []
        for s in self.sessions[:15]:
            ts = format_timestamp(s.get("started_at", 0))
            model = (s.get("model") or "?").split("/")[-1][:16]
            title = s.get("title") or _truncate(s.get("preview", ""), 30) or "untitled"
            title = title[:30]
            tc = s.get("tool_call_count", 0)
            msgs = s.get("message_count", 0)
            sid = s.get("id", "")[:12]
            
            # Heat indicator based on tool calls
            tc_color = "#FF4444" if tc > 20 else "#FFA500" if tc > 10 else "#00FF99"
            heat = "🔥" * min(tc // 10 + 1, 5)
            
            lines.append(
                f"  {heat:<7}  [{tc_color}]{tc:>5}[/]   [#00D4FF]{msgs:>3}[/]   "
                f"[dim #00A8CC]{ts:<16}[/]  [#E0F7FF]{title:<30}[/]  "
                f"[dim #555577]{model:<16}[/]  [dim #2A2A50]{sid}[/]"
            )
        
        return header + "\n".join(lines)


class HephaestusPortrait(Static):
    """Hephaestus pixel art portrait with lore and abilities."""
    
    god_data: reactive[dict] = reactive(dict, always_update=True)
    
    def render(self) -> str:
        if not self.god_data:
            return "[dim #555577]Summoning the Divine Smith...[/]"
        
        pixel_art = self.god_data.get("pixel_art", "")
        abilities = self.god_data.get("abilities", [])
        quotes = self.god_data.get("quotes", [])
        
        content = ""
        if pixel_art:
            content += pixel_art + "\n"
        
        if abilities:
            content += "\n[bold #FF8C00]DIVINE POWERS:[/]\n"
            for ability in abilities[:3]:
                content += f"  [dim #FFA500]{ability}[/]\n"
        
        if quotes:
            quote = random.choice(quotes)
            content += f"\n[italic dim #555577]\"{quote}\"[/]"
        
        return content


class SessionTimeline(Static):
    """Session timeline with step-by-step tool chain visualization."""
    
    messages: reactive[list] = reactive(list, always_update=True)
    session_meta: reactive[dict] = reactive(dict, always_update=True)

    def render(self) -> str:
        from hermes_cli.dashboard.data import format_timestamp, format_tokens, format_cost
        
        if not self.session_meta:
            return "[dim #555577]Enter a session ID above to inspect the forging log.[/]"
        
        s = self.session_meta
        sid = s.get("id", "?")
        model = s.get("model") or "unknown"
        title = s.get("title") or "untitled"
        tc = s.get("tool_call_count", 0)
        msgs_count = s.get("message_count", 0)
        tokens_in = s.get("input_tokens", 0)
        tokens_out = s.get("output_tokens", 0)
        cost = s.get("actual_cost_usd") or s.get("estimated_cost_usd") or 0
        ts = format_timestamp(s.get("started_at", 0))
        
        tc_color = '#FF4444' if tc > 20 else '#FFA500' if tc > 10 else '#00FF99'
        
        header = (
            f"[bold #FF8C00]╔═══════════════════════════════════════════════════════════════════════════════════════════════════════╗[/]\n"
            f"[bold #FF8C00]║[/]  [bold #FFA500]🔨 FORGING LOG:[/] [bold #E0F7FF]{title}[/]\n"
            f"[bold #FF8C00]╠═══════════════════════════════════════════════════════════════════════════════════════════════════════╣[/]\n"
            f"[bold #FF8C00]║[/]  [dim #00A8CC]ID[/] {sid}  [dim #00A8CC]Model[/] [#E0F7FF]{model}[/]  "
            f"[dim #00A8CC]Started[/] {ts}\n"
            f"[bold #FF8C00]║[/]  [dim #00A8CC]Messages[/] {msgs_count}  "
            f"[dim #00A8CC]Strikes[/] [{tc_color}]{tc}[/]  "
            f"[dim #00A8CC]Tokens[/] [#00D4FF]{format_tokens(tokens_in + tokens_out)}[/]  "
            f"[dim #00A8CC]Cost[/] [#FFD700]{format_cost(cost)}[/]\n"
            f"[bold #FF8C00]╚═══════════════════════════════════════════════════════════════════════════════════════════════════════╝[/]\n"
        )
        
        if not self.messages:
            return header + "\n[dim #555577]No messages in this session.[/]"
        
        lines = []
        step = 0
        
        for msg in self.messages:
            role = msg.get("role", "?")
            
            if role == "user":
                step += 1
                content = _truncate(msg.get("content") or "", 120)
                lines.append(
                    f"\n  [bold #FFA500]╔══ STEP {step} ══════════════════════════════════════════════════════════════════════════════╗[/]\n"
                    f"  [bold #00FF99]👤 USER[/]\n"
                    f"    [#E0F7FF]{content}[/]"
                )
            elif role == "assistant":
                tool_calls = msg.get("tool_calls")
                content = msg.get("content")
                
                if tool_calls and isinstance(tool_calls, list):
                    for tc_item in tool_calls:
                        fn = tc_item.get("function", tc_item)
                        name = fn.get("name", "?")
                        args_str = _format_tool_call_args(tc_item)
                        tc_id = tc_item.get("id", "")[:12]
                        lines.append(
                            f"    [bold #FF4444]🔥 STRIKE[/]  [bold #FFA500]{name}[/]  [dim #2A2A50]{tc_id}[/]\n"
                            f"      {args_str}"
                        )
                elif content:
                    text = _truncate(content, 200)
                    lines.append(f"    [bold #9B59B6]💬 RESPONSE[/]\n      [#E0F7FF]{text}[/]")
            elif role == "tool":
                tool_name = msg.get("tool_name") or "?"
                content = _truncate(msg.get("content") or "", 150)
                lines.append(
                    f"    [dim #00A8CC]⚡ YIELD[/]  [dim #FFA500]{tool_name}[/]\n"
                    f"      [dim #555577]{content}[/]"
                )
        
        return header + "\n".join(lines)


class DeepDiveView(ScrollableContainer):
    """Session Deep Dive -- Divine forge with tool chain inspector.
    
    Features:
    - Epic Hephaestus hero art
    - Hephaestus braille pixel art portrait
    - Forge statistics bar
    - Tool-heavy sessions list
    - Session timeline with step-by-step visualization
    """

    def compose(self) -> ComposeResult:
        yield ForgeHero(id="forge-hero", classes="hero-art")
        yield ForgeStats(id="forge-stats", classes="bento-gold")
        with Horizontal(classes="bento-row"):
            yield HephaestusPortrait(id="hephaestus-portrait", classes="divine-panel-gold")
            with Vertical():
                yield Input(
                    placeholder="🔨 Enter a session ID (or prefix) to inspect the forging log...",
                    id="dive-input",
                    classes="divine-panel",
                )
                yield ToolHeavySessions(id="tool-sessions", classes="divine-panel")
        yield SessionTimeline(id="session-timeline", classes="divine-panel")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        sid = event.value.strip()
        if sid:
            self.inspect_session(sid)

    @work(thread=True)
    def load_data(self) -> None:
        from hermes_cli.dashboard.data import get_tool_heavy_sessions, get_god_detail
        sessions = get_tool_heavy_sessions(limit=15)
        
        # Calculate stats
        total_strikes = sum(s.get("tool_call_count", 0) for s in sessions)
        heaviest = max((s.get("tool_call_count", 0) for s in sessions), default=0)
        avg_strikes = total_strikes / len(sessions) if sessions else 0
        
        stats = {
            "total_strikes": total_strikes,
            "heaviest_session": heaviest,
            "avg_strikes": avg_strikes,
        }
        
        hephaestus_data = get_god_detail("Hephaestus")
        
        self.app.call_from_thread(self._apply_sessions, sessions, stats, hephaestus_data)

    def _apply_sessions(self, sessions, stats, hephaestus_data):
        self.query_one("#tool-sessions", ToolHeavySessions).sessions = sessions
        self.query_one("#forge-stats", ForgeStats).stats = stats
        if hephaestus_data:
            self.query_one("#hephaestus-portrait", HephaestusPortrait).god_data = hephaestus_data

    @work(thread=True)
    def inspect_session(self, session_id: str) -> None:
        from hermes_cli.dashboard.data import get_session_detail, get_session_messages
        from hermes_state import SessionDB
        
        db = SessionDB()
        try:
            resolved = db.resolve_session_id(session_id)
        finally:
            db.close()
        
        if not resolved:
            self.app.call_from_thread(self._show_error, session_id)
            return
        
        meta = get_session_detail(resolved)
        messages = get_session_messages(resolved)
        self.app.call_from_thread(self._apply_session, meta, messages)

    def _apply_session(self, meta, messages):
        timeline = self.query_one("#session-timeline", SessionTimeline)
        timeline.session_meta = meta or {}
        timeline.messages = messages or []

    def _show_error(self, sid):
        timeline = self.query_one("#session-timeline", SessionTimeline)
        timeline.session_meta = {"id": sid, "title": f"Session '{sid}' not found"}
        timeline.messages = []

    def on_show(self) -> None:
        self.load_data()
