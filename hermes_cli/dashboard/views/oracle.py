"""View 3: The Oracle -- Cost analytics with epic Apollo divine art and bento grid.

Features:
- Epic Apollo hero art with divine eye (god of prophecy/light)
- Apollo braille pixel art portrait
- Enhanced stat cards with Greek styling
- Activity sparklines with 14-day data
- Model breakdown table with visual bars
- Cost predictions and insights
"""

from textual.app import ComposeResult
from textual.containers import Horizontal, ScrollableContainer
from textual.reactive import reactive
from textual.widgets import Static
from textual import work
import random

ORACLE_HERO_FRAME_1 = """\
[dim #0A0A12]░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░[/]
[dim #1A1A38]░░[/][#2A2A50]╔════════════════════════════════════════════════════════════════════════════════════════════════════════════════╗[/][dim #1A1A38]░░[/]
[dim #1A1A38]░░[/][#2A2A50]║[/]                                                                                                              [#2A2A50]║[/][dim #1A1A38]░░[/]
[dim #1A1A38]░░[/][#2A2A50]║[/]      [dim #3A3A6A]⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣀⣀⣀⣀⣀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]       [bold #FFE066]╔═══════════════════════════════════════╗[/]      [#2A2A50]║[/][dim #1A1A38]░░[/]
[dim #1A1A38]░░[/][#2A2A50]║[/]      [dim #3A3A6A]⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣠⣴⣾⣿⣿⣿⣿⣿⣿⣿⣷⣦⣄⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]       [bold #FFE066]║[/]  [bold #FFD700]☀ THE ORACLE ☀[/]                 [bold #FFE066]║[/]      [#2A2A50]║[/][dim #1A1A38]░░[/]
[dim #1A1A38]░░[/][#2A2A50]║[/]      [#555577]⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣠⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣦⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]       [bold #FFE066]║[/]  [dim #00D4FF]Divine Analytics & Prophecy[/]        [bold #FFE066]║[/]      [#2A2A50]║[/][dim #1A1A38]░░[/]
[dim #1A1A38]░░[/][#2A2A50]║[/]      [#C9A227]⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣼⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣧⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]       [bold #FFE066]╠═══════════════════════════════════════╣[/]      [#2A2A50]║[/][dim #1A1A38]░░[/]
[dim #1A1A38]░░[/][#2A2A50]║[/]      [#FFE066]⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣾⣿⣿⣿⣿⣿⣿⣿[/][bold #FFFFFF]☉[/][#FFE066]⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡄⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]       [bold #FFE066]║[/]                                       [bold #FFE066]║[/]      [#2A2A50]║[/][dim #1A1A38]░░[/]
[dim #1A1A38]░░[/][#2A2A50]║[/]      [#FFD700]⠀⠀⠀⠀⠀⠀⠀⠀⠀⢸⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡇⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]       [bold #FFE066]║[/]  [#FFE066]☀[/] [dim #555577]APOLLO[/] — God of Prophecy      [bold #FFE066]║[/]      [#2A2A50]║[/][dim #1A1A38]░░[/]
[dim #1A1A38]░░[/][#2A2A50]║[/]      [#FFD700]⠀⠀⠀⠀⠀⠀⠀⠀⠀⢸⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡇⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]       [bold #FFE066]║[/]  [dim #00D4FF]foresee · analyze · illuminate[/]    [bold #FFE066]║[/]      [#2A2A50]║[/][dim #1A1A38]░░[/]
[dim #1A1A38]░░[/][#2A2A50]║[/]      [#C9A227]⠀⠀⠀⠀⠀⠀⠀⠀⠀⠘⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⠃⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]       [bold #FFE066]║[/]                                       [bold #FFE066]║[/]      [#2A2A50]║[/][dim #1A1A38]░░[/]
[dim #1A1A38]░░[/][#2A2A50]║[/]      [#555577]⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠹⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⠏⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]       [bold #FFE066]║[/]  [dim #555577]Cost Tracking • Token Analytics[/]   [bold #FFE066]║[/]      [#2A2A50]║[/][dim #1A1A38]░░[/]
[dim #1A1A38]░░[/][#2A2A50]║[/]      [dim #3A3A6A]⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠙⢿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡿⠋⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]       [bold #FFE066]╚═══════════════════════════════════════╝[/]      [#2A2A50]║[/][dim #1A1A38]░░[/]
[dim #1A1A38]░░[/][#2A2A50]║[/]      [dim #3A3A6A]⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠉⠛⠻⠿⠿⠿⠿⠿⠿⠟⠛⠉⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]                                                              [#2A2A50]║[/][dim #1A1A38]░░[/]
[dim #1A1A38]░░[/][#2A2A50]║[/]                                                                                                              [#2A2A50]║[/][dim #1A1A38]░░[/]
[dim #1A1A38]░░[/][#2A2A50]╚════════════════════════════════════════════════════════════════════════════════════════════════════════════════╝[/][dim #1A1A38]░░[/]
[dim #0A0A12]░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░[/]\
"""


