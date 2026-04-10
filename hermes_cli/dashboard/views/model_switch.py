"""View 7: Model Switchboard -- Uses the native hermes model pipeline.

Features:
- Epic Hermes hero art (messenger god - model routing)
- Hermes braille pixel art portrait
- Active model panel with divine styling
- Authenticated providers with curated model lists
- Model switch input supporting aliases and --provider flag
- Real credential resolution and models.dev catalog lookup
"""

from textual.app import ComposeResult
from textual.containers import Horizontal, ScrollableContainer
from textual.reactive import reactive
from textual.widgets import Static, Input
from textual import work
import random


SWITCH_HERO_FRAME_1 = """\
[dim #0A0A12]░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░[/]
[dim #1A1A38]░░[/][#2A2A50]╔════════════════════════════════════════════════════════════════════════════════════════════════════════════════╗[/][dim #1A1A38]░░[/]
[dim #1A1A38]░░[/][#2A2A50]║[/]                                                                                                              [#2A2A50]║[/][dim #1A1A38]░░[/]
[dim #1A1A38]░░[/][#2A2A50]║[/]      [dim #3A3A6A]⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣀⣀⣀⣀⣀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]       [bold #FFD700]╔═══════════════════════════════════════╗[/]      [#2A2A50]║[/][dim #1A1A38]░░[/]
[dim #1A1A38]░░[/][#2A2A50]║[/]      [dim #3A3A6A]⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣠⣴⣾⣿⣿⣿⣿⣿⣿⣿⣷⣦⣄⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]       [bold #FFD700]║[/]  [bold #FFEC8B]⚕ MODEL SWITCHBOARD ⚕[/]          [bold #FFD700]║[/]      [#2A2A50]║[/][dim #1A1A38]░░[/]
[dim #1A1A38]░░[/][#2A2A50]║[/]      [#555577]⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣠⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣦⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]       [bold #FFD700]║[/]  [dim #00D4FF]Divine Model Routing[/]               [bold #FFD700]║[/]      [#2A2A50]║[/][dim #1A1A38]░░[/]
[dim #1A1A38]░░[/][#2A2A50]║[/]      [#C9A227]⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣼⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣧⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]       [bold #FFD700]╠═══════════════════════════════════════╣[/]      [#2A2A50]║[/][dim #1A1A38]░░[/]
[dim #1A1A38]░░[/][#2A2A50]║[/]      [#FFD700]⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣾⣿⣿⣿⣿[/][#FFEC8B]⚕[/][#FFD700]⣿⣿⣿⣿⣿⣿⣿⣿[/][#FFEC8B]⚕[/][#FFD700]⣿⣿⣿⣿⣿⡄⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]       [bold #FFD700]║[/]                                       [bold #FFD700]║[/]      [#2A2A50]║[/][dim #1A1A38]░░[/]
[dim #1A1A38]░░[/][#2A2A50]║[/]      [#FFEC8B]⠀⠀⠀⠀⠀⠀⠀⠀⠀⢸⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡇⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]       [bold #FFD700]║[/]  [#FFD700]⚕[/] [dim #555577]HERMES[/] — Divine Messenger     [bold #FFD700]║[/]      [#2A2A50]║[/][dim #1A1A38]░░[/]
[dim #1A1A38]░░[/][#2A2A50]║[/]      [#FFEC8B]⠀⠀⠀⠀⠀⠀⠀⠀⠀⢸⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡇⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]       [bold #FFD700]║[/]  [dim #00D4FF]route · switch · connect[/]          [bold #FFD700]║[/]      [#2A2A50]║[/][dim #1A1A38]░░[/]
[dim #1A1A38]░░[/][#2A2A50]║[/]      [#C9A227]⠀⠀⠀⠀⠀⠀⠀⠀⠀⠘⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⠃⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]       [bold #FFD700]║[/]                                       [bold #FFD700]║[/]      [#2A2A50]║[/][dim #1A1A38]░░[/]
[dim #1A1A38]░░[/][#2A2A50]║[/]      [#555577]⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠹⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⠏⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]       [bold #FFD700]║[/]  [dim #555577]Aliases • Providers • models.dev[/]  [bold #FFD700]║[/]      [#2A2A50]║[/][dim #1A1A38]░░[/]
[dim #1A1A38]░░[/][#2A2A50]║[/]      [dim #3A3A6A]⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠙⢿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡿⠋⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]       [bold #FFD700]╚═══════════════════════════════════════╝[/]      [#2A2A50]║[/][dim #1A1A38]░░[/]
[dim #1A1A38]░░[/][#2A2A50]║[/]      [dim #3A3A6A]⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠉⠛⠻⠿⠿⠿⠿⠿⠿⠟⠛⠉⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]                                                              [#2A2A50]║[/][dim #1A1A38]░░[/]
[dim #1A1A38]░░[/][#2A2A50]║[/]                                                                                                              [#2A2A50]║[/][dim #1A1A38]░░[/]
[dim #1A1A38]░░[/][#2A2A50]╚════════════════════════════════════════════════════════════════════════════════════════════════════════════════╝[/][dim #1A1A38]░░[/]
[dim #0A0A12]░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░[/]\
"""

