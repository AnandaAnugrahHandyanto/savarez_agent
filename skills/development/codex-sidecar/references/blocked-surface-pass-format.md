# Blocked-surface PASS formatting pitfall

Context: During crypto_bot S006 branch-local completion evidence, Codex produced a semantically passing sidecar result with:

`- Blocked-surface scan: PASS, with basis: ...`

The Hermes completion gate initially rejected it because the parser accepted exact `PASS`, `PASS ` with a space after it, `exit code 0`, `no blocked`, or `no matches`, but not `PASS, ...` where punctuation immediately follows PASS.

Reusable lesson:

- Prefer making Codex emit machine fields in the narrowest parser-compatible shape.
- For `Blocked-surface scan`, `PASS with basis: ...` or standalone `PASS` plus details elsewhere is still the most robust emission shape.
- If a sidecar result is semantically correct but rejected, inspect the completion-gate parser before rerunning broad audits; patch parser/tests when the expected result shape is reasonable.
- Use TDD for parser repairs: write a regression test that fails on the rejected evidence shape, then patch the predicate and verify the original completion gate artifact passes.
- Keep this distinction clear: blocked-surface scan is not necessarily an all-files allowlist check. Unlisted discovery docs, JSON evidence, and validation scripts are not blocked merely because they are absent from a task allowlist; allowlists decide whether otherwise sensitive workflow/service/docs paths are approved for the task.

Regression pattern:

```python
def test_blocked_surface_scan_accepts_pass_with_punctuated_basis() -> None:
    assert completion_gate.blocked_surface_scan_passed([
        "PASS, with basis: approved workflow path"
    ])
    assert not completion_gate.blocked_surface_scan_passed(["passive wording only"])
```

Robust parser predicate:

```python
if normalized == "pass" or re.match(r"^pass\b", normalized):
    return True
```
