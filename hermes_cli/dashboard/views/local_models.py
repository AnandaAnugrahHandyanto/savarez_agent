"""View 6: Local Model Forge -- Epic Poseidon art with local inference stats.

Features:
- Epic Poseidon hero art (god of the sea/depths - local inference)
- Poseidon braille pixel art portrait
- LM Studio connection status with divine styling
- Local model statistics and breakdown
- Recent local sessions list
"""

import random
from textual.app import ComposeResult
from textual.containers import Horizontal, ScrollableContainer
from textual.reactive import reactive
from textual.widgets import Static
from textual import work

LOCAL_HERO_FRAME_1 = """\
[dim #0A0A12]░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░[/]
[dim #1A1A38]░░[/][#2A2A50]╔════════════════════════════════════════════════════════════════════════════════════════════════════════════════╗[/][dim #1A1A38]░░[/]
[dim #1A1A38]░░[/][#2A2A50]║[/]                                                                                                              [#2A2A50]║[/][dim #1A1A38]░░[/]
[dim #1A1A38]░░[/][#2A2A50]║[/]      [dim #3A3A6A]⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣀⣀⣀⣀⣀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]       [bold #1E90FF]╔═══════════════════════════════════════╗[/]      [#2A2A50]║[/][dim #1A1A38]░░[/]
[dim #1A1A38]░░[/][#2A2A50]║[/]      [dim #3A3A6A]⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣠⣴⣾⣿⣿⣿⣿⣿⣿⣿⣷⣦⣄⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]       [bold #1E90FF]║[/]  [bold #87CEEB]🌊 LOCAL FORGE 🌊[/]              [bold #1E90FF]║[/]      [#2A2A50]║[/][dim #1A1A38]░░[/]
[dim #1A1A38]░░[/][#2A2A50]║[/]      [#555577]⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣠⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣦⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]       [bold #1E90FF]║[/]  [dim #00D4FF]Local Model Inference[/]              [bold #1E90FF]║[/]      [#2A2A50]║[/][dim #1A1A38]░░[/]
[dim #1A1A38]░░[/][#2A2A50]║[/]      [#1E90FF]⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣼⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣧⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]       [bold #1E90FF]╠═══════════════════════════════════════╣[/]      [#2A2A50]║[/][dim #1A1A38]░░[/]
[dim #1A1A38]░░[/][#2A2A50]║[/]      [#1E90FF]⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣾⣿⣿⣿⣿[/][#87CEEB]🔱[/][#1E90FF]⣿⣿⣿⣿⣿⣿⣿⣿[/][#87CEEB]🔱[/][#1E90FF]⣿⣿⣿⣿⣿⡄⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]       [bold #1E90FF]║[/]                                       [bold #1E90FF]║[/]      [#2A2A50]║[/][dim #1A1A38]░░[/]
[dim #1A1A38]░░[/][#2A2A50]║[/]      [#87CEEB]⠀⠀⠀⠀⠀⠀⠀⠀⠀⢸⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡇⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]       [bold #1E90FF]║[/]  [#1E90FF]🌊[/] [dim #555577]POSEIDON[/] — Lord of Depths    [bold #1E90FF]║[/]      [#2A2A50]║[/][dim #1A1A38]░░[/]
[dim #1A1A38]░░[/][#2A2A50]║[/]      [#87CEEB]⠀⠀⠀⠀⠀⠀⠀⠀⠀⢸⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡇⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]       [bold #1E90FF]║[/]  [dim #00D4FF]local · private · sovereign[/]       [bold #1E90FF]║[/]      [#2A2A50]║[/][dim #1A1A38]░░[/]
[dim #1A1A38]░░[/][#2A2A50]║[/]      [#1E90FF]⠀⠀⠀⠀⠀⠀⠀⠀⠀⠘⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⠃⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]       [bold #1E90FF]║[/]                                       [bold #1E90FF]║[/]      [#2A2A50]║[/][dim #1A1A38]░░[/]
[dim #1A1A38]░░[/][#2A2A50]║[/]      [#555577]⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠹⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⠏⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]       [bold #1E90FF]║[/]  [dim #555577]LM Studio • Ollama • Custom[/]       [bold #1E90FF]║[/]      [#2A2A50]║[/][dim #1A1A38]░░[/]
[dim #1A1A38]░░[/][#2A2A50]║[/]      [dim #3A3A6A]⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠙⢿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡿⠋⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]       [bold #1E90FF]╚═══════════════════════════════════════╝[/]      [#2A2A50]║[/][dim #1A1A38]░░[/]
[dim #1A1A38]░░[/][#2A2A50]║[/]      [dim #3A3A6A]⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠉⠛⠻⠿⠿⠿⠿⠿⠿⠟⠛⠉⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]                                                              [#2A2A50]║[/][dim #1A1A38]░░[/]
[dim #1A1A38]░░[/][#2A2A50]║[/]                                                                                                              [#2A2A50]║[/][dim #1A1A38]░░[/]
[dim #1A1A38]░░[/][#2A2A50]╚════════════════════════════════════════════════════════════════════════════════════════════════════════════════╝[/][dim #1A1A38]░░[/]
[dim #0A0A12]░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░[/]\
"""


