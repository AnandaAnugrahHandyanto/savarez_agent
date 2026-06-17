# Plano de Branding CEODigital — Hermes Agent Fork

**Data:** 2026-06-17  
**Repositório:** `paulojmorais/hermes-agent` (fork de `NousResearch/hermes-agent`)  
**Objetivo:** Distribuição branded do Hermes Agent com:

1. Instalador próprio no site CEODigital
2. Deteção automática pelo Connector existente
3. Configurações limitadas
4. Sync com upstream

---

## Arquitetura de Integração Connector ↔ Hermes

O connector CEODigital já detecta e usa o Hermes localmente:

```
┌─────────────────────────────────────────────────────────────────┐
│                   Connector (Go daemon + Companion App)          │
│                                                                  │
│  findHermesBinary()                 hermes_wrapper.py            │
│  ├─ ~/.local/bin/hermes             ├─ pip show hermes-agent     │
│  ├─ PATH: hermes                    ├─ ~/.hermes/hermes-agent/   │
│  └─ /usr/local/bin/hermes           └─ sys.path                  │
│           │                              │                       │
│           ▼                              ▼                       │
│  probeHermesForSidecar()           import run_agent              │
│  ├─ hermes --version               run_agent.main(query, ...)    │
│  └─ hermes_status: {                                             │
│       installed: true,                                           │
│       path: "~/.local/bin/hermes",                              │
│       version: "ceodigital-agent v2026.6.17"                    │
│     }                                                            │
└─────────────────────────────────────────────────────────────────┘
```

**Ponto crítico:** o instalador tem de colocar o binário `hermes` nos mesmos paths
e registar o package Python para que `pip show hermes-agent` funcione (ou
adaptar o wrapper). O connector não precisa de ser alterado — só precisa de
encontrar o binário.

---

## Wave 0 — Clonar o Fork e Setup

### 0.1 — Clonar
```bash
cd ~/dev
git clone https://github.com/paulojmorais/hermes-agent.git
cd hermes-agent
git remote add upstream https://github.com/NousResearch/hermes-agent.git
git fetch upstream
```

### 0.2 — Branch inicial
```bash
git checkout -b ceodigital-branding
```

---

## Wave 1 — Instalador no Site CEODigital

### Objetivo
`curl -fsSL https://hermes.ceodigital.pt/install.sh | bash` clona do teu fork.

### 1.1 — Alterar URLs no install.sh
**Ficheiro:** `scripts/install.sh`

| Linha | Alteração |
|-------|-----------|
| 47 | `REPO_URL_HTTPS="https://github.com/paulojmorais/hermes-agent.git"` |
| 46 | `REPO_URL_SSH="git@github.com:paulojmorais/hermes-agent.git"` |
| 9 | Comentário: URL do site → `hermes.ceodigital.pt` |
| 473 | Windows install.ps1 URL → `hermes.ceodigital.pt` |

### 1.2 — Alterar URLs no install.ps1 e install.cmd
Mesmo padrão — todas as referências a `NousResearch/hermes-agent` → `paulojmorais/hermes-agent`.

### 1.3 — Servir o instalador

**Opção — GitHub Raw (mais simples, grátis):**
```bash
# O instalador fica disponível em:
curl -fsSL https://raw.githubusercontent.com/paulojmorais/hermes-agent/main/scripts/install.sh | bash
```

**Com domínio próprio (nginx ou Cloudflare):**
```nginx
# nginx — proxy reverso para o raw GitHub
location = /install.sh {
    proxy_pass https://raw.githubusercontent.com/paulojmorais/hermes-agent/main/scripts/install.sh;
}
location = /install.ps1 {
    proxy_pass https://raw.githubusercontent.com/paulojmorais/hermes-agent/main/scripts/install.ps1;
}
```

### 1.4 — Verificação
```bash
# O install.sh deve mostrar o header com REPO_URL_HTTPS apontando para o fork
curl -fsSL https://raw.githubusercontent.com/paulojmorais/hermes-agent/main/scripts/install.sh | head -50
```

---

## Wave 2 — Branding Core (CLI + Identidade)