def _sparkline(values: list, width: int = 40, color: str = "#00D4FF") -> str:
    """Create a sparkline visualization."""
    blocks = " ▁▂▃▄▅▆▇█"
    if not values:
        empty = '░' * width
        return f"[dim #1A1A3A]{empty}[/]"
    mx = max(values) if max(values) > 0 else 1
    padded = values[-width:] if len(values) >= width else values
    chars = []
    for v in padded:
        idx = min(int((v / mx) * (len(blocks) - 1)), len(blocks) - 1)
        chars.append(blocks[idx])
    return f"[{color}]{''.join(chars)}[/]"


class OracleHero(Static):
    """Oracle hero art widget."""
    
    def render(self) -> str:
        return ORACLE_HERO_FRAME_1


class StatCard(Static):
    """Divine stat card with Greek styling."""
    
    label: reactive[str] = reactive("")
    value: reactive[str] = reactive("—")
    sub: reactive[str] = reactive("")
    greek: reactive[str] = reactive("")
    icon: reactive[str] = reactive("✦")
    color: reactive[str] = reactive("#FFD700")

    def render(self) -> str:
        gk = f"[dim #2A2A50]{self.greek}[/]\n" if self.greek else ""
        return (
            f"[{self.color}]{self.icon}[/]  {gk}"
            f"[bold {self.color}]{self.label}[/]\n"
            f"[bold #00FF99]{self.value}[/]\n"
            f"[dim #555577]{self.sub}[/]"
        )


class ActivityChart(Static):
    """Enhanced activity chart with sparklines."""
    
    activity: reactive[list] = reactive(list, always_update=True)

    def render(self) -> str:
        header = "[bold #FFE066]📊 ΓΡΑΦΗΜΑ — Activity Overview (Last 14 Days)[/]\n\n"
        
        if not self.activity:
            return header + "[dim #555577]The oracle has no visions yet. Begin your divine journey.[/]"
        
        session_vals = [d.get("sessions", 0) for d in self.activity]
        msg_vals = [d.get("messages", 0) for d in self.activity]
        cost_vals = [d.get("cost", 0) for d in self.activity]
        tool_vals = [d.get("tool_calls", 0) for d in self.activity]
        
        lines = [
            f"  [dim #00A8CC]Sessions  [/]  {_sparkline(session_vals, 50, '#00FF99')}  [bold #00FF99]{sum(session_vals)}[/]",
            f"  [dim #00A8CC]Messages  [/]  {_sparkline(msg_vals, 50, '#00D4FF')}  [bold #00D4FF]{sum(msg_vals)}[/]",
            f"  [dim #00A8CC]Tools     [/]  {_sparkline(tool_vals, 50, '#FF8C00')}  [bold #FF8C00]{sum(tool_vals)}[/]",
            f"  [dim #00A8CC]Cost      [/]  {_sparkline(cost_vals, 50, '#FFD700')}  [bold #FFD700]${sum(cost_vals):.2f}[/]",
        ]
        
        # Day labels
        day_labels = "\n  [dim #555577]"
        for d in self.activity[-14:]:
            day_labels += d.get("day", "")[-2:] + " "
        day_labels += "[/]"
        
        return header + "\n".join(lines) + day_labels


