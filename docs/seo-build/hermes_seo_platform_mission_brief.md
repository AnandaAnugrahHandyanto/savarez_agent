# Hermes Mission Brief: Agent-Run SEO Operating System

## Document Purpose

This document is intended to be used as the primary mission prompt and support brief for Hermes Agent to build the first production version of an internal agent-run SEO operating system.

The system is not a chatbot. It is a closed-loop SEO operations platform that uses agents to replace most SEO execution roles while keeping two humans in governance:

1. Company owner / final authority
2. Lead SEO manager / SEO quality gate

The front-end developer remains responsible for the reusable page factory, technical implementation surface, template system, and production deployment mechanics. Agents should assemble pages, create briefs, validate work, create ClickUp tasks, verify fixes, and generate reports inside controlled interfaces.

The system must follow this operating loop:

Find -> Prove -> Prioritize -> Assign -> Build/Fix -> Validate -> Approve -> Publish/Deliver -> Verify -> Measure -> Report -> Learn

No evidence means no recommendation.
No validation means not ready.
No verification means not fixed.
No measured delta means impact pending.

---

# Section 1: Mission for Hermes

## Primary Mission

Build the MVP foundation for an internal SEO Intelligence Platform that runs a bi-weekly SEO search audit, generates evidence-backed findings, creates prioritized ClickUp tasks, tracks implementation, verifies fixes, and prepares a client-ready report.

The initial build should support one client/site/market, but the architecture must be multi-client ready.

## What Hermes Should Build First

Build the first closed loop:

1. Ingest or mock SEO data from provider adapters.
2. Normalize evidence into a shared internal schema.
3. Run specialist analysis agents through LangGraph.
4. Validate findings with adversarial QA agents.
5. Generate a bi-weekly report JSON.
6. Create ClickUp-ready task payloads.
7. Track task status transitions.
8. Verify implemented fixes.
9. Store report runs, recommendations, evidence, and verification results.
10. Provide a foundation for page generation through a PageSpec template schema.

Do not build the full dashboard first. Build the engine, schemas, API contracts, report output, task loop, and validation gates.

## Non-Negotiables

- This is a production-oriented build, not a demo chatbot.
- The system must be evidence-first.
- Agents must return structured JSON, not only prose.
- Every recommendation must include evidence IDs.
- Every ClickUp task must include acceptance criteria and a verification method.
- Every report claim must trace back to evidence.
- Every generated page must pass validators before publishing.
- Implementation status must be separate from verification status.
- The architecture must protect confidential client data from contractors.
- Provider adapters must be swappable.
- The first version must avoid scope explosion.

---

# Section 2: Product Scope

## Product Name

Working name: SEO Mission Control

## Product Category

Internal agent-run SEO operating system for search audit, content operations, local SEO, tasking, verification, reporting, and long-term SEO memory.

## Primary Users

1. Owner / executive approver
2. Lead SEO manager / quality gate
3. Front-end developer / implementation owner
4. Agent workers / automated SEO department

## Replaced Human Roles

Agents will replace most of the operational SEO team:

- SEO coordinator
- SEO analyst
- keyword researcher
- technical SEO analyst
- local SEO analyst
- content strategist
- landing page strategist
- SEO writer
- editor
- reporting specialist
- QA analyst
- project traffic manager
- business impact analyst

## Retained Human Roles

### Owner

Approves:

- major strategy changes
- budget thresholds
- client-sensitive decisions
- system behavior changes
- escalated risks

### Lead SEO Manager

Approves:

- final SEO strategy
- content briefs
- page recommendations
- local SEO actions
- report delivery
- high-risk generated work

### Front-End Developer

Owns:

- page template system
- PageSpec renderer
- CMS integration
- schema rendering components
- preview/staging
- analytics/tracking components
- production deployment safety
- reusable front-end implementation

Agents should not require the developer to manually build every page. The developer builds the factory; agents assemble pages through PageSpec.

---

# Section 3: Architecture Principles

## Core Architecture

Use this division of labor:

- GSC: first-party organic performance truth
- GA4: business outcome and conversion truth
- BigQuery: analytics warehouse
- Postgres: operational application database
- Cloud Storage: raw artifact storage
- Bright Data: live SERP and raw Google output
- DataForSEO: SEO database, keyword metrics, SERP backup, backlinks, on-page, AI visibility data
- BrightLocal: local SEO operations, local rank, geo-grid, citations, review workflows
- Firecrawl: page/content extraction and competitor page analysis
- Perplexity: external research assistant, not canonical measurement source
- ClickUp: human/developer execution layer
- LangGraph: durable mission orchestration
- Hermes Agent: coding and implementation executor for this build

## Data Source Truth Hierarchy

If data sources conflict, use this hierarchy:

- GSC is truth for owned organic search performance.
- GA4/CRM is truth for business outcomes.
- BrightLocal is truth for local rank and local SEO operations.
- Bright Data is truth for live SERP snapshots.
- DataForSEO is truth for keyword metrics and SEO market data.
- Firecrawl is truth for extracted page content.
- ClickUp is execution mirror, not analytical truth.
- Postgres is operational product truth.
- BigQuery is analytics warehouse truth.

Agents must identify the source behind every claim.

## Storage Rules

Use Postgres for:

- clients
- sites
- locations
- missions
- report runs
- recommendations
- evidence records
- agent handoffs
- approval requests
- ClickUp task mappings
- content briefs
- PageSpecs
- verification results
- workflow state

Use BigQuery for:

- GSC bulk export
- GA4 export
- historical search metrics
- historical rank snapshots
- historical local snapshots
- large trend analysis
- long-term analytics joins

Use Cloud Storage for:

- raw SERP HTML
- Firecrawl markdown/html snapshots
- screenshots
- rendered PDFs
- CSV/XLSX appendices
- raw API archives

Do not use BigQuery as the operational app database.
Do not use GSC as a database.
Do not store large raw HTML artifacts in Postgres.

---

# Section 4: MVP Build Scope

## MVP Goal

Build the first end-to-end system that can run a bi-weekly SEO audit for one client and produce:

1. Evidence-backed findings
2. Prioritized recommendations
3. ClickUp-ready task payloads
4. A report JSON output
5. Verification workflows for implemented fixes
6. Page opportunity and PageSpec scaffolding

## In Scope for MVP

- FastAPI backend or equivalent API server
- Postgres schema and migrations
- LangGraph mission orchestration
- Provider adapter interfaces
- Mock provider implementations
- Optional real adapters with environment variables
- Evidence normalization
- Agent role prompts and output schemas
- Technical SEO analysis agent
- Search performance agent
- Keyword/SERP opportunity agent
- Local SEO agent
- Report writer agent
- Evidence validator agent
- ClickUp sync agent
- Fix verification agent
- PageSpec schema
- Landing page validation contract
- Report validation contract
- Basic admin CLI or API endpoints to start a mission
- Tests for schemas, scoring, validation, and task creation

## Out of Scope for MVP

- Full visual dashboard
- Fully autonomous CMS publishing
- Mass local page generation
- Backlink intelligence
- Automated GBP posting
- Automated outreach
- Predictive ranking models
- AI visibility across every LLM
- Multi-client benchmarking
- Full revenue attribution

These can be Phase 2 or Phase 3.

---

# Section 5: Recommended Repo Structure

Create a monorepo structure:

```txt
seo-mission-control/
  AGENTS.md
  README.md
  docker-compose.yml
  .env.example
  backend/
    AGENTS.md
    pyproject.toml
    alembic.ini
    app/
      main.py
      config.py
      db.py
      models/
      schemas/
      api/
      services/
      providers/
      agents/
      graphs/
      validators/
      scoring/
      reporting/
      clickup/
      storage/
      utils/
    tests/
  frontend/
    AGENTS.md
    package.json
    src/
      app/
      components/
      pagespec/
      reports/
      tasks/
  docs/
    architecture.md
    provider-contracts.md
    agent-specs.md
    validation-contracts.md
    report-schema.md
    pagespec-schema.md
    security-model.md
    clickup-integration.md
```

If building backend only first, still create the frontend folder and README placeholder for the page factory.

---

# Section 6: Hermes Context Files

Hermes should create and follow an `AGENTS.md` file at the repo root. Hermes supports project context files such as `.hermes.md`, `AGENTS.md`, and `CLAUDE.md`; use `AGENTS.md` as the main project instruction file.

## Root AGENTS.md Content

```md
# SEO Mission Control - Agent Instructions

## Product Purpose

This repository implements an internal agent-run SEO operating system. It is not a chatbot. It runs scheduled and on-demand SEO missions that collect evidence, analyze findings, validate recommendations, create ClickUp tasks, generate reports, verify fixes, and track impact over time.

## Non-Negotiable Rules

1. No evidence ID means no recommendation.
2. No validation means not ready.
3. Implemented is not verified.
4. No measured delta means impact pending.
5. Agents must output structured JSON matching schemas.
6. Provider adapters must be swappable.
7. Do not hard-code provider-specific response shapes into agents.
8. Do not expose confidential client data in logs.
9. Do not store secrets in code.
10. Prefer small, testable modules over large agent prompts.

## Architecture

- Backend: Python FastAPI
- Orchestration: LangGraph
- Operational DB: Postgres
- Analytics warehouse: BigQuery
- Raw artifacts: Cloud Storage compatible storage
- Task execution: ClickUp
- Frontend/page factory: Next.js later, with PageSpec renderer

## Coding Standards

- Use Python type hints.
- Use Pydantic for request/response/internal schemas.
- Use SQLAlchemy or SQLModel for Postgres models.
- Use Alembic for migrations.
- Write tests for every schema, validator, scoring function, and graph node.
- Do not implement unvalidated free-form agent outputs.

## Security

- Never commit secrets.
- Use environment variables and secret managers.
- Use mock data in tests.
- Avoid logging raw client data.
- Treat prompts, scoring formulas, and client data as confidential.

## Build Order

1. Data models and schemas
2. Mock provider adapters
3. Evidence normalization
4. LangGraph mission state
5. Analysis agents
6. Validators
7. Recommendation scoring
8. Report JSON generation
9. ClickUp task payload generation
10. Fix verification loop
11. PageSpec scaffolding
```

