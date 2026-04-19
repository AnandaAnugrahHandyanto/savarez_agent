# Finland SME AI Operations Dashboard — Detailed Customer Playbook (V3)

Prepared for: Wael Helmi  
Date: 2026-04-15  
Method: homepage + secondary-page browsing (automated fetch), then customer-specific solution architecture.

## What this version adds
- Multi-page depth: one full technical page per customer (15 customers).
- Per-customer architecture: APIs, AI pipeline, data model, security, and implementation plan.
- Budgeting refined by SME constraints (Starter / Growth / Pro) with implementation and monthly run-cost breakdown.

## Budget framework (SME-realistic)
- **Starter:** setup €4,500–€8,000, monthly €900–€1,600
- **Growth:** setup €9,000–€15,000, monthly €1,700–€2,900
- **Pro:** setup €16,000–€26,000, monthly €3,200–€5,200

## Table of Contents
1. [Varjo](#varjo)
2. [Oura](#oura)
3. [HappyOrNot](#happyornot)
4. [Haltian](#haltian)
5. [Sulapac](#sulapac)
6. [Vapaus](#vapaus)
7. [Swappie](#swappie)
8. [Gubbe](#gubbe)
9. [Freska](#freska)
10. [Fiksuruoka](#fiksuruoka)
11. [Framery](#framery)
12. [IQM Quantum Computers](#iqm-quantum-computers)
13. [Supermetrics](#supermetrics)
14. [Lyyti](#lyyti)
15. [Genelec](#genelec)


---

## 1. Varjo

**Sector:** XR Hardware & Software  
**Company size band:** Scale-up / Mid-market  
**Primary dashboard objective:** Sales Pipeline + Demo Operations  
**Recommended package:** Pro (pro)  

### Site research signals
- Site URL: https://varjo.com
- Text signal: Military-Grade VR/XR Headsets and Solutions for Simulation Training – Varjo window.dataLayer = window.dataLayer || []; function gtag() { dataLayer.push(arguments) } gtag("consent", "default", { ad_personalization: "denied", ad_storage: "denied", ad_user_data: ...
- Secondary page scanned: https://varjo.com/about
- Secondary text signal: About Us | Varjo | World Leader in Industrial-Grade VR and XR window.dataLayer = window.dataLayer || []; function gtag() { dataLayer.push(arguments) } gtag("consent", "default", { ad_personalization: "denied", ad_storage...

### Pain points this dashboard should solve
- Long B2B sales cycle with many demo touchpoints
- Demo requests and follow-up notes fragmented across tools
- Technical questions from prospects routed manually

### User roles
- Sales Director
- Solutions Engineer
- Partner Manager
- Support Lead

### Dashboard module blueprint
| Module | Purpose | Data Sources | AI Capability |
|---|---|---|---|
| Deal Flow Board | Track lead stage velocity and stuck opportunities | CRM, forms, meeting logs | LLM-generated next-best-action per deal |
| Demo Command Center | Plan demos, owners, and prep assets | Calendar, CRM, docs | AI-generated demo brief from account history |
| Technical Question Triage | Classify incoming pre-sales questions | Email/helpdesk | AI routing + draft answers with source links |
| Executive KPI Wall | Monitor conversion, cycle time, forecast risk | CRM analytics | Anomaly detection for stage drop-off |

### API integration map (to validate in discovery week)
- CRM API (HubSpot/Salesforce)
- Calendar API
- Support API
- Product docs index

### AI/ML architecture
- **LLM layer:** Claude/OpenAI/Gemini class model for reasoning, summarization, drafting
- **RAG layer:** document ingestion -> chunking -> embeddings -> vector index -> citation-grounded answers
- **Orchestration:** workflow engine for triggers, escalations, SLA alerts, and human-in-the-loop approvals
- **Guardrails:** policy prompts, PII masking, allowlisted actions, audit logs
- **Evaluation:** weekly precision/recall on routing, answer quality QA, deflection and resolution KPIs

### Data model (core entities)
- `account`
- `opportunity`
- `demo_event`
- `technical_question`
- `owner`
- `partner`

### Workflow automation examples
- demo prep brief generation
- meeting-summary-to-CRM writeback
- escalation alerts for stalled opportunities

### Security, compliance, and reliability
- RBAC and environment-level tenant isolation
- Encrypted data at rest and in transit
- Full audit logs for AI suggestions and human overrides
- Regional hosting and retention policy configured per client contract
- Fallback mode: if AI is unavailable, route to deterministic workflow and manual queue

### Implementation plan
- **Week 1:** discovery, API access checklist, baseline KPI definitions
- **Week 2:** connector setup, data model + ingestion pipelines
- **Week 3:** dashboard UI + role-based views
- **Week 4:** AI copilots + routing rules + red-team QA
- **Week 5:** pilot with selected team, tuning and governance
- **Week 6-7:** executive reporting layer, SLA optimization, handover

### Budget breakdown
- Setup range: €16 000 - €26 000 (midpoint €21 000)
- Monthly service range: €3 200 - €5 200 (midpoint €4 200)
- Estimated monthly AI token cost (@8,750,000 tokens): €4.08
- Estimated monthly delivery cost (infra + ops + AI): €2 454.08
- Expected monthly gross margin at midpoint: €1 745.92

### KPI targets (first 90 days)
- 20-35% reduction in repetitive support workload
- 25-40% faster triage/first-response in targeted workflows
- 10-20% improvement in SLA compliance on prioritized queues
- Weekly leadership visibility with one-page KPI narrative

---

## 2. Oura

**Sector:** Wearable Health Tech  
**Company size band:** Scale-up / Mid-market  
**Primary dashboard objective:** Subscription Health + Customer Success  
**Recommended package:** Pro (pro)  

### Site research signals
- Site URL: https://ouraring.com
- Text signal: Oura Ring. Smart Ring for Fitness, Stress, Sleep & Health. @font-face { font-family: 'AkkuratLL'; font-style: normal; font-weight: 400; src: url('/assets/fonts/AkkuratLL-Regular.woff2') format('woff2'); } @font-face { font-family: 'AkkuratLL'; font-style: norm...
- Secondary page: no reliable auto-scrape; roadmap built from homepage signal + sector model.

### Pain points this dashboard should solve
- Subscription churn signals spread across billing, support, and product data
- Customer success teams react late to cancellation intent
- High volume of repetitive support queries

### User roles
- Head of CX
- Retention Manager
- Support Ops
- Data Analyst

### Dashboard module blueprint
| Module | Purpose | Data Sources | AI Capability |
|---|---|---|---|
| Subscription Health | Cohorts by renewal risk and reason codes | Billing + ecommerce + app analytics | Predictive churn scoring and explanations |
| Retention Playbooks | Trigger interventions based on risk level | CRM, messaging, support | AI-recommended offer/action by segment |
| Support Deflection Hub | Knowledge answer and ticket deflection tracking | Helpdesk + knowledge base | RAG assistant with guardrails |
| Voice of Customer | Themes and sentiment from tickets/reviews | Helpdesk, reviews, surveys | Topic clustering and sentiment trend detection |

### API integration map (to validate in discovery week)
- Ecommerce API
- Billing/subscription API
- Support API
- Analytics API

### AI/ML architecture
- **LLM layer:** Claude/OpenAI/Gemini class model for reasoning, summarization, drafting
- **RAG layer:** document ingestion -> chunking -> embeddings -> vector index -> citation-grounded answers
- **Orchestration:** workflow engine for triggers, escalations, SLA alerts, and human-in-the-loop approvals
- **Guardrails:** policy prompts, PII masking, allowlisted actions, audit logs
- **Evaluation:** weekly precision/recall on routing, answer quality QA, deflection and resolution KPIs

### Data model (core entities)
- `customer`
- `subscription`
- `renewal`
- `ticket`
- `risk_score`
- `intervention`

### Workflow automation examples
- at-risk cohort alerts
- ticket auto-summarization
- retention campaign draft copy

### Security, compliance, and reliability
- RBAC and environment-level tenant isolation
- Encrypted data at rest and in transit
- Full audit logs for AI suggestions and human overrides
- Regional hosting and retention policy configured per client contract
- Fallback mode: if AI is unavailable, route to deterministic workflow and manual queue

### Implementation plan
- **Week 1:** discovery, API access checklist, baseline KPI definitions
- **Week 2:** connector setup, data model + ingestion pipelines
- **Week 3:** dashboard UI + role-based views
- **Week 4:** AI copilots + routing rules + red-team QA
- **Week 5:** pilot with selected team, tuning and governance
- **Week 6-7:** executive reporting layer, SLA optimization, handover

### Budget breakdown
- Setup range: €16 000 - €26 000 (midpoint €21 000)
- Monthly service range: €3 200 - €5 200 (midpoint €4 200)
- Estimated monthly AI token cost (@8,750,000 tokens): €4.08
- Estimated monthly delivery cost (infra + ops + AI): €2 454.08
- Expected monthly gross margin at midpoint: €1 745.92

### KPI targets (first 90 days)
- 20-35% reduction in repetitive support workload
- 25-40% faster triage/first-response in targeted workflows
- 10-20% improvement in SLA compliance on prioritized queues
- Weekly leadership visibility with one-page KPI narrative

---

## 3. HappyOrNot

**Sector:** Customer Experience SaaS  
**Company size band:** SME / Mid-market  
**Primary dashboard objective:** Client Feedback Intelligence  
**Recommended package:** Growth (growth)  

### Site research signals
- Site URL: https://www.happy-or-not.com/en/
- Text signal: Customer Feedback Platform That Works | HappyOrNot® {"@context":"https://schema.org","@graph":[{"@type":"WebPage","@id":"https://www.happy-or-not.com/en/","url":"https://www.happy-or-not.com/en/","name":"Customer Feedback Platform That Works | HappyOrNot®","is...
- Secondary page scanned: https://www.happy-or-not.com/about
- Secondary text signal: The Pioneers of Smiley-Faced Feedback Solution | HappyOrNot® {"@context":"https://schema.org","@graph":[{"@type":["WebPage","AboutPage"],"@id":"https://www.happy-or-not.com/en/about-us/","url":"https://www.happy-or-not.c...

### Pain points this dashboard should solve
- Expansion opportunities hidden in product usage
- Churn indicators discovered too late
- Support and CSM data live in separate systems

### User roles
- VP Customer Success
- CSM
- Support Manager
- RevOps

### Dashboard module blueprint
| Module | Purpose | Data Sources | AI Capability |
|---|---|---|---|
| Account Health Radar | Unified health score per account | Product events, CRM, support | Explainable health scoring |
| Expansion Finder | Spot cross-sell/upsell timing | Usage + contract data | AI signals for expansion intent |
| Churn Early Warning | Detect risk with confidence intervals | Usage decline, ticket sentiment | Risk forecasting and playbook suggestions |
| QBR Builder | Generate account summary packs | CRM + analytics + support | Auto-generated QBR narrative and charts |

### API integration map (to validate in discovery week)
- CRM API
- Product usage API
- Support API
- Billing API

### AI/ML architecture
- **LLM layer:** Claude/OpenAI/Gemini class model for reasoning, summarization, drafting
- **RAG layer:** document ingestion -> chunking -> embeddings -> vector index -> citation-grounded answers
- **Orchestration:** workflow engine for triggers, escalations, SLA alerts, and human-in-the-loop approvals
- **Guardrails:** policy prompts, PII masking, allowlisted actions, audit logs
- **Evaluation:** weekly precision/recall on routing, answer quality QA, deflection and resolution KPIs

### Data model (core entities)
- `workspace`
- `account`
- `feature_event`
- `contract`
- `health_score`
- `renewal`

### Workflow automation examples
- weekly CSM briefing
- renewal risk alerts
- auto-drafted QBR decks

### Security, compliance, and reliability
- RBAC and environment-level tenant isolation
- Encrypted data at rest and in transit
- Full audit logs for AI suggestions and human overrides
- Regional hosting and retention policy configured per client contract
- Fallback mode: if AI is unavailable, route to deterministic workflow and manual queue

### Implementation plan
- **Week 1:** discovery, API access checklist, baseline KPI definitions
- **Week 2:** connector setup, data model + ingestion pipelines
- **Week 3:** dashboard UI + role-based views
- **Week 4:** AI copilots + routing rules + red-team QA
- **Week 5:** pilot with selected team, tuning and governance

### Budget breakdown
- Setup range: €9 000 - €15 000 (midpoint €12 000)
- Monthly service range: €1 700 - €2 900 (midpoint €2 300)
- Estimated monthly AI token cost (@5,250,000 tokens): €2.45
- Estimated monthly delivery cost (infra + ops + AI): €1 602.45
- Expected monthly gross margin at midpoint: €697.55

### KPI targets (first 90 days)
- 20-35% reduction in repetitive support workload
- 25-40% faster triage/first-response in targeted workflows
- 10-20% improvement in SLA compliance on prioritized queues
- Weekly leadership visibility with one-page KPI narrative

---

## 4. Haltian

**Sector:** IoT Solutions  
**Company size band:** SME / Mid-market  
**Primary dashboard objective:** Device Fleet + Support Triage  
**Recommended package:** Growth (growth)  

### Site research signals
- Site URL: https://haltian.com
- Text signal: window.dataLayer = window.dataLayer || []; function gtag() { dataLayer.push(arguments); } gtag("consent", "default", { ad_personalization: "denied", ad_storage: "denied", ad_user_data: "denied", analytics_storage: "denied", functionality_storage: "denied", per...
- Secondary page scanned: https://haltian.com/about
- Secondary text signal: window.dataLayer = window.dataLayer || []; function gtag() { dataLayer.push(arguments); } gtag("consent", "default", { ad_personalization: "denied", ad_storage: "denied", ad_user_data: "denied", analytics_storage: "denie...

### Pain points this dashboard should solve
- Device telemetry and support incidents are disconnected
- Root-cause analysis is slow due to fragmented logs
- Enterprise customers need SLA transparency

### User roles
- IoT Operations Lead
- Support Lead
- Field Engineer
- Account Manager

### Dashboard module blueprint
| Module | Purpose | Data Sources | AI Capability |
|---|---|---|---|
| Fleet Health | Real-time device status and degradation trends | IoT cloud telemetry | Anomaly detection across device cohorts |
| Incident Triage | Prioritize incidents by impact | Ticketing + telemetry | AI-generated probable cause and routing |
| SLA Console | Track MTTR/uptime per account | Support + monitoring | Forecasted SLA breach alerts |
| Knowledge Debug Assistant | Rapid troubleshooting aid | Runbooks + docs + historical incidents | RAG with source-grounded answers |

### API integration map (to validate in discovery week)
- IoT telemetry API
- Helpdesk API
- Monitoring API
- CRM API

### AI/ML architecture
- **LLM layer:** Claude/OpenAI/Gemini class model for reasoning, summarization, drafting
- **RAG layer:** document ingestion -> chunking -> embeddings -> vector index -> citation-grounded answers
- **Orchestration:** workflow engine for triggers, escalations, SLA alerts, and human-in-the-loop approvals
- **Guardrails:** policy prompts, PII masking, allowlisted actions, audit logs
- **Evaluation:** weekly precision/recall on routing, answer quality QA, deflection and resolution KPIs

### Data model (core entities)
- `device`
- `telemetry_event`
- `incident`
- `runbook`
- `sla_metric`
- `account`

### Workflow automation examples
- auto-incident classification
- runbook recommendation
- SLA breach notification

### Security, compliance, and reliability
- RBAC and environment-level tenant isolation
- Encrypted data at rest and in transit
- Full audit logs for AI suggestions and human overrides
- Regional hosting and retention policy configured per client contract
- Fallback mode: if AI is unavailable, route to deterministic workflow and manual queue

### Implementation plan
- **Week 1:** discovery, API access checklist, baseline KPI definitions
- **Week 2:** connector setup, data model + ingestion pipelines
- **Week 3:** dashboard UI + role-based views
- **Week 4:** AI copilots + routing rules + red-team QA
- **Week 5:** pilot with selected team, tuning and governance

### Budget breakdown
- Setup range: €9 000 - €15 000 (midpoint €12 000)
- Monthly service range: €1 700 - €2 900 (midpoint €2 300)
- Estimated monthly AI token cost (@5,250,000 tokens): €2.45
- Estimated monthly delivery cost (infra + ops + AI): €1 602.45
- Expected monthly gross margin at midpoint: €697.55

### KPI targets (first 90 days)
- 20-35% reduction in repetitive support workload
- 25-40% faster triage/first-response in targeted workflows
- 10-20% improvement in SLA compliance on prioritized queues
- Weekly leadership visibility with one-page KPI narrative

---

## 5. Sulapac

**Sector:** Sustainable Materials  
**Company size band:** SME / Mid-market  
**Primary dashboard objective:** B2B Leads + Regulatory Documentation  
**Recommended package:** Growth (growth)  

### Site research signals
- Site URL: https://www.sulapac.com/
- Text signal: function OptanonWrapper() { } (function(w,d,s,l,i){w[l]=w[l]||[];w[l].push({'gtm.start':new Date().getTime(),event:'gtm.js'});var f=d.getElementsByTagName(s)[0],j=d.createElement(s),dl=l!='dataLayer'?'&l='+l:'';j.async=true;j.src='https://www.googletagmanager....
- Secondary page scanned: https://www.sulapac.com/about
- Secondary text signal: function OptanonWrapper() { } (function(w,d,s,l,i){w[l]=w[l]||[];w[l].push({'gtm.start':new Date().getTime(),event:'gtm.js'});var f=d.getElementsByTagName(s)[0],j=d.createElement(s),dl=l!='dataLayer'?'&l='+l:'';j.async=t...

### Pain points this dashboard should solve
- Dealer/support questions consume senior staff time
- Technical and regulatory documentation is hard to navigate
- Lead-to-order visibility is limited

### User roles
- Sales Ops
- Dealer Success
- Support Engineer
- Compliance Lead

### Dashboard module blueprint
| Module | Purpose | Data Sources | AI Capability |
|---|---|---|---|
| Dealer Support Desk | Ticket and request flow by dealer | CRM + helpdesk | AI draft responses with policy checks |
| Knowledge & Compliance Vault | Search specs, docs, and standards | DMS/SharePoint/Drive | RAG with citation-only answers |
| Lead-to-Order Tracker | Pipeline and quote progression | CRM + ERP | Forecast risk and delay detection |
| Warranty & Service Analytics | Warranty claim trends and root causes | RMA + support | Pattern detection and quality feedback loops |

### API integration map (to validate in discovery week)
- CRM API
- ERP/quote API
- Document repository API
- Helpdesk API

### AI/ML architecture
- **LLM layer:** Claude/OpenAI/Gemini class model for reasoning, summarization, drafting
- **RAG layer:** document ingestion -> chunking -> embeddings -> vector index -> citation-grounded answers
- **Orchestration:** workflow engine for triggers, escalations, SLA alerts, and human-in-the-loop approvals
- **Guardrails:** policy prompts, PII masking, allowlisted actions, audit logs
- **Evaluation:** weekly precision/recall on routing, answer quality QA, deflection and resolution KPIs

### Data model (core entities)
- `dealer`
- `quote`
- `order`
- `warranty_claim`
- `product_sku`
- `document`

### Workflow automation examples
- dealer self-service answers
- quote delay alerts
- warranty trend summaries

### Security, compliance, and reliability
- RBAC and environment-level tenant isolation
- Encrypted data at rest and in transit
- Full audit logs for AI suggestions and human overrides
- Regional hosting and retention policy configured per client contract
- Fallback mode: if AI is unavailable, route to deterministic workflow and manual queue

### Implementation plan
- **Week 1:** discovery, API access checklist, baseline KPI definitions
- **Week 2:** connector setup, data model + ingestion pipelines
- **Week 3:** dashboard UI + role-based views
- **Week 4:** AI copilots + routing rules + red-team QA
- **Week 5:** pilot with selected team, tuning and governance

### Budget breakdown
- Setup range: €9 000 - €15 000 (midpoint €12 000)
- Monthly service range: €1 700 - €2 900 (midpoint €2 300)
- Estimated monthly AI token cost (@5,250,000 tokens): €2.45
- Estimated monthly delivery cost (infra + ops + AI): €1 602.45
- Expected monthly gross margin at midpoint: €697.55

### KPI targets (first 90 days)
- 20-35% reduction in repetitive support workload
- 25-40% faster triage/first-response in targeted workflows
- 10-20% improvement in SLA compliance on prioritized queues
- Weekly leadership visibility with one-page KPI narrative

---

## 6. Vapaus

**Sector:** Employee Mobility Benefits  
**Company size band:** SME / Scale-up  
**Primary dashboard objective:** Employer Onboarding + Support Automation  
**Recommended package:** Growth (growth)  

### Site research signals
- Site URL: https://www.vapaus.io/
- Text signal: Joustavin ja vastuullisin työsuhdepyöräetu - Vapaus a.cta_button{-moz-box-sizing:content-box !important;-webkit-box-sizing:content-box !important;box-sizing:content-box !important;vertical-align:middle}.hs-breadcrumb-menu{list-style-type:none;margin:0px 0px 0p...
- Secondary page: no reliable auto-scrape; roadmap built from homepage signal + sector model.

### Pain points this dashboard should solve
- Employer onboarding workflows are manual
- Policy questions repeat across channels
- Operational visibility across partner network is weak

### User roles
- Onboarding Manager
- Partnership Ops
- Support Lead
- Finance Ops

### Dashboard module blueprint
| Module | Purpose | Data Sources | AI Capability |
|---|---|---|---|
| Onboarding Pipeline | Employer setup status and blockers | CRM + onboarding forms | AI-generated next-step nudges |
| Policy Assistant | Answer benefit policy questions | Policy docs + FAQ | RAG with legal-safe response templates |
| Partner Network View | Utilization and support load by partner | Partner APIs + support | Demand forecasting for partner capacity |
| Billing Exceptions | Detect and resolve invoice anomalies | Billing + ERP | AI exception detection and case creation |

### API integration map (to validate in discovery week)
- CRM API
- Onboarding forms API
- Payroll/benefit API
- Helpdesk API

### AI/ML architecture
- **LLM layer:** Claude/OpenAI/Gemini class model for reasoning, summarization, drafting
- **RAG layer:** document ingestion -> chunking -> embeddings -> vector index -> citation-grounded answers
- **Orchestration:** workflow engine for triggers, escalations, SLA alerts, and human-in-the-loop approvals
- **Guardrails:** policy prompts, PII masking, allowlisted actions, audit logs
- **Evaluation:** weekly precision/recall on routing, answer quality QA, deflection and resolution KPIs

### Data model (core entities)
- `employer`
- `employee`
- `benefit_plan`
- `partner`
- `ticket`
- `invoice`

### Workflow automation examples
- onboarding follow-up generation
- policy answer assistant
- billing anomaly queue

### Security, compliance, and reliability
- RBAC and environment-level tenant isolation
- Encrypted data at rest and in transit
- Full audit logs for AI suggestions and human overrides
- Regional hosting and retention policy configured per client contract
- Fallback mode: if AI is unavailable, route to deterministic workflow and manual queue

### Implementation plan
- **Week 1:** discovery, API access checklist, baseline KPI definitions
- **Week 2:** connector setup, data model + ingestion pipelines
- **Week 3:** dashboard UI + role-based views
- **Week 4:** AI copilots + routing rules + red-team QA
- **Week 5:** pilot with selected team, tuning and governance

### Budget breakdown
- Setup range: €9 000 - €15 000 (midpoint €12 000)
- Monthly service range: €1 700 - €2 900 (midpoint €2 300)
- Estimated monthly AI token cost (@5,250,000 tokens): €2.45
- Estimated monthly delivery cost (infra + ops + AI): €1 602.45
- Expected monthly gross margin at midpoint: €697.55

### KPI targets (first 90 days)
- 20-35% reduction in repetitive support workload
- 25-40% faster triage/first-response in targeted workflows
- 10-20% improvement in SLA compliance on prioritized queues
- Weekly leadership visibility with one-page KPI narrative

---

## 7. Swappie

**Sector:** Refurbished Electronics E-commerce  
**Company size band:** Scale-up / Mid-market  
**Primary dashboard objective:** Order Exceptions + Returns Resolution  
**Recommended package:** Pro (pro)  

### Site research signals
- Site URL: https://swappie.com
- Text signal: Swappie | Refurbished and affordable iPhones with a 12-month warranty /* Disable horizontal scroll on mobiles and tablet */ @media (max-width: 575px) { html, .page-wrapper { max-width: 100%; } } *, ::after, ::before { box-sizing: border-box; } html { direction...
- Secondary page: no reliable auto-scrape; roadmap built from homepage signal + sector model.

### Pain points this dashboard should solve
- Order exceptions and returns create operational drag
- Inventory and promotions are not synchronized with support insights
- CSAT declines when resolution time spikes

### User roles
- Ecom Ops Manager
- Customer Support Lead
- Returns Lead
- Growth Manager

### Dashboard module blueprint
| Module | Purpose | Data Sources | AI Capability |
|---|---|---|---|
| Order Exception Monitor | Track failed payment, delayed shipment, fraud checks | Commerce + OMS + payment | AI-prioritized resolution queue |
| Returns Intelligence | Reason-code and refund trend analytics | Returns/WMS + support | Auto-clustered return reasons |
| Promo & Inventory Cockpit | Promotion impact vs stock risk | PIM/ERP + commerce | Demand forecast + stockout warnings |
| Customer Care Copilot | Assist agents with response drafts | Helpdesk + knowledge base | RAG + tone control + policy constraints |

### API integration map (to validate in discovery week)
- Commerce API
- OMS/WMS API
- Payments API
- Customer support API

### AI/ML architecture
- **LLM layer:** Claude/OpenAI/Gemini class model for reasoning, summarization, drafting
- **RAG layer:** document ingestion -> chunking -> embeddings -> vector index -> citation-grounded answers
- **Orchestration:** workflow engine for triggers, escalations, SLA alerts, and human-in-the-loop approvals
- **Guardrails:** policy prompts, PII masking, allowlisted actions, audit logs
- **Evaluation:** weekly precision/recall on routing, answer quality QA, deflection and resolution KPIs

### Data model (core entities)
- `order`
- `shipment`
- `return`
- `refund`
- `sku`
- `ticket`

### Workflow automation examples
- return reason summarization
- priority queue scoring
- agent reply drafts

### Security, compliance, and reliability
- RBAC and environment-level tenant isolation
- Encrypted data at rest and in transit
- Full audit logs for AI suggestions and human overrides
- Regional hosting and retention policy configured per client contract
- Fallback mode: if AI is unavailable, route to deterministic workflow and manual queue

### Implementation plan
- **Week 1:** discovery, API access checklist, baseline KPI definitions
- **Week 2:** connector setup, data model + ingestion pipelines
- **Week 3:** dashboard UI + role-based views
- **Week 4:** AI copilots + routing rules + red-team QA
- **Week 5:** pilot with selected team, tuning and governance
- **Week 6-7:** executive reporting layer, SLA optimization, handover

### Budget breakdown
- Setup range: €16 000 - €26 000 (midpoint €21 000)
- Monthly service range: €3 200 - €5 200 (midpoint €4 200)
- Estimated monthly AI token cost (@8,750,000 tokens): €4.08
- Estimated monthly delivery cost (infra + ops + AI): €2 454.08
- Expected monthly gross margin at midpoint: €1 745.92

### KPI targets (first 90 days)
- 20-35% reduction in repetitive support workload
- 25-40% faster triage/first-response in targeted workflows
- 10-20% improvement in SLA compliance on prioritized queues
- Weekly leadership visibility with one-page KPI narrative

---

## 8. Gubbe

**Sector:** Elderly Care Platform  
**Company size band:** SME / Scale-up  
**Primary dashboard objective:** Care Matching + Escalation Queue  
**Recommended package:** Growth (growth)  

### Site research signals
- Site URL: https://www.gubbe.com/fi
- Text signal: Gubbe - Tutkitusti vaikuttava hoivapalvelu! !function(o,c){var n=c.documentElement,t=" w-mod-";n.className+=t+"js",("ontouchstart"in o||o.DocumentTouch&&c instanceof DocumentTouch)&&(n.className+=t+"touch")}(window,document); (function(w,i,g){w[g]=w[g]||[];if(...
- Secondary page scanned: https://www.gubbe.com/en/about
- Secondary text signal: About us !function(o,c){var n=c.documentElement,t=" w-mod-";n.className+=t+"js",("ontouchstart"in o||o.DocumentTouch&&c instanceof DocumentTouch)&&(n.className+=t+"touch")}(window,document); (function(w,i,g){w[g]=w[g]||[...

### Pain points this dashboard should solve
- Matching and scheduling must balance quality and response time
- Escalations require fast triage with context
- Care quality insights are scattered

### User roles
- Care Operations Manager
- Scheduler
- Quality Lead
- Support Lead

### Dashboard module blueprint
| Module | Purpose | Data Sources | AI Capability |
|---|---|---|---|
| Matching Queue | Prioritize client-caregiver matching tasks | Scheduling + profile data | Recommendation engine for best fit |
| Escalation Control | Track urgent cases end-to-end | Support + incident logs | Urgency classification and SLA alerts |
| Care Quality Dashboard | Service quality and consistency metrics | Surveys + service logs | Theme extraction from feedback |
| Coordinator Assistant | Case summaries and follow-up drafts | CRM + notes | Summarization + action extraction |

### API integration map (to validate in discovery week)
- Scheduling API
- Support API
- Survey API
- CRM API

### AI/ML architecture
- **LLM layer:** Claude/OpenAI/Gemini class model for reasoning, summarization, drafting
- **RAG layer:** document ingestion -> chunking -> embeddings -> vector index -> citation-grounded answers
- **Orchestration:** workflow engine for triggers, escalations, SLA alerts, and human-in-the-loop approvals
- **Guardrails:** policy prompts, PII masking, allowlisted actions, audit logs
- **Evaluation:** weekly precision/recall on routing, answer quality QA, deflection and resolution KPIs

### Data model (core entities)
- `client`
- `caregiver`
- `match_event`
- `service_visit`
- `escalation`
- `quality_metric`

### Workflow automation examples
- urgent-case alerts
- case-note summarization
- follow-up message drafting

### Security, compliance, and reliability
- RBAC and environment-level tenant isolation
- Encrypted data at rest and in transit
- Full audit logs for AI suggestions and human overrides
- Regional hosting and retention policy configured per client contract
- Fallback mode: if AI is unavailable, route to deterministic workflow and manual queue

### Implementation plan
- **Week 1:** discovery, API access checklist, baseline KPI definitions
- **Week 2:** connector setup, data model + ingestion pipelines
- **Week 3:** dashboard UI + role-based views
- **Week 4:** AI copilots + routing rules + red-team QA
- **Week 5:** pilot with selected team, tuning and governance

### Budget breakdown
- Setup range: €9 000 - €15 000 (midpoint €12 000)
- Monthly service range: €1 700 - €2 900 (midpoint €2 300)
- Estimated monthly AI token cost (@5,250,000 tokens): €2.45
- Estimated monthly delivery cost (infra + ops + AI): €1 602.45
- Expected monthly gross margin at midpoint: €697.55

### KPI targets (first 90 days)
- 20-35% reduction in repetitive support workload
- 25-40% faster triage/first-response in targeted workflows
- 10-20% improvement in SLA compliance on prioritized queues
- Weekly leadership visibility with one-page KPI narrative

---

## 9. Freska

**Sector:** Home Cleaning Services  
**Company size band:** SME  
**Primary dashboard objective:** Booking Support + Staff Dispatch  
**Recommended package:** Starter (starter)  

### Site research signals
- Site URL: https://www.freska.fi/
- Text signal: Suomen suosituin kotisiivous | Freska {"@context":"https://schema.org","@type":"Organization","name":"Freska","url":"https://www.freska.fi","logo":"https://www.freska.fi/images/freska-logo.svg","sameAs":["https://www.facebook.com/freska.fi/","https://www.insta...
- Secondary page: no reliable auto-scrape; roadmap built from homepage signal + sector model.

### Pain points this dashboard should solve
- Dispatch planning is reactive
- Customer communication around timing is inconsistent
- Low visibility into recurring issue patterns

### User roles
- Operations Manager
- Dispatch Coordinator
- Support Lead
- Regional Supervisor

### Dashboard module blueprint
| Module | Purpose | Data Sources | AI Capability |
|---|---|---|---|
| Dispatch Board | Live schedule and capacity | Booking system + workforce data | ETA prediction and conflict alerts |
| Customer Resolution Hub | Track requests and SLA status | Support + CRM | Auto-priority and response drafting |
| Recurring Issue Analyzer | Identify repeat problems by area/team | Tickets + service logs | Pattern detection and root cause hints |
| Ops KPI Wall | Throughput, punctuality, and satisfaction | Ops DB + surveys | Anomaly detection on service quality |

### API integration map (to validate in discovery week)
- Booking API
- Dispatch/workforce API
- Support API
- Survey API

### AI/ML architecture
- **LLM layer:** Claude/OpenAI/Gemini class model for reasoning, summarization, drafting
- **RAG layer:** document ingestion -> chunking -> embeddings -> vector index -> citation-grounded answers
- **Orchestration:** workflow engine for triggers, escalations, SLA alerts, and human-in-the-loop approvals
- **Guardrails:** policy prompts, PII masking, allowlisted actions, audit logs
- **Evaluation:** weekly precision/recall on routing, answer quality QA, deflection and resolution KPIs

### Data model (core entities)
- `booking`
- `worker_shift`
- `dispatch`
- `ticket`
- `sla_event`
- `customer_feedback`

### Workflow automation examples
- dispatch conflict alerts
- customer update drafts
- recurring issue digest

### Security, compliance, and reliability
- RBAC and environment-level tenant isolation
- Encrypted data at rest and in transit
- Full audit logs for AI suggestions and human overrides
- Regional hosting and retention policy configured per client contract
- Fallback mode: if AI is unavailable, route to deterministic workflow and manual queue

### Implementation plan
- **Week 1:** discovery, API access checklist, baseline KPI definitions
- **Week 2:** connector setup, data model + ingestion pipelines
- **Week 3:** dashboard UI + role-based views
- **Week 4:** AI copilots + routing rules + red-team QA

### Budget breakdown
- Setup range: €4 500 - €8 000 (midpoint €6 250)
- Monthly service range: €900 - €1 600 (midpoint €1 250)
- Estimated monthly AI token cost (@2,600,000 tokens): €1.21
- Estimated monthly delivery cost (infra + ops + AI): €1 001.21
- Expected monthly gross margin at midpoint: €248.79

### KPI targets (first 90 days)
- 20-35% reduction in repetitive support workload
- 25-40% faster triage/first-response in targeted workflows
- 10-20% improvement in SLA compliance on prioritized queues
- Weekly leadership visibility with one-page KPI narrative

---

## 10. Fiksuruoka

**Sector:** Discount Grocery E-commerce  
**Company size band:** SME  
**Primary dashboard objective:** Inventory Promotion + Customer Support  
**Recommended package:** Starter (starter)  

### Site research signals
- Site URL: https://www.fiksuruoka.fi
- Text signal: Fiksua ruokaa jopa 80% alennuksella vertailuhinnoista - Fiksuruoka.fi {"@context":"https://schema.org","@type":"Organization","name":"Fiksuruoka.fi","logo":"https://www.fiksuruoka.fi/_nuxt/logo-fiksuruoka-secondary-forest.tBVygSid.png","url":"https://www.fiksu...
- Secondary page scanned: https://www.fiksuruoka.fi/products
- Secondary text signal: Fiksua ruokaa jopa 80% alennuksella vertailuhinnoista - Fiksuruoka.fi {"@context":"https://schema.org","@type":"Organization","name":"Fiksuruoka.fi","logo":"https://www.fiksuruoka.fi/_nuxt/logo-fiksuruoka-secondary-fores...

### Pain points this dashboard should solve
- Order exceptions and returns create operational drag
- Inventory and promotions are not synchronized with support insights
- CSAT declines when resolution time spikes

### User roles
- Ecom Ops Manager
- Customer Support Lead
- Returns Lead
- Growth Manager

### Dashboard module blueprint
| Module | Purpose | Data Sources | AI Capability |
|---|---|---|---|
| Order Exception Monitor | Track failed payment, delayed shipment, fraud checks | Commerce + OMS + payment | AI-prioritized resolution queue |
| Returns Intelligence | Reason-code and refund trend analytics | Returns/WMS + support | Auto-clustered return reasons |
| Promo & Inventory Cockpit | Promotion impact vs stock risk | PIM/ERP + commerce | Demand forecast + stockout warnings |
| Customer Care Copilot | Assist agents with response drafts | Helpdesk + knowledge base | RAG + tone control + policy constraints |

### API integration map (to validate in discovery week)
- Commerce API
- Inventory API
- Promotion API
- Support API

### AI/ML architecture
- **LLM layer:** Claude/OpenAI/Gemini class model for reasoning, summarization, drafting
- **RAG layer:** document ingestion -> chunking -> embeddings -> vector index -> citation-grounded answers
- **Orchestration:** workflow engine for triggers, escalations, SLA alerts, and human-in-the-loop approvals
- **Guardrails:** policy prompts, PII masking, allowlisted actions, audit logs
- **Evaluation:** weekly precision/recall on routing, answer quality QA, deflection and resolution KPIs

### Data model (core entities)
- `order`
- `shipment`
- `return`
- `refund`
- `sku`
- `ticket`

### Workflow automation examples
- return reason summarization
- priority queue scoring
- agent reply drafts

### Security, compliance, and reliability
- RBAC and environment-level tenant isolation
- Encrypted data at rest and in transit
- Full audit logs for AI suggestions and human overrides
- Regional hosting and retention policy configured per client contract
- Fallback mode: if AI is unavailable, route to deterministic workflow and manual queue

### Implementation plan
- **Week 1:** discovery, API access checklist, baseline KPI definitions
- **Week 2:** connector setup, data model + ingestion pipelines
- **Week 3:** dashboard UI + role-based views
- **Week 4:** AI copilots + routing rules + red-team QA

### Budget breakdown
- Setup range: €4 500 - €8 000 (midpoint €6 250)
- Monthly service range: €900 - €1 600 (midpoint €1 250)
- Estimated monthly AI token cost (@2,600,000 tokens): €1.21
- Estimated monthly delivery cost (infra + ops + AI): €1 001.21
- Expected monthly gross margin at midpoint: €248.79

### KPI targets (first 90 days)
- 20-35% reduction in repetitive support workload
- 25-40% faster triage/first-response in targeted workflows
- 10-20% improvement in SLA compliance on prioritized queues
- Weekly leadership visibility with one-page KPI narrative

---

## 11. Framery

**Sector:** Office Pod Manufacturing  
**Company size band:** Mid-market  
**Primary dashboard objective:** Dealer Enablement + Warranty Support  
**Recommended package:** Growth (growth)  

### Site research signals
- Site URL: https://framery.com/en/
- Text signal: var gform;gform||(document.addEventListener("gform_main_scripts_loaded",function(){gform.scriptsLoaded=!0}),document.addEventListener("gform/theme/scripts_loaded",function(){gform.themeScriptsLoaded=!0}),window.addEventListener("DOMContentLoaded",function(){gf...
- Secondary page scanned: https://framery.com/about
- Secondary text signal: // Create dataLayer. window.dataLayer = window.dataLayer || []; var dataLayer_site = { 'event': 'agtm4wp_pageview', 'wp_title': 'About - Framery', 'wp_lang': 'en', 'wp_loggedin': false, 'wp_posttype': 'fr_menu', 'geo_cou...

### Pain points this dashboard should solve
- Dealer/support questions consume senior staff time
- Technical and regulatory documentation is hard to navigate
- Lead-to-order visibility is limited

### User roles
- Sales Ops
- Dealer Success
- Support Engineer
- Compliance Lead

### Dashboard module blueprint
| Module | Purpose | Data Sources | AI Capability |
|---|---|---|---|
| Dealer Support Desk | Ticket and request flow by dealer | CRM + helpdesk | AI draft responses with policy checks |
| Knowledge & Compliance Vault | Search specs, docs, and standards | DMS/SharePoint/Drive | RAG with citation-only answers |
| Lead-to-Order Tracker | Pipeline and quote progression | CRM + ERP | Forecast risk and delay detection |
| Warranty & Service Analytics | Warranty claim trends and root causes | RMA + support | Pattern detection and quality feedback loops |

### API integration map (to validate in discovery week)
- CRM API
- Dealer portal API
- Warranty/RMA API
- Document API

### AI/ML architecture
- **LLM layer:** Claude/OpenAI/Gemini class model for reasoning, summarization, drafting
- **RAG layer:** document ingestion -> chunking -> embeddings -> vector index -> citation-grounded answers
- **Orchestration:** workflow engine for triggers, escalations, SLA alerts, and human-in-the-loop approvals
- **Guardrails:** policy prompts, PII masking, allowlisted actions, audit logs
- **Evaluation:** weekly precision/recall on routing, answer quality QA, deflection and resolution KPIs

### Data model (core entities)
- `dealer`
- `quote`
- `order`
- `warranty_claim`
- `product_sku`
- `document`

### Workflow automation examples
- dealer self-service answers
- quote delay alerts
- warranty trend summaries

### Security, compliance, and reliability
- RBAC and environment-level tenant isolation
- Encrypted data at rest and in transit
- Full audit logs for AI suggestions and human overrides
- Regional hosting and retention policy configured per client contract
- Fallback mode: if AI is unavailable, route to deterministic workflow and manual queue

### Implementation plan
- **Week 1:** discovery, API access checklist, baseline KPI definitions
- **Week 2:** connector setup, data model + ingestion pipelines
- **Week 3:** dashboard UI + role-based views
- **Week 4:** AI copilots + routing rules + red-team QA
- **Week 5:** pilot with selected team, tuning and governance

### Budget breakdown
- Setup range: €9 000 - €15 000 (midpoint €12 000)
- Monthly service range: €1 700 - €2 900 (midpoint €2 300)
- Estimated monthly AI token cost (@5,250,000 tokens): €2.45
- Estimated monthly delivery cost (infra + ops + AI): €1 602.45
- Expected monthly gross margin at midpoint: €697.55

### KPI targets (first 90 days)
- 20-35% reduction in repetitive support workload
- 25-40% faster triage/first-response in targeted workflows
- 10-20% improvement in SLA compliance on prioritized queues
- Weekly leadership visibility with one-page KPI narrative

---

## 12. IQM Quantum Computers

**Sector:** Quantum Technology  
**Company size band:** Scale-up / Mid-market  
**Primary dashboard objective:** Partnership Pipeline + Technical Requests  
**Recommended package:** Pro (pro)  

### Site research signals
- Site URL: https://meetiqm.com
- Text signal: window.dataLayer = window.dataLayer || []; function gtag() { dataLayer.push(arguments); } gtag("consent", "default", { ad_personalization: "denied", ad_storage: "denied", ad_user_data: "denied", analytics_storage: "denied", functionality_storage: "denied", per...
- Secondary page scanned: https://meetiqm.com/about
- Secondary text signal: window.dataLayer = window.dataLayer || []; function gtag() { dataLayer.push(arguments); } gtag("consent", "default", { ad_personalization: "denied", ad_storage: "denied", ad_user_data: "denied", analytics_storage: "denie...

### Pain points this dashboard should solve
- Highly technical pre-sales questions require senior experts
- Partnership and grant workflows involve complex documentation
- Request prioritization lacks a single view

### User roles
- Partnership Lead
- Technical Sales
- Program Manager
- Support Engineer

### Dashboard module blueprint
| Module | Purpose | Data Sources | AI Capability |
|---|---|---|---|
| Partner Pipeline | Track institutions, enterprises, and strategic deals | CRM + email/calendar | AI stage progression recommendations |
| Technical Request Desk | Classify and route complex inquiries | Forms + support channels | Semantic triage and expert matching |
| Knowledge Index | Search papers, specs, and internal notes | Docs/wiki | Citation-grounded Q&A assistant |
| Program Tracking | Milestones for pilots and funded projects | PM tools + docs | Risk flags and milestone summarization |

### API integration map (to validate in discovery week)
- CRM API
- Technical request API
- Knowledge API
- PM/milestone API

### AI/ML architecture
- **LLM layer:** Claude/OpenAI/Gemini class model for reasoning, summarization, drafting
- **RAG layer:** document ingestion -> chunking -> embeddings -> vector index -> citation-grounded answers
- **Orchestration:** workflow engine for triggers, escalations, SLA alerts, and human-in-the-loop approvals
- **Guardrails:** policy prompts, PII masking, allowlisted actions, audit logs
- **Evaluation:** weekly precision/recall on routing, answer quality QA, deflection and resolution KPIs

### Data model (core entities)
- `partner`
- `technical_request`
- `milestone`
- `document`
- `expert`
- `engagement`

### Workflow automation examples
- expert routing
- technical brief generation
- milestone risk alerts

### Security, compliance, and reliability
- RBAC and environment-level tenant isolation
- Encrypted data at rest and in transit
- Full audit logs for AI suggestions and human overrides
- Regional hosting and retention policy configured per client contract
- Fallback mode: if AI is unavailable, route to deterministic workflow and manual queue

### Implementation plan
- **Week 1:** discovery, API access checklist, baseline KPI definitions
- **Week 2:** connector setup, data model + ingestion pipelines
- **Week 3:** dashboard UI + role-based views
- **Week 4:** AI copilots + routing rules + red-team QA
- **Week 5:** pilot with selected team, tuning and governance
- **Week 6-7:** executive reporting layer, SLA optimization, handover

### Budget breakdown
- Setup range: €16 000 - €26 000 (midpoint €21 000)
- Monthly service range: €3 200 - €5 200 (midpoint €4 200)
- Estimated monthly AI token cost (@8,750,000 tokens): €4.08
- Estimated monthly delivery cost (infra + ops + AI): €2 454.08
- Expected monthly gross margin at midpoint: €1 745.92

### KPI targets (first 90 days)
- 20-35% reduction in repetitive support workload
- 25-40% faster triage/first-response in targeted workflows
- 10-20% improvement in SLA compliance on prioritized queues
- Weekly leadership visibility with one-page KPI narrative

---

## 13. Supermetrics

**Sector:** Marketing Data Software  
**Company size band:** Scale-up / Mid-market  
**Primary dashboard objective:** Expansion + Churn Risk Intelligence  
**Recommended package:** Pro (pro)  

### Site research signals
- Site URL: https://supermetrics.com
- Text signal: Marketing Intelligence Platform: Supermetrics window._vwo_code || (function () { var w = window, d = document; var account_id = 611975, version = 2.2, settings_tolerance = 2000, hide_element = 'body', hide_element_style = 'opacity:0 !important;filter:alpha(opa...
- Secondary page scanned: https://supermetrics.com/about
- Secondary text signal: About Supermetrics window._vwo_code || (function () { var w = window, d = document; var account_id = 611975, version = 2.2, settings_tolerance = 2000, hide_element = 'body', hide_element_style = 'opacity:0 !important;fil...

### Pain points this dashboard should solve
- Expansion opportunities hidden in product usage
- Churn indicators discovered too late
- Support and CSM data live in separate systems

### User roles
- VP Customer Success
- CSM
- Support Manager
- RevOps

### Dashboard module blueprint
| Module | Purpose | Data Sources | AI Capability |
|---|---|---|---|
| Account Health Radar | Unified health score per account | Product events, CRM, support | Explainable health scoring |
| Expansion Finder | Spot cross-sell/upsell timing | Usage + contract data | AI signals for expansion intent |
| Churn Early Warning | Detect risk with confidence intervals | Usage decline, ticket sentiment | Risk forecasting and playbook suggestions |
| QBR Builder | Generate account summary packs | CRM + analytics + support | Auto-generated QBR narrative and charts |

### API integration map (to validate in discovery week)
- CRM API
- Product usage API
- Support API
- Billing API

### AI/ML architecture
- **LLM layer:** Claude/OpenAI/Gemini class model for reasoning, summarization, drafting
- **RAG layer:** document ingestion -> chunking -> embeddings -> vector index -> citation-grounded answers
- **Orchestration:** workflow engine for triggers, escalations, SLA alerts, and human-in-the-loop approvals
- **Guardrails:** policy prompts, PII masking, allowlisted actions, audit logs
- **Evaluation:** weekly precision/recall on routing, answer quality QA, deflection and resolution KPIs

### Data model (core entities)
- `workspace`
- `account`
- `feature_event`
- `contract`
- `health_score`
- `renewal`

### Workflow automation examples
- weekly CSM briefing
- renewal risk alerts
- auto-drafted QBR decks

### Security, compliance, and reliability
- RBAC and environment-level tenant isolation
- Encrypted data at rest and in transit
- Full audit logs for AI suggestions and human overrides
- Regional hosting and retention policy configured per client contract
- Fallback mode: if AI is unavailable, route to deterministic workflow and manual queue

### Implementation plan
- **Week 1:** discovery, API access checklist, baseline KPI definitions
- **Week 2:** connector setup, data model + ingestion pipelines
- **Week 3:** dashboard UI + role-based views
- **Week 4:** AI copilots + routing rules + red-team QA
- **Week 5:** pilot with selected team, tuning and governance
- **Week 6-7:** executive reporting layer, SLA optimization, handover

### Budget breakdown
- Setup range: €16 000 - €26 000 (midpoint €21 000)
- Monthly service range: €3 200 - €5 200 (midpoint €4 200)
- Estimated monthly AI token cost (@8,750,000 tokens): €4.08
- Estimated monthly delivery cost (infra + ops + AI): €2 454.08
- Expected monthly gross margin at midpoint: €1 745.92

### KPI targets (first 90 days)
- 20-35% reduction in repetitive support workload
- 25-40% faster triage/first-response in targeted workflows
- 10-20% improvement in SLA compliance on prioritized queues
- Weekly leadership visibility with one-page KPI narrative

---

## 14. Lyyti

**Sector:** Event Management Software  
**Company size band:** SME / Mid-market  
**Primary dashboard objective:** Event Operations + Attendee Support  
**Recommended package:** Growth (growth)  

### Site research signals
- Site URL: https://www.lyyti.com/en/
- Text signal: window.dataLayer = window.dataLayer || []; function gtag(){dataLayer.push(arguments);} gtag('consent', 'default', { 'analytics_storage': 'denied', 'ad_storage': 'denied', 'ad_user_data': 'denied', 'ad_personalization': 'denied', 'wait_for_update': "500" }); (f...
- Secondary page: no reliable auto-scrape; roadmap built from homepage signal + sector model.

### Pain points this dashboard should solve
- Event operations span marketing, registration, support and finance
- Attendee issues peak close to event date
- Post-event insights arrive too late

### User roles
- Event Operations Lead
- Customer Success
- Support Manager
- Marketing Ops

### Dashboard module blueprint
| Module | Purpose | Data Sources | AI Capability |
|---|---|---|---|
| Event Operations Center | Live readiness across upcoming events | Event platform + CRM | Risk scoring for event readiness |
| Attendee Support Queue | Issue volume and SLA by event | Support + chat/email | Intent classification and smart routing |
| Revenue & Attendance Lens | Registration, conversion, and no-show trends | Billing + event analytics | Forecasting and conversion diagnostics |
| Post-event Intelligence | Feedback and operational retrospectives | Surveys + support + analytics | Theme extraction and action generation |

### API integration map (to validate in discovery week)
- Event platform API
- CRM API
- Support API
- Payments API

### AI/ML architecture
- **LLM layer:** Claude/OpenAI/Gemini class model for reasoning, summarization, drafting
- **RAG layer:** document ingestion -> chunking -> embeddings -> vector index -> citation-grounded answers
- **Orchestration:** workflow engine for triggers, escalations, SLA alerts, and human-in-the-loop approvals
- **Guardrails:** policy prompts, PII masking, allowlisted actions, audit logs
- **Evaluation:** weekly precision/recall on routing, answer quality QA, deflection and resolution KPIs

### Data model (core entities)
- `event`
- `attendee`
- `registration`
- `ticket`
- `campaign`
- `feedback`

### Workflow automation examples
- event risk alerts
- attendee response drafts
- post-event summary generation

### Security, compliance, and reliability
- RBAC and environment-level tenant isolation
- Encrypted data at rest and in transit
- Full audit logs for AI suggestions and human overrides
- Regional hosting and retention policy configured per client contract
- Fallback mode: if AI is unavailable, route to deterministic workflow and manual queue

### Implementation plan
- **Week 1:** discovery, API access checklist, baseline KPI definitions
- **Week 2:** connector setup, data model + ingestion pipelines
- **Week 3:** dashboard UI + role-based views
- **Week 4:** AI copilots + routing rules + red-team QA
- **Week 5:** pilot with selected team, tuning and governance

### Budget breakdown
- Setup range: €9 000 - €15 000 (midpoint €12 000)
- Monthly service range: €1 700 - €2 900 (midpoint €2 300)
- Estimated monthly AI token cost (@5,250,000 tokens): €2.45
- Estimated monthly delivery cost (infra + ops + AI): €1 602.45
- Expected monthly gross margin at midpoint: €697.55

### KPI targets (first 90 days)
- 20-35% reduction in repetitive support workload
- 25-40% faster triage/first-response in targeted workflows
- 10-20% improvement in SLA compliance on prioritized queues
- Weekly leadership visibility with one-page KPI narrative

---

## 15. Genelec

**Sector:** Professional Audio Manufacturing  
**Company size band:** Mid-market  
**Primary dashboard objective:** Dealer Support + Product Knowledge  
**Recommended package:** Growth (growth)  

### Site research signals
- Site URL: https://www.genelec.com
- Text signal: World Leader in Studio Monitors - Genelec.com // // .sidenav-box-light a { z-index: 1; } #p_p_id_cmscontent_INSTANCE_2jjlhjQAZxe3_ .portlet-content { }
.gradient-layer-black-left {opacity:0.8!important;}
#portlet_cmscontent_INSTANCE_2jjlhjQAZxe3 .background {m...
- Secondary page scanned: https://www.genelec.com/company
- Secondary text signal: Company - Genelec.com // // .sidenav-box-light a { z-index: 1; } if (window.Analytics) { window._com_liferay_document_library_analytics_isViewFileEntry = false; } // var _mtm = window._mtm = window._mtm || []; _mtm.push(...

### Pain points this dashboard should solve
- Dealer/support questions consume senior staff time
- Technical and regulatory documentation is hard to navigate
- Lead-to-order visibility is limited

### User roles
- Sales Ops
- Dealer Success
- Support Engineer
- Compliance Lead

### Dashboard module blueprint
| Module | Purpose | Data Sources | AI Capability |
|---|---|---|---|
| Dealer Support Desk | Ticket and request flow by dealer | CRM + helpdesk | AI draft responses with policy checks |
| Knowledge & Compliance Vault | Search specs, docs, and standards | DMS/SharePoint/Drive | RAG with citation-only answers |
| Lead-to-Order Tracker | Pipeline and quote progression | CRM + ERP | Forecast risk and delay detection |
| Warranty & Service Analytics | Warranty claim trends and root causes | RMA + support | Pattern detection and quality feedback loops |

### API integration map (to validate in discovery week)
- Dealer support API
- Warranty API
- CRM API
- Product docs API

### AI/ML architecture
- **LLM layer:** Claude/OpenAI/Gemini class model for reasoning, summarization, drafting
- **RAG layer:** document ingestion -> chunking -> embeddings -> vector index -> citation-grounded answers
- **Orchestration:** workflow engine for triggers, escalations, SLA alerts, and human-in-the-loop approvals
- **Guardrails:** policy prompts, PII masking, allowlisted actions, audit logs
- **Evaluation:** weekly precision/recall on routing, answer quality QA, deflection and resolution KPIs

### Data model (core entities)
- `dealer`
- `quote`
- `order`
- `warranty_claim`
- `product_sku`
- `document`

### Workflow automation examples
- dealer self-service answers
- quote delay alerts
- warranty trend summaries

### Security, compliance, and reliability
- RBAC and environment-level tenant isolation
- Encrypted data at rest and in transit
- Full audit logs for AI suggestions and human overrides
- Regional hosting and retention policy configured per client contract
- Fallback mode: if AI is unavailable, route to deterministic workflow and manual queue

### Implementation plan
- **Week 1:** discovery, API access checklist, baseline KPI definitions
- **Week 2:** connector setup, data model + ingestion pipelines
- **Week 3:** dashboard UI + role-based views
- **Week 4:** AI copilots + routing rules + red-team QA
- **Week 5:** pilot with selected team, tuning and governance

### Budget breakdown
- Setup range: €9 000 - €15 000 (midpoint €12 000)
- Monthly service range: €1 700 - €2 900 (midpoint €2 300)
- Estimated monthly AI token cost (@5,250,000 tokens): €2.45
- Estimated monthly delivery cost (infra + ops + AI): €1 602.45
- Expected monthly gross margin at midpoint: €697.55

### KPI targets (first 90 days)
- 20-35% reduction in repetitive support workload
- 25-40% faster triage/first-response in targeted workflows
- 10-20% improvement in SLA compliance on prioritized queues
- Weekly leadership visibility with one-page KPI narrative

---

## Portfolio economics summary
- Average setup midpoint per client: €14 233
- Average monthly midpoint per client: €2 793
- Average monthly delivery cost per client: €1 806.16
- Average monthly gross margin per client: €987.17

### Close scenarios
| Scenario | Clients Closed | Setup Revenue | Monthly Recurring Revenue | Monthly Gross Margin |
|---|---:|---:|---:|---:|
| Conservative | 2 | €28 467 | €5 587 | €1 974.35 |
| Base | 4 | €56 933 | €11 173 | €3 948.70 |
| Aggressive | 6 | €85 400 | €16 760 | €5 923.05 |

## Implementation stack recommendation (common baseline)
- **Frontend:** Next.js dashboard with role-aware views
- **Backend:** FastAPI/Node API layer + worker queue
- **Data:** Postgres for operational state + warehouse for analytics
- **AI:** LLM gateway (Claude/OpenAI/Gemini), embeddings model, vector DB
- **Integrations:** modular connector SDK for CRM, support, billing, analytics, docs
- **Observability:** structured logs, prompt trace IDs, latency and cost monitors
- **Governance:** RBAC, audit trail, policy engine, PII redaction