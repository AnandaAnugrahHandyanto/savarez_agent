# PeopleOS Schema and Migration Rules

## Top-level split

`profile_type` is required conceptually and must normalize to exactly one of:

- `internal`
- `external`

## External relationship kinds

External profiles use `relationship_kind` from this closed taxonomy:

- `investor`
- `advisor`
- `board`
- `strategic_partner`
- `customer`
- `friend`
- `family`
- `other`

Investors such as Su / Roland must be represented as:

```json
{
  "profile_type": "external",
  "relationship_kind": "investor"
}
```

They must not be modeled as internal ranking entries.

## Internal rank logic

Internal rank logic is only for Amber people.

`internal_rank` is preserved exactly when present and valid:

- `N-`
- `N`
- `N+`
- `S-`
- `S`
- `S+`
- `unknown`

External profiles always normalize `internal_rank` to `null`, even if an imported source accidentally contains a rank.

## Normalization rules

- Unknown `profile_type` -> `internal` for backward compatibility.
- External with unknown/legacy `relationship_kind` -> `other`.
- Internal with unknown/legacy `relationship_kind` -> `direct_report`.
- External clears `performance.current_performance_read` because rank/performance read is an internal Amber management concept.

## Migration rules

When importing or correcting historical data:

1. If the person is an Amber employee / operator / direct report, keep `profile_type=internal` and internal rank fields may apply.
2. If the person is an investor, advisor, board member, strategic partner, customer, friend, or family contact, use `profile_type=external`.
3. Investors like Su and Roland must become `external + investor`.
4. Do not preserve N-/S- ranking on external profiles.
5. Preserve relationship notes, interaction logs, open loops, cadence, and next-touch fields across the split.

## UI behavior

- Creation form must expose `profile_type` explicitly.
- When `profile_type=external`, relationship choices should show only the external relationship taxonomy.
- When `profile_type=internal`, relationship choices should show internal relationship choices and the internal rank field.
- Internal rank control should be disabled/hidden for external profiles.
- Structured fields are preferred over raw JSON editing.
