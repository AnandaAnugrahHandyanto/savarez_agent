# People Co-Manager V1 Operating Spec

> **For Miya:** This is the operating spec for Michael’s Telegram-first direct-report management workflow. Treat this as a management decision-support system, not HR software.

**Goal:** Create a Telegram-first operating layer that helps Michael maintain high-quality longitudinal judgment on his direct reports: role clarity, performance calibration, management interventions, follow-ups, and team-wide pattern recognition.

**Core design choice:** V1 should optimize for low-friction capture and high-signal synthesis, not full workflow automation. The system should learn from real management usage first; NexusOS comes after the operating model is proven.

**Critical boundary:** Keep **people-manager context isolated** from speech/post/hiring/project contexts. Within people-manager context, keep **facts**, **Michael’s judgments**, and **Miya’s synthesis** explicitly separated.

---

## 1. Product framing

This system is not primarily for:
- HR recordkeeping
- compliance tracking
- generic performance review templates
- polished dashboards

This system is for:
- founder-manager judgment accumulation
- better 1:1 preparation
- better post-meeting follow-through
- clearer calibration over time
- surfacing hidden team risks and delayed people decisions
- helping Michael manage direct reports with more consistency and sharper pattern recognition

**Working thesis:**
The scarce asset is not notes. It is **compounding managerial judgment**.

---

## 2. V1 user jobs to be done

V1 should help Michael do five things well:

1. **Capture**
   - quickly log new information about a direct report over Telegram

2. **Prepare**
   - generate a concise pre-1:1 or pre-review brief

3. **Assess**
   - maintain an explicit evolving view of the person’s performance, trajectory, and management needs

4. **Follow through**
   - track promises, asks, interventions, and unresolved issues

5. **See across the team**
   - identify concentration risk, org weaknesses, under-management, over-delegation, and miscalibration

---

## 3. Scope: V1 vs later

### In scope for V1
- direct-report profile creation
- profile updates through natural-language Telegram inputs
- structured separation of:
  - facts
  - Michael’s judgments
  - Miya’s synthesis
- pre-1:1 prep
- post-1:1 wrap-up
- per-person review summary
- team scan / cross-report synthesis
- explicit tracking of:
  - role and mandate
  - goals / KPIs / OKRs
  - strengths
  - weaknesses
  - trajectory
  - risks
  - manager actions
  - next steps

### Out of scope for V1
- employee self-service
- calendar integration as a hard dependency
- automated reminders as a hard dependency
- compensation workflow
- formal HR documentation pipeline
- permissions / multi-user workflows
- company-wide org chart tooling
- recruitment / candidate tracking inside the same data model

**Rule:** Hiring and people-management stay separate even if the same human moves from candidate to employee.

---

## 4. Storage and context boundary

### Global memory
Global Hermes memory should store only durable cross-project rules such as:
- Michael wants Miya to act as a people co-manager
- role isolation matters
- Telegram-first workflow

### People-manager project state
Per-report and team-management state should **not** go into global memory.

It should live in people-manager project storage, ideally under a project-specific area, e.g.:
- `projects/people-manager/registry.json`
- `projects/people-manager/reports/<person-slug>.json`
- `projects/people-manager/team-snapshots/<date>.json`

### Golden separation rule
Every material note should be tagged into one of three layers:

1. **Facts**
   - observable events, stated commitments, outcomes, dates, deliverables
   - examples:
     - "Missed March hiring target by 3 roles"
     - "Said he wants broader scope"
     - "Delivered board draft on Tuesday"

2. **Michael judgment**
   - Michael’s direct assessment or interpretation
   - examples:
     - "I think she is operating below level"
     - "I trust him more on execution than people leadership"

3. **Miya synthesis**
   - synthesized read, pattern recognition, challenge, suggested action
   - examples:
     - "Pattern suggests strong operator, weak scaling manager"
     - "You may be over-indexing on loyalty over throughput"

**Never collapse these three into one blob.** That destroys calibration quality over time.

---

## 5. Canonical per-report schema

Each direct report should have one living profile.

## 5.1 Core identity
- `name`
- `role_title`
- `manager` = Michael
- `function`
- `location` (optional)
- `start_date` (optional)
- `status` = active / transitioning / exited / paused
- `profile_owner` = people-manager

## 5.2 Role charter
- `mandate`
- `what_good_looks_like`
- `current_priorities`
- `decision_rights`
- `interfaces`
  - who they depend on
  - who depends on them

## 5.3 Goals and scorecards
- `current_okrs_or_kpis`
- `expected_outputs`
- `measures_of_success`
- `review_window`
- `last_goal_refresh_at`