MAX_MODELS_PER_PROVIDER = 6
ALIAS_DISPLAY_COLS = 6


class SwitchHero(Static):
    """Model switch hero art widget."""

    def render(self) -> str:
        return SWITCH_HERO_FRAME_1


class ActiveModelPanel(Static):
    """Shows the current active model config with divine styling."""

    info: reactive[dict] = reactive(dict, always_update=True)

    def render(self) -> str:
        header = "[bold #FFD700]⚕ ACTIVE MODEL[/]\n\n"

        if not self.info:
            return header + "[dim #555577]Loading...[/]"

        model = self.info.get("model", "?")
        provider = self.info.get("provider", "?")
        provider_label = self.info.get("provider_label", provider)
        base_url = self.info.get("base_url", "")
        ctx = self.info.get("context_length")

        if "openrouter" in provider.lower():
            provider_icon = "🌐"
            provider_color = "#00D4FF"
        elif "custom" in provider.lower() or "local" in provider.lower():
            provider_icon = "🖥"
            provider_color = "#00FF99"
        elif "ollama" in provider.lower():
            provider_icon = "🦙"
            provider_color = "#FF8C00"
        elif "anthropic" in provider.lower():
            provider_icon = "🔮"
            provider_color = "#D4A574"
        elif "openai" in provider.lower() or "codex" in provider.lower():
            provider_icon = "⚡"
            provider_color = "#74AA9C"
        elif "google" in provider.lower() or "gemini" in provider.lower():
            provider_icon = "💎"
            provider_color = "#4285F4"
        else:
            provider_icon = "⚡"
            provider_color = "#FFD700"

        ctx_line = ""
        if ctx:
            ctx_line = f"\n  [dim #555577]Context: {ctx:,} tokens ({ctx // 1024}K)[/]"

        url_line = ""
        if base_url:
            url_line = f"\n  [dim #555577]{base_url}[/]"

        return (
            header
            + f"  [{provider_color}]{provider_icon}[/] [bold #00FF99]{model}[/]\n"
            + f"  [dim #00A8CC]{provider_label}[/]"
            + url_line
            + ctx_line
        )


class ProvidersPanel(Static):
    """Shows authenticated providers with their curated model lists."""

    providers_data: reactive[list] = reactive(list, always_update=True)

    def render(self) -> str:
        header = "[bold #FFD700]ΓΝΩΣΤΟΙ — AUTHENTICATED PROVIDERS[/]\n\n"

        if not self.providers_data:
            return header + "[dim #555577]Scanning for providers...[/]"

        lines = []
        for p in self.providers_data:
            slug = p.get("slug", "?")
            name = p.get("name", slug)
            is_current = p.get("is_current", False)
            is_user = p.get("is_user_defined", False)
            models = p.get("models", [])
            total = p.get("total_models", 0)

            badge = "[bold #00FF99]◆ ACTIVE[/]" if is_current else "[dim #555577]◇[/]"
            user_tag = "  [dim #C9A227](user)[/]" if is_user else ""
            lines.append(
                f"  {badge}  [bold #FFD700]{name}[/]{user_tag}  "
                f"[dim #555577]--provider {slug}[/]"
            )

            if models:
                shown = models[:MAX_MODELS_PER_PROVIDER]
                model_parts = [f"[#E0F7FF]{m}[/]" for m in shown]
                extra = ""
                if total > len(shown):
                    extra = f"  [dim #555577]+{total - len(shown)} more[/]"
                lines.append(f"      {', '.join(model_parts)}{extra}")
            elif p.get("api_url"):
                lines.append(
                    f"      [dim #555577]{p['api_url']}[/]"
                )

            lines.append("")

        return header + "\n".join(lines)