### 2.1 — Skin default CEODigital
**Ficheiro:** `hermes_cli/skin_engine.py` (linhas 165-198)

```python
"default": {
    "name": "default",
    "description": "CEODigital Agent",
    "colors": {
        # Manter paleta actual ou ajustar para cores CEODigital
        # ...
    },
    "branding": {
        "agent_name": "CEODigital Agent",
        "welcome": "Welcome to CEODigital Agent! Type /help for commands.",
        "goodbye": "Goodbye! 🚀",
        "response_label": " ⚡ CEODigital ",
        "prompt_symbol": "❯",
        "help_header": "Available Commands",
    },
    "tool_prefix": "┊",
},
```

### 2.2 — Identidade SOUL.md
**Ficheiro:** `hermes_cli/default_soul.py`

```python
DEFAULT_SOUL_MD = (
    "You are CEODigital Agent, an AI assistant created by CEODigital. "
    "You are helpful, knowledgeable, and direct. You assist users with a wide "
    "range of tasks including answering questions, writing and editing code, "
    "analyzing information, creative work, and executing actions via your tools. "
    "You communicate clearly, admit uncertainty when appropriate, and prioritize "
    "being genuinely useful over being verbose unless otherwise directed below. "
    "Be targeted and efficient in your exploration and investigations."
)
```

### 2.3 — Metadados do package
**Ficheiro:** `pyproject.toml`
```toml
name = "ceodigital-agent"
version = "0.16.0"  # manter sync com upstream
authors = [{ name = "CEODigital" }]
```

### 2.4 — URLs de serviço e mensagens
| Ficheiro | Linha | Valor |
|----------|-------|-------|
| `hermes_cli/gateway.py` | 1422 | `SERVICE_DESCRIPTION = "CEODigital Agent Gateway"` |
| `hermes_cli/dashboard_auth/login_page.py` | 41,308 | `<title>Sign in — CEODigital Agent</title>` |
| `tools/send_message_tool.py` | 1438 | `msg["Subject"] = "CEODigital Agent"` |
| `tools/mcp_oauth.py` | 675 | `client_name = cfg.get("client_name", "CEODigital Agent")` |
| `gateway/platforms/whatsapp_common.py` | 57 | `DEFAULT_REPLY_PREFIX = "⚡ *CEODigital Agent*\n────────────\n"` |

---

## Wave 3 — Compatibilidade com o Connector

### 3.1 — Manter o binário como `hermes`
**IMPORTANTE:** O connector procura `hermes` (não `ceodigital`). O entry point
no `pyproject.toml` deve manter:
```toml
[project.scripts]
hermes = "hermes_cli.main:main"
```

Isto garante que o binário instalado se chama `hermes` e é encontrado pelo
`findHermesBinary()` sem alterações no connector.

### 3.2 — Compatibilidade do hermes_wrapper.py
O wrapper procura:
1. `pip show hermes-agent` — se mudarmos o nome do package para `ceodigital-agent`, o wrapper não encontra

**Opção A — Manter `hermes-agent` como package name** (recomendado)
- Menos alterações no connector
- `pip show hermes-agent` continua a funcionar

**Opção B — Mudar para `ceodigital-agent` + adaptar wrapper**
- Alterar `hermes_wrapper.py` para procurar `ceodigital-agent`
- Alterar paths conhecidos

**Recomendação:** Opção A para MVP. O package name é interno — o branding visível
vem da skin + SOUL.md + mensagens.

### 3.3 — Versão detectável
A versão deve ser detectável via `hermes --version`:
- O connector chama `hermes --version` para preencher `hermes_status.version`
- O `hermes --version` já funciona (vem do `hermes_cli/main.py`)

---

## Wave 4 — Docker Images

### Ficheiros a alterar
| Ficheiro | Alteração |
|----------|-----------|
| `Dockerfile` | LABEL maintainer, referências |
| `docker-compose.yml` | `image: paulojmorais/ceodigital-agent:latest` |
| `docker-compose.windows.yml` | mesmo |
| `hermes_cli/config.py:438` | `return "docker pull paulojmorais/ceodigital-agent:latest"` |
| `hermes_cli/config.py:476-492` | docstring Docker |