## 5.4 Current operating state
- `energy_level`
- `focus_quality`
- `execution_reliability`
- `communication_quality`
- `decision_velocity`
- `ownership_level`
- `team_health_impact`

Use plain-language ratings in V1, not fake precision.
Suggested values:
- strong
- solid
- uneven
- concerning
- unknown

## 5.5 Strengths
- `known_strengths`
- `best_use_cases`
- `where_they_create_leverage`

## 5.6 Weaknesses / failure modes
- `known_weaknesses`
- `recurring_failure_modes`
- `watchouts`

## 5.7 Performance and trajectory read
- `current_performance_read`
- `trajectory`
  - rising / flat / declining / unclear
- `scope_fit`
  - under-scoped / well-matched / over-scoped / unclear
- `confidence_level_in_read`
  - high / medium / low
- `evidence_basis`

## 5.8 Management strategy
- `how_michael_should_manage_them`
- `what_kind_of_feedback_works`
- `what_kind_of_pressure_backfires`
- `current_manager_interventions`
- `support_needed`
- `stretch_opportunities`

## 5.9 Open loops
- `open_todos_for_them`
- `open_todos_for_michael`
- `unresolved_questions`
- `active_risks`
- `next_review_date`

## 5.10 Interaction log
Chronological entries with:
- `date`
- `type`
  - update / 1:1 / assessment / review / incident / promotion-discussion / org-change / feedback
- `facts`
- `michael_judgment`
- `miya_synthesis`
- `resulting_actions`

---

## 6. Telegram input grammar

V1 should support natural, low-friction patterns. These do not need to be slash commands initially; plain messages inside `/people` mode are enough.

### 6.1 Create profile
**Pattern**
- `New report: <name> - <role> - <mandate>`

**Example**
- `New report: Alice Chen - Head of IR - owns investor communication rhythm and key fundraising support`

**System behavior**
- create report profile
- ask only for the minimum missing fields if necessary
- confirm active profile summary

### 6.2 General update
**Pattern**
- `Update <name>: <notes>`

**Use for**
- new facts
- progress updates
- behavior changes
- org changes
- delivery wins/misses

### 6.3 1:1 notes
**Pattern**
- `1:1 <name>: <notes>`

**Expected parsing intent**
- capture meeting observations
- commitments
- mood/energy
- manager follow-ups

### 6.4 Assessment input
**Pattern**
- `Assessment <name>: <view>`

**Use for**
- explicit performance read
- scope fit
- promotion risk
- confidence concerns
- trust level

### 6.5 Todo capture
**Patterns**
- `Todo <name>: <todo>`
- `Todo for me on <name>: <todo>`

### 6.6 Prep request
**Pattern**
- `Prep <name>`

**Output should include**
- current read
- what changed since last meeting
- open loops
- hard questions to ask
- likely management objective for the meeting

### 6.7 Review request
**Pattern**
- `Review <name>`

**Output should include**
- current performance read
- trajectory
- strongest evidence
- unresolved doubts
- suggested next management move

### 6.8 Team scan
**Pattern**
- `Team scan`

**Output should include**
- strongest people
- fragile nodes
- under-managed people
- people with unclear mandate
- people needing stretch
- people needing support
- decisions Michael may be postponing

### 6.9 Challenge mode
**Patterns**
- `Challenge my view of <name>`
- `Am I under-managing anyone?`
- `Who is over-scoped?`
- `Where am I being too generous?`

**This is important.** The system should not just mirror Michael’s stated view. It should occasionally pressure-test it.

---

## 7. Output specs

## 7.1 Pre-1:1 brief
Target length: short enough to read in under 2 minutes.

Structure:
1. **Current read**
2. **What changed since last touchpoint**
3. **Open loops**
4. **Questions to ask**
5. **Message to land**
6. **Management objective for this meeting**

## 7.2 Post-1:1 wrap
Structure:
1. **What we learned**
2. **What changed in the read**
3. **Commitments made**
4. **Follow-ups for Michael**
5. **Risks to keep watching**

## 7.3 Person review
Structure:
1. **Role and mandate**
2. **Current performance read**
3. **Trajectory**
4. **Strengths**
5. **Weaknesses / failure modes**
6. **Managerial recommendation**
7. **Confidence and missing evidence**

## 7.4 Team scan
Structure:
1. **Overall org read**
2. **Top performers / leverage nodes**
3. **Concerning situations**
4. **Mis-scoped or unclear roles**
5. **Management attention allocation advice**
6. **Hard calls being delayed**

---

## 8. Review cadence

