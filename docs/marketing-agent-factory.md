# Marketing Agent Factory

The Marketing Agent Factory is a dry-run-first multi-agent marketing system bundled as `plugins/marketing_factory`.

MVP guardrail: it never posts publicly. The only publisher records `mode=dry_run`, `would_post=true`, and `posted=false` audit events. Real posting integrations must be added behind explicit approval and dry-run flags.

## What it includes

- Isolated app/brand profiles under `HERMES_HOME/marketing_factory/state.json`
- JSONL audit log at `HERMES_HOME/marketing_factory/audit.jsonl`
- Deterministic MVP agents:
  - Brand Brain Agent
  - Research Agent
  - Strategy Agent
  - Copy Agent
  - Creative Agent
  - Review/Safety Agent
  - Scheduler Agent
  - Publisher Agent (dry-run only)
  - Analytics Agent
- Operator CLI: `hermes marketing-factory ...`
- Agent tool: `marketing_factory`
- Pupular and SetVenue sample campaigns
- Tests for schema/store isolation, routing metadata, approvals, scheduling, dry-run publishing, audit, analytics feedback, and CLI behavior

## CLI quick start

```bash
hermes marketing-factory init
hermes marketing-factory status
hermes marketing-factory generate --app pupular --days 7
hermes marketing-factory drafts --app pupular
hermes marketing-factory approve <draft_id>
hermes marketing-factory schedule --app pupular
hermes marketing-factory publish-dry-run --app pupular
hermes marketing-factory audit --app pupular
```

End-to-end dry-run for one app:

```bash
hermes marketing-factory full-dry-run --app pupular --days 7
hermes marketing-factory full-dry-run --app setvenue --days 7
```

For tests or sandboxes, pass `--store-path /tmp/marketing-factory-test` before the subcommand:

```bash
hermes marketing-factory --store-path /tmp/mf init
hermes marketing-factory --store-path /tmp/mf full-dry-run --app pupular --days 3
```

## Adding a new app

Add a brand profile with these fields, either programmatically through `MarketingFactoryStore.upsert_app()` or by adding a seed profile in `plugins/marketing_factory/pipeline.py`:

```python
{
    "slug": "myapp",
    "name": "MyApp",
    "positioning": "One-line market position",
    "icp": "Primary audience",
    "tone": "Voice and style",
    "cta": "Primary call to action",
    "links": ["https://example.com"],
    "channels": ["x", "linkedin", "blog"],
    "content_pillars": ["pillar one", "pillar two"],
    "claims": ["verified factual claim"],
    "forbidden_claims": ["claim we must not make"],
    "assets": ["screenshots", "logo"],
    "competitors": ["Competitor"],
    "current_campaigns": ["current push"],
}
```

Brand memory is app-scoped in `brand_memories[slug]`. Do not store cross-app learnings in another app’s slug.

## Adding a new marketing channel

1. Add the channel name to the app profile’s `channels`.
2. Update `_content_type(channel)` in `pipeline.py` if it needs a platform-specific type.
3. Update `_within_channel_constraints(channel, body)` with length/platform constraints.
4. Add tests for draft generation and safety constraints for the new channel.

## Adding a new model/provider

The MVP records model routing policy but does not call external models. Extend by adding a provider adapter behind an interface that accepts:

- task type (`classification`, `strategy`, `final_review`, etc.)
- app slug
- budget scope
- prompt/context summary
- cache key

Keep the routing tiers:

- cheap/local: classification, summarization, scraping cleanup, first-pass duplicate checks
- mid-tier cloud: rewrites, repurposing, channel variants
- premium Claude/GPT-level: strategy, final review, high-value copy

Before enabling calls, enforce:

- daily token budget
- per-app budget
- per-channel budget
- cache lookup before model call
- compressed campaign summaries instead of raw context reloads
- audit events for model route, estimated tokens, and cost

## Adding a posting integration

Real posting must remain behind approval and dry-run gates.

Implementation checklist:

1. Add a publisher adapter with `dry_run=True` default.
2. Require draft status `scheduled` and approval status `approved`.
3. In dry-run mode, record the exact payload that would be sent and return without network side effects.
4. In real mode, require an explicit config flag and human approval token/flag.
5. Record audit events before and after the posting attempt.
6. Add tests proving dry-run does not call the external API and real mode refuses without approval.

Suggested first integration after MVP: X/Twitter via the existing `xurl`/`x-cli` workflow, because Pupular already has a defined X cadence. Keep it disabled by default and dry-run-only until the approval trail is verified.

## Verification

Targeted test command:

```bash
scripts/run_tests.sh tests/plugins/test_marketing_factory.py
```

Manual smoke:

```bash
STORE=$(mktemp -d)
hermes marketing-factory --store-path "$STORE" init
hermes marketing-factory --store-path "$STORE" full-dry-run --app pupular --days 2
hermes marketing-factory --store-path "$STORE" full-dry-run --app setvenue --days 2
hermes marketing-factory --store-path "$STORE" status
```
