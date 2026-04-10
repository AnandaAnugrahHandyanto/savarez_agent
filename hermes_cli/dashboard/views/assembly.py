"""View 1: The Assembly -- OLYMPUS ASCENDED Home View.

Divine command center with:
- Cinematic animated hero banner with Hermes pixel art
- Divine execution flow diagram showing god routing
- Interactive pantheon strip with status indicators
- Live execution lanes with real tool call data
- God Stats Leaderboard with rankings
- Divine notifications panel
- Cost tracker (Drachmai treasury)
- Activity heatmap and sparklines
- Divine achievements system
- God Gallery with epic braille pixel art portraits
"""

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, ScrollableContainer
from textual.reactive import reactive
from textual.widgets import Static
from textual import work
import random


GOD_COLORS = {
    "Hermes": "#FFD700", "Athena": "#C0C0C0", "Apollo": "#FFE066",
    "Ares": "#DC143C", "Zeus": "#F0F0FF", "Hephaestus": "#FF8C00",
    "Artemis": "#32CD32", "Poseidon": "#1E90FF", "Hades": "#9B59B6",
    "Dionysus": "#FF00FF",
}

DEFAULT_LMSTUDIO_URL = "http://localhost:1234/v1"

HERMES_HERO_FRAME_1 = """\
[dim #0A0A12]░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░[/]
[dim #1A1A38]░░[/][#2A2A50]◈════════════════════════════════════════════════════════════════════════════════════════════════════════════════◈[/][dim #1A1A38]░░[/]
[dim #1A1A38]░░[/][#2A2A50]║[/]                                                                                                              [#2A2A50]║[/][dim #1A1A38]░░[/]
[dim #1A1A38]░░[/][#2A2A50]║[/]      [dim #3A3A6A]⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣀⣀⣀⣀⣀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]       [bold #FFD700]◈═══════════════════════════════════════◈[/]      [#2A2A50]║[/][dim #1A1A38]░░[/]
[dim #1A1A38]░░[/][#2A2A50]║[/]      [dim #3A3A6A]⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣠⣴⣾⣿⣿⣿⣿⣿⣿⣿⣷⣦⣄⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]       [bold #FFD700]║[/]  [bold #FFEC8B]⚡ OLYMPUS ASCENDED ⚡[/]            [bold #FFD700]║[/]      [#2A2A50]║[/][dim #1A1A38]░░[/]
[dim #1A1A38]░░[/][#2A2A50]║[/]      [#555577]⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣠⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣦⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]       [bold #FFD700]║[/]  [dim #00D4FF]Divine Orchestration System[/]       [bold #FFD700]║[/]      [#2A2A50]║[/][dim #1A1A38]░░[/]
[dim #1A1A38]░░[/][#2A2A50]║[/]      [#555577]⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣼⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣧⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]       [bold #FFD700]╠═══════════════════════════════════════╣[/]      [#2A2A50]║[/][dim #1A1A38]░░[/]
[dim #1A1A38]░░[/][#2A2A50]║[/]      [#C9A227]⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣾⣿⣿⣿⣿[/][#FFD700]⚡[/][#C9A227]⣿⣿⣿⣿⣿⣿⣿⣿[/][#FFD700]⚡[/][#C9A227]⣿⣿⣿⣿⣿⡄⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]       [bold #FFD700]║[/]                                       [bold #FFD700]║[/]      [#2A2A50]║[/][dim #1A1A38]░░[/]
[dim #1A1A38]░░[/][#2A2A50]║[/]      [#FFD700]⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢸⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡇⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]       [bold #FFD700]║[/]  [#C0C0C0]△[/] [dim #555577]ATHENA[/]    [#32CD32]🏹[/] [dim #555577]ARTEMIS[/]          [bold #FFD700]║[/]      [#2A2A50]║[/][dim #1A1A38]░░[/]
[dim #1A1A38]░░[/][#2A2A50]║[/]      [#FFD700]⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢸⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡇⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]       [bold #FFD700]║[/]  [#DC143C]⚔[/] [dim #555577]ARES[/]      [#FF8C00]🔨[/] [dim #555577]HEPHAESTUS[/]       [bold #FFD700]║[/]      [#2A2A50]║[/][dim #1A1A38]░░[/]
[dim #1A1A38]░░[/][#2A2A50]║[/]      [#C9A227]⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠘⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⠃⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]       [bold #FFD700]║[/]  [#1E90FF]🌊[/] [dim #555577]POSEIDON[/]  [#9B59B6]🕯[/] [dim #555577]HADES[/]            [bold #FFD700]║[/]      [#2A2A50]║[/][dim #1A1A38]░░[/]
[dim #1A1A38]░░[/][#2A2A50]║[/]      [#555577]⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠹⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⠏⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]       [bold #FFD700]║[/]  [#FFE066]☀[/] [dim #555577]APOLLO[/]    [#F0F0FF]👁[/] [dim #555577]ZEUS[/]             [bold #FFD700]║[/]      [#2A2A50]║[/][dim #1A1A38]░░[/]
[dim #1A1A38]░░[/][#2A2A50]║[/]      [dim #3A3A6A]⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠙⢿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡿⠋⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]       [bold #FFD700]║[/]                                       [bold #FFD700]║[/]      [#2A2A50]║[/][dim #1A1A38]░░[/]
[dim #1A1A38]░░[/][#2A2A50]║[/]      [dim #3A3A6A]⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠉⠛⠻⠿⠿⠿⠿⠿⠿⠟⠛⠉⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]       [bold #FFD700]║[/]  [bold #FFD700]⚕ HERMES[/] [dim #555577]— Divine Messenger[/]     [bold #FFD700]║[/]      [#2A2A50]║[/][dim #1A1A38]░░[/]
[dim #1A1A38]░░[/][#2A2A50]║[/]      [#FFD700]⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢸⣿⣿⡇⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]       [bold #FFD700]║[/]  [dim #00D4FF]route · spawn · synthesize[/]         [bold #FFD700]║[/]      [#2A2A50]║[/][dim #1A1A38]░░[/]
[dim #1A1A38]░░[/][#2A2A50]║[/]      [#C9A227]⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢸⣿⣿⡇⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]       [bold #FFD700]◈═══════════════════════════════════════◈[/]      [#2A2A50]║[/][dim #1A1A38]░░[/]
[dim #1A1A38]░░[/][#2A2A50]║[/]      [#555577]⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢸⣿⣿⡇⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]                                                              [#2A2A50]║[/][dim #1A1A38]░░[/]
[dim #1A1A38]░░[/][#2A2A50]║[/]      [dim #3A3A6A]⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢸⣿⣿⡇⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]                                                              [#2A2A50]║[/][dim #1A1A38]░░[/]
[dim #1A1A38]░░[/][#2A2A50]║[/]                                                                                                              [#2A2A50]║[/][dim #1A1A38]░░[/]
[dim #1A1A38]░░[/][#2A2A50]◈════════════════════════════════════════════════════════════════════════════════════════════════════════════════◈[/][dim #1A1A38]░░[/]
[dim #0A0A12]░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░[/]\
"""

