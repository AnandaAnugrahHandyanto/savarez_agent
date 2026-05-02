# PeopleOS Mobile-First Hybrid Dashboard Plan

> **For Hermes:** Implement after Michael approves this staged plan. Use TDD and keep PeopleOS standalone, not embedded in Hermes Dashboard.

**Goal:** Redesign PeopleOS WebUI into a mobile-first hybrid relationship dashboard: Internal + External tabs with fast actions, then structured profile editing, then internal management cockpit views.

**Priority order from Michael:**
1. Hybrid dashboard — Internal and External tabs with fast actions for both.
2. Structured profile editor — make profile fields easy to edit without raw JSON / giant form confusion.
3. Management cockpit — internal Amber ranks/performance/open loops as a deeper view.

**Current implementation:** standalone PeopleOS lives in `people_manager/web_service.py` as a minimal inline HTML/JS shell served at `http://100.118.42.113:8891/`, backed by canonical data root `/Users/michael.wu/.PeopleOS/data`.

---

## UX Principles

1. **Mobile-first, PC-compatible**
   - Phone should be the default design target.
   - Desktop can use the same components in a wider two-pane layout later.

2. **Dashboard first, editor second**
   - Landing screen should answer: who needs attention?
   - Editing should be one tap away, not all fields always visible.

3. **Internal vs external is primary taxonomy**
   - Internal = Amber people / N-/S- rank / management context.
   - External = relationship CRM / investor-advisor-board-partner-customer-friend-family-other.

4. **Fast actions beat forms**
   - Most mobile actions should be:
     - log touch
     - add note
     - add follow-up
     - set next check-in
   - Full field editing is a separate mode.

---

## Target UX Structure

### Home / Roster

Top mobile header:

```text
PeopleOS                 [+]
14 profiles · 3 external
[Search...]
```

Segmented nav:

```text
All | Internal | External | Due | Open Loops
```

Card layout:

Internal card:

```text
Yi Bao
Internal · direct_report · Rank: N-
Role: AMBR CPO...
Next check-in: —
Open loops: 2 · Notes: 5
[Open] [Touch]
```

External card:

```text
Su
External · investor
Cadence: quarterly
Next touch: —
Open loops: 0 · Notes: 0
[Open] [Touch]
```

### Add Profile

Instead of always-expanded create form:

- floating/action button: `+ Add`
- opens a sheet/panel:

Step 1:

```text
What type?
[Internal Amber] [External relationship]
```

Step 2 fields:

Internal:
- Name
- Role
- Relationship kind: direct_report / manager / peer / cross_functional / other
- Internal rank: N-, N, N+, S-, S, S+, unknown
- Cadence
- Notes / mandate

External:
- Name
- Role / context
- Relationship kind: investor / advisor / board / strategic_partner / customer / friend / family / other
- Cadence
- Notes / context

### Profile Detail

Open profile should become a focused panel/card, not a huge section below everything.

Mobile layout tabs:

```text
Summary | Touch | Fields | Loops
```

Desktop future layout:

```text
Left: roster    Right: detail panel
```

#### Summary tab

Internal summary:
- role
- internal rank
- performance read
- trajectory/scope/confidence
- cadence / last touch / next check-in
- top open loops
- recent notes

External summary:
- relationship kind
- role/context
- cadence / last touch / next touch
- top open loops / asks
- recent notes

#### Touch tab

Fast action panel:

- Log touch
- Add note
- Add follow-up
- Set next check-in

Implement as simple action buttons that reveal minimal fields.

#### Fields tab

Structured editor:
- core identity fields
- taxonomy fields
- cadence/touch dates
- internal-only fields if internal
- external-only relationship fields if external

#### Loops tab

Open loops checklist:
- add loop
- owner: Michael / Them / Question / Risk
- mark closed

---

## Implementation Stages

### Stage 1 — Mobile dashboard shell

**Objective:** Make home usable on phone.

Files:
- `people_manager/web_service.py`
- `tests/people_manager/test_peopleos_web_service.py`

Changes:
- Add top segmented nav: All/Internal/External/Due/Open Loops.
- Collapse create profile into hidden panel opened by `+ Add`.
- Add compact profile cards with direct `Open` and `Touch` buttons.
- Maintain current API endpoints.

Acceptance:
- HTML contains `tab-all`, `tab-internal`, `tab-external`, `tab-due`, `tab-open-loops`.
- Create form is not always visually primary; it is hidden/collapsible by default.
- Cards show type, relationship, cadence/next touch, open-loop count, note count.

### Stage 2 — Profile detail tabs

**Objective:** Stop showing one giant editor; split profile detail by use case.

Changes:
- Add detail tab controls: `Summary`, `Touch`, `Fields`, `Loops`.
- Default open tab = Summary.
- Move current structured editor into Fields tab.
- Move quick note into Touch tab.

Acceptance:
- HTML contains `detail-tab-summary`, `detail-tab-touch`, `detail-tab-fields`, `detail-tab-loops`.
- `openProfile()` renders tabbed detail.
- Internal/external conditional fields still work.

### Stage 3 — Fast actions

**Objective:** Optimize the main mobile workflow.

Changes:
- Add `Touch` button on each card.
- `Touch` opens profile directly to Touch tab.
- Add action modes:
  - log touch
  - add note
  - add follow-up
  - set next check-in

Initial implementation can map:
- log touch -> PATCH `last_touch_at` + interaction note
- add note -> POST interaction
- follow-up -> POST open loop
- next check-in -> PATCH `next_checkup_at`

Acceptance:
- Tapping `Touch` from a card opens Touch tab.
- Each action writes to existing API endpoints.

### Stage 4 — Structured editor polish

**Objective:** Make Fields tab a clean editor, not a dense wall.

Changes:
- Group fields:
  - Identity
  - Taxonomy
  - Cadence / Touch
  - Internal management OR External relationship
- Save button sticks at bottom on mobile.
- Hide irrelevant internal/external fields.

Acceptance:
- Internal profile shows rank/performance fields.
- External profile hides rank/performance and shows external relationship fields.

### Stage 5 — Management cockpit

**Objective:** Add the deeper internal review layer.

Changes:
- Add Internal dashboard badges:
  - rank
  - trajectory
  - stale touch
  - open loop count
- Add filtered internal view: `Needs attention` based on open loops or missing next check-in.
- Add simple rank filter later if needed.

Acceptance:
- Internal tab supports management review without polluting external CRM.

---

## Non-goals for this iteration

- Full React/Vite rewrite.
- Auth/user accounts.
- Cloud/mobile app packaging.
- Complex offline sync.
- Replacing Miya bridge.

---

## Verification

```bash
source venv/bin/activate
pytest tests/people_manager -q
PEOPLEOS_DATA_ROOT=/Users/michael.wu/.PeopleOS/data python scripts/peopleos_server.py --host 100.118.42.113 --port 8891
python - <<'PY'
import json, urllib.request
base='http://100.118.42.113:8891'
root=urllib.request.urlopen(base+'/', timeout=5).read().decode()
for marker in ['tab-internal', 'tab-external', 'detail-tab-summary', 'detail-tab-touch', 'create-profile-panel']:
    print(marker, marker in root)
profiles=json.loads(urllib.request.urlopen(base+'/api/profiles', timeout=5).read())['profiles']
print(len(profiles), sum(1 for p in profiles if p.get('profile_type')=='external'))
PY
```

---

## Recommended first build slice

Implement Stages 1 and 2 together:
- mobile dashboard tabs
- collapsed create panel
- tabbed detail with Summary/Touch/Fields/Loops

Then pause for Michael to test on phone before adding more fast-action depth.