V1 should support this minimum rhythm:

### Ongoing
- ad hoc updates whenever Michael sends them

### Before any 1:1
- `Prep <name>`

### After any 1:1
- `1:1 <name>: ...`
- optional follow-up `Wrap <name>` later if needed

### Biweekly or monthly per person
- `Review <name>`

### Monthly across team
- `Team scan`

**Key design point:** cadence should be recommended by Miya, but not blocked by automation dependencies.

---

## 9. Judgment and calibration rules

### Rule 1: evidence over vibe
Strong claims should cite supporting facts where possible.

### Rule 2: uncertainty should be explicit
If the read is weak, say so.
- not: "He is definitely not scalable"
- better: "Current evidence suggests scaling risk, but confidence is medium because most evidence comes from two incidents"

### Rule 3: distinguish skill from scope mismatch
Do not confuse:
- weak person
- overloaded person
- poorly defined role
- manager neglect
- structural dependency failure

### Rule 4: push on delayed decisions
When patterns are clear, Miya should challenge drift.

### Rule 5: preserve history of changing reads
The point is not to be permanently right. The point is to become better calibrated over time.

---

## 10. Example report profile

## Alice Chen — example skeleton

**Core identity**
- Role: Head of IR
- Function: Investor relations / fundraising support
- Status: active

**Role charter**
- Mandate: own investor communication cadence, support fundraising narrative prep, maintain follow-through with priority investors
- What good looks like: proactive updates, clean materials, reliable follow-up, strong message consistency with Michael

**Goals / scorecard**
- maintain investor update rhythm
- improve meeting follow-through quality
- shorten turnaround time on investor materials

**Current operating state**
- energy: solid
- execution reliability: strong
- communication quality: solid
- ownership: uneven

**Strengths**
- fast turnaround
- good external polish
- dependable on discrete asks

**Weaknesses / failure modes**
- waits for direction too often on ambiguous work
- may optimize presentation over strategic prioritization

**Performance / trajectory read**
- current read: solid but not yet fully strategic
- trajectory: rising
- scope fit: well-matched
- confidence: medium

**Management strategy**
- give clearer outcome framing, not step-by-step instruction
- push for more proactive synthesis rather than reactive execution
- test stretch into investor-prioritization judgment

**Open loops**
- ask her to propose investor segmentation view
- check whether follow-up discipline is systematized or still personality-dependent

---

## 11. What `/people` mode should actually do in V1

When Michael enters `/people`, Miya should switch into a clean people-manager workspace and default to these behaviors:

1. interpret incoming messages primarily as people-management context
2. avoid importing speech/post/hiring context unless explicitly requested
3. route direct-report notes into structured report records
4. answer with management-useful outputs, not generic summaries
5. maintain continuity across reports and across time
6. proactively distinguish:
   - raw notes
   - assessment
   - suggested management move

### Recommended `/people` response style
For most interactions, respond in one of these modes:
- **capture confirmed**
- **profile updated**
- **prep brief**
- **review memo**
- **team scan**
- **challenge memo**

---

## 12. Minimal implementation recommendation

If implementing now, do the minimum viable version in this order:

### Phase A
- `/people` enters isolated workspace
- create per-report JSON files
- support `New report`, `Update`, `1:1`, `Assessment`, `Todo`, `Prep`, `Review`, `Team scan`

### Phase B
- add team-level summary files
- add confidence tracking and evidence basis
- add challenge-mode prompts

### Phase C
- add reminders, cadence suggestions, and meeting pre/post packets
- use this validated operating model as the basis for NexusOS

---

## 13. Open design questions

These should be decided before broader build-out:

1. **Single active report vs free-form report references**
   - Should Miya keep one active person in focus until changed, or always parse names explicitly?
   - Recommendation: explicit names first; active-person shortcuts later.

2. **How structured should ratings be?**
   - Recommendation: plain-language buckets in V1, not numeric scoring.

3. **Should team ranking exist in V1?**
   - Recommendation: yes, but only as synthesized output when asked, not as a canonical always-on field.

4. **Should Miya proactively challenge Michael?**
   - Recommendation: yes, but briefly and only where evidence exists.

5. **What is the first persistence surface?**
   - Recommendation: project-scoped JSON/Markdown files, not global memory and not a DB-first build.

---

## 14. Recommended next step

Build a **People Co-Manager V1 implementation plan** with:
- exact file paths
- storage schema
- Telegram parsing rules
- update/merge behavior
- output templates
- tests for each input pattern

That plan should be implementation-grade and should treat this as a project-scoped workflow under `/people`, not a global assistant behavior.