HERMES_HERO_FRAME_2 = """\
[dim #0A0A12]░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░[/]
[dim #1A1A38]░░[/][#3A3A6A]◈════════════════════════════════════════════════════════════════════════════════════════════════════════════════◈[/][dim #1A1A38]░░[/]
[dim #1A1A38]░░[/][#3A3A6A]║[/]                                                                                                              [#3A3A6A]║[/][dim #1A1A38]░░[/]
[dim #1A1A38]░░[/][#3A3A6A]║[/]      [dim #3A3A6A]⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣀⣀⣀⣀⣀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]       [bold #FFEC8B]◈═══════════════════════════════════════◈[/]      [#3A3A6A]║[/][dim #1A1A38]░░[/]
[dim #1A1A38]░░[/][#3A3A6A]║[/]      [dim #3A3A6A]⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣠⣴⣾⣿⣿⣿⣿⣿⣿⣿⣷⣦⣄⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]       [bold #FFEC8B]║[/]  [bold #FFD700]✦ OLYMPUS ASCENDED ✦[/]            [bold #FFEC8B]║[/]      [#3A3A6A]║[/][dim #1A1A38]░░[/]
[dim #1A1A38]░░[/][#3A3A6A]║[/]      [#555577]⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣠⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣦⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]       [bold #FFEC8B]║[/]  [dim #00D4FF]Divine Orchestration System[/]       [bold #FFEC8B]║[/]      [#3A3A6A]║[/][dim #1A1A38]░░[/]
[dim #1A1A38]░░[/][#3A3A6A]║[/]      [#555577]⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣼⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣧⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]       [bold #FFEC8B]╠═══════════════════════════════════════╣[/]      [#3A3A6A]║[/][dim #1A1A38]░░[/]
[dim #1A1A38]░░[/][#3A3A6A]║[/]      [#FFD700]⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣾⣿⣿⣿⣿[/][#FFEC8B]✦[/][#FFD700]⣿⣿⣿⣿⣿⣿⣿⣿[/][#FFEC8B]✦[/][#FFD700]⣿⣿⣿⣿⣿⡄⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]       [bold #FFEC8B]║[/]                                       [bold #FFEC8B]║[/]      [#3A3A6A]║[/][dim #1A1A38]░░[/]
[dim #1A1A38]░░[/][#3A3A6A]║[/]      [#FFEC8B]⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢸⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡇⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]       [bold #FFEC8B]║[/]  [#C0C0C0]△[/] [dim #555577]ATHENA[/]    [#32CD32]🏹[/] [dim #555577]ARTEMIS[/]          [bold #FFEC8B]║[/]      [#3A3A6A]║[/][dim #1A1A38]░░[/]
[dim #1A1A38]░░[/][#3A3A6A]║[/]      [#FFEC8B]⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢸⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡇⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]       [bold #FFEC8B]║[/]  [#DC143C]⚔[/] [dim #555577]ARES[/]      [#FF8C00]🔨[/] [dim #555577]HEPHAESTUS[/]       [bold #FFEC8B]║[/]      [#3A3A6A]║[/][dim #1A1A38]░░[/]
[dim #1A1A38]░░[/][#3A3A6A]║[/]      [#FFD700]⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠘⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⠃⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]       [bold #FFEC8B]║[/]  [#1E90FF]🌊[/] [dim #555577]POSEIDON[/]  [#9B59B6]🕯[/] [dim #555577]HADES[/]            [bold #FFEC8B]║[/]      [#3A3A6A]║[/][dim #1A1A38]░░[/]
[dim #1A1A38]░░[/][#3A3A6A]║[/]      [#555577]⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠹⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⠏⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]       [bold #FFEC8B]║[/]  [#FFE066]☀[/] [dim #555577]APOLLO[/]    [#F0F0FF]👁[/] [dim #555577]ZEUS[/]             [bold #FFEC8B]║[/]      [#3A3A6A]║[/][dim #1A1A38]░░[/]
[dim #1A1A38]░░[/][#3A3A6A]║[/]      [dim #3A3A6A]⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠙⢿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡿⠋⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]       [bold #FFEC8B]║[/]                                       [bold #FFEC8B]║[/]      [#3A3A6A]║[/][dim #1A1A38]░░[/]
[dim #1A1A38]░░[/][#3A3A6A]║[/]      [dim #3A3A6A]⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠉⠛⠻⠿⠿⠿⠿⠿⠿⠟⠛⠉⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]       [bold #FFEC8B]║[/]  [bold #FFEC8B]⚕ HERMES[/] [dim #555577]— Divine Messenger[/]     [bold #FFEC8B]║[/]      [#3A3A6A]║[/][dim #1A1A38]░░[/]
[dim #1A1A38]░░[/][#3A3A6A]║[/]      [#FFEC8B]⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢸⣿⣿⡇⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]       [bold #FFEC8B]║[/]  [dim #00D4FF]route · spawn · synthesize[/]         [bold #FFEC8B]║[/]      [#3A3A6A]║[/][dim #1A1A38]░░[/]
[dim #1A1A38]░░[/][#3A3A6A]║[/]      [#FFD700]⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢸⣿⣿⡇⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]       [bold #FFEC8B]◈═══════════════════════════════════════◈[/]      [#3A3A6A]║[/][dim #1A1A38]░░[/]
[dim #1A1A38]░░[/][#3A3A6A]║[/]      [#555577]⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢸⣿⣿⡇⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]                                                              [#3A3A6A]║[/][dim #1A1A38]░░[/]
[dim #1A1A38]░░[/][#3A3A6A]║[/]      [dim #3A3A6A]⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢸⣿⣿⡇⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]                                                              [#3A3A6A]║[/][dim #1A1A38]░░[/]
[dim #1A1A38]░░[/][#3A3A6A]║[/]                                                                                                              [#3A3A6A]║[/][dim #1A1A38]░░[/]
[dim #1A1A38]░░[/][#3A3A6A]◈════════════════════════════════════════════════════════════════════════════════════════════════════════════════◈[/][dim #1A1A38]░░[/]
[dim #0A0A12]░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░[/]\
"""

