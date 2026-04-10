"""OLYMPUS ASCENDED DASHBOARD — Divine Command Center for Hermes Agent.

A Textual application providing an elite multi-agent orchestration interface
with cinematic TUI aesthetics, real-time divine metrics, and mythological vibes.

Features:
- Animated hero art with frame cycling
- Interactive pantheon god cards
- Live execution lanes with tool call data
- Divine notifications panel
- Cost tracker (Drachmai)
- Flow diagram visualization
- Quick actions bar

Launch: `hermes dashboard` or `/dashboard` in the CLI.
"""

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal
from textual.reactive import reactive
from textual.widgets import Static, Header, Footer, Button
from textual import work

from hermes_cli.dashboard.views.assembly import AssemblyView
from hermes_cli.dashboard.views.chronicle import ChronicleView
from hermes_cli.dashboard.views.oracle import OracleView
from hermes_cli.dashboard.views.tablets import TabletsView
from hermes_cli.dashboard.views.deep_dive import DeepDiveView
from hermes_cli.dashboard.views.local_models import LocalModelsView
from hermes_cli.dashboard.views.model_switch import ModelSwitchView
from hermes_cli.dashboard.views.zeus import ZeusView


VIEWS = [
    ("assembly", "⚡ Assembly", "1"),
    ("chronicle", "📜 Chronicle", "2"),
    ("oracle", "☀ Oracle", "3"),
    ("tablets", "🕯 Tablets", "4"),
    ("deepdive", "🔨 Deep Dive", "5"),
    ("local", "🌊 Local Forge", "6"),
    ("switch", "⚕ Switch", "7"),
    ("zeus", "👁 Zeus", "8"),
]

STATUS_ERROR_MAX_LEN = 50


class NavBar(Static):
    """Top navigation bar with divine Olympus styling."""

    current_view: reactive[str] = reactive("assembly")

    def compose(self) -> ComposeResult:
        with Horizontal(id="nav-tabs"):
            yield Button(" ◀ ", id="back-btn")
            yield Static(
                " [bold #FFD700]⚡[/] [bold #FFD700]OLYMPUS ASCENDED[/] [dim #2A2A50]│[/] ",
                id="header-title",
            )
            for view_id, label, key in VIEWS:
                btn = Button(f" {key}·{label} ", id=f"nav-{view_id}", classes="nav-button")
                if view_id == self.current_view:
                    btn.add_class("-active")
                yield btn
            yield Static(
                " [dim #555577]Λακεδαίμων[/] [dim #00D4FF]q[/]:quit [dim #00D4FF]r[/]:refresh ",
                id="header-status",
            )

    def watch_current_view(self, value: str) -> None:
        try:
            for view_id, _, _ in VIEWS:
                btn = self.query_one(f"#nav-{view_id}", Button)
                if view_id == value:
                    btn.add_class("-active")
                else:
                    btn.remove_class("-active")
        except Exception:
            pass


class QuickActionsBar(Static):
    """Quick actions bar with divine command buttons and model switcher."""

    def compose(self) -> ComposeResult:
        with Horizontal(classes="quick-actions"):
            yield Button(" ⚡ Refresh ", id="action-refresh", classes="quick-action-btn")
            yield Button(" 🖥 LM Studio ", id="action-lmstudio", classes="quick-action-btn")
            yield Button(" 🌐 OpenRouter ", id="action-openrouter", classes="quick-action-btn")
            yield Button(" ⚕ Models ", id="action-models", classes="quick-action-btn")
            yield Static(
                "  [dim #2A2A50]│[/]  [dim #555577]Quick Switch[/]  [dim #2A2A50]│[/]  ",
                id="actions-label",
            )


class StatusBar(Static):
    """Bottom status bar with divine Greek border."""

    status_text: reactive[str] = reactive("")

    def compose(self) -> ComposeResult:
        yield Static(id="footer-content")

    def on_mount(self) -> None:
        self._update_footer()

    def watch_status_text(self, value: str) -> None:
        self._update_footer()

    def _update_footer(self) -> None:
        status = self.status_text or "Olympus Online"
        content = (
            "[dim #2A2A50]═══════════════[/]  "
            "[dim #555577][1]⚡  [2]📜  [3]☀  [4]🕯  [5]🔨  [6]🌊  [7]⚕  [8]👁[/]  "
            "[dim #2A2A50]│[/]  [dim #555577]q:quit  r:refresh  ◀:back[/]  "
            f"[dim #2A2A50]│[/]  [bold #FFD700]✦[/] [dim #00D4FF]{status}[/]  "
            "[dim #2A2A50]═══════════════[/]"
        )
        try:
            self.query_one("#footer-content", Static).update(content)
        except Exception:
            pass

    def set_status(self, text: str) -> None:
        self.status_text = text