class LocalHero(Static):
    """Local forge hero art widget."""
    
    def render(self) -> str:
        return LOCAL_HERO_FRAME_1


class ConnectionStatus(Static):
    """LM Studio connection status with divine styling."""
    
    status: reactive[dict] = reactive(dict, always_update=True)

    def render(self) -> str:
        header = "[bold #1E90FF]🔱 CONNECTION STATUS[/]\n\n"
        
        if not self.status:
            return header + "[dim #555577]Diving into the depths...[/]"
        
        online = self.status.get("online", False)
        url = self.status.get("url", "localhost:1234")
        models = self.status.get("models", [])
        
        if online:
            status_line = f"[bold #00FF99]● ONLINE[/]  [dim #00A8CC]{url}[/]"
            if models:
                status_line += f"\n[dim #555577]{len(models)} model{'s' if len(models) != 1 else ''} loaded[/]\n"
                model_lines = []
                for m in models[:6]:
                    mid = m.get("id", "?")
                    model_lines.append(f"  [#87CEEB]🔱[/] [#E0F7FF]{mid}[/]")
                return header + status_line + "\n".join(model_lines)
            return header + status_line
        else:
            error = self.status.get("error", "Connection refused")
            return header + (
                f"[bold #FF4444]○ OFFLINE[/]  [dim #00A8CC]{url}[/]\n\n"
                f"[dim #555577]{error}[/]\n\n"
                f"[dim #1E90FF]Start LM Studio to enable local inference[/]"
            )


class LocalStats(Static):
    """Local model statistics with divine styling."""
    
    stats: reactive[dict] = reactive(dict, always_update=True)

    def render(self) -> str:
        from hermes_cli.dashboard.data import format_tokens
        
        header = "[bold #1E90FF]📊 ΣΤΑΤ — LOCAL USAGE[/]\n\n"
        
        if not self.stats:
            return header + "[dim #555577]No local forging recorded yet.[/]"
        
        sessions = self.stats.get("sessions", 0)
        messages = self.stats.get("messages", 0)
        tools = self.stats.get("tool_calls", 0)
        tokens = self.stats.get("total_tokens", 0)
        avg = int(self.stats.get("avg_tokens_per_session", 0))
        
        return (
            header
            + f"  [bold #1E90FF]Sessions[/]     [bold #00FF99]{sessions}[/]\n"
            + f"  [bold #1E90FF]Messages[/]     [bold #00FF99]{messages}[/]\n"
            + f"  [bold #1E90FF]Tool Calls[/]   [bold #87CEEB]{tools}[/]\n"
            + f"  [bold #1E90FF]Tokens[/]       [bold #00D4FF]{format_tokens(tokens)}[/]\n"
            + f"  [bold #1E90FF]Avg/Session[/]  [dim #00A8CC]{format_tokens(avg)}[/]"
        )


class LocalModelBreakdown(Static):
    """Local model breakdown table with divine styling."""
    
    models: reactive[list] = reactive(list, always_update=True)

    def render(self) -> str:
        from hermes_cli.dashboard.data import format_tokens
        
        header = "[bold #1E90FF]🌊 ΜΟΝΤΕΛ — LOCAL MODELS USED[/]\n\n"
        
        if not self.models:
            return header + "[dim #555577]No local model usage data.[/]"
        
        col_header = (
            "  [dim #1E90FF]MODEL" + " " * 32 + 
            "SESSIONS    MSGS      TOKENS[/]\n"
            "  [dim #2A2A50]" + "─" * 80 + "[/]"
        )
        
        lines = [col_header]
        max_sessions = max(m.get("sessions", 1) for m in self.models) or 1
        
        for m in self.models:
            name = m.get("model", "?")[:38]
            sessions = m.get("sessions", 0)
            msgs = m.get("messages", 0)
            tokens = format_tokens(m.get("tokens", 0))
            
            bar_len = int((sessions / max_sessions) * 25) if max_sessions > 0 else 0
            bar = "█" * bar_len + "░" * (25 - bar_len)
            
            lines.append(
                f"  [#E0F7FF]{name:<38}[/]  "
                f"[#00FF99]{sessions:>5}[/]    "
                f"[#00D4FF]{msgs:>5}[/]    "
                f"[#87CEEB]{tokens:>10}[/]\n"
                f"  [dim #1E90FF]{bar}[/]"
            )
        
        return header + "\n".join(lines)