HERMES_HERO_FRAME_3 = """\
[dim #0A0A12]░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░[/]
[dim #1A1A38]░░[/][#FFD700]◈════════════════════════════════════════════════════════════════════════════════════════════════════════════════◈[/][dim #1A1A38]░░[/]
[dim #1A1A38]░░[/][#FFD700]║[/]                                                                                                              [#FFD700]║[/][dim #1A1A38]░░[/]
[dim #1A1A38]░░[/][#FFD700]║[/]      [dim #3A3A6A]⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣀⣀⣀⣀⣀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]       [bold #FFD700]◈═══════════════════════════════════════◈[/]      [#FFD700]║[/][dim #1A1A38]░░[/]
[dim #1A1A38]░░[/][#FFD700]║[/]      [dim #3A3A6A]⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣠⣴⣾⣿⣿⣿⣿⣿⣿⣿⣷⣦⣄⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]       [bold #FFD700]║[/]  [bold #FFD700]◈ OLYMPUS ASCENDED ◈[/]            [bold #FFD700]║[/]      [#FFD700]║[/][dim #1A1A38]░░[/]
[dim #1A1A38]░░[/][#FFD700]║[/]      [#C9A227]⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣠⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣦⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]       [bold #FFD700]║[/]  [dim #00D4FF]Divine Orchestration System[/]       [bold #FFD700]║[/]      [#FFD700]║[/][dim #1A1A38]░░[/]
[dim #1A1A38]░░[/][#FFD700]║[/]      [#C9A227]⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣼⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣧⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]       [bold #FFD700]╠═══════════════════════════════════════╣[/]      [#FFD700]║[/][dim #1A1A38]░░[/]
[dim #1A1A38]░░[/][#FFD700]║[/]      [#FFEC8B]⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣾⣿⣿⣿⣿[/][bold #FFD700]◈[/][#FFEC8B]⣿⣿⣿⣿⣿⣿⣿⣿[/][bold #FFD700]◈[/][#FFEC8B]⣿⣿⣿⣿⣿⡄⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]       [bold #FFD700]║[/]                                       [bold #FFD700]║[/]      [#FFD700]║[/][dim #1A1A38]░░[/]
[dim #1A1A38]░░[/][#FFD700]║[/]      [bold #FFD700]⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢸⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡇⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]       [bold #FFD700]║[/]  [#C0C0C0]△[/] [dim #555577]ATHENA[/]    [#32CD32]🏹[/] [dim #555577]ARTEMIS[/]          [bold #FFD700]║[/]      [#FFD700]║[/][dim #1A1A38]░░[/]
[dim #1A1A38]░░[/][#FFD700]║[/]      [bold #FFD700]⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢸⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡇⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]       [bold #FFD700]║[/]  [#DC143C]⚔[/] [dim #555577]ARES[/]      [#FF8C00]🔨[/] [dim #555577]HEPHAESTUS[/]       [bold #FFD700]║[/]      [#FFD700]║[/][dim #1A1A38]░░[/]
[dim #1A1A38]░░[/][#FFD700]║[/]      [#FFEC8B]⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠘⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⠃⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]       [bold #FFD700]║[/]  [#1E90FF]🌊[/] [dim #555577]POSEIDON[/]  [#9B59B6]🕯[/] [dim #555577]HADES[/]            [bold #FFD700]║[/]      [#FFD700]║[/][dim #1A1A38]░░[/]
[dim #1A1A38]░░[/][#FFD700]║[/]      [#C9A227]⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠹⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⠏⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]       [bold #FFD700]║[/]  [#FFE066]☀[/] [dim #555577]APOLLO[/]    [#F0F0FF]👁[/] [dim #555577]ZEUS[/]             [bold #FFD700]║[/]      [#FFD700]║[/][dim #1A1A38]░░[/]
[dim #1A1A38]░░[/][#FFD700]║[/]      [dim #3A3A6A]⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠙⢿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡿⠋⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]       [bold #FFD700]║[/]                                       [bold #FFD700]║[/]      [#FFD700]║[/][dim #1A1A38]░░[/]
[dim #1A1A38]░░[/][#FFD700]║[/]      [dim #3A3A6A]⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠉⠛⠻⠿⠿⠿⠿⠿⠿⠟⠛⠉⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]       [bold #FFD700]║[/]  [bold #FFD700]⚕ HERMES[/] [dim #555577]— Divine Messenger[/]     [bold #FFD700]║[/]      [#FFD700]║[/][dim #1A1A38]░░[/]
[dim #1A1A38]░░[/][#FFD700]║[/]      [bold #FFD700]⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢸⣿⣿⡇⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]       [bold #FFD700]║[/]  [dim #00D4FF]route · spawn · synthesize[/]         [bold #FFD700]║[/]      [#FFD700]║[/][dim #1A1A38]░░[/]
[dim #1A1A38]░░[/][#FFD700]║[/]      [#FFEC8B]⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢸⣿⣿⡇⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]       [bold #FFD700]◈═══════════════════════════════════════◈[/]      [#FFD700]║[/][dim #1A1A38]░░[/]
[dim #1A1A38]░░[/][#FFD700]║[/]      [#C9A227]⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢸⣿⣿⡇⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]                                                              [#FFD700]║[/][dim #1A1A38]░░[/]
[dim #1A1A38]░░[/][#FFD700]║[/]      [dim #3A3A6A]⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢸⣿⣿⡇⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]                                                              [#FFD700]║[/][dim #1A1A38]░░[/]
[dim #1A1A38]░░[/][#FFD700]║[/]                                                                                                              [#FFD700]║[/][dim #1A1A38]░░[/]
[dim #1A1A38]░░[/][#FFD700]◈════════════════════════════════════════════════════════════════════════════════════════════════════════════════◈[/][dim #1A1A38]░░[/]
[dim #0A0A12]░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░[/]\
"""

HERO_FRAMES = [HERMES_HERO_FRAME_1, HERMES_HERO_FRAME_2, HERMES_HERO_FRAME_3]


FLOW_DIAGRAM = """\
[dim #2A2A50]◈─────────────────────────────────────────────────────────────────────────────────────◈[/]
[dim #2A2A50]│[/]  [bold #FFD700]⚡ DIVINE EXECUTION FLOW[/]                                                          [dim #2A2A50]│[/]
[dim #2A2A50]│[/]                                                                                     [dim #2A2A50]│[/]
[dim #2A2A50]│[/]   [#C0C0C0]△ ATHENA[/]  ──▶  [#32CD32]🏹 ARTEMIS[/]  ──▶  [#DC143C]⚔ ARES[/]  ──▶  [#FF8C00]🔨 HEPHAESTUS[/]           [dim #2A2A50]│[/]
[dim #2A2A50]│[/]   [dim #555577]strategy[/]      [dim #555577]retrieval[/]       [dim #555577]execution[/]     [dim #555577]forge[/]                     [dim #2A2A50]│[/]
[dim #2A2A50]│[/]       │              │               │              │                          [dim #2A2A50]│[/]
[dim #2A2A50]│[/]       └──────────────┴───────────────┴──────────────┘                          [dim #2A2A50]│[/]
[dim #2A2A50]│[/]                              │                                                  [dim #2A2A50]│[/]
[dim #2A2A50]│[/]                              ▼                                                  [dim #2A2A50]│[/]
[dim #2A2A50]│[/]                      [#FFD700]⚕ HERMES[/]  ◀──  [#9B59B6]🕯 HADES[/]  ◀──  [#1E90FF]🌊 POSEIDON[/]          [dim #2A2A50]│[/]
[dim #2A2A50]│[/]                      [dim #555577]orchestrator[/]    [dim #555577]archive[/]        [dim #555577]flow[/]                  [dim #2A2A50]│[/]
[dim #2A2A50]│[/]                                                                                     [dim #2A2A50]│[/]
[dim #2A2A50]◈─────────────────────────────────────────────────────────────────────────────────────◈[/]\
"""


def _make_leaderboard_entry(rank: int, god: dict, stats: dict) -> str:
    """Create a leaderboard entry for a god."""
    name = god.get("name", "?")
    icon = god.get("icon", "✦")
    calls = stats.get("calls", 0)
    pct = stats.get("pct", 0)
    
    color = GOD_COLORS.get(name, "#FFD700")
    
    rank_colors = {1: "#FFD700", 2: "#C0C0C0", 3: "#CD7F32"}
    rank_color = rank_colors.get(rank, "#555577")
    rank_icon = {1: "🥇", 2: "🥈", 3: "🥉"}.get(rank, f"#{rank}")
    
    bar_len = min(int(pct / 5), 20)
    bar = "█" * bar_len + "░" * (20 - bar_len)
    
    return (
        f"  [{rank_color}]{rank_icon:<3}[/]  [{color}]{icon}[/] [{color}]{name:<12}[/]  "
        f"[{color}]{bar}[/]  [bold #00FF99]{calls:>6}[/]  [dim #555577]{pct:>3}%[/]"
    )


def _make_exec_lane_live(lane: dict) -> str:
    """Create an execution lane display with live data."""
    name = lane.get("name", "UNKNOWN")
    god = lane.get("god", "Hermes")
    icon = lane.get("icon", "◈")
    color = lane.get("color", "#FFD700")
    calls = lane.get("calls", 0)
    pct = lane.get("pct", 0)
    latency = lane.get("latency_ms", 0)
    
    filled = int(pct / 100 * 20)
    bar = "█" * filled + "░" * (20 - filled)
    
    bar_color = "#00FF99" if pct > 60 else "#FFD700" if pct > 30 else "#FF4444" if pct > 0 else "#2A2A50"
    
    return (
        f"  [{color}]{icon}[/]  [bold #E0F7FF]{name:<12}[/]  "
        f"[dim #555577]{god:<12}[/]  "
        f"[{bar_color}]{bar}[/] [{bar_color}]{pct:>3}%[/]  "
        f"[dim #00D4FF]{calls:>5} calls[/]  "
        f"[dim #555577]{latency}ms[/]"
    )


