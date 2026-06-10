# USER.md routing benchmark

This benchmark captures representative durable-memory routing decisions from Ryan's historical USER.md cleanup and routing issues.

It is intentionally provider-free: a candidate policy, prompt, tool schema, or model run can emit JSONL predictions, and the local scorer reports whether the decisions would keep USER.md broad and cross-domain.

## Fixture fields

Each line in `fixtures.jsonl` is a JSON object with:

- `id` — stable fixture identifier.
- `source` — issue/memory cleanup source for the historical example.
- `category` — broad fixture class, e.g. `positive_user_profile`, `negative_domain_specific`.
- `prompt` — the fact/correction being routed.
- `expected_route` — one of `user`, `memory`, `skill`, `project_doc`, `kb_page`, `kb_inventory`, `issue_comment`, `nowhere`.
- `expected_destination` — the concrete durable surface expected for the route.
- `rationale` — why the fixture belongs there.

## Prediction format

Prediction JSONL should use:

```json
{"id":"user_pref_concise_direct_answers","route":"user","destination":"USER.md"}
```

`route` is the primary scored value. For non-USER routes, `destination` should name the narrower surface so a model cannot get credit for merely avoiding USER.md without saying where the information belongs.

## Run

```bash
python scripts/memory_routing_benchmark.py predictions.jsonl
```

The script exits non-zero for route mismatches, missing predictions, invalid routes, or domain-specific USER.md false positives.
