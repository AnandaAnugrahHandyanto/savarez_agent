# Hermes CLI setup
Use this process to install and verify the `hermes` CLI.

## 1) Install
```zsh
npm install -g hermes
```

## 2) Verify installation
```zsh
hermes --version
hermes --help
```

Expected behavior:
- `--version` prints a semantic version (for example `0.4.4`)
- `--help` prints command usage

## 3) Start REPL (if needed)
If REPL startup fails with a missing config error, create `hermes.json` in the working directory:

```json
{
  "name": "Local Hermes",
  "nickname": "hermes",
  "plugins": {}
}
```

Then run:
```zsh
hermes --repl
```

At the `>` prompt, enter a simple input to confirm interactivity, then exit with `Ctrl-D`.

## 4) Optional cleanup
If the config was only for a temporary REPL test:

```zsh
rm hermes.json
```