def _make_notification(notif: dict, icons: dict) -> str:
    """Create a notification line with icon and message."""
    level = notif.get("level", "info")
    message = notif.get("message", "")
    ts = notif.get("timestamp", 0)
    
    from hermes_cli.dashboard.data import format_timestamp
    time_str = format_timestamp(ts)
    
    icon_map = {
        "info": icons.get("info_icon", "✦"),
        "warn": icons.get("warn_icon", "⚠"),
        "error": icons.get("error_icon", "⚡"),
        "success": icons.get("success_icon", "✓"),
    }
    color_map = {
        "info": "#00D4FF",
        "warn": "#FFD700",
        "error": "#FF4444",
        "success": "#00FF99",
    }
    
    icon = icon_map.get(level, "•")
    color = color_map.get(level, "#555577")
    
    return f"  [{color}]{icon}[/]  [dim #555577]{time_str}[/]  [{color}]{message}[/]"


def _make_activity_heatmap(daily_data: list) -> str:
    """Create a 14-day activity heatmap."""
    if not daily_data:
        return "[dim #555577]No activity data[/]"
    
    blocks = " ░▒▓█"
    max_sessions = max(d.get("sessions", 0) for d in daily_data) or 1
    
    heatmap = ""
    for d in daily_data[-14:]:
        sessions = d.get("sessions", 0)
        level = min(int((sessions / max_sessions) * 4), 4)
        color = ["#1A1A38", "#2A4A2A", "#3A6A3A", "#4A8A4A", "#00FF99"][level]
        heatmap += f"[{color}]{blocks[level]}[/]"
    
    return heatmap


def _make_sparkline(values: list, width: int = 20, color: str = "#00D4FF") -> str:
    """Create a sparkline from values."""
    if not values:
        return "[dim #1A1A38]" + "░" * width + "[/]"
    
    blocks = " ▁▂▃▄▅▆▇█"
    mx = max(values) if max(values) > 0 else 1
    
    padded = values[-width:] if len(values) >= width else values
    chars = []
    for v in padded:
        idx = min(int((v / mx) * (len(blocks) - 1)), len(blocks) - 1)
        chars.append(blocks[idx])
    
    return f"[{color}]{''.join(chars)}[/]"


class HeroArt(Static):
    """Animated hero art widget with frame cycling."""
    
    frame_index: reactive[int] = reactive(0)
    
    def render(self) -> str:
        frames = HERO_FRAMES
        if self.frame_index < len(frames):
            return frames[self.frame_index]
        return frames[0] if frames else ""
    
    def cycle_frame(self) -> None:
        self.frame_index = (self.frame_index + 1) % len(HERO_FRAMES)


class GodLeaderboard(Static):
    """God stats leaderboard with rankings."""
    
    activity: reactive[list] = reactive(list, always_update=True)
    
    def render(self) -> str:
        header = "[bold #FFD700]◈ DIVINE LEADERBOARD — God Activity Rankings[/]\n\n"
        header += "  [dim #555577]RANK  GOD           ACTIVITY                  CALLS    %[/]\n"
        header += "  [dim #2A2A50]" + "─" * 70 + "[/]\n"
        
        if not self.activity:
            return header + "  [dim #555577]The gods are resting. No activity recorded.[/]"
        
        sorted_gods = sorted(self.activity, key=lambda x: x.get("calls", 0), reverse=True)
        
        lines = []
        for i, god in enumerate(sorted_gods[:10], 1):
            lines.append(_make_leaderboard_entry(i, god, god))
        
        total_calls = sum(g.get("calls", 0) for g in self.activity)
        footer = f"\n  [dim #2A2A50]{'─' * 70}[/]\n"
        footer += f"  [bold #FFD700]TOTAL DIVINE STRIKES:[/]  [bold #00FF99]{total_calls:,}[/]"
        
        return header + "\n".join(lines) + footer


class PantheonStrip(Static):
    """Compact pantheon strip showing all gods with divine styling."""
    
    gods: reactive[list] = reactive(list, always_update=True)
    activity: reactive[dict] = reactive(dict, always_update=True)
    
    def render(self) -> str:
        if not self.gods:
            return "[dim #555577]Summoning the pantheon...[/]"
        
        activity_map = {g.get("name"): g for g in self.activity} if isinstance(self.activity, list) else {}
        
        god_colors = {
            "Hermes": "#FFD700", "Athena": "#C0C0C0", "Apollo": "#FFE066",
            "Ares": "#DC143C", "Zeus": "#F0F0FF", "Hephaestus": "#FF8C00",
            "Artemis": "#32CD32", "Poseidon": "#1E90FF", "Hades": "#9B59B6",
            "Dionysus": "#FF00FF",
        }
        
        header = "[bold #FFD700]◈ PANTHEON[/]  "
        
        parts = []
        for god in self.gods[:10]:
            name = god.get("name", "?")
            icon = god.get("icon", "✦")
            rank = god.get("rank", "???")
            color = god_colors.get(name, "#FFD700")
            
            stats = activity_map.get(name, {})
            calls = stats.get("calls", 0)
            status = stats.get("status", "idle")
            
            status_color = "#00FF99" if status == "active" else "#FFD700" if status == "ready" else "#3A3A6A"
            status_dot = "●" if status == "active" else "◐" if status == "ready" else "○"
            
            parts.append(
                f"[{color}]{icon}[/][{status_color}]{status_dot}[/]"
            )
        
        return header + "  ".join(parts) + f"  [dim #555577]│ {len(self.gods)} gods watching[/]"


class DivineFlowDiagram(Static):
    """Divine execution flow diagram showing god routing."""
    
    active_god: reactive[str] = reactive("")
    
    def render(self) -> str:
        return FLOW_DIAGRAM


class ExecutionLanes(Static):
    """Live execution lanes with real tool call data."""
    
    lanes: reactive[list] = reactive(list, always_update=True)
    
    def render(self) -> str:
        header = "[bold #FFD700]◈ EXECUTION LANES — Divine Tool Flow[/]\n\n"
        header += "  [dim #555577]LANE          GOD           ACTIVITY                  CALLS    LATENCY[/]\n"
        header += "  [dim #2A2A50]" + "─" * 75 + "[/]\n"
        
        if not self.lanes:
            return header + "  [dim #555577]The lanes are quiet. No tool calls recorded.[/]"
        
        lane_lines = [_make_exec_lane_live(lane) for lane in self.lanes]
        
        total_calls = sum(l.get("calls", 0) for l in self.lanes)
        footer = f"\n  [dim #2A2A50]{'─' * 75}[/]\n"
        footer += f"  [bold #FFD700]TOTAL DIVINE STRIKES:[/]  [bold #00FF99]{total_calls:,}[/]"
        
        return header + "\n".join(lane_lines) + footer


class ActivityDashboard(Static):
    """Activity dashboard with heatmap and sparklines."""

    daily_data: reactive[list] = reactive(list, always_update=True)
    
    def render(self) -> str:
        header = "[bold #FFD700]◈ ACTIVITY OVERVIEW — Divine Metrics[/]\n\n"
        
        heatmap = _make_activity_heatmap(self.daily_data)
        header += f"  [dim #00A8CC]14-Day Heatmap[/]  {heatmap}\n\n"
        
        if self.daily_data:
            sessions = [d.get("sessions", 0) for d in self.daily_data]
            messages = [d.get("messages", 0) for d in self.daily_data]
            costs = [d.get("cost", 0) for d in self.daily_data]
            
            header += f"  [dim #00A8CC]Σεσσιονς [/]  {_make_sparkline(sessions, 30, '#00FF99')}\n"
            header += f"  [dim #00A8CC]Μεσσαγες [/]  {_make_sparkline(messages, 30, '#00D4FF')}\n"
            header += f"  [dim #00A8CC]Δραχμαί  [/]  {_make_sparkline(costs, 30, '#FFD700')}\n"
        
        return header