class AliasesPanel(Static):
    """Shows available model aliases."""

    aliases_data: reactive[list] = reactive(list, always_update=True)

    def render(self) -> str:
        header = "[bold #FFD700]⚡ ALIASES — Quick Switch[/]\n\n"

        if not self.aliases_data:
            return header + "[dim #555577]No aliases loaded[/]"

        rows = []
        row: list[str] = []
        for alias in self.aliases_data:
            row.append(f"[#00D4FF]{alias}[/]")
            if len(row) >= ALIAS_DISPLAY_COLS:
                rows.append("  " + "  ".join(f"{a:<12}" for a in row))
                row = []
        if row:
            rows.append("  " + "  ".join(f"{a:<12}" for a in row))

        return header + "\n".join(rows)


class StatusMessage(Static):
    """Status message display."""

    message: reactive[str] = reactive("")

    def render(self) -> str:
        return f"\n{self.message}\n" if self.message else ""


class HermesPortrait(Static):
    """Hermes pixel art portrait with lore and abilities."""

    god_data: reactive[dict] = reactive(dict, always_update=True)

    def render(self) -> str:
        if not self.god_data:
            return "[dim #555577]Summoning the Divine Messenger...[/]"

        pixel_art = self.god_data.get("pixel_art", "")
        abilities = self.god_data.get("abilities", [])
        quotes = self.god_data.get("quotes", [])

        content = ""
        if pixel_art:
            content += pixel_art + "\n"

        if abilities:
            content += "\n[bold #FFD700]DIVINE POWERS:[/]\n"
            for ability in abilities[:3]:
                content += f"  [dim #FFEC8B]{ability}[/]\n"

        if quotes:
            quote = random.choice(quotes)
            content += f"\n[italic dim #555577]\"{quote}\"[/]"

        return content


