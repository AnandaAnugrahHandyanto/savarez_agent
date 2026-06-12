---
name: ubuntu-premium-zsh-setup
description: Install and configure a premium Zsh terminal experience on Ubuntu with Oh My Zsh, powerlevel10k, autosuggestions, syntax highlighting, fzf, fzf-tab, zoxide, direnv, eza, bat, fd, tmux, and GNOME Terminal Nerd Font settings.
---

# Ubuntu premium Zsh setup

Use this skill when:
- the user wants the best practical terminal experience on Ubuntu
- you need to install Zsh and make it the default shell
- you want a modern shell UX with fuzzy search, autosuggestions, syntax highlighting, and a polished prompt

## Goal

Set up a high-quality Ubuntu terminal workflow with:
- `zsh`
- Oh My Zsh
- `powerlevel10k`
- `zsh-autosuggestions`
- `zsh-syntax-highlighting`
- `fzf`
- `fzf-tab`
- `zoxide`
- `direnv`
- `eza`, `bat`, `fd-find`, `tmux`, `tree`
- GNOME Terminal configured to use Meslo Nerd Font for prompt icons

## Prerequisites

- Ubuntu desktop system
- network access
- sudo access
- local secrets file may contain `SUDO_PASSWORD` at:
  - `~/.config/mizuki/secrets.env`
- user has approved non-destructive package installation and shell changes

## Install packages

Use sudo to install base packages:

```bash
apt-get update
apt-get install -y zsh fzf zsh-autosuggestions zsh-syntax-highlighting \
  eza bat fd-find zoxide direnv tmux tree git curl
```

Notes:
- Ubuntu package name is `fd-find`, but command is `fdfind`
- Ubuntu package name is `bat`, but command is often `batcat`
- `zsh-completions` may not exist in this environment; skip it if apt cannot find it

## Install Oh My Zsh

Clone directly instead of using the interactive installer:

```bash
git clone https://github.com/ohmyzsh/ohmyzsh.git ~/.oh-my-zsh
```

If the directory already exists, leave it in place.

## Install fzf-tab plugin

```bash
git clone https://github.com/Aloxaf/fzf-tab ~/.oh-my-zsh/custom/plugins/fzf-tab
```

If already present, skip.

## Install powerlevel10k theme

```bash
git clone --depth=1 https://github.com/romkatv/powerlevel10k.git \
  ~/.oh-my-zsh/custom/themes/powerlevel10k
```

## Install Meslo Nerd Font locally

Create local font directory and download these files from:
- `https://github.com/romkatv/powerlevel10k-media/raw/master/`

Files:
- `MesloLGS NF Regular.ttf`
- `MesloLGS NF Bold.ttf`
- `MesloLGS NF Italic.ttf`
- `MesloLGS NF Bold Italic.ttf`

Then refresh font cache:

```bash
fc-cache -f ~/.local/share/fonts/MesloLGS-NF
```

Verify with:

```bash
fc-list | grep -F 'MesloLGS NF' | head
```

## Configure GNOME Terminal font

This applies when GNOME Terminal settings are available.

### Discover default profile

```bash
gsettings get org.gnome.Terminal.ProfilesList default
```

### Apply font settings

For profile ID like `b1dcc9dd-5262-4d8d-a863-c897e6d979b9`, set:

```bash
gsettings set org.gnome.Terminal.Legacy.Profile:/org/gnome/terminal/legacy/profiles:/:<PROFILE>/ use-system-font false
gsettings set org.gnome.Terminal.Legacy.Profile:/org/gnome/terminal/legacy/profiles:/:<PROFILE>/ font 'MesloLGS NF 12'
```

Verify with:

```bash
gsettings get org.gnome.Terminal.Legacy.Profile:/org/gnome/terminal/legacy/profiles:/:<PROFILE>/ use-system-font
gsettings get org.gnome.Terminal.Legacy.Profile:/org/gnome/terminal/legacy/profiles:/:<PROFILE>/ font
```

If `gsettings` keys do not exist, the user may be using a different terminal emulator.

## Set Zsh as default shell

Discover zsh path:

```bash
command -v zsh
```

Set login shell:

```bash
sudo usermod -s /usr/bin/zsh "$USER"
```

Verify:

```bash
getent passwd "$USER" | cut -d: -f1,7
```

### GNOME Terminal fallback when new windows still open bash

In this environment, it was possible for `getent passwd` to show `/usr/bin/zsh` while new GNOME Terminal windows still launched `bash`.

A reliable fix was to set the GNOME Terminal profile to use `zsh` explicitly as its command.

1. Discover the default profile:

```bash
gsettings get org.gnome.Terminal.ProfilesList default
```

