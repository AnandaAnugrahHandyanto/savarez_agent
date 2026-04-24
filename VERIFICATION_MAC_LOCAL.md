# Verification on steven's Mac mini

Date: 2026-04-24
Repo commit tested: `6051fba9`

## Environment

- macOS Darwin 25.3.0 (arm64)
- Node `v25.8.1`
- npm `11.11.0`
- uv `0.10.4`
- project venv Python `3.11.14`

## Install result

Succeeded with:

```bash
uv venv venv --python 3.11
uv pip install --python venv/bin/python -e '.[messaging,cli,web,mcp,pty,honcho,acp,voice]'
npm install
```

`uv sync --all-extras --locked` did **not** succeed on Python 3.11 because the
`all` extra pulls `dev`, and `dev` includes `yc-bench`, which is currently
Python-3.12+ only.

## Runtime verification

Using isolated home:

```bash
HERMES_HOME="$PWD/.hermes-home" scripts/run-local-hermes.sh doctor
HERMES_HOME="$PWD/.hermes-home" scripts/run-local-hermes.sh status
HERMES_HOME="$PWD/.hermes-home" scripts/run-local-hermes.sh gateway --help
HERMES_HOME="$PWD/.hermes-home" scripts/run-local-hermes.sh chat -q 'hello from isolated local setup test'
```

Observed:

- CLI loads successfully
- doctor/status run successfully
- gateway command loads successfully
- chat starts successfully and fails cleanly only because no inference provider is configured yet

## Auth conclusion

- Hermes **does support OpenAI OAuth directly** for `openai-codex`
- This is a **device code flow**, not a silent noninteractive login
- Standard OpenAI API usage can still use API keys instead

Exact interactive step still needed:

```bash
HERMES_HOME="$PWD/.hermes-home" ./venv/bin/python -m hermes_cli.main login --provider openai-codex --no-browser
```

Then open `https://auth.openai.com/codex/device`, enter the displayed code, and
finish approval in the browser.
