# 2026-05-27 upstream sync (hermes-agent)

## やったことやで

- `origin/main` の独自更新 `f011ff8d3` を取り込んでから、公式 `upstream/main` の `9eadb6805` までを Python 経由で `main` にマージした。
- 公式側の新機能・修正として、Docker 所有権/環境変数修正、Docker voice-mode、MCP カタログ/ピッカー、TUI セッションオーケストレーター、Codex Responses 復旧、`/reload-mcp` の cached agent 更新、`hermes update --branch` を取り込んだ。
- 独自機能の OpenCode Zen `auto-free`、OpenClaw credential bridge、llama.cpp fallback、VRChat/VOICEVOX/Neuro tooling、Windows autostart、gateway 運用 hardening は保持した。
- README の current baseline と Inherited Upstream Capabilities を今回の同期内容へ更新した。

## 確認ポイント

- Python 棚卸し: upstream touched paths 92、overlap paths 17。
- 3-way 予測: conflict marker が必要な衝突なし。
- `git diff --check HEAD^..HEAD`: whitespace error なし。

## まだ見るところ

- 公式差分が大きいので、対象テストを先に通してから push する。
