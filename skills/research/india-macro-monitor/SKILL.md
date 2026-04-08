---
name: india-macro-monitor
description: >
  Track and analyze Indian macroeconomic indicators including FII/DII flows, 
  RBI policy rates, Forex reserves, Trade balance, Oil imports, and CMIE data.
  Use this skill for daily economic digests, finance research, and market-to-macro correlation.
---

# India Macro Monitor Skill

Provides comprehensive tracking of Indian economic metrics from primary sources (RBI, NSE, CMIE, Google Finance).

## Capabilities

### 1. Market Flows (NSE)
- Fetch daily FII (Foreign Institutional Investors) and DII (Domestic Institutional Investors) net buying/selling.
- Check market status and trading sessions.

### 2. Monetary Policy (RBI)
- Monitor current Repo, Reverse Repo, MSF, and Bank rates.
- Track Foreign Exchange (Forex) reserves and trend analysis.

### 3. Real-time Pulse (Google Finance)
- Get instant quotes for Nifty 50, Sensex, and INR/USD.
- Track Brent Crude and US 10Y Yields for correlation analysis.

### 4. High-Frequency Macro (CMIE)
- Track Unemployment rates and Consumer Sentiment (when available via public dashboards).

## Usage Examples

- "What was the FII/DII activity yesterday?"
- "Give me a macro digest for India today."
- "How are forex reserves trending vs oil prices?"
- "Is the market rally supported by institutional flows?"

## Implementation Details

The skill uses `agent.india_finance_providers` to fetch data:
- `NSEProvider` for flows.
- `RBIProvider` for policy rates.
- `GoogleFinanceProvider` for real-time indices and commodities.

## Output Format

The skill produces structured Markdown reports suitable for the Daily Digest. It includes:
- **Macro Pulse Table**: Rates and Indices.
- **Institutional Flows**: FII/DII net values.
- **Risk Assessment**: Color-coded indicators (🟢, 🟡, 🔴) for key metrics like Brent Crude and VIX.