class ModelTable(Static):
    """Enhanced model breakdown table."""
    
    models: reactive[list] = reactive(list, always_update=True)

    def render(self) -> str:
        from hermes_cli.dashboard.data import format_tokens, format_cost
        
        header = "[bold #FFE066]⚡ ΜΟΝΤΕΛ — Model Breakdown[/]\n\n"
        
        if not self.models:
            return header + "[dim #555577]No model data yet.[/]"
        
        col_header = (
            "  [dim #00A8CC]MODEL" + " " * 28 + 
            "SESSIONS    TOKENS         COST[/]\n"
            "  [dim #2A2A50]" + "─" * 75 + "[/]"
        )
        
        lines = [col_header]
        max_sessions = max(m.get("sessions", 1) for m in self.models) or 1
        
        for m in self.models:
            model_name = m.get("model", "unknown")[:32]
            sessions = m.get("sessions", 0)
            tokens = format_tokens(m.get("total_tokens", 0))
            cost = format_cost(m.get("cost", 0))
            
            # Visual bar based on sessions
            bar_len = int((sessions / max_sessions) * 25)
            bar = "█" * bar_len + "░" * (25 - bar_len)
            
            lines.append(
                f"  [#E0F7FF]{model_name:<32}[/]  "
                f"[#00FF99]{sessions:>5}[/]    "
                f"[#00D4FF]{tokens:>10}[/]    "
                f"[#FFD700]{cost:>8}[/]\n"
                f"  [dim #00D4FF]{bar}[/]"
            )
        
        return header + "\n".join(lines)


class CostInsights(Static):
    """Cost insights and predictions widget."""
    
    costs: reactive[dict] = reactive(dict, always_update=True)
    
    def render(self) -> str:
        from hermes_cli.dashboard.data import format_cost
        
        header = "[bold #FFE066]💰 ΔΡΑΧΜΑΙ — Cost Insights[/]\n\n"
        
        if not self.costs:
            return header + "[dim #555577]Consulting the treasury...[/]"
        
        daily = self.costs.get("daily", 0)
        weekly = self.costs.get("weekly", 0)
        monthly = self.costs.get("monthly", 0)
        total = self.costs.get("total", 0)
        
        # Calculate projections
        daily_avg = weekly / 7 if weekly > 0 else daily
        monthly_projection = daily_avg * 30
        
        lines = [
            f"  [dim #00A8CC]Today[/]           [bold #00FF99]{format_cost(daily)}[/]",
            f"  [dim #00A8CC]This Week[/]       [bold #00D4FF]{format_cost(weekly)}[/]",
            f"  [dim #00A8CC]This Month[/]      [bold #FFD700]{format_cost(monthly)}[/]",
            f"  [dim #00A8CC]All Time[/]        [bold #FF4444]{format_cost(total)}[/]",
            "",
            "  [dim #2A2A50]── Prophecy ──[/]",
            f"  [dim #555577]Daily Avg[/]       [#FFE066]{format_cost(daily_avg)}[/]",
            f"  [dim #555577]Month Projection[/] [#FFE066]{format_cost(monthly_projection)}[/]",
        ]
        
        return header + "\n".join(lines)


class ApolloPortrait(Static):
    """Apollo pixel art portrait with lore and abilities."""
    
    god_data: reactive[dict] = reactive(dict, always_update=True)
    
    def render(self) -> str:
        if not self.god_data:
            return "[dim #555577]Summoning the Sun God...[/]"
        
        pixel_art = self.god_data.get("pixel_art", "")
        abilities = self.god_data.get("abilities", [])
        quotes = self.god_data.get("quotes", [])
        
        content = ""
        if pixel_art:
            content += pixel_art + "\n"
        
        if abilities:
            content += "\n[bold #FFE066]DIVINE POWERS:[/]\n"
            for ability in abilities[:3]:
                content += f"  [dim #FFD700]{ability}[/]\n"
        
        if quotes:
            quote = random.choice(quotes)
            content += f"\n[italic dim #555577]\"{quote}\"[/]"
        
        return content


