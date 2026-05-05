# Sample inbound messages for the file-based property loop (CHG-0002)

These three messages exercise the full P-01 / P-02 path from `hermes-ucpm
test-property-loop`. They are also wired in as pytest fixtures via
`tests/ucpm/conftest.py`.

| File                       | Expected P-01 intent | Expected P-02 outcome                       |
|----------------------------|----------------------|---------------------------------------------|
| `maintenance-hvac.json`    | `maintenance`        | urgency=high, category=hvac                 |
| `rent-question.json`       | `payment`            | (no triage — non-maintenance)               |
| `emergency-water.json`     | `maintenance`        | urgency=emergency, gates=[emergency, spend] |

Run the loop locally:

```sh
mkdir -p inbox outbox audit-log
cp hermes_agent/loops/sample_emails/*.json inbox/
doppler run -- uv run hermes-ucpm test-property-loop \
    --inbox ./inbox \
    --outbox ./outbox \
    --audit ./audit-log \
    --company-dir ../paperclip-UCPM/companies/ucpm-default
```

`outbox/drafts/<id>.json` will hold the drafted action(s); `audit-log/<id>.jsonl`
will hold the per-step audit rows. Set `ANTHROPIC_API_KEY` via Doppler — never
in a `.env` file.

Note: this directory is named `sample_emails/` (not `examples/`) because
the upstream `.gitignore` excludes any `examples/` directory at any depth.
Test code resolves the path via `EXAMPLES_DIR` in `tests/ucpm/conftest.py`.