class DivineNotifications(Static):
    """Divine notifications panel showing recent events."""
    
    notifications: reactive[list] = reactive(list, always_update=True)
    
    def render(self) -> str:
        from hermes_cli.dashboard.data import get_skin_notifications_config
        icons = get_skin_notifications_config()
        
        header = "[bold #FFD700]◈ DIVINE PROCLAMATIONS — Oracle Messages[/]\n\n"
        
        if not self.notifications:
            return header + "  [dim #555577]The oracle is silent. No recent decrees.[/]"
        
        lines = [_make_notification(n, icons) for n in self.notifications[:8]]
        return header + "\n".join(lines)


class CostTracker(Static):
    """Drachmai cost tracker widget."""
    
    costs: reactive[dict] = reactive(dict, always_update=True)
    
    def render(self) -> str:
        from hermes_cli.dashboard.data import format_cost
        
        header = "[bold #FFD700]◈ ΔΡΑΧΜΑΙ — Divine Treasury[/]\n\n"
        
        if not self.costs:
            return header + "  [dim #555577]Consulting the treasury...[/]"
        
        daily = self.costs.get("daily", 0)
        weekly = self.costs.get("weekly", 0)
        monthly = self.costs.get("monthly", 0)
        total = self.costs.get("total", 0)
        
        lines = [
            f"  [dim #00A8CC]Σήμερα   [/]  [bold #00FF99]{format_cost(daily)}[/]",
            f"  [dim #00A8CC]Εβδομάδα [/]  [bold #00D4FF]{format_cost(weekly)}[/]",
            f"  [dim #00A8CC]Μήνας    [/]  [bold #FFD700]{format_cost(monthly)}[/]",
            f"  [dim #00A8CC]Σύνολο   [/]  [bold #FF4444]{format_cost(total)}[/]",
        ]
        
        model_breakdown = self.costs.get("model_breakdown", [])
        if model_breakdown:
            lines.append("")
            lines.append("  [dim #2A2A50]─── By Model ───[/]")
            for m in model_breakdown[:3]:
                model_name = (m.get("model", "?")).split("/")[-1][:20]
                cost = format_cost(m.get("cost", 0))
                lines.append(f"  [dim #555577]{model_name:<20}[/]  [#FFD700]{cost}[/]")
        
        return header + "\n".join(lines)


class RecentSessions(Static):
    """Recent sessions list with divine styling."""
    
    sessions: reactive[list] = reactive(list, always_update=True)
    
    def render(self) -> str:
        from hermes_cli.dashboard.data import format_timestamp, format_cost
        
        header = "[bold #FFD700]◈ RECENT DECREES — Session Archive[/]\n\n"
        header += "  [dim #555577]TIME          TITLE                                MODEL           MSG  TOOLS  COST[/]\n"
        header += "  [dim #2A2A50]" + "─" * 90 + "[/]\n"
        
        if not self.sessions:
            return header + "  [dim #555577]No decrees yet. The scrolls await.[/]"
        
        lines = []
        for i, s in enumerate(self.sessions[:8]):
            ts = format_timestamp(s.get("last_active") or s.get("started_at", 0))
            model = (s.get("model") or "?").split("/")[-1][:14]
            title = (s.get("title") or s.get("preview", "") or "untitled")[:35]
            cost = format_cost(s.get("actual_cost_usd") or s.get("estimated_cost_usd") or 0)
            msgs = s.get("message_count", 0)
            tools = s.get("tool_call_count", 0)
            
            marker = "[#FFD700]✦[/]" if i % 2 == 0 else "[#00A8CC]·[/]"
            tool_indicator = f"[#DC143C]⚔{tools}[/]" if tools > 10 else f"[dim #555577]⚔{tools}[/]"
            
            lines.append(
                f"  {marker}  [dim #00A8CC]{ts:<12}[/]  [#E0F7FF]{title:<35}[/]  "
                f"[dim #555577]{model:<14}[/]  [dim #00D4FF]{msgs:>3}[/]  {tool_indicator}  [#FFD700]{cost}[/]"
            )
        
        return header + "\n".join(lines)


class QuickStats(Static):
    """Quick stats bar with divine metrics."""
    
    stats: reactive[dict] = reactive(dict, always_update=True)
    
    def render(self) -> str:
        from hermes_cli.dashboard.data import format_tokens, format_cost
        
        if not self.stats:
            return "[dim #555577]Consulting the oracle...[/]"
        
        sessions = self.stats.get("total_sessions", 0)
        messages = self.stats.get("total_messages", 0)
        tools = self.stats.get("total_tool_calls", 0)
        tokens = self.stats.get("total_input_tokens", 0) + self.stats.get("total_output_tokens", 0)
        cost = self.stats.get("total_cost", 0)
        
        return (
            f"[bold #FFD700]Σεσσιονς[/]  [bold #00FF99]{sessions}[/]"
            f"     [bold #FFD700]Μεσσαγες[/]  [bold #00FF99]{messages}[/]"
            f"     [bold #FFD700]Εργαλεία[/]  [bold #00FF99]{tools}[/]"
            f"     [bold #FFD700]Μάρκες[/]  [bold #00D4FF]{format_tokens(tokens)}[/]"
            f"     [bold #FFD700]Δραχμαί[/]  [bold #FFD700]{format_cost(cost)}[/]"
        )


class ModelStatus(Static):
    """Quick model status showing current active model."""
    
    model_info: reactive[dict] = reactive(dict, always_update=True)
    lms_status: reactive[str] = reactive("checking")
    
    def render(self) -> str:
        from hermes_cli.dashboard.data import format_tokens
        
        model = self.model_info.get("model", "unknown")
        provider = self.model_info.get("provider", "unknown")
        ctx = self.model_info.get("context_length")
        
        if "openrouter" in provider.lower():
            provider_icon = "◈"
            provider_color = "#00D4FF"
            provider_label = "OpenRouter"
        elif "lmstudio" in provider.lower() or "custom:" in provider.lower():
            provider_icon = "⚙"
            provider_color = "#00FF99"
            provider_label = "LM Studio"
        elif "ollama" in provider.lower():
            provider_icon = "◎"
            provider_color = "#FF8C00"
            provider_label = "Ollama"
        else:
            provider_icon = "⚡"
            provider_color = "#FFD700"
            provider_label = provider.split(":")[-1] if ":" in provider else provider
        
        model_short = model.split("/")[-1] if "/" in model else model
        if len(model_short) > 25:
            model_short = model_short[:22] + "..."
        
        ctx_str = f"  [dim #555577]{ctx//1024}K ctx[/]" if ctx else ""
        
        lms_indicator = ""
        if self.lms_status == "online":
            lms_indicator = "  [#00FF99]● LMS[/]"
        elif self.lms_status == "offline":
            lms_indicator = "  [#FF4444]○ LMS[/]"
        
        return (
            f"[bold #FFD700]◈ ACTIVE MODEL[/]  "
            f"[{provider_color}]{provider_icon} {provider_label}[/]  "
            f"[bold #E0F7FF]{model_short}[/]"
            f"{ctx_str}{lms_indicator}"
        )