class OracleView(ScrollableContainer):
    """The Oracle -- Divine analytics with Apollo hero art.
    
    Features:
    - Epic Apollo hero art with divine eye
    - Apollo braille pixel art portrait
    - Enhanced stat cards with Greek labels
    - Activity sparklines with 14-day data
    - Model breakdown with visual bars
    - Cost insights and predictions
    """

    def compose(self) -> ComposeResult:
        yield OracleHero(id="oracle-hero", classes="hero-art")
        with Horizontal(id="stats-row", classes="bento-row"):
            yield StatCard(id="stat-sessions", classes="stat-card divine-panel-gold")
            yield StatCard(id="stat-tokens", classes="stat-card divine-panel-gold")
            yield StatCard(id="stat-cost", classes="stat-card divine-panel-gold")
            yield StatCard(id="stat-tools", classes="stat-card divine-panel-gold")
        with Horizontal(classes="bento-row"):
            yield ApolloPortrait(id="apollo-portrait", classes="divine-panel-gold")
            yield ActivityChart(id="activity-chart", classes="divine-panel")
            yield CostInsights(id="cost-insights", classes="divine-panel-gold")
        yield ModelTable(id="model-table", classes="divine-panel")

    @work(thread=True)
    def load_data(self) -> None:
        from hermes_cli.dashboard.data import (
            get_usage_stats, get_daily_activity, get_model_breakdown,
            get_cost_breakdown, format_tokens, format_cost, get_god_detail,
        )
        stats = get_usage_stats()
        activity = get_daily_activity(14)
        models = get_model_breakdown()
        costs = get_cost_breakdown(30)
        apollo_data = get_god_detail("Apollo")
        self.app.call_from_thread(self._apply, stats, activity, models, costs, apollo_data)

    def _apply(self, stats, activity, models, costs, apollo_data):
        from hermes_cli.dashboard.data import format_tokens, format_cost
        
        total_tokens = stats.get("total_input_tokens", 0) + stats.get("total_output_tokens", 0)
        
        # Sessions stat
        s = self.query_one("#stat-sessions", StatCard)
        s.greek = "Συνεδρίες"
        s.label = "SESSIONS"
        s.value = str(stats.get("total_sessions", 0))
        s.sub = f"{stats.get('total_messages', 0)} messages"
        s.icon = "📜"
        s.color = "#00FF99"
        
        # Tokens stat
        t = self.query_one("#stat-tokens", StatCard)
        t.greek = "Μάρκες"
        t.label = "TOKENS"
        t.value = format_tokens(total_tokens)
        t.sub = f"in:{format_tokens(stats.get('total_input_tokens', 0))} out:{format_tokens(stats.get('total_output_tokens', 0))}"
        t.icon = "⚡"
        t.color = "#00D4FF"
        
        # Cost stat
        c = self.query_one("#stat-cost", StatCard)
        c.greek = "Δραχμαί"
        c.label = "COST"
        c.value = format_cost(stats.get("total_cost", 0))
        c.sub = "all time"
        c.icon = "💰"
        c.color = "#FFD700"
        
        # Tools stat
        tl = self.query_one("#stat-tools", StatCard)
        tl.greek = "Εργαλεία"
        tl.label = "TOOL CALLS"
        tl.value = str(stats.get("total_tool_calls", 0))
        tl.sub = "all sessions"
        tl.icon = "⚔"
        tl.color = "#FF8C00"
        
        self.query_one("#activity-chart", ActivityChart).activity = activity
        self.query_one("#model-table", ModelTable).models = models
        self.query_one("#cost-insights", CostInsights).costs = costs
        
        if apollo_data:
            self.query_one("#apollo-portrait", ApolloPortrait).god_data = apollo_data

    def on_show(self) -> None:
        self.load_data()