---

# Section 7: Core Domain Models

Implement Pydantic schemas first.

## Client

```python
class Client(BaseModel):
    id: str
    name: str
    default_market: str | None = None
```

## Site

```python
class Site(BaseModel):
    id: str
    client_id: str
    domain: str
    gsc_property_url: str | None = None
    ga4_property_id: str | None = None
```

## ReportRun

```python
class ReportRun(BaseModel):
    id: str
    client_id: str
    site_id: str
    current_start: date
    current_end: date
    previous_start: date
    previous_end: date
    status: Literal[
        "created",
        "collecting_evidence",
        "analyzing",
        "validating",
        "awaiting_approval",
        "approved",
        "delivered",
        "failed"
    ]
```

## EvidenceRecord

```python
class EvidenceRecord(BaseModel):
    id: str
    report_run_id: str
    source: Literal[
        "gsc",
        "ga4",
        "dataforseo",
        "bright_data",
        "brightlocal",
        "gbp",
        "firecrawl",
        "perplexity",
        "crawler",
        "manual"
    ]
    evidence_type: str
    title: str
    summary: str
    data: dict[str, Any]
    confidence: float
    collected_at: datetime
```

## Finding

```python
class Finding(BaseModel):
    id: str
    report_run_id: str
    category: Literal[
        "technical",
        "search_performance",
        "serp",
        "local",
        "content",
        "ai_visibility",
        "business_impact",
        "reporting"
    ]
    title: str
    description: str
    severity: Literal["critical", "high", "medium", "low", "info"]
    evidence_ids: list[str]
    affected_urls: list[str] = []
    confidence: float
```

## Recommendation

```python
class Recommendation(BaseModel):
    id: str
    report_run_id: str
    finding_ids: list[str]
    title: str
    action: str
    priority: Literal["P1", "P2", "P3", "P4"]
    priority_score: float
    impact: Literal["critical", "high", "medium", "low"]
    effort: Literal["high", "medium", "low"]
    owner_type: Literal["agent", "seo_manager", "developer", "owner"]
    requires_human_approval: bool
    acceptance_criteria: list[str]
    verification_method: str
    evidence_ids: list[str]
    status: Literal[
        "drafted",
        "validated",
        "needs_human_approval",
        "approved",
        "sent_to_clickup",
        "in_progress",
        "implemented",
        "awaiting_verification",
        "verified",
        "impact_measuring",
        "closed",
        "rejected"
    ]
```

## AgentHandoff

```python
class AgentHandoff(BaseModel):
    id: str
    mission_id: str
    agent_name: str
    status: Literal["completed", "failed", "partial"]
    completed_work: list[str]
    left_undone: list[str]
    evidence_ids: list[str]
    findings_created: list[str]
    recommendations_created: list[str]
    commands_executed: list[dict[str, Any]] = []
    errors: list[str] = []
    next_actions: list[str] = []
```

---

# Section 8: LangGraph Mission Architecture

## Graphs to Implement

Implement these graphs as separate modules.

### 1. BiWeeklyAuditGraph

Purpose: scheduled or manual SEO audit.

Flow:

```txt
START
-> load_client_context
-> create_report_run
-> collect_evidence_subgraph
-> normalize_evidence
-> analysis_subgraph
-> prioritization_agent
-> evidence_validator
-> report_writer
-> report_validator
-> clickup_task_payload_builder
-> approval_gate
-> finalize_report_run
-> END
```

### 2. IssueVerificationGraph

Purpose: verify work after a ClickUp task is marked implemented.

Flow:

```txt
START
-> load_recommendation
-> load_verification_method
-> collect_targeted_evidence
-> run_verification_validator
-> update_recommendation_status
-> update_clickup_task
-> write_impact_pending_record
-> END
```

### 3. ContentOpportunityGraph

Purpose: decide whether to build, refresh, merge, or ignore a page opportunity.

Flow:

```txt
START
-> load_keyword_or_local_opportunity
-> collect_serp_evidence
-> collect_existing_page_evidence
-> collect_competitor_page_evidence
-> content_gap_agent
-> landing_page_decision_agent
-> page_validation_precheck
-> create_pagespec_draft
-> human_approval_gate
-> END
```