class ModelSwitchView(ScrollableContainer):
    """Model Switchboard -- Uses the native hermes model pipeline.

    Supports the same syntax as ``/model`` in the CLI:
    - Model name or alias (e.g. ``sonnet``, ``gpt5``, ``deepseek``)
    - ``--provider <slug>`` flag
    - ``--global`` flag to persist to config.yaml
    """

    def compose(self) -> ComposeResult:
        yield SwitchHero(id="switch-hero", classes="hero-art")
        with Horizontal(classes="bento-row"):
            yield HermesPortrait(id="hermes-portrait", classes="divine-panel-gold")
            yield ActiveModelPanel(id="active-model", classes="divine-panel-gold")
        yield ProvidersPanel(id="providers-panel", classes="divine-panel")
        yield AliasesPanel(id="aliases-panel", classes="divine-panel")
        yield Static(
            "[bold #FFD700]⚕ SWITCH MODEL[/]  "
            "[dim #00A8CC]Same syntax as /model — "
            "enter a name, alias, or use --provider and --global flags[/]",
            classes="bento-gold",
        )
        with Horizontal(id="switch-row", classes="divine-panel"):
            yield Input(
                placeholder="e.g. sonnet, gpt5, deepseek, my-model --provider openrouter --global",
                id="switch-input-model",
            )
        yield StatusMessage(id="switch-status")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "switch-input-model":
            return

        raw = self.query_one("#switch-input-model", Input).value.strip()
        if not raw:
            self._set_status("[bold #FF4444]✗ Enter a model name or alias[/]")
            return

        self._set_status("[dim #00A8CC]Resolving model...[/]")
        self._do_switch(raw)

    @work(thread=True)
    def _do_switch(self, raw_input: str) -> None:
        from hermes_cli.model_switch import switch_model, parse_model_flags

        model_input, explicit_provider, is_global = parse_model_flags(raw_input)

        if not model_input and not explicit_provider:
            self.app.call_from_thread(
                self._set_status,
                "[bold #FF4444]✗ Enter a model name or alias[/]",
            )
            return

        current = _get_current_model_state()

        result = switch_model(
            raw_input=model_input,
            current_provider=current["provider"],
            current_model=current["model"],
            current_base_url=current["base_url"],
            current_api_key=current["api_key"],
            is_global=is_global,
            explicit_provider=explicit_provider,
            user_providers=current.get("user_providers"),
        )

        if not result.success:
            self.app.call_from_thread(
                self._set_status,
                f"[bold #FF4444]✗ {result.error_message}[/]",
            )
            return

        if is_global:
            _persist_model_switch(result)

        alias_note = ""
        if result.resolved_via_alias:
            alias_note = f"  [dim #C9A227](alias: {result.resolved_via_alias})[/]"

        global_note = ""
        if is_global:
            global_note = "  [dim #00FF99]saved to config.yaml[/]"

        provider_note = ""
        if result.provider_changed:
            label = result.provider_label or result.target_provider
            provider_note = f"  [dim #00A8CC]provider: {label}[/]"

        warn = ""
        if result.warning_message:
            warn = f"\n[dim #FFD700]⚠ {result.warning_message}[/]"

        msg = (
            f"[bold #00FF99]✓ Switched to {result.new_model}[/]"
            f"{alias_note}{provider_note}{global_note}{warn}"
        )

        self.app.call_from_thread(self._set_status, msg)
        self.app.call_from_thread(self.load_data)

    def _set_status(self, msg: str) -> None:
        try:
            self.query_one("#switch-status", StatusMessage).message = msg
        except Exception:
            pass

    @work(thread=True)
    def load_data(self) -> None:
        from hermes_cli.model_switch import (
            list_authenticated_providers,
            MODEL_ALIASES,
        )
        from hermes_cli.dashboard.data import get_god_detail

        current = _get_current_model_state()
        hermes_data = get_god_detail("Hermes")

        try:
            providers = list_authenticated_providers(
                current_provider=current["provider"],
                user_providers=current.get("user_providers"),
                max_models=MAX_MODELS_PER_PROVIDER,
            )
        except Exception:
            providers = []

        aliases = sorted(MODEL_ALIASES.keys())

        active_info = {
            "model": current["model"],
            "provider": current["provider"],
            "provider_label": current.get("provider_label", current["provider"]),
            "base_url": current["base_url"],
            "context_length": current.get("context_length"),
        }

        self.app.call_from_thread(
            self._apply, active_info, providers, aliases, hermes_data,
        )

    def _apply(
        self,
        active: dict,
        providers: list,
        aliases: list,
        hermes_data: dict,
    ) -> None:
        self.query_one("#active-model", ActiveModelPanel).info = active
        self.query_one("#providers-panel", ProvidersPanel).providers_data = providers
        self.query_one("#aliases-panel", AliasesPanel).aliases_data = aliases

        if hermes_data:
            self.query_one("#hermes-portrait", HermesPortrait).god_data = hermes_data

    def on_show(self) -> None:
        self.load_data()


def _get_current_model_state() -> dict:
    """Read the current model/provider/credentials from config + env.

    This mirrors what the CLI does at startup to resolve the active model.
    """
    from hermes_cli.dashboard.data import get_active_model_info, get_hermes_config
    from hermes_cli.providers import get_label

    info = get_active_model_info()
    cfg = get_hermes_config()

    model = info.get("model", "unknown")
    provider = info.get("provider", "unknown")
    base_url = info.get("base_url", "")
    context_length = info.get("context_length")

    api_key = ""
    try:
        from hermes_cli.runtime_provider import resolve_runtime_provider
        runtime = resolve_runtime_provider(requested=provider)
        api_key = runtime.get("api_key", "")
        if not base_url:
            base_url = runtime.get("base_url", "")
    except Exception:
        pass

    return {
        "model": model,
        "provider": provider,
        "provider_label": get_label(provider),
        "base_url": base_url,
        "api_key": api_key,
        "context_length": context_length,
        "user_providers": cfg.get("providers"),
    }


def _persist_model_switch(result) -> None:
    """Write a --global model switch to config.yaml."""
    try:
        import yaml
        from hermes_constants import get_hermes_home
        from utils import atomic_yaml_write

        config_path = get_hermes_home() / "config.yaml"
        if not config_path.exists():
            return

        with open(config_path) as f:
            cfg = yaml.safe_load(f) or {}

        if "model" not in cfg:
            cfg["model"] = {}
        cfg["model"]["default"] = result.new_model
        cfg["model"]["provider"] = result.target_provider
        if result.base_url:
            cfg["model"]["base_url"] = result.base_url

        atomic_yaml_write(config_path, cfg)
    except Exception:
        pass