class RecentLocalSessions(Static):
    """Recent local sessions list with divine styling."""
    
    sessions: reactive[list] = reactive(list, always_update=True)

    def render(self) -> str:
        from hermes_cli.dashboard.data import format_timestamp
        
        header = "[bold #1E90FF]📜 ΛΟΓ — RECENT LOCAL SESSIONS[/]\n\n"
        
        if not self.sessions:
            return header + "[dim #555577]No local model sessions found.[/]"
        
        lines = []
        for i, s in enumerate(self.sessions[:12]):
            ts = format_timestamp(s.get("started_at", 0))
            model = (s.get("model") or "?").split("/")[-1][:22]
            msgs = s.get("message_count", 0)
            tools = s.get("tool_call_count", 0)
            title = (s.get("title") or "untitled")[:28]
            sid = s.get("id", "")[:10]
            
            marker = "[#1E90FF]🔱[/]" if i % 2 == 0 else "[#87CEEB]·[/]"
            tool_color = "#FF4444" if tools > 10 else "#87CEEB"
            
            lines.append(
                f"  {marker}  [dim #00A8CC]{ts:<14}[/]  [#E0F7FF]{model:<22}[/]  "
                f"[dim #00D4FF]{msgs:>3}m[/]  [{tool_color}]{tools:>3}⚔[/]  "
                f"[dim #555577]{title:<28}[/]  [dim #2A2A50]{sid}[/]"
            )
        
        return header + "\n".join(lines)


class PoseidonPortrait(Static):
    """Poseidon pixel art portrait with lore and abilities."""
    
    god_data: reactive[dict] = reactive(dict, always_update=True)
    
    def render(self) -> str:
        if not self.god_data:
            return "[dim #555577]Summoning the Lord of the Depths...[/]"
        
        pixel_art = self.god_data.get("pixel_art", "")
        abilities = self.god_data.get("abilities", [])
        quotes = self.god_data.get("quotes", [])
        
        content = ""
        if pixel_art:
            content += pixel_art + "\n"
        
        if abilities:
            content += "\n[bold #1E90FF]DIVINE POWERS:[/]\n"
            for ability in abilities[:3]:
                content += f"  [dim #87CEEB]{ability}[/]\n"
        
        if quotes:
            quote = random.choice(quotes)
            content += f"\n[italic dim #555577]\"{quote}\"[/]"
        
        return content


class LocalModelsView(ScrollableContainer):
    """Local Model Forge -- Divine depths with Poseidon hero art.
    
    Features:
    - Epic Poseidon hero art
    - Poseidon braille pixel art portrait
    - LM Studio connection status
    - Local model statistics
    - Model breakdown table
    - Recent local sessions
    """

    def compose(self) -> ComposeResult:
        yield LocalHero(id="local-hero", classes="hero-art")
        with Horizontal(classes="bento-row"):
            yield PoseidonPortrait(id="poseidon-portrait", classes="divine-panel-gold")
            yield ConnectionStatus(id="conn-status", classes="divine-panel-gold")
            yield LocalStats(id="local-stats", classes="divine-panel-gold")
        yield LocalModelBreakdown(id="local-breakdown", classes="divine-panel")
        yield RecentLocalSessions(id="local-sessions", classes="divine-panel")

    @work(thread=True)
    def load_data(self) -> None:
        from hermes_cli.dashboard.data import (
            get_local_model_stats, get_local_model_breakdown,
            get_local_model_sessions, get_god_detail,
        )
        stats = get_local_model_stats()
        breakdown = get_local_model_breakdown()
        sessions = get_local_model_sessions(limit=12)
        conn = self._check_connection()
        poseidon_data = get_god_detail("Poseidon")
        self.app.call_from_thread(self._apply, stats, breakdown, sessions, conn, poseidon_data)

    def _check_connection(self) -> dict:
        """Check LM Studio connection status."""
        import yaml
        from hermes_constants import get_hermes_home
        
        config_path = get_hermes_home() / "config.yaml"
        base_url = "http://localhost:1234/v1"
        
        try:
            if config_path.exists():
                with open(config_path) as f:
                    cfg = yaml.safe_load(f) or {}
                for p in cfg.get("custom_providers", []):
                    url = p.get("base_url", "")
                    if "localhost" in url or "127.0.0.1" in url:
                        base_url = url
                        break
        except Exception:
            pass
        
        try:
            import httpx
            resp = httpx.get(f"{base_url}/models", timeout=3.0)
            if resp.status_code == 200:
                data = resp.json()
                models = data.get("data", [])
                return {"online": True, "url": base_url, "models": models}
            return {"online": False, "url": base_url, "error": f"HTTP {resp.status_code}"}
        except Exception as e:
            return {"online": False, "url": base_url, "error": str(e)[:60]}

    def _apply(self, stats, breakdown, sessions, conn, poseidon_data):
        self.query_one("#conn-status", ConnectionStatus).status = conn
        self.query_one("#local-stats", LocalStats).stats = stats
        self.query_one("#local-breakdown", LocalModelBreakdown).models = breakdown
        self.query_one("#local-sessions", RecentLocalSessions).sessions = sessions
        if poseidon_data:
            self.query_one("#poseidon-portrait", PoseidonPortrait).god_data = poseidon_data

    def on_show(self) -> None:
        self.load_data()