class OlympusDashboard(App):
    """OLYMPUS ASCENDED Dashboard — Divine Command Center for Hermes Agent.
    
    Features:
    - 8 divine views: Assembly, Chronicle, Oracle, Tablets, Deep Dive, Local Forge, Switch, Zeus
    - Animated hero art with frame cycling
    - Interactive pantheon with god cards
    - Live execution lanes
    - Divine notifications
    - Cost tracker (Drachmai)
    - Quick actions bar
    - Zeus Overseer monitor with live session turns and evaluations
    """

    TITLE = "⚡ OLYMPUS ASCENDED // DIVINE ORCHESTRATION SYSTEM"
    CSS_PATH = "styles.tcss"

    BINDINGS = [
        Binding("1", "switch_view('assembly')", "Assembly", show=False),
        Binding("2", "switch_view('chronicle')", "Chronicle", show=False),
        Binding("3", "switch_view('oracle')", "Oracle", show=False),
        Binding("4", "switch_view('tablets')", "Tablets", show=False),
        Binding("5", "switch_view('deepdive')", "Deep Dive", show=False),
        Binding("6", "switch_view('local')", "Local Forge", show=False),
        Binding("7", "switch_view('switch')", "Switch", show=False),
        Binding("8", "switch_view('zeus')", "Zeus", show=False),
        Binding("escape", "go_back", "Back", show=False),
        Binding("q", "quit", "Quit"),
        Binding("r", "refresh_data", "Refresh", show=False),
        Binding("h", "switch_view('assembly')", "Home", show=False),
    ]

    current_view: reactive[str] = reactive("assembly")
    _view_history: list[str] = []

    def compose(self) -> ComposeResult:
        yield NavBar()
        yield QuickActionsBar()
        yield Container(
            AssemblyView(id="view-assembly"),
            ChronicleView(id="view-chronicle", classes="hidden"),
            OracleView(id="view-oracle", classes="hidden"),
            TabletsView(id="view-tablets", classes="hidden"),
            DeepDiveView(id="view-deepdive", classes="hidden"),
            LocalModelsView(id="view-local", classes="hidden"),
            ModelSwitchView(id="view-switch", classes="hidden"),
            ZeusView(id="view-zeus", classes="hidden"),
            id="main-content",
        )
        yield StatusBar()

    def on_mount(self) -> None:
        from hermes_cli.dashboard.data import _ensure_skin_loaded
        _ensure_skin_loaded()
        
        for view_id, _, _ in VIEWS:
            try:
                w = self.query_one(f"#view-{view_id}")
                if view_id == "assembly":
                    w.remove_class("hidden")
                    w.display = True
                else:
                    w.add_class("hidden")
                    w.display = False
            except Exception:
                pass
        
        self._set_status("Divine systems initialized")
        self.refresh_current_view()

    def action_switch_view(self, view_name: str) -> None:
        if view_name != self.current_view:
            self._view_history.append(self.current_view)
        self.current_view = view_name
        
        view_labels = {v[0]: v[1] for v in VIEWS}
        label = view_labels.get(view_name, view_name)
        self._set_status(f"Viewing {label}")

    def action_go_back(self) -> None:
        if self._view_history:
            prev = self._view_history.pop()
            self.current_view = prev
        else:
            self.current_view = "assembly"
        self._set_status("Returned to previous view")

    def watch_current_view(self, value: str) -> None:
        try:
            navbar = self.query_one(NavBar)
            navbar.current_view = value
        except Exception:
            return

        for view_id, _, _ in VIEWS:
            try:
                widget = self.query_one(f"#view-{view_id}")
                if view_id == value:
                    widget.remove_class("hidden")
                    widget.display = True
                else:
                    widget.add_class("hidden")
                    widget.display = False
            except Exception:
                pass

        try:
            active_view = self.query_one(f"#view-{value}")
            if hasattr(active_view, "on_show"):
                active_view.on_show()
        except Exception:
            pass

    def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id or ""
        
        if btn_id == "back-btn":
            self.action_go_back()
        elif btn_id.startswith("nav-"):
            view_name = btn_id[4:]
            self.action_switch_view(view_name)
        elif btn_id == "action-refresh":
            self.action_refresh_data()
            self._set_status("Refreshing divine data...")
        elif btn_id == "action-lmstudio":
            self._quick_switch_lmstudio()
        elif btn_id == "action-openrouter":
            self._quick_switch_openrouter()
        elif btn_id == "action-models":
            self.action_switch_view("switch")

    @work(thread=True)
    def _quick_switch_lmstudio(self) -> None:
        """Quick switch to LM Studio local model."""
        self.app.call_from_thread(self._set_status, "Switching to LM Studio...")
        
        try:
            from hermes_cli.dashboard.data import get_lmstudio_models
            import yaml
            from hermes_constants import get_hermes_home
            from utils import atomic_yaml_write
            
            models = get_lmstudio_models("http://localhost:1234/v1")
            
            if not models:
                self.app.call_from_thread(
                    self._set_status, 
                    "⚠ LM Studio offline - start it first!"
                )
                return
            
            model_id = models[0].get("id", "local-model")
            
            config_path = get_hermes_home() / "config.yaml"
            with open(config_path) as f:
                cfg = yaml.safe_load(f) or {}
            
            if "model" not in cfg:
                cfg["model"] = {}
            cfg["model"]["default"] = model_id
            cfg["model"]["provider"] = "custom:lmstudio"
            
            if "custom_providers" not in cfg:
                cfg["custom_providers"] = []
            
            lms_exists = any(
                p.get("name") == "lmstudio" 
                for p in cfg.get("custom_providers", [])
            )
            
            if not lms_exists:
                cfg["custom_providers"].append({
                    "name": "lmstudio",
                    "base_url": "http://localhost:1234/v1",
                    "api_key": "lm-studio",
                    "models": {model_id: {"context_length": 32768}}
                })
            else:
                for p in cfg["custom_providers"]:
                    if p.get("name") == "lmstudio":
                        if "models" not in p:
                            p["models"] = {}
                        p["models"][model_id] = {"context_length": 32768}
            
            atomic_yaml_write(config_path, cfg)
            
            self.app.call_from_thread(
                self._set_status, 
                f"✓ Switched to LM Studio: {model_id}"
            )
            self.app.call_from_thread(self._refresh_assembly_model)
            
        except Exception as e:
            self.app.call_from_thread(
                self._set_status, 
                f"✗ Error: {str(e)[:STATUS_ERROR_MAX_LEN]}"
            )
    
    @work(thread=True)
    def _quick_switch_openrouter(self) -> None:
        """Quick switch to OpenRouter."""
        self.app.call_from_thread(self._set_status, "Switching to OpenRouter...")
        
        try:
            import yaml
            import os
            from hermes_constants import get_hermes_home
            from utils import atomic_yaml_write
            
            env_path = get_hermes_home() / ".env"
            api_key = None
            if env_path.exists():
                with open(env_path) as f:
                    for line in f:
                        if line.startswith("OPENROUTER_API_KEY="):
                            api_key = line.split("=", 1)[1].strip()
                            break
            
            if not api_key:
                api_key = os.environ.get("OPENROUTER_API_KEY", "")
            
            if not api_key:
                self.app.call_from_thread(
                    self._set_status, 
                    "⚠ No OpenRouter API key found in .env"
                )
                return
            
            config_path = get_hermes_home() / "config.yaml"
            with open(config_path) as f:
                cfg = yaml.safe_load(f) or {}
            
            if "model" not in cfg:
                cfg["model"] = {}
            cfg["model"]["default"] = "anthropic/claude-sonnet-4"
            cfg["model"]["provider"] = "openrouter"
            
            atomic_yaml_write(config_path, cfg)
            
            self.app.call_from_thread(
                self._set_status, 
                "✓ Switched to OpenRouter: claude-sonnet-4"
            )
            self.app.call_from_thread(self._refresh_assembly_model)
            
        except Exception as e:
            self.app.call_from_thread(
                self._set_status, 
                f"✗ Error: {str(e)[:STATUS_ERROR_MAX_LEN]}"
            )
    
    def _refresh_assembly_model(self) -> None:
        """Refresh the assembly view's model display."""
        try:
            assembly = self.query_one("#view-assembly")
            if hasattr(assembly, "load_data"):
                assembly.load_data()
        except Exception:
            pass

    def action_refresh_data(self) -> None:
        self._set_status("Consulting the oracle...")
        self.refresh_current_view()

    @work(thread=True)
    def refresh_current_view(self) -> None:
        try:
            view = self.query_one(f"#view-{self.current_view}")
            if hasattr(view, "load_data"):
                view.load_data()
            self.app.call_from_thread(self._set_status, "Data refreshed")
        except Exception:
            pass

    def _set_status(self, text: str) -> None:
        try:
            status_bar = self.query_one(StatusBar)
            status_bar.set_status(text)
        except Exception:
            pass


def run_dashboard():
    """Entry point for `hermes dashboard`.
    
    Launches the OLYMPUS ASCENDED dashboard — a divine command center
    for Hermes Agent with cinematic TUI aesthetics.
    """
    app = OlympusDashboard()
    app.run()


if __name__ == "__main__":
    run_dashboard()
