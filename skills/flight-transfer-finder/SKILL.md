---
name: flight-transfer-finder
description: "Find cheaper self-transfer flight routes via hub airports using the fast_flights Python library. Scans 25-70 hub airports, multi-origin/multi-date search, cabin class selection, and route history tracking. Saves time and money by revealing hidden connections."
version: "1.0.0"
license: MIT
compatibility:
  hermes: ">=0.7.0"
  platforms: [macos, linux]
metadata:
  author: Wali Reheman
  hermes:
    tags: [flights, travel, budget, hub-transfer, fast-flights]
    category: research
    requires_tools: [terminal]
    requires_toolsets: [web]
---

# Flight Transfer Finder

Find cheaper self-transfer flight routes by searching hub airports. A self-transfer
is two separate one-way tickets booked together — often hundreds of dollars cheaper
than a direct or airline-optimized itinerary.

## When to Use

- User wants to find the cheapest route between two airports
- User is flexible on routing and wants to discover hidden cheap connections
- User is booking multiple passengers and wants to minimize total cost
- User wants to compare prices across multiple dates or departure cities

## How It Works

The script searches the **fast_flights** API (Skyscanner/Google Flights data) for:
1. Direct price: origin → destination (baseline)
2. Transfer prices: origin → hub + hub → destination (two legs)

If the sum of two legs is cheaper than the direct, it reports the saving.

## Prerequisites

```bash
# Create isolated venv (one-time setup)
python3 -m venv ~/.hermes/venvs/flight-search
~/.hermes/venvs/flight-search/bin/pip install fast-flights
```

## Usage

```bash
# Single route — find cheapest transfer
python3 ~/.hermes/scripts/flight-transfer-finder.py \
  -o SFO -d HKG -dt 2026-06-15

# Flexible dates (±3 days = 7 dates scanned)
python3 ~/.hermes/scripts/flight-transfer-finder.py \
  -o LAX -d HKG -dt 2026-06-15 --flexible 3

# Multi-origin — find cheapest departure city
python3 ~/.hermes/scripts/flight-transfer-finder.py \
  -o SFO,LAX,OAK,SEA -d HKG -dt 2026-06-15 --flexible 3

# Business class, 3 passengers
python3 ~/.hermes/scripts/flight-transfer-finder.py \
  -o JFK -d LHR -dt 2026-07-01 -c business -p 3

# Aggressive mode (checks 60 hubs instead of 25)
python3 ~/.hermes/scripts/flight-transfer-finder.py \
  -o SFO -d HKG -dt 2026-06-15 --aggressive

# Direct price only — fast (< 5 seconds)
python3 ~/.hermes/scripts/flight-transfer-finder.py \
  -o SFO -d HKG -dt 2026-06-15 --direct-only

# Alert if transfer drops below threshold
python3 ~/.hermes/scripts/flight-transfer-finder.py \
  -o SFO -d HKG -dt 2026-06-15 --alert-below 800

# Save route to history
python3 ~/.hermes/scripts/flight-transfer-finder.py \
  -o SFO -d HKG -dt 2026-06-15 --save-route

# JSON output (for scripting)
python3 ~/.hermes/scripts/flight-transfer-finder.py \
  -o SFO -d HKG -dt 2026-06-15 --json
```

## Key Arguments

| Argument | Description |
|----------|-------------|
| `-o, --origin` | Origin IATA code(s), comma-separated for multi-origin |
| `-d, --destination` | Destination IATA code |
| `-dt, --date` | Departure date (YYYY-MM-DD) |
| `-c, --cabin` | Cabin class: economy, premium-economy, business, first |
| `-p, --passengers` | Number of passengers (default: 1) |
| `--flexible N` | Scan ±N days (e.g. 3 = 7 dates) |
| `--date-range START:END` | Explicit date range |
| `--aggressive` | Check 60 hubs (default: 25) |
| `--all-hubs` | Check all 70+ hubs |
| `--direct-only` | Skip hub search — show direct price only |
| `--alert-below PRICE` | Print alert if best transfer < PRICE |
| `--save-route` | Save result to route history |
| `--no-cache` | Bypass 1-hour cache |
| `--timeout SECONDS` | Overall timeout (default: 600s) |
| `--json` | Raw JSON output |

## Self-Transfer Warning

A self-transfer involves two separate tickets. This means:
- No through-checked bags (carry-on only recommended)
- 3+ hour buffer between flights (airport transit time)
- Check transit visa requirements for the hub country
- No airline compensation if one leg is missed

## Output Interpretation

```
✅ 4 cheaper transfer(s) found:

  [ 1] LAX → ICN → HKG
       LAX→ICN: $320  +  ICN→HKG: $185  =  $505
       Save $295 (36.9%)   vs. direct $800

  🏆 BEST: LAX→ICN→HKG = $505  save $295 (36.9%)

  ⚠️  Self-transfer: 2 separate one-ways | carry-on only | 3h+ buffer | check ICN transit visa

  🔗 Book leg 1: https://www.google.com/flights#flt=LAX.ICN/2026-06-15
          leg 2: https://www.google.com/flights#flt=ICN.HKG/2026-06-15
```

## Caching

Results are cached for 1 hour in `~/.hermes/cache/flights/transfer_cache.db`.
Use `--no-cache` to force fresh data.

## Route History

With `--save-route`, results are appended to `~/.hermes/data/flight-searches.jsonl`.

## Limitations

- fast_flights uses Google Flights / Skyscanner pricing — real-time accurate
- Self-transfer prices are indicative; always confirm on the booking platform
- Hub coverage is biased toward major international airports
- Results improve with 2+ weeks advance booking