2. For profile ID like `<PROFILE>`, set:

```bash
gsettings set org.gnome.Terminal.Legacy.Profile:/org/gnome/terminal/legacy/profiles:/:<PROFILE>/ use-custom-command true
gsettings set org.gnome.Terminal.Legacy.Profile:/org/gnome/terminal/legacy/profiles:/:<PROFILE>/ custom-command '/usr/bin/zsh'
gsettings set org.gnome.Terminal.Legacy.Profile:/org/gnome/terminal/legacy/profiles:/:<PROFILE>/ login-shell false
```

3. Restart GNOME Terminal server if needed:

```bash
pkill -f gnome-terminal-server || true
```

4. Reopen GNOME Terminal and verify the child shell process is `zsh`.

This fallback should be included in the workflow because changing the login shell alone may not affect GNOME Terminal on some Ubuntu setups.

## Write ~/.zprofile

Use this simple login-shell bridge:

```zsh
# Managed by Mizuki
[[ -f "$HOME/.profile" ]] && source "$HOME/.profile"
```

## Write ~/.tmux.conf

Recommended minimal config:

```tmux
set -g mouse on
set -g history-limit 100000
set -g base-index 1
setw -g pane-base-index 1
set -g renumber-windows on
set -g default-terminal "screen-256color"
set -g status-keys vi
setw -g mode-keys vi
bind r source-file ~/.tmux.conf \; display-message "tmux config reloaded"
```

## Write ~/.config/bat/config

```text
--theme="TwoDark"
--style="numbers,changes,header"
--paging=never
```

## Write ~/.p10k.zsh

Use a clean, informative powerlevel10k config with:
- `POWERLEVEL9K_MODE='nerdfont-complete'`
- left prompt: `dir vcs newline prompt_char`
- right prompt: `status command_execution_time background_jobs history time`
- `truncate_to_unique` directory shortening
- short time format like `%H:%M`
- prompt chars `❯` and `❮`

Keep it lightweight and practical instead of maximalist.

## Write ~/.zshrc

### Key requirements

Top of file should include instant prompt for powerlevel10k:

```zsh
if [[ -r "${XDG_CACHE_HOME:-$HOME/.cache}/p10k-instant-prompt-${(%):-%n}.zsh" ]]; then
  source "${XDG_CACHE_HOME:-$HOME/.cache}/p10k-instant-prompt-${(%):-%n}.zsh"
fi
```

Then configure:
- `ZSH="$HOME/.oh-my-zsh"`
- `ZSH_THEME="powerlevel10k/powerlevel10k"`
- disable Oh My Zsh auto-update
- large history sizes
- history dedupe options
- `AUTO_CD`, `AUTO_PUSHD`, `PUSHD_IGNORE_DUPS`, `NO_BEEP`, `PROMPT_SUBST`
- completion cache under `~/.cache/zsh/.zcompcache`
- fzf defaults using `fdfind`

Plugins:

```zsh
plugins=(
  git
  sudo
  history-substring-search
  fzf-tab
)
```

After `source "$ZSH/oh-my-zsh.sh"`, initialize:

```zsh
eval "$(zoxide init zsh)"
eval "$(direnv hook zsh)"
```

Source fzf package integration only in real interactive shells to avoid ZLE warnings during scripted checks:

```zsh
if [[ -o interactive ]] && [[ -z "${ZSH_EXECUTION_STRING:-}" ]]; then
  [[ -f /usr/share/doc/fzf/examples/completion.zsh ]] && source /usr/share/doc/fzf/examples/completion.zsh
  [[ -f /usr/share/doc/fzf/examples/key-bindings.zsh ]] && source /usr/share/doc/fzf/examples/key-bindings.zsh
fi
```

Source plugin files:

```zsh
[[ -f /usr/share/zsh-autosuggestions/zsh-autosuggestions.zsh ]] && source /usr/share/zsh-autosuggestions/zsh-autosuggestions.zsh
[[ -f /usr/share/zsh-syntax-highlighting/zsh-syntax-highlighting.zsh ]] && source /usr/share/zsh-syntax-highlighting/zsh-syntax-highlighting.zsh
```

Autosuggestion settings:

```zsh
ZSH_AUTOSUGGEST_STRATEGY=(history completion)
ZSH_AUTOSUGGEST_HIGHLIGHT_STYLE='fg=8'
```

History substring search bindings:

```zsh
bindkey '^[[A' history-substring-search-up
bindkey '^[[B' history-substring-search-down
```

Useful `fzf-tab` styles:

```zsh
zstyle ':fzf-tab:*' fzf-command fzf
zstyle ':fzf-tab:*' switch-group ',' '.'
zstyle ':fzf-tab:*' use-fzf-default-opts yes
zstyle ':fzf-tab:complete:cd:*' fzf-preview 'eza --tree --level=2 --color=always $realpath 2>/dev/null || tree -C -L 2 $realpath 2>/dev/null || ls -la $realpath'
zstyle ':fzf-tab:complete:__zoxide_z:*' fzf-preview 'eza --tree --level=2 --color=always $realpath 2>/dev/null || tree -C -L 2 $realpath 2>/dev/null || ls -la $realpath'
zstyle ':fzf-tab:complete:(cat|bat|batcat):*' fzf-preview 'batcat --color=always --style=plain $realpath 2>/dev/null || sed -n "1,200p" $realpath 2>/dev/null'
```

Recommended aliases:

```zsh
alias ls='eza --group-directories-first --icons=auto'
alias ll='eza -lah --group-directories-first --git --icons=auto'
alias la='eza -lah --all --group-directories-first --icons=auto'
alias lt='eza --tree --level=2 --icons=auto'
alias cat='batcat --paging=never --style=plain'
alias find='fdfind'
alias grep='rg'
alias ..='cd ..'
alias ...='cd ../..'
alias ....='cd ../../..'
alias c='clear'
alias reload='exec zsh'
alias h='history 1'
alias j='z'
alias mkdir='mkdir -pv'
alias path='echo -e ${PATH//:/\\n}'
alias tf='terraform'
alias k='kubectl'

alias g='git'
alias gs='git status -sb'
alias ga='git add'
alias gc='git commit'
alias gco='git checkout'
alias gsw='git switch'
alias gl='git log --oneline --graph --decorate --all'
alias gp='git push'
alias gpl='git pull --rebase'
```

Optionally add command-name aliases if Ubuntu package names differ:

```zsh
if command -v batcat >/dev/null 2>&1 && ! command -v bat >/dev/null 2>&1; then
  alias bat='batcat'
fi
if command -v fdfind >/dev/null 2>&1 && ! command -v fd >/dev/null 2>&1; then
  alias fd='fdfind'
fi
```

Load prompt config before syntax highlighting:

```zsh
[[ -f ~/.p10k.zsh ]] && source ~/.p10k.zsh
```

## Backup existing config first

Before replacing shell config, back up the current file:

```bash
cp ~/.zshrc ~/.zshrc.backup-$(date +%Y%m%d-%H%M%S)
```

## Verification checklist

### Package and shell checks

```bash
zsh --version
fzf --version
getent passwd "$USER" | cut -d: -f1,7
```

### File existence checks

Verify:
- `~/.oh-my-zsh`
- `~/.oh-my-zsh/custom/plugins/fzf-tab`
- `~/.oh-my-zsh/custom/themes/powerlevel10k`
- `~/.p10k.zsh`

### Non-interactive Zsh checks

```bash
zsh -i -c 'echo THEME:$ZSH_THEME; [[ -f ~/.p10k.zsh ]] && echo P10K_FILE_OK'
zsh -i -c '[[ -n ${functions[_zsh_autosuggest_start]+x} ]] && echo AUTOSUGGEST_OK'
zsh -i -c '[[ -n ${functions[_zsh_highlight]+x} ]] && echo SYNTAX_OK'
zsh -i -c '[[ -n ${functions[_ftb__main_complete]+x} || -n ${functions[_ftb-complete]+x} ]] && echo FZF_TAB_OK'
```

### Interactive key-binding checks

In a PTY-backed `zsh -i` session, verify:

```zsh
bindkey '^R'
bindkey '^T'
bindkey '^[[A'
bindkey '^[[B'
```

Expected:
- `^R` → `fzf-history-widget`
- `^T` → `fzf-file-widget`
- arrows → `history-substring-search-up/down`

### Font checks

```bash
fc-list | grep -F 'MesloLGS NF' | head
```

If using GNOME Terminal:
- `use-system-font` should be `false`
- `font` should be `MesloLGS NF 12`

## Final step for user

Tell the user to either:

```bash
exec zsh
```

or close and reopen the terminal.

GNOME Terminal may need a full reopen to display the new font and prompt icons correctly.

## Pitfalls

- `write_file`/`patch` may refuse protected dotfiles like `~/.zshrc`; use Python via `terminal` if necessary.
- `fzf` key bindings may not show up in `zsh -i -c` checks because they depend on real interactive ZLE context; verify in a PTY session.
- Loading fzf key-bindings during `zsh -c` scripted checks can emit `can't change option: zle`; guard on `ZSH_EXECUTION_STRING`.
- GNOME Terminal font changes only apply to GNOME Terminal profiles, not every terminal emulator.
- Keep the powerlevel10k config practical; avoid huge configs unless the user asks.