class DivineAchievements(Static):
    """Divine achievements/badges widget."""
    
    stats: reactive[dict] = reactive(dict, always_update=True)
    
    def render(self) -> str:
        header = "[bold #FFD700]◈ DIVINE ACHIEVEMENTS — Badges of Honor[/]\n\n"
        
        if not self.stats:
            return header + "  [dim #555577]No achievements yet.[/]"
        
        sessions = self.stats.get("total_sessions", 0)
        messages = self.stats.get("total_messages", 0)
        tools = self.stats.get("total_tool_calls", 0)
        
        achievements = []
        
        if sessions >= 100:
            achievements.append(("[#FFD700]⚡[/]", "Olympian", "100+ sessions"))
        elif sessions >= 50:
            achievements.append(("[#C0C0C0]✦[/]", "Demigod", "50+ sessions"))
        elif sessions >= 10:
            achievements.append(("[#CD7F32]◈[/]", "Initiate", "10+ sessions"))
        
        if tools >= 1000:
            achievements.append(("[#FFD700]⚔[/]", "Forge Master", "1000+ tool calls"))
        elif tools >= 500:
            achievements.append(("[#FF8C00]🔨[/]", "Craftsman", "500+ tool calls"))
        elif tools >= 100:
            achievements.append(("[#CD7F32]⚙[/]", "Apprentice", "100+ tool calls"))
        
        if messages >= 1000:
            achievements.append(("[#FFD700]⚕[/]", "Chronicler", "1000+ messages"))
        elif messages >= 500:
            achievements.append(("[#C0C0C0]§[/]", "Scribe", "500+ messages"))
        
        if not achievements:
            return header + "  [dim #555577]Begin your divine journey to earn badges![/]"
        
        lines = []
        for icon, name, desc in achievements:
            lines.append(f"  {icon}  [bold #E0F7FF]{name}[/]  [dim #555577]{desc}[/]")
        
        return header + "\n".join(lines)


class GodGallery(Static):
    """Gallery showing all god portraits with epic braille pixel art."""
    
    gods: reactive[list] = reactive(list, always_update=True)
    selected_god: reactive[int] = reactive(0)
    
    def render(self) -> str:
        header = "[bold #FFD700]◈ PANTHEON GALLERY — Divine Portraits ◈[/]\n\n"
        
        if not self.gods:
            return header + "  [dim #555577]The gods have not yet revealed themselves...[/]"
        
        # Get the selected god's pixel art
        god = self.gods[self.selected_god % len(self.gods)]
        pixel_art = god.get("pixel_art", "")
        name = god.get("name", "Unknown")
        title = god.get("title", "")
        icon = god.get("icon", "✦")
        color = god.get("color", "#FFD700")
        abilities = god.get("abilities", [])
        quotes = god.get("quotes", [])
        lore = god.get("lore", "")
        
        # Navigation strip with divine styling
        nav_parts = []
        for i, g in enumerate(self.gods):
            g_icon = g.get("icon", "✦")
            g_color = g.get("color", "#555577")
            if i == self.selected_god % len(self.gods):
                nav_parts.append(f"[bold {g_color}]⟪{g_icon}⟫[/]")
            else:
                nav_parts.append(f"[dim #3A3A6A]{g_icon}[/]")
        
        nav_line = "  " + "  ".join(nav_parts) + "\n\n"
        
        # Build the display
        content = header + nav_line
        
        if pixel_art:
            content += pixel_art + "\n"
        
        # Add abilities
        if abilities:
            content += "\n[bold #FFD700]DIVINE POWERS:[/]\n"
            for ability in abilities[:3]:
                content += f"  [dim #00D4FF]{ability}[/]\n"
        
        # Add a random quote
        if quotes:
            quote = random.choice(quotes)
            content += f"\n[italic dim #555577]\"{quote}\"[/]\n"
        
        return content
    
    def next_god(self) -> None:
        """Cycle to next god."""
        if self.gods:
            self.selected_god = (self.selected_god + 1) % len(self.gods)
    
    def prev_god(self) -> None:
        """Cycle to previous god."""
        if self.gods:
            self.selected_god = (self.selected_god - 1) % len(self.gods)


class SessionNotesViewer(Static):
    """Live session notes viewer showing important observations from current session.
    
    Displays:
    - Recent turns with user prompts and key observations
    - Tools used and files modified
    - Errors encountered
    - Key decisions made
    """
    
    notes_data: reactive[dict] = reactive(dict, always_update=True)
    
    def render(self) -> str:
        header = "[bold #FFD700]◈ DIVINE CHRONICLE — Session Notes[/]\n"
        header += "[dim #555577]" + "─" * 72 + "[/]\n"
        
        if not self.notes_data or not self.notes_data.get("turns"):
            session_id = self.notes_data.get("session_id", "")
            if session_id:
                return header + f"\n  [dim #555577]📜 Session: {session_id[:20]}...[/]\n  [dim #555577]No turns recorded yet. Awaiting divine action...[/]"
            return header + "\n  [dim #555577]📜 No active session. Start a conversation to see notes.[/]"
        
        session_id = self.notes_data.get("session_id", "unknown")
        model = self.notes_data.get("model", "")
        turns = self.notes_data.get("turns", [])
        
        lines = []
        
        # Session header
        lines.append(f"  [bold #00D4FF]SESSION:[/] [dim #555577]{session_id[:30]}...[/]")
        if model:
            lines.append(f"  [bold #00D4FF]MODEL:[/] [dim #555577]{model}[/]")
        lines.append("")
        
        # Show recent turns (last 5)
        recent_turns = turns[-5:] if len(turns) > 5 else turns
        
        for turn in recent_turns:
            turn_num = turn.get("turn", 0)
            timestamp = turn.get("timestamp", "")
            user_msg = turn.get("user", "")[:60]
            if len(turn.get("user", "")) > 60:
                user_msg += "..."
            
            # Turn header
            lines.append(f"  [bold #FFD700]TURN {turn_num}[/] [dim #555577]| {timestamp}[/]")
            lines.append(f"    [#E0F7FF]💬 {user_msg}[/]")
            
            # Tools used
            tools = turn.get("tools", [])
            if tools:
                tool_str = ", ".join(tools[:4])
                if len(tools) > 4:
                    tool_str += f" +{len(tools) - 4}"
                lines.append(f"    [#00D4FF]⚡ {tool_str}[/]")
            
            # Files modified
            files = turn.get("files_modified", [])
            if files:
                for f in files[:2]:
                    short_path = f.split("/")[-1] if "/" in f else f
                    lines.append(f"    [#00FF99]📝 {short_path}[/]")
                if len(files) > 2:
                    lines.append(f"    [dim #555577]+{len(files) - 2} more files[/]")
            
            # Errors
            errors = turn.get("errors", [])
            if errors:
                for err in errors[:1]:
                    err_short = err[:40] + "..." if len(err) > 40 else err
                    lines.append(f"    [#FF4444]⚠ {err_short}[/]")
            
            # Key observations
            observations = turn.get("observations", [])
            if observations:
                for obs in observations[:2]:
                    obs_short = obs[:45] + "..." if len(obs) > 45 else obs
                    lines.append(f"    [#9B59B6]• {obs_short}[/]")
            
            # Response preview
            response = turn.get("response", "")[:50]
            if response:
                if len(turn.get("response", "")) > 50:
                    response += "..."
                lines.append(f"    [dim #555577]→ {response}[/]")
            
            lines.append("")
        
        # Stats footer
        total_turns = len(turns)
        total_tools = sum(len(t.get("tools", [])) for t in turns)
        total_files = len(set(f for t in turns for f in t.get("files_modified", [])))
        
        lines.append("[dim #555577]" + "─" * 72 + "[/]")
        lines.append(f"  [dim #555577]📊 {total_turns} turns | {total_tools} tool calls | {total_files} files modified[/]")
        
        return header + "\n".join(lines)