### 4. LandingPageBuildGraph

Purpose: assemble a page from PageSpec and validate before publishing.

Flow:

```txt
START
-> load_approved_pagespec
-> generate_content_blocks
-> generate_metadata
-> generate_schema
-> run_editorial_validator
-> run_eeat_validator
-> run_doorway_risk_validator
-> render_preview
-> run_technical_page_validator
-> human_approval_gate
-> publish_or_stage
-> post_publish_verification
-> END
```

## LangGraph State

Define a central state object:

```python
class SEOMissionState(TypedDict):
    mission_id: str
    report_run_id: str | None
    client_id: str
    site_id: str
    market: str | None
    current_period: dict[str, str]
    previous_period: dict[str, str]
    evidence: list[dict]
    findings: list[dict]
    recommendations: list[dict]
    content_opportunities: list[dict]
    pagespecs: list[dict]
    validation_results: list[dict]
    clickup_payloads: list[dict]
    report_json: dict | None
    errors: list[dict]
    approval_requests: list[dict]
```

## Persistence

Use durable checkpointing for all long-running graphs. Prefer Postgres-backed persistence for production. Human approval gates must be resumable.

## Parallelism Rules

Parallelize read-only collection and validation. Do not parallelize core writes that mutate mission state unless reducers are explicit and tested.

Safe to parallelize:

- GSC data pull
- GA4 data pull
- SERP pulls
- BrightLocal pulls
- Firecrawl page reads
- independent validators

Do not parallelize without explicit merge rules:

- task creation
- recommendation status changes
- report finalization
- publishing operations
- database migrations

---

# Section 9: Agent Specs

Every agent must implement:

- name
- role
- inputs
- allowed tools
- forbidden actions
- output schema
- evidence requirements
- approval requirements
- validator assignment

## SEO Supervisor Agent

Role: Mission manager and dispatcher.

Responsibilities:

- choose which subgraphs run
- enforce budget limits
- route findings to validators
- suppress low-value work
- decide when human approval is required
- prevent task spam
- ensure outputs match schemas

Forbidden:

- inventing metrics
- making unsupported SEO claims
- creating ClickUp tasks without validated recommendations
- marking work verified without evidence

Output:

```json
{
  "routing_decisions": [],
  "suppressed_items": [],
  "required_subgraphs": [],
  "approval_requests": [],
  "budget_status": {}
}
```

## Technical SEO Agent

Role: Diagnose crawl, indexability, schema, internal linking, and technical issues.

Inputs:

- crawler evidence
- DataForSEO OnPage evidence
- Lighthouse evidence
- sitemap evidence
- GSC URL/page data

Output finding categories:

- crawlability
- indexability
- canonicalization
- internal links
- redirects
- status codes
- metadata
- schema
- performance
- AI crawler accessibility

Must prioritize by affected page value, not raw count.

## Search Performance Agent

Role: Interpret GSC and GA4 performance changes.

Inputs:

- GSC query/page data
- GA4 landing page/event data
- previous report data

Finds:

- winning queries
- losing queries
- high impressions/low CTR
- positions 4 to 15 opportunities
- query-page mismatch
- possible cannibalization
- pages losing clicks
- pages driving leads

Must distinguish measured facts from inferred attribution.

## Keyword and SERP Agent

Role: Find keyword gaps and SERP opportunities.

Inputs:

- DataForSEO Labs
- Bright Data SERPs
- DataForSEO SERPs
- GSC query data

Finds:

- keyword clusters
- intent labels
- page type recommendations
- competitor domains
- SERP feature changes
- PAA/FAQ opportunities
- local pack presence
- AI Overview presence

Output must include build/refresh/merge/ignore recommendation.

## Local SEO Agent

Role: Diagnose local SEO performance.

Inputs:

- BrightLocal rankings
- BrightLocal geo-grid
- GBP data
- DataForSEO business data
- reviews
- GSC local query patterns

Finds:

- local pack losses
- weak markets
- review velocity gaps
- GBP category gaps
- citation/NAP issues
- local page opportunities

Forbidden:

- changing GBP data without approval
- recommending local pages without local value evidence

## Content Opportunity Agent

Role: Decide what pages or content changes should exist.

Inputs:

- keyword clusters
- SERP evidence
- GSC data
- GA4 data
- Firecrawl page extracts
- competitor page extracts

Decisions:

- build new page
- refresh existing page
- merge/consolidate
- add section
- add FAQ
- no action

Must explain duplicate risk and doorway risk.

## Landing Page Builder Agent

Role: Create PageSpec drafts from approved opportunities.

Outputs:

- URL slug
- title tag
- meta description
- H1/H2 structure
- components
- content blocks
- FAQ
- schema plan
- internal links
- QA checklist

Must not publish directly in MVP.

## Editorial QA Agent

Role: Reject weak, repetitive, generic, misleading, or AI-sounding content.

Checks:

- clarity
- grammar
- repetition
- keyword stuffing
- helpfulness
- local uniqueness
- brand fit
- conversion clarity

## E-E-A-T Validator

Role: Validate experience, expertise, authoritativeness, and trust.

Checks:

- real local value
- real inventory/service relevance
- accurate NAP
- real trust signals
- no unsupported claims
- visible contact options
- no fake reviews
- transparent offer language

## Evidence Validator

Role: Validate that claims and recommendations are supported.

Rules:

- Every factual claim needs evidence IDs.
- Every recommendation needs source evidence.
- Every metric delta must match the source data.
- No hallucinated rankings.
- No unsupported causal claims.

## Report Writer Agent

Role: Generate bi-weekly report JSON from validated findings.

Must include:

- executive summary
- scorecard
- technical findings
- search performance findings
- local SEO findings
- content/page opportunities
- completed fixes
- open actions
- prioritized recommendations
- impact pending items
- appendix references

## Report QA Agent

Role: Validate final report before approval.

Checks:

- evidence coverage
- metric accuracy
- contradiction detection
- client-safe language
- dates and periods
- status accuracy

## ClickUp Sync Agent

Role: Convert validated recommendations into task payloads.

Rules:

- Do not create tasks for unvalidated recommendations.
- Group low-value issues.
- Every task needs priority, evidence, owner, due date, acceptance criteria, verification method, and report_run_id.
- Sync status changes back to Postgres.

## Fix Verification Agent

Role: Verify completed work.

Rules:

- Implemented is not verified.
- Only mark verified when evidence proves the acceptance criteria passed.
- If verification fails, create a follow-up recommendation or return task to in progress.

---

# Section 10: Scoring Models

## Recommendation Priority Score

Implement a transparent scoring function:

```txt
Priority Score =
  severity_weight
  * page_value_multiplier
  * search_visibility_multiplier
  * business_impact_multiplier
  * confidence_multiplier
  * recency_multiplier
  / effort_divisor
```

Suggested values:

```txt
Severity:
critical = 5
high = 4
medium = 3
low = 1

Page value multiplier:
money page = 2.0
high impression page = 1.5
standard page = 1.0
low value page = 0.5

Confidence:
high = 1.0
medium = 0.75
low = 0.45

Effort divisor:
low = 1.0
medium = 1.4
high = 2.0
```

## Page Opportunity Score

```txt
Page Opportunity Score =
  business_value * 0.25
  + local_relevance * 0.20
  + search_demand * 0.15
  + ranking_gap * 0.15
  + competitor_weakness * 0.10
  + conversion_potential * 0.10
  + ease_of_implementation * 0.05
  - duplicate_risk_penalty
  - doorway_risk_penalty
```

## Report Quality Score

```txt
Report Quality Score =
  evidence_coverage * 0.30
  + metric_accuracy * 0.25
  + recommendation_quality * 0.20
  + business_usefulness * 0.15
  + clarity * 0.10
```

Minimum pass: 90.

## Page Quality Score

```txt
Page Quality Score =
  content_usefulness * 0.25
  + search_intent_match * 0.15
  + eeat * 0.20
  + local_uniqueness * 0.15
  + technical_seo * 0.10
  + conversion_quality * 0.10
  + compliance_risk * 0.05
```

Minimum pass: 85.
Doorway risk must be below 20.

---

# Section 11: PageSpec Schema

Agents should build pages by producing PageSpec JSON. The developer builds the renderer.

```json
{
  "page_type": "local_inventory_landing_page",
  "status": "draft",
  "primary_keyword": "used trucks near Naperville",
  "target_location": "Naperville, IL",
  "url_slug": "/used-trucks-near-naperville-il/",
  "template": "local_inventory",
  "components": [
    {
      "type": "hero",
      "h1": "Used Trucks Near Naperville, IL",
      "subheadline": "Shop used pickup trucks available near Naperville from Example Dealer."
    },
    {
      "type": "inventory_feed",
      "filters": {
        "body_style": "truck",
        "condition": "used"
      }
    },
    {
      "type": "local_content_block",
      "heading": "Used Pickup Trucks for Naperville Drivers",
      "body": "Draft copy goes here. Must be unique, useful, and locally relevant."
    },
    {
      "type": "directions_block",
      "origin_city": "Naperville",
      "destination_dealership_id": "dealer_123"
    },
    {
      "type": "faq",
      "items": []
    },
    {
      "type": "review_block",
      "source": "google_business_profile",
      "filter": "relevant_reviews"
    }
  ],
  "seo": {
    "title_tag": "Used Trucks Near Naperville, IL | Example Dealer",
    "meta_description": "Shop used trucks near Naperville, IL. Browse used Ford, Chevy, Ram, and Toyota trucks with financing and trade-in options.",
    "canonical": "https://exampledealer.com/used-trucks-near-naperville-il/"
  },
  "schema": ["LocalBusiness", "BreadcrumbList", "FAQPage", "Vehicle"],
  "internal_links": [
    "/used-inventory/",
    "/finance/",
    "/trade-in/",
    "/service/"
  ],
  "validation": {
    "requires_human_approval": true,
    "minimum_quality_score": 85,
    "doorway_risk_max": 20
  }
}
```

---

# Section 12: Validation Contracts

## Report Validation Contract

```json
{
  "report_type": "bi_weekly_search_audit",
  "must_pass": [
    "all_metrics_have_source_ids",
    "date_ranges_are_correct",
    "current_vs_previous_deltas_are_verified",
    "recommendations_have_evidence",
    "resolved_items_are_verified",
    "unverified_items_are_not_marked_fixed",
    "no_hallucinated_findings",
    "client_safe_language",
    "lead_seo_manager_approval_required"
  ],
  "minimum_quality_score": 90
}
```

## Landing Page Validation Contract

```json
{
  "page_type": "local_inventory_landing_page",
  "must_pass": [
    "page_has_unique_local_value",
    "page_matches_search_intent",
    "page_has_real_inventory_or_service_relevance",
    "page_has_correct_nap",
    "page_has_clear_cta",
    "page_has_valid_canonical",
    "page_is_indexable",
    "schema_matches_visible_content",
    "no_fake_reviews_or_claims",
    "no_city_swap_boilerplate",
    "no_keyword_stuffing",
    "doorway_risk_score_below_20"
  ],
  "requires_human_approval": true,
  "minimum_quality_score": 85
}
```

## Recommendation Validation Contract

```json
{
  "recommendation_type": "seo_action",
  "must_pass": [
    "has_finding_ids",
    "has_evidence_ids",
    "has_priority_score",
    "has_business_or_search_rationale",
    "has_acceptance_criteria",
    "has_verification_method",
    "has_owner_type",
    "has_approval_requirement",
    "is_not_duplicate_of_existing_open_task"
  ]
}
```

---

# Section 13: ClickUp Integration

## ClickUp Role

ClickUp is the execution board. It is not the analytical source of truth.

The platform should store canonical recommendation and verification state in Postgres. ClickUp mirrors work for humans and developers.

## Task Creation Rules

Create ClickUp tasks only for:

- validated P1/P2 recommendations
- approved page briefs
- approved report review tasks
- verification tasks
- grouped low-risk P3 batch tasks

Do not create tasks for every raw issue.

## Recommended Statuses

```txt
Backlog
Agent Scoping
Evidence Collection
Recommendation Drafted
Needs Human Approval
Approved
Assigned to Developer
In Progress
Implemented
Awaiting Verification
Verified
Impact Measuring
Closed
Rejected
```

## Required Custom Fields

- Client
- Domain
- Mission ID
- Report Run ID
- Evidence IDs
- Agent Owner
- Human Owner
- Implementation Owner
- Priority Score
- Impact
- Effort
- Confidence
- Validation Status
- Approval Required
- Page Type
- Target Keyword
- Target Location
- Affected URLs
- Published URL
- Implemented At
- Verified At
- Result Delta

## Task Payload Shape

```json
{
  "name": "P1 - Remove noindex from service appointment page",
  "description": "Evidence-backed issue and implementation instructions go here.",
  "priority": 1,
  "assignees": ["developer_user_id"],
  "due_date": "2026-05-15",
  "custom_fields": {
    "mission_id": "mission_123",
    "report_run_id": "report_123",
    "evidence_ids": "crawl_884,gsc_page_loss_112",
    "priority_score": 93,
    "validation_status": "validated",
    "verification_method": "recrawl_url_and_check_meta_robots"
  },
  "checklist": [
    "Affected URLs attached",
    "Expected behavior defined",
    "Acceptance criteria defined",
    "Verification method defined"
  ]
}
```

## Webhook Behavior

When ClickUp status changes to Implemented:

1. Receive webhook.
2. Verify signature.
3. Deduplicate by webhook_id + history_item_id.
4. Find matching recommendation_id.
5. Start IssueVerificationGraph.
6. Update ClickUp with pass/fail result.

---

# Section 14: Report JSON Shape

