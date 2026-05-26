# 2026-05-26 AI Portfolio Evidence Refresh - Codex

## Goal

READMEをAI/agent engineering portfolioとして見た時に、モデル運用・fallback・gateway・Windows運用証跡がすぐ読めるようにしたで。

## Review Finding

- READMEは運用forkとして濃い内容やけど、AIエンジニアリング実績としての `model / runtime / repro / metrics / limitations` が上部で一覧化されていなかった。
- コード本体には触っていない。今回はレビュー結果に基づくREADME証跡の追加や。

## Files Changed

- `README.md`
- `_docs/2026-05-26_ai-portfolio-evidence-codex.md`

## Verification

- Documentation-only change.
- 既存READMEのOpenCode Zen、llama.cpp fallback、gateway、VRChat、Windows autostart説明と矛盾しないことを確認した。

## Remaining Risk

- 実運用PRとしてさらに強くするなら、gateway uptime、fallback switch events、catalog freshnessなどをREADMEに貼れる形式で定期出力するとええ。