class FleetObserver(Static):
    """Live subagent/god activity monitor with full observability.
    
    Shows:
    - Active subagents with status, progress bars, and current tool
    - Thinking snippets from each god
    - Tool call history with timing
    - Real-time progress updates from FleetMonitor
    """
    
    fleet_data: reactive[dict] = reactive(dict, always_update=True)
    
    def render(self) -> str:
        header = "[bold #FFD700]◈ DIVINE FLEET OBSERVER — Live Subagent Activity[/]\n"
        header += "[dim #555577]" + "─" * 72 + "[/]\n"
        
        if not self.fleet_data or not self.fleet_data.get("agents"):
            return header + "\n  [dim #555577]⚡ No active subagents. Hermes awaits your command.[/]"
        
        agents = self.fleet_data.get("agents", {})
        task = self.fleet_data.get("task", "")
        elapsed = self.fleet_data.get("elapsed", 0)
        
        lines = []
        
        # Task header
        if task:
            task_short = task[:60] + "..." if len(task) > 60 else task
            mins, secs = divmod(int(elapsed), 60)
            lines.append(f"  [bold #00D4FF]TASK:[/] [#E0F7FF]{task_short}[/]  [dim #555577]⏱ {mins}:{secs:02d}[/]\n")
        
        # Sort: active agents first, then by name
        active_statuses = ("spawning", "thinking", "querying", "processing")
        sorted_agents = sorted(
            agents.items(),
            key=lambda x: (0 if x[1].get("status") in active_statuses else 1, x[0])
        )
        
        god_colors = {
            "Hermes": "#FFD700", "Athena": "#C0C0C0", "Apollo": "#FFE066",
            "Ares": "#DC143C", "Zeus": "#F0F0FF", "Hephaestus": "#FF8C00",
            "Artemis": "#32CD32", "Poseidon": "#1E90FF", "Hades": "#9B59B6",
            "Dionysus": "#FF00FF",
        }
        
        status_icons = {
            "idle": "○", "spawning": "◐", "thinking": "◑", "querying": "◒",
            "processing": "◓", "responding": "◔", "complete": "●", "failed": "✗",
        }
        
        for name, agent in sorted_agents:
            if name == "Hermes":
                continue  # Skip orchestrator, show subagents only
            
            color = god_colors.get(name, "#FFD700")
            status = agent.get("status", "idle")
            status_icon = status_icons.get(status, "◈")
            
            # Status color
            if status in ("thinking", "querying", "processing", "spawning"):
                status_color = "#00FF99"
            elif status == "complete":
                status_color = "#00D4FF"
            elif status == "failed":
                status_color = "#FF4444"
            else:
                status_color = "#555577"
            
            # Progress bar
            progress = agent.get("progress_pct", 0)
            step = agent.get("step", 0)
            max_iter = agent.get("max_iterations", 50)
            bar_len = 20
            filled = int(progress / 100 * bar_len)
            bar = "█" * filled + "░" * (bar_len - filled)
            
            # Current tool
            current_tool = agent.get("current_tool", "")
            tool_preview = agent.get("tool_preview", "")
            
            # Agent header line
            lines.append(
                f"  [{status_color}]{status_icon}[/] [bold {color}]{name:<12}[/]  "
                f"[{status_color}]{bar}[/] [{status_color}]{progress:>3.0f}%[/]  "
                f"[dim #555577]{step}/{max_iter} calls[/]"
            )
            
            # Goal (if available)
            goal = agent.get("goal", "")
            if goal:
                goal_short = goal[:50] + "..." if len(goal) > 50 else goal
                lines.append(f"     [dim #00A8CC]⚡ {goal_short}[/]")
            
            # Current tool (if active)
            if current_tool and status in ("querying", "processing"):
                tool_line = f"     [#00D4FF]→ {current_tool}[/]"
                if tool_preview:
                    preview_short = tool_preview[:35] + "..." if len(tool_preview) > 35 else tool_preview
                    tool_line += f"  [dim #555577]{preview_short}[/]"
                lines.append(tool_line)
            
            # Thinking snippet (if available)
            thinking = agent.get("thinking_snippet", "")
            if thinking and status == "thinking":
                think_short = thinking[:55] + "..." if len(thinking) > 55 else thinking
                lines.append(f"     [dim #9B59B6]💭 {think_short}[/]")
            
            # Recent tool history
            tool_history = agent.get("tool_history", [])
            if tool_history:
                recent = tool_history[-3:]  # Last 3 tools
                history_parts = []
                for t in recent:
                    t_name = t.get("name", "?")[:8]
                    t_dur = t.get("duration", 0)
                    t_status = t.get("status", "ok")
                    t_color = "#00FF99" if t_status == "success" else "#FF4444" if t_status == "error" else "#555577"
                    history_parts.append(f"[{t_color}]{t_name}[/][dim #555577]({t_dur:.1f}s)[/]")
                lines.append(f"     [dim #555577]history:[/] " + " → ".join(history_parts))
            
            lines.append("")  # Spacer between agents
        
        # Events feed
        events = self.fleet_data.get("events", [])
        if events:
            lines.append("[dim #555577]" + "─" * 72 + "[/]")
            lines.append("[bold #C9A227]◈ RECENT EVENTS[/]")
            for evt in events[-5:]:
                lines.append(f"  [dim #555577]{evt}[/]")
        
        return header + "\n".join(lines)