---

## Wave 5 — Limitação de Configurações

### 5.1 — DEFAULT_CONFIG restrito
**Ficheiro:** `hermes_cli/config.py:808`

```python
DEFAULT_CONFIG = {
    "model": "",                       # user deve escolher
    "toolsets": [
        "terminal", "file", "web",
        "safe", "skills", "memory",
        "session_search", "clarify",
        "todo",
    ],
    "disabled_toolsets": [
        "image_gen", "video_gen",
        "discord", "homeassistant",
        "spotify", "browser",
    ],
    "agent": {
        "max_turns": 50,              # reduzido de 90
        "gateway_timeout": 1800,
        "coding_context": "auto",
        "task_completion_guidance": True,
    },
    "security": {
        "redact_secrets": True,
        "allow_private_urls": False,
    },
    "approvals": {
        "mode": "manual",             # sempre confirmar
        "cron_mode": "deny",
    },
    # ... resto do config mantido
}
```

### 5.2 — Providers whitelist
**Ficheiro:** `hermes_cli/providers.py`

Manter apenas: `openrouter`, `openai`, `anthropic`, `deepseek`, `ollama`, `custom`.
Remover ou comentar: `nous`, `huggingface`, `qwen-oauth`, `kimi`, etc.

### 5.3 — Setup wizard minimal
**Ficheiro:** `hermes_cli/setup.py`

Remover steps que expõem providers não suportados.

---

## Wave 6 — Website / Documentação

### Ficheiros a alterar
| Ficheiro | Alteração |
|----------|-----------|
| `website/docusaurus.config.ts` | `title`, `tagline`, `url`, `baseUrl` → CEODigital |
| `website/static/img/` | logo CEODigital |
| `README.md` | Links → teu domínio e fork |

---

## Wave 7 — Mecanismo de Sync com Upstream

### Setup único
```bash
cd ~/dev/paulojmorais/hermes-agent
git remote add upstream https://github.com/NousResearch/hermes-agent.git
git fetch upstream
```

### Workflow por release
```bash
git fetch upstream
git checkout main
git rebase upstream/main
# Resolver conflitos:
#   - scripts/install.sh  → raro (URLs)
#   - pyproject.toml       → name/version
#   - skin_engine.py       → secção "default"
#   - config.py            → DEFAULT_CONFIG
#   - providers.py         → lista de providers
git push origin main --force-with-lease
```

### Ficheiros com maior probabilidade de conflito
| Ficheiro | Risco | Estratégia |
|----------|-------|-----------|
| `scripts/install.sh` | **Baixo** | Mudanças são nas primeiras linhas; upstream raramente mexe |
| `pyproject.toml` | **Médio** | Conflito no `name` + `authors`; manter resto do upstream |
| `skin_engine.py` | **Baixo** | Upstream adiciona skins novos, não mexe no "default" |
| `config.py` | **Médio** | DEFAULT_CONFIG muda ocasionalmente; merge com cuidado |
| `providers.py` | **Médio** | Upstream adiciona providers; aceitar novos mas não os expor |
| `i18n/web files` | **Alto** | **Não alterar** no MVP — strings "Hermes" no UI web são aceitáveis |

---

## Resumo de Esforço

| Wave | O quê | Ficheiros | Tempo |
|------|-------|-----------|-------|
| 0 | Clone + setup | — | 15min |
| 1 | Instalador | 3 | 30min |
| 2 | Branding core | 8 | 1h30 |
| 3 | Compatibilidade connector | 1-2 | 30min |
| 4 | Docker | 5 | 30min |
| 5 | Limitações | 3 | 1h |
| 6 | Website | 5 | 2h |
| 7 | Sync workflow | — | setup único |

**Total MVP (Waves 0-5): ~4h** — tens instalador branded, connector-compatible, e configurações limitadas.

---

## Próximo passo

Avançar com Wave 0 + Wave 1: clonar o fork, alterar install.sh, e testar.
