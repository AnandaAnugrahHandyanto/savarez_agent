# Plan: Resolve Research and Finance Module Flaws

## Objectives
Comprehensively resolve the architectural and implementation flaws identified in the Research and Finance modules:
1. **Fragile Dependencies:** Replace runtime `pip install` with structured management.
2. **API Brittleness:** Decouple `yfinance` via a Provider-Adapter pattern.
3. **Parsing Risks:** Provide robust, defensive parsing utilities for arXiv and Polymarket.
4. **Static Reasoning:** Enable user-centric parameterization (time horizon, interval).
5. **Safety/Privacy:** Implement rate-limiting and `robots.txt` awareness.
6. **Global Coverage:** Add support for international assets and fallback data sources.

---

## Phase 1: Standardize "Skill Environment" Management
- **Status:** TODO
- **Task 1.1:** Add `dependencies` field to `SKILL.md` frontmatter.
- **Task 1.2:** Update `skills_tool.py` to recognize `requirements.txt` and provide a `check_dependencies` helper.
- **Task 1.3:** Create a `setup_skill` internal utility for isolated environment preparation.

## Phase 2: Provider-Adapter Pattern (Finance)
- **Status:** TODO
- **Task 2.1:** Create `hermes-agent/hermes/finance_utils.py` with `AbstractFinanceProvider`.
- **Task 2.2:** Implement `YahooFinanceProvider` (scraped) and `OfficialFinanceProvider` (e.g., AlphaVantage/Polygon as fallback).
- **Task 2.3:** Refactor `finance-skills/skills/yfinance-data` to use the adapter.

## Phase 3: Robust Research Utilities
- **Status:** TODO
- **Task 3.1:** Create `hermes-agent/hermes/research_utils.py`.
- **Task 3.2:** Implement `safe_parse_arxiv` with defensive XML handling.
- **Task 3.3:** Implement `safe_parse_polymarket` with double-encoding support.
- **Task 3.4:** Update `hermes-agent/skills/research/arxiv/SKILL.md` to use these utilities.

## Phase 4: Contextual Parameterization
- **Status:** TODO
- **Task 4.1:** Update all `SKILL.md` files with a mandatory "Step 0: Context Discovery".
- **Task 4.2:** Modify `stock-correlation` to dynamically suggest intervals based on asset class.

## Phase 5: Rate Limiting & Ethics
- **Status:** TODO
- **Task 5.1:** Implement `hermes-agent/hermes/rate_limit.py`.
- **Task 5.2:** Add `robots.txt` check to `web_extract` for batch research operations.

## Phase 6: Globalization & Failovers
- **Status:** TODO
- **Task 6.1:** Add international ticker suffix mapping (e.g., `.NS`, `.L`, `.TO`).
- **Task 6.2:** Implement "Fallback Discovery" (e.g., if API lacks earnings date, use web search).

---

## Verification Plan
1. **Dependency Test:** Try to run a skill with a missing library; ensure the agent identifies and offers to install it via the new `check_dependencies` flow.
2. **Brittle API Test:** Mock a `yfinance` failure and verify the adapter switches to a fallback provider.
3. **Robust Parsing Test:** Feed malformed XML/JSON to the research skills and ensure they don't crash.
4. **Global Asset Test:** Run `earnings-preview` on an Indian (NSE) or London (LSE) ticker.
5. **Batch Stress Test:** Trigger a bulk arXiv search (20+ papers) and verify the rate-limiter engages.