```json
{
  "report_type": "bi_weekly_search_audit",
  "client": {
    "name": "Example Dealer",
    "domain": "exampledealer.com",
    "market": "Chicago, IL"
  },
  "period": {
    "current_start": "2026-04-28",
    "current_end": "2026-05-11",
    "previous_start": "2026-04-14",
    "previous_end": "2026-04-27"
  },
  "scorecard": {
    "overall_search_health": 78,
    "technical_health": 82,
    "search_performance": 74,
    "local_visibility": 69,
    "content_opportunity": 81,
    "ai_visibility": 52,
    "business_impact": 77
  },
  "executive_summary": {
    "headline": "Organic visibility improved, but local pack visibility remains weak.",
    "wins": [],
    "risks": [],
    "top_actions": []
  },
  "findings": {
    "technical": [],
    "search_performance": [],
    "serp": [],
    "local": [],
    "content": [],
    "ai_visibility": [],
    "business_impact": []
  },
  "recommendations": [],
  "completed_work": [],
  "verified_fixes": [],
  "impact_pending": [],
  "appendix": {
    "technical_issues_csv": null,
    "keyword_rankings_csv": null,
    "gsc_queries_csv": null
  }
}
```

---

# Section 15: Provider Adapter Interfaces

Build adapters with stable internal interfaces.

## Search Console Adapter

```python
class GSCProvider(Protocol):
    async def get_query_performance(self, site_id: str, start: date, end: date) -> list[EvidenceRecord]: ...
    async def get_page_performance(self, site_id: str, start: date, end: date) -> list[EvidenceRecord]: ...
```

## GA4 Adapter

```python
class GA4Provider(Protocol):
    async def get_landing_page_outcomes(self, site_id: str, start: date, end: date) -> list[EvidenceRecord]: ...
```

## SERP Adapter

```python
class LiveSerpProvider(Protocol):
    async def search(self, query: str, location: str, device: str, language: str) -> EvidenceRecord: ...
```

## DataForSEO Adapter

```python
class SEODataProvider(Protocol):
    async def get_keyword_metrics(self, keywords: list[str], location: str) -> list[EvidenceRecord]: ...
    async def get_serp_competitors(self, keywords: list[str], location: str) -> list[EvidenceRecord]: ...
    async def get_onpage_issues(self, domain: str) -> list[EvidenceRecord]: ...
```

## BrightLocal Adapter

```python
class LocalSEOProvider(Protocol):
    async def get_local_rankings(self, client_id: str, start: date, end: date) -> list[EvidenceRecord]: ...
    async def get_reviews_summary(self, client_id: str, start: date, end: date) -> list[EvidenceRecord]: ...
```

## Firecrawl Adapter

```python
class PageExtractionProvider(Protocol):
    async def scrape_page(self, url: str) -> EvidenceRecord: ...
    async def crawl_section(self, base_url: str, include_paths: list[str]) -> list[EvidenceRecord]: ...
```

---

# Section 16: Security and Confidentiality

## Principle

Contractors should be able to build the system without seeing confidential client data, scoring formulas, prompts, SEO memory, or production credentials.

## Implementation Requirements

- Use mock data for local development.
- Use separate dev/staging/prod environments.
- Use secret manager for credentials.
- Use least-privilege service accounts.
- Avoid logging raw client data.
- Separate confidential prompts/scoring from UI code.
- Keep provider keys out of frontend code.
- Use API boundaries between frontend and data stores.
- Do not give contractors direct BigQuery, GSC, GA4, production CMS, or production ClickUp admin access unless explicitly approved.

## Data Classification

Level 0: Public
Level 1: Internal
Level 2: Confidential
Level 3: Restricted
Level 4: Crown Jewels

Crown Jewels include:

- full supervisor prompt
- validation contracts
- scoring formulas
- client performance history
- SEO memory
- production credentials
- provider API keys

---

# Section 17: Hermes Execution Prompt

Paste the following into Hermes as the main mission prompt.

