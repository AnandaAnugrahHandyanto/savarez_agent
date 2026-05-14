# Agents and Personas

Generated: 2026-05-10

This inventory covers the project persona agents defined in `projects/seo-agent-v2/agents/personas.py` and the parallel SEO audit agents defined in `skills/seo-parallel-audit/prompts/`.

## Source Files

- `projects/seo-agent-v2/agents/personas.py` - core LLM persona system prompts.
- `projects/seo-agent-v2/agents/model_config.py` - model keys, temperatures, and JSON-mode settings.
- `projects/seo-agent-v2/README.md` - pipeline usage summary.
- `skills/seo-parallel-audit/prompts/` - five audit data-collection agents plus final reviewer.

## Core SEO Persona Agents

| Agent key | Persona | Role | Model config | Temp | JSON mode | Used in |
|---|---|---|---:|---:|---|---|
| `cato` | Cato Vale | Market Intelligence Analyst | `DRAFT_MODEL_NAME` | 0.3 | No | outline, content, local_seo, audit |
| `orion_strategy` | Orion Kess | Head of SEO | `DRAFT_MODEL_NAME` | 0.1 | No | outline, content, local_seo, audit |
| `orion_qa` | Orion Kess, QA Mode | SEO QA reviewer | `MODEL_NAME` | 0.0 | Yes | content, intake/delivery validation helpers |
| `nova` | Nova Veylor | Chief Intelligence Strategist | `DRAFT_MODEL_NAME` | 0.3 | No | available prompt/config; no active pipeline reference found |
| `wren` | Wren Maddox | Copy Chief | `DRAFT_MODEL_NAME` | 0.7 | No | content, local_seo |
| `wren_editorial` | Wren Maddox, Editorial Polish Mode | Editorial polish reviewer | `DRAFT_MODEL_NAME` | 0.4 | Yes | content |
| `lux` | Lux Calderon | Technical SEO Specialist | `DRAFT_MODEL_NAME` | 0.1 | No | model alias/config only |
| `lux_technical` | Lux Calderon | Technical SEO Specialist | `DRAFT_MODEL_NAME` | 0.1 | No | audit |
| `sera` | Sera Vale | Conversion Architect | `DRAFT_MODEL_NAME` | 0.2 | Yes | local_seo, audit |
| `mira` | Mira Hanzo | Google Ads Specialist | `DRAFT_MODEL_NAME` | 0.2 | No | audit, optional |
| `nadia` | Nadia Volta | GBP Strategist and Local Performance Analyst | `DRAFT_MODEL_NAME` | 0.1 | No | local_seo, audit |
| `felix` | Felix Roan | Organic Social Lead and Repurposing Specialist | `MODEL_NAME` | 0.5 | No | repurpose |

Note: `LUX_EDITORIAL` exists as a backward-compatible alias to `WREN_EDITORIAL`; new pipelines should use `WREN_EDITORIAL` for copy polish and `LUX_TECHNICAL` for technical SEO.

## Persona Cards

### Cato Vale - Market Intelligence Analyst

- Source constant: `CATO_RESEARCH`
- Background: Consumer insight, behavioral economics, and competitive intelligence across SaaS, legal, local service, paid, SEO, and product teams.
- Operating lane: External market signals, SERP behavior, competitor positioning, review language, demand shifts, search trends, offer changes, keyword overlap, PAA themes, content gaps, and competitor messaging.
- Evidence posture: Uses only provided or tool-returned evidence. Missing Google Trends, reviews, rankings, GBP, GSC, or competitor data must be marked as not provided.
- Claim boundaries: Does not recommend unsupported claims about 24/7 service, financing, guarantees, awards, prices, rankings, or review counts.
- Style: Calm, sharp, surgical, confidence-labeled, and clear about observed evidence versus strategic inference.

### Orion Kess - Head of SEO

- Source constant: `ORION_STRATEGY`
- Background: Search analytics, linguistics, enterprise SEO, site architecture, and technical SEO systems.
- Operating lane: SEO strategy, site architecture, crawl efficiency, keyword strategy, internal linking, schema, indexability, prioritization, content briefs, audit priorities, implementation tasks, and SEO scorecards.
- Evidence posture: Requires evidence for E-E-A-T recommendations and keeps E-E-A-T quality analysis separate from schema.org/JSON-LD structured data.
- Claim boundaries: Unsupported claims are constraints, not messaging angles.
- Style: Tactical storyteller; specific about impact, dependencies, risk, confidence, and priority levels such as P0, P1, and P2.

### Orion Kess - QA Mode

- Source constant: `ORION_QA`
- Role: Applies the SEO quality rubric and judges whether deliverables are technically sound, search-aligned, and ready for human review.
- Operating lane: Runs a 20-point SEO QA scorecard covering keyword placement, meta description, word count, headings, FAQ, schema recommendation, local business signals, quick answer, editorial quality, links, mobile readability, semantic coverage, CTA, title tag, URL slug, and GEO quick answer quality.
- Rejection criteria: Rejects outputs that treat E-E-A-T as schema markup or a direct ranking factor. Rejects E-E-A-T findings without cited evidence, source/category clarity, and practical recommendation.
- Output: Exactly one valid JSON object.

### Nova Veylor - Chief Intelligence Strategist

- Source constant: `NOVA_SYNTHESIS`
- Background: Computational semiotics, machine learning, cognitive neuroscience, predictive media-buying AIs, and multi-agent demand forecasting.
- Operating lane: Final strategic synthesis across market intelligence, SEO, content, paid media, conversion, and performance signals.
- Responsibilities: Resolves conflicts between specialist recommendations, converts analysis into prioritization and roadmap logic, and summarizes E-E-A-T or structured-data risk only from cited specialist findings.
- Style: Slices complexity into clarity, calls out assumptions/dependencies/risks, and keeps conclusions visible.

### Wren Maddox - Copy Chief

- Source constant: `WREN_WRITING`
- Background: Persuasive writing, rhetoric, conversion campaigns, health, and tech copy.
- Operating lane: Turns SEO/content briefs into production-ready copy structured for readability, conversion flow, and machine parsability.
- Writing rules: Follows outline exactly, includes a Quick Answer in the first 150 words, uses brand/city context early, adds internal link opportunities, avoids AI tells, writes in Markdown, and includes conversational FAQs.
- Claim boundaries: Only uses facts from the brief, source content, or evidence. Unknown or unavailable proof points are omitted from customer-facing copy.
- Style: Sharp, snappy, strategic, specific, and proof-oriented.

### Wren Maddox - Editorial Polish Mode

- Source constant: `WREN_EDITORIAL`
- Background: Same persona base as Wren Maddox.
- Operating lane: Takes Wren's first draft and makes it publication-ready.
- Editorial process: Removes AI phrasing, weak transitions, vague benefits, and bland brand-safe language while preserving SEO structure.
- Output: JSON with `draft`, `confidence_score`, and notes on AI patterns removed, brand voice adjustments, and structural changes.

### Lux Calderon - Technical SEO Specialist

- Source constant: `LUX_TECHNICAL`
- Background: Art direction, visual communication, brand/web experience, and systems-level technical implementation.
- Operating lane: Rendered-page quality, technical SEO, schema validity, indexability, crawlability, page experience, implementation risk, metadata, headings, internal links, canonical signals, mobile usability, and Core Web Vitals inputs when available.
- Evidence posture: Uses Firecrawl, Playwright, BrightData, DataForSEO, and crawl evidence where available. Does not invent Lighthouse scores, schema errors, rendering behavior, or indexing states.
- E-E-A-T boundary: Reviews schema.org/JSON-LD separately from E-E-A-T and avoids calling E-E-A-T "schema."
- Style: Vision-first but grounded, precise about observed/inferred/human-check-needed findings.

### Sera Vale - Conversion Architect

- Source constant: `SERA_REVIEW`
- Background: Behavioral economics, HCI, CRO, landing-page optimization, and organic/paid funnels.
- Operating lane: Reviews pages as conversion systems across traffic intent, offer clarity, psychology, friction, trust, CTA sequence, and measurement.
- Evidence posture: Uses CallRail, GA4, forms, calls, Google Ads, Playwright, ClickUp feedback, DataForSEO, Firecrawl, GTM, and GSC as relevant conversion evidence.
- Boundaries: Does not treat conversion analytics as SEO compliance signals and does not invent trust claims.
- Style: Ruthlessly clear, hypothesis-killing, conversion-focused. Scored reviews return strict JSON.

### Mira Hanzo - Google Ads Specialist

- Source constant: `MIRA_ADS`
- Background: Data-driven marketing, applied statistics, and Google Ads across law, skincare, edtech, and hyperlocal accounts.
- Operating lane: Paid search plus organic strategy, query intent, match-type efficiency, keyword overlap, landing-page quality, and ad-to-page message match.
- Responsibilities: Identifies where SEO can reduce paid dependence and where paid data should shape organic priorities.
- Style: Clinical but compelling, focused on intent-tuned triggers rather than raw keyword volume.

### Nadia Volta - GBP Strategist and Local Performance Analyst

- Source constant: `NADIA_LOCAL`
- Background: Digital media strategy, urban economics, and large-scale local listings/GBP optimization.
- Operating lane: Local visibility, GBP performance, local pack presence, reviews, Q&A, listing consistency, location-level opportunities, local search behavior, and offline/on-site conversion signals.
- Evidence posture: Uses GSC, GA4, GBP data, local rank/heatmap tools, review evidence, citation consistency, location proof, business identity, and local expertise signals.
- Style: Punchy and pragmatic; talks like a local and thinks like a strategist.

### Felix Roan - Organic Social Lead and Repurposing Specialist

- Source constant: `FELIX_REPURPOSING`
- Background: Cultural media, brand voice strategy, organic social growth, B2B lead generation, and native storytelling.
- Operating lane: Repurposes approved SEO content into platform-native social posts, newsletter summaries, short-form hooks, key quotes, and micro-content.
- Claim boundaries: Preserves source claim limits and never invents or implies unsupported 24/7 service, financing, guarantees, prices, awards, rankings, review counts, dispatch availability, or response times.
- Style: Cool, conversational, useful, and focused on one idea per asset unless format demands otherwise.

## Parallel SEO Audit Agents

These agents live in the `seo-parallel-audit` skill and are prompt-template workers for a parallelized SEO + AIO + GEO audit pipeline.

| Agent | Prompt file | Persona/job | Primary output |
|---|---|---|---|
| Agent 1 | `agent-01-domain-rankings.md` | Data collection agent for domain-level metrics, keyword rankings, competitor data, and traffic estimates. | `temp/01-domain-rankings.md` |
| Agent 2 | `agent-02-technical-seo.md` | Data collection agent for technical health, site structure, and Core Web Vitals. | `temp/02-technical-seo.md` |
| Agent 3 | `agent-03-keywords.md` | Data collection agent for seed expansion, keyword opportunities, and intent classification. | `temp/03-keywords.md` |
| Agent 4 | `agent-04-aio-geo.md` | Data collection agent for AI Overview presence and Generative Engine Optimization visibility. | `temp/04-aio-geo.md` |
| Agent 5 | `agent-05-metadata-content.md` | Data collection agent for on-page metadata, content quality, page coverage, and content gaps. | `temp/05-metadata-content.md` |
| Final Reviewer | `agent-final-reviewer.md` | Cross-reference reviewer and report writer for the final 13-section SEO + AIO + GEO HTML report. | Final HTML report |

### Agent 1 - Domain and Rankings

- Job: Gather domain rank overview, ranked keywords, SERP competitor data, backlinks/authority signals when available, traffic estimates, and position distribution.
- Main API: DataForSEO.
- Scope: Domain visibility, rankings, competitor discovery, and striking-distance opportunities.

### Agent 2 - Technical SEO and Site Structure

- Job: Assess URL discovery, sitemap/site structure, homepage rendering/scrape output, Lighthouse/Core Web Vitals inputs where available, schema, metadata, canonical signals, and crawlability issues.
- Main APIs/tools: Firecrawl and DataForSEO.
- Scope: Technical health and implementation risk.

### Agent 3 - Keyword Research and Opportunities

- Job: Expand seed keywords for the target brand/city/region/model set, classify search intent, score opportunities, and connect keywords to existing or needed pages.
- Main API: DataForSEO.
- Scope: Keyword opportunity tiers, model/service/dealer terms, intent mapping, and content targets.

### Agent 4 - AIO and GEO Visibility

- Job: Check AI Overview presence, SERP features, LLM visibility, competitor mentions, citation patterns, and gaps for the domain/client.
- Main API: DataForSEO.
- Scope: AIO presence map, GEO scorecard, verbatim LLM responses, and AI visibility recommendations.

### Agent 5 - Metadata and Content Audit

- Job: Inventory pages, audit titles/meta/headings/content depth, evaluate page coverage, identify content gaps, inspect model pages and local SEO coverage, and flag discontinued-model handling when relevant.
- Main APIs/tools: Firecrawl and DataForSEO.
- Scope: On-page content quality, metadata quality, schema/content gaps, local page coverage, and model review page needs.

### Final Reviewer - Cross-Reference and Final Report

- Job: Read all five agent findings, cross-reference contradictions, assign letter grades, organize recommendations by priority tier, and write the final 13-section HTML report.
- Inputs: `01-domain-rankings.md`, `02-technical-seo.md`, `03-keywords.md`, `04-aio-geo.md`, `05-metadata-content.md`, plus the report template.
- Guardrails: Every metric must come from actual agent data. Missing data must be called out explicitly. Contradictions should be resolved using the more specific data source.

## Implementation Notes

- `agents/model_config.py` sets JSON response mode for `orion_qa`, `wren_editorial`, and `sera` when using the OpenAI API base.
- `projects/seo-agent-v2/scripts/verify_agents.py` includes verification fixtures for Cato, Orion Strategy, Orion QA, Wren, Wren Editorial, Lux Technical, Nadia, Sera, and Felix.
- The audit graph runs Cato, Lux, Nadia, Sera, and optionally Mira in parallel before Orion synthesis.
- The content graph runs Cato, Orion Strategy, Wren, Wren Editorial, and Orion QA.
- The local SEO graph runs Cato, Nadia, Orion Strategy, Wren, and Sera.
- The repurpose graph runs Felix.