class AssemblyView(ScrollableContainer):
    """The Assembly — OLYMPUS ASCENDED main dashboard view.
    
    Features:
    - Cinematic animated hero art with Hermes pixel art
    - Divine execution flow diagram showing god routing
    - Quick model status with LM Studio / OpenRouter indicator
    - God Stats Leaderboard with rankings
    - Compact pantheon strip with status indicators
    - God Gallery with epic braille pixel art portraits
    - Live execution lanes with real tool call data
    - Activity dashboard with heatmap and sparklines
    - Divine notifications (oracle messages)
    - Cost tracker (Drachmai treasury)
    - Recent sessions (decrees)
    - Divine achievements (badges of honor)
    """
    
    _animation_timer = None
    _gallery_timer = None
    _fleet_timer = None
    _notes_timer = None
    
    def compose(self) -> ComposeResult:
        yield HeroArt(id="hero-art", classes="hero-art")
        yield ModelStatus(id="model-status", classes="bento-gold")
        yield QuickStats(id="quick-stats", classes="bento-gold")
        yield FleetObserver(id="fleet-observer", classes="divine-panel-gold")
        yield DivineFlowDiagram(id="flow-diagram", classes="divine-panel")
        yield PantheonStrip(id="pantheon-strip", classes="divine-panel")
        with Horizontal(classes="bento-row"):
            yield GodLeaderboard(id="god-leaderboard", classes="divine-panel-gold")
            yield GodGallery(id="god-gallery", classes="divine-panel-gold")
        with Horizontal(classes="bento-row"):
            yield ExecutionLanes(id="exec-lanes", classes="divine-panel")
            yield ActivityDashboard(id="activity-dashboard", classes="divine-panel")
        with Horizontal(classes="bento-row"):
            yield RecentSessions(id="recent-sessions", classes="divine-panel")
            with Vertical():
                yield CostTracker(id="cost-tracker", classes="divine-panel-gold")
                yield DivineAchievements(id="achievements", classes="divine-panel")
        yield SessionNotesViewer(id="session-notes", classes="divine-panel-gold")
        yield DivineNotifications(id="notifications", classes="divine-panel")
    
    @work(thread=True)
    def load_data(self) -> None:
        """Load all dashboard data from the data layer."""
        from hermes_cli.dashboard.data import (
            get_recent_sessions, get_usage_stats,
            get_skin_pantheon,
            get_execution_lane_stats, get_pantheon_activity,
            get_recent_notifications, get_cost_breakdown,
            get_daily_activity, get_active_model_info, get_lmstudio_models,
            get_gods_with_pixel_art,
        )
        
        sessions = get_recent_sessions(limit=8)
        stats = get_usage_stats()
        pantheon = get_skin_pantheon()
        lanes = get_execution_lane_stats()
        activity = get_pantheon_activity()
        notifications = get_recent_notifications(limit=6)
        costs = get_cost_breakdown(days=30)
        daily = get_daily_activity(days=14)
        
        model_info = get_active_model_info()
        lms_models = get_lmstudio_models(DEFAULT_LMSTUDIO_URL)
        lms_status = "online" if lms_models else "offline"
        
        gods_with_art = get_gods_with_pixel_art()
        
        # Get live fleet data from FleetMonitor
        fleet_data = {}
        try:
            from agent.fleet_monitor import get_fleet_monitor
            fm = get_fleet_monitor()
            fleet_data = fm.get_fleet_snapshot()
        except Exception:
            pass
        
        # Get session notes data
        session_notes_data = self._load_session_notes()
        
        self.app.call_from_thread(
            self._apply_data, 
            sessions, stats, pantheon, 
            lanes, activity, notifications, costs, daily,
            model_info, lms_status, gods_with_art, fleet_data, session_notes_data
        )
    
    def _load_session_notes(self) -> dict:
        """Load the most recent session notes file."""
        try:
            from hermes_constants import get_hermes_home
            from pathlib import Path
            import re
            
            sessions_dir = get_hermes_home() / "sessions"
            if not sessions_dir.exists():
                return {}
            
            # Find the most recent notes file
            notes_files = sorted(sessions_dir.glob("notes_*.txt"), key=lambda p: p.stat().st_mtime, reverse=True)
            if not notes_files:
                return {}
            
            latest_notes = notes_files[0]
            content = latest_notes.read_text(encoding="utf-8")
            
            # Parse the notes file
            session_id = ""
            model = ""
            turns = []
            
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
                if not turn_match:
                    continue
                
                turn_num = int(turn_match.group(1))
                timestamp = turn_match.group(2)
                
                # Extract user message
                user_match = re.search(r"USER: (.+?)(?:\n|$)", block)
                user_msg = user_match.group(1).strip() if user_match else ""
                
                # Extract tools
                tools = []
                tool_matches = re.findall(r"→ (\w+)", block)
                tools = tool_matches[:6]  # Limit to 6
                
                # Extract files modified
                files_modified = []
                file_matches = re.findall(r"• (.+\.(?:py|js|ts|yaml|json|md|txt))", block)
                files_modified = file_matches[:5]
                
                # Extract errors
                errors = []
                error_matches = re.findall(r"⚠ (.+?)(?:\n|$)", block)
                errors = error_matches[:2]
                
                # Extract observations
                observations = []
                obs_matches = re.findall(r"\[(?:Finding|Decision|Fixed|Created)\] (.+?)(?:\n|$)", block)
                observations = obs_matches[:3]
                
                # Extract response
                response_match = re.search(r"RESPONSE: (.+?)(?:\n|$)", block)
                response = response_match.group(1).strip() if response_match else ""
                
                turns.append({
                    "turn": turn_num,
                    "timestamp": timestamp,
                    "user": user_msg,
                    "tools": tools,
                    "files_modified": files_modified,
                    "errors": errors,
                    "observations": observations,
                    "response": response,
                })
            
            return {
                "session_id": session_id,
                "model": model,
                "turns": turns,
            }
        except Exception:
            return {}
    
    def _apply_data(self, sessions, stats, pantheon, lanes, activity, notifications, costs, daily, model_info, lms_status, gods_with_art, fleet_data=None, session_notes_data=None):
        """Apply loaded data to widgets."""
        self.query_one("#recent-sessions", RecentSessions).sessions = sessions
        self.query_one("#quick-stats", QuickStats).stats = stats
        
        model_widget = self.query_one("#model-status", ModelStatus)
        model_widget.model_info = model_info
        model_widget.lms_status = lms_status
        
        if pantheon:
            strip = self.query_one("#pantheon-strip", PantheonStrip)
            strip.gods = pantheon
            strip.activity = activity
        
        leaderboard = self.query_one("#god-leaderboard", GodLeaderboard)
        leaderboard.activity = activity
        
        self.query_one("#exec-lanes", ExecutionLanes).lanes = lanes
        self.query_one("#notifications", DivineNotifications).notifications = notifications
        self.query_one("#cost-tracker", CostTracker).costs = costs
        
        self.query_one("#activity-dashboard", ActivityDashboard).daily_data = daily
        
        self.query_one("#achievements", DivineAchievements).stats = stats
        
        if gods_with_art:
            gallery = self.query_one("#god-gallery", GodGallery)
            gallery.gods = gods_with_art
        
        # Update fleet observer with live subagent data
        if fleet_data:
            self.query_one("#fleet-observer", FleetObserver).fleet_data = fleet_data
        
        # Update session notes viewer
        if session_notes_data:
            self.query_one("#session-notes", SessionNotesViewer).notes_data = session_notes_data
    
    def on_show(self) -> None:
        """Called when the view is shown."""
        self.load_data()
        self._start_animation()
    
    def on_hide(self) -> None:
        """Called when the view is hidden."""
        self._stop_animation()
    
    def _start_animation(self) -> None:
        """Start the hero art, gallery, fleet observer, and session notes timers."""
        if self._animation_timer is None:
            self._animation_timer = self.set_interval(2.5, self._animate_hero)
        if self._gallery_timer is None:
            self._gallery_timer = self.set_interval(5.0, self._cycle_gallery)
        if self._fleet_timer is None:
            self._fleet_timer = self.set_interval(1.0, self._refresh_fleet)
        if self._notes_timer is None:
            self._notes_timer = self.set_interval(3.0, self._refresh_notes)
    
    def _stop_animation(self) -> None:
        """Stop all animation timers."""
        if self._animation_timer is not None:
            self._animation_timer.stop()
            self._animation_timer = None
        if self._gallery_timer is not None:
            self._gallery_timer.stop()
            self._gallery_timer = None
        if self._fleet_timer is not None:
            self._fleet_timer.stop()
            self._fleet_timer = None
        if self._notes_timer is not None:
            self._notes_timer.stop()
            self._notes_timer = None
    
    def _animate_hero(self) -> None:
        """Cycle the hero art frame."""
        try:
            hero = self.query_one("#hero-art", HeroArt)
            hero.cycle_frame()
        except Exception:
            pass
    
    def _cycle_gallery(self) -> None:
        """Cycle the god gallery to next god."""
        try:
            gallery = self.query_one("#god-gallery", GodGallery)
            gallery.next_god()
        except Exception:
            pass
    
    def _refresh_fleet(self) -> None:
        """Refresh the fleet observer with live subagent data."""
        try:
            from agent.fleet_monitor import get_fleet_monitor
            fm = get_fleet_monitor()
            fleet_data = fm.get_fleet_snapshot()
            self.query_one("#fleet-observer", FleetObserver).fleet_data = fleet_data
        except Exception:
            pass
    
    def _refresh_notes(self) -> None:
        """Refresh the session notes viewer with latest data."""
        try:
            session_notes_data = self._load_session_notes()
            if session_notes_data:
                self.query_one("#session-notes", SessionNotesViewer).notes_data = session_notes_data
        except Exception:
            pass