```txt
You are the senior agentic coding engineer for this project. Build the MVP foundation for SEO Mission Control, an internal agent-run SEO operating system.

Read and follow the repository AGENTS.md. If it does not exist, create it from the mission brief. Do not build a chatbot. Build a closed-loop SEO operations engine.

Primary outcome:
Create a working backend foundation that can run a bi-weekly SEO audit mission for one client/site/market using mock providers first, then optional real provider adapters. The mission must collect evidence, create findings, validate them, generate recommendations, create ClickUp-ready task payloads, produce report JSON, and support fix verification.

Hard rules:
1. No evidence ID means no recommendation.
2. No validation means not ready.
3. Implemented is not verified.
4. No measured delta means impact pending.
5. Every agent output must be structured JSON.
6. Every recommendation must include evidence IDs, acceptance criteria, and a verification method.
7. Every ClickUp task must be derived from a validated recommendation.
8. Do not build the dashboard first.
9. Use mock data in tests.
10. Do not commit secrets.

Build order:
1. Create repo structure.
2. Create Pydantic schemas for Client, Site, ReportRun, EvidenceRecord, Finding, Recommendation, AgentHandoff, PageSpec, ValidationResult, ClickUpTaskPayload.
3. Create Postgres models and Alembic migrations.
4. Create provider adapter protocols and mock implementations.
5. Create evidence normalization service.
6. Create scoring functions for recommendation priority, page opportunity, report quality, and page quality.
7. Create LangGraph state and BiWeeklyAuditGraph.
8. Implement agents as structured functions first, with LLM integration behind an interface.
9. Implement validators as deterministic checks where possible and LLM-backed only when needed.
10. Implement report JSON generation.
11. Implement ClickUp task payload generation, but do not require live ClickUp credentials for tests.
12. Implement IssueVerificationGraph for verifying implemented tasks.
13. Add PageSpec schema and landing page validation contracts.
14. Add tests for schemas, scoring, validators, graph flow, report JSON, and ClickUp payloads.
15. Add README instructions and example CLI commands.

Acceptance criteria:
- Tests pass.
- A local command can run a demo bi-weekly audit with mock data.
- The demo outputs report JSON.
- The demo outputs validated recommendations.
- The demo outputs ClickUp-ready task payloads.
- At least one recommendation can be moved through implemented -> awaiting verification -> verified or failed using mock verification evidence.
- The system distinguishes implemented from verified.
- The system stores or simulates evidence IDs for every finding and recommendation.
- The code is modular enough to swap mock providers for real providers.

Do not overbuild. Favor a narrow working loop over broad incomplete modules.

After each major milestone, output a structured handoff with:
- completed work
- files changed
- commands run
- tests passed/failed
- unresolved issues
- next recommended step
```

---

# Section 18: Milestone Plan for Hermes

## Milestone 1: Foundation

Deliver:

- repo structure
- AGENTS.md
- README
- pyproject
- docker-compose for Postgres
- app config
- test setup

Acceptance:

- app imports
- tests run
- environment config documented

## Milestone 2: Schemas and Database

Deliver:

- Pydantic schemas
- database models
- migrations
- seed demo client/site

Acceptance:

- migrations run
- schema tests pass

## Milestone 3: Mock Providers and Evidence

Deliver:

- mock GSC
- mock GA4
- mock SERP
- mock BrightLocal
- mock crawler
- evidence records

Acceptance:

- demo evidence collected with stable IDs

## Milestone 4: Agents and Validators

Deliver:

- technical SEO agent
- search performance agent
- keyword/SERP agent
- local SEO agent
- evidence validator
- prioritization agent

Acceptance:

- findings created
- invalid findings rejected
- recommendations include evidence IDs and verification methods

## Milestone 5: BiWeeklyAuditGraph

Deliver:

- LangGraph state
- graph nodes
- graph run command
- checkpoint integration placeholder

Acceptance:

- one command runs full audit with mock data

## Milestone 6: Report and ClickUp Payloads

Deliver:

- report JSON generator
- report validator
- ClickUp task payload builder
- task de-duplication by recommendation ID

Acceptance:

- report JSON validates
- ClickUp payloads include custom fields and checklists

## Milestone 7: Fix Verification

Deliver:

- IssueVerificationGraph
- mock verification inputs
- recommendation status transitions

Acceptance:

- implemented is not verified
- verification pass updates status to verified
- verification fail creates follow-up output

## Milestone 8: PageSpec Foundation

Deliver:

- PageSpec schema
- landing page validation contract
- doorway risk validator stub
- E-E-A-T validator stub

Acceptance:

- sample PageSpec validates
- low-quality PageSpec fails validation

---

# Section 19: Quality Gates

Before Hermes considers the build complete, it must pass:

- unit tests
- schema validation tests
- scoring tests
- report JSON validation
- ClickUp payload validation
- recommendation validation
- issue verification test
- PageSpec validation test
- no secrets in repository
- README runnable instructions

---

# Section 20: Final Deliverables

Hermes should produce:

1. Working codebase
2. README
3. AGENTS.md
4. Database migrations
5. Mock data
6. Demo audit command
7. Report JSON sample
8. ClickUp payload sample
9. PageSpec sample
10. Test suite
11. Implementation notes
12. Known limitations
13. Next-phase roadmap

---

# Section 21: Next-Phase Roadmap

After MVP:

1. Add real GSC BigQuery adapter.
2. Add real GA4 BigQuery adapter.
3. Add real DataForSEO adapter.
4. Add real Bright Data adapter.
5. Add real BrightLocal adapter.
6. Add real Firecrawl adapter.
7. Add ClickUp live API sync.
8. Add front-end mission control UI.
9. Add report PDF renderer.
10. Add PageSpec preview renderer.
11. Add CMS staging/publishing adapter.
12. Add SEO memory and impact learning.
13. Add AI visibility graph.
14. Add backlink/citation graph.
15. Add multi-client scheduler.

