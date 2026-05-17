# PR 1 — Claude Code CLI contract findings (real-host probe)

Findings recorded as each Phase C task runs against the real `claude`
binary on the user's host. Used to consolidate the CLI Contract appendix
into the design spec in Task 15.

## Host environment

- Date: 2026-05-17
- Claude version: 2.1.143 (Claude Code)
- OS: Linux pepper 6.8.0-100-generic #100-Ubuntu SMP PREEMPT_DYNAMIC Tue Jan 13 16:40:06 UTC 2026 x86_64
- Hermes worktree: /root/.hermes/hermes-agent-claude-cli-pr1
- Branch: claude-cli-pr1

## Task 8: basic stream-json invocation

- Test: `tests/e2e/test_claude_cli_probe.py::test_basic_stream_json_invocation`
- Result: PASS
- Exit code observed: 0
- Event types seen in stream: system, system, system, assistant, rate_limit_event, result
- Stderr digest (first 500 bytes): (empty — no stderr output)
- Wall time: ~5.3 seconds
- stdin prompt transport supported: yes

### Notes

- Three `system` events arrive before `assistant`; these appear to be
  Claude Code's internal init/session setup events emitted by `--verbose`.
- A `rate_limit_event` event is emitted between `assistant` and `result`.
  This is a normal informational event, not an error. It does not indicate
  actual rate limiting was hit.
- The `--no-session-persistence` and `--allowedTools ""` flags work as expected
  on version 2.1.143.
- Empty stderr confirms no warnings, banners, or debug logs leaked to stderr
  when using `--output-format stream-json`.

Conclusion: stdin prompt transport via `-p` + `--output-format stream-json`
works correctly on version 2.1.143; the adapter design assumption is valid.
