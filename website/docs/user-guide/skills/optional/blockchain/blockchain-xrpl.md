---
title: "Xrpl"
sidebar_label: "Xrpl"
description: "Query XRP Ledger data with USD pricing - account reserves, trust lines, recent transactions, ledger stats, fees, and transaction details"
---

{/* This page is auto-generated from the skill's SKILL.md by website/scripts/generate-skill-docs.py. Edit the source SKILL.md, not this page. */}

# Xrpl

Query XRP Ledger data with USD pricing - account reserves, trust lines, recent transactions, ledger stats, fees, and transaction details. Uses public XRPL JSON-RPC + CoinGecko. No API key required.

## Skill metadata

| | |
|---|---|
| Source | Optional — install with `hermes skills install official/blockchain/xrpl` |
| Path | `optional-skills/blockchain/xrpl` |
| Version | `0.1.0` |
| Author | Osraka, Hermes Agent |
| License | MIT |
| Platforms | linux, macos, windows |
| Tags | `XRP`, `XRPL`, `XRP Ledger`, `Blockchain`, `Crypto`, `Web3`, `RPC`, `DeFi` |
| Related skills | [`solana`](/docs/user-guide/skills/optional/blockchain/blockchain-solana), [`base`](/docs/user-guide/skills/optional/blockchain/blockchain-base) |

## Reference: full SKILL.md

:::info
The following is the complete skill definition that Hermes loads when this skill is triggered. This is what the agent sees as instructions when the skill is active.
:::

# XRP Ledger Skill

Query XRP Ledger account and network data through public JSON-RPC endpoints,
with optional XRP/USD pricing from CoinGecko.

Read-only: no private keys, no signing, no transaction submission.

6 commands: account reserve and trust-line review, trust lines, recent activity,
transaction details, ledger stats, and price lookup. Uses only Python standard
library (`urllib`, `json`, `argparse`).

---

## When to Use

- User asks for an XRP Ledger account balance or reserve requirement
- User wants to inspect trust lines, IOU balances, or rippling exposure
- User wants recent XRPL activity for an account
- User wants to inspect a specific transaction by hash
- User wants live XRPL ledger, fee, reserve, or XRP price data
- User asks for a read-only XRPL account risk or exposure summary

---

## Prerequisites

The helper script uses only Python standard library. No external packages and
no API key are required.

Pricing data comes from CoinGecko's free API. It is optional and can be skipped
with `--no-price` when you only need RPC data.

---

## Quick Reference

RPC endpoint (default): https://s1.ripple.com:51234/
Override: export XRPL_RPC_URL=https://your-xrpl-rpc.example.com/

Helper script path: ~/.hermes/skills/blockchain/xrpl/scripts/xrpl_client.py

```bash
python3 xrpl_client.py stats [--no-price]
python3 xrpl_client.py account  <address> [--lines-limit N] [--tx-limit N] [--no-price]
python3 xrpl_client.py lines    <address> [--limit N]
python3 xrpl_client.py activity <address> [--limit N]
python3 xrpl_client.py tx       <transaction_hash>
python3 xrpl_client.py ledger   [--transactions]
python3 xrpl_client.py price
```

---

## Procedure

### 0. Setup Check

```bash
python3 --version

# Optional: set your preferred XRPL server
export XRPL_RPC_URL="https://s1.ripple.com:51234/"

# Confirm connectivity
python3 ~/.hermes/skills/blockchain/xrpl/scripts/xrpl_client.py stats
```

### 1. Account Reserve and Trust-Line Review

Get XRP balance, estimated USD value, reserve requirement, spendable XRP
estimate, trust-line summary, recent activity, and heuristic risk hints.

```bash
python3 ~/.hermes/skills/blockchain/xrpl/scripts/xrpl_client.py \
  account r9cZA1mLK5R5Am25ArfXFmqgNwjZgnfk59
```

Flags:
- `--lines-limit N` - fetch up to N trust lines (default: 50)
- `--tx-limit N` - fetch up to N recent transactions (default: 10)
- `--no-price` - skip CoinGecko price lookup

Output includes: XRP balance, `OwnerCount`, base and owner reserve values,
spendable XRP estimate, nonzero trust-line balances, open rippling count,
recent transaction summaries, and risk hints.

### 2. Trust Lines

List trust lines for an account, normalized by currency, peer, balance, limit,
and NoRipple flags.

```bash
python3 ~/.hermes/skills/blockchain/xrpl/scripts/xrpl_client.py \
  lines r9cZA1mLK5R5Am25ArfXFmqgNwjZgnfk59 --limit 100
```

Use this when a user asks about issued assets, IOUs, gateway exposure, or
rippling settings.

### 3. Recent Activity

Fetch recent transactions affecting an account.

```bash
python3 ~/.hermes/skills/blockchain/xrpl/scripts/xrpl_client.py \
  activity r9cZA1mLK5R5Am25ArfXFmqgNwjZgnfk59 --limit 20
```

Output includes transaction hash, type, result, ledger index, fee, date, and
normalized amount when present.

### 4. Transaction Details

Inspect a transaction by its 64-character hash.

```bash
python3 ~/.hermes/skills/blockchain/xrpl/scripts/xrpl_client.py \
  tx 7B9E7C4E2F...your_transaction_hash_here
```

Output includes the raw transaction result from the XRPL server, plus a compact
summary with transaction type, result, ledger index, fee, account, destination,
and amount when present.

### 5. Ledger and Network Stats

Live XRPL health: server state, validated ledger, reserve values, current fee
levels, and optional XRP/USD price.

```bash
python3 ~/.hermes/skills/blockchain/xrpl/scripts/xrpl_client.py stats
python3 ~/.hermes/skills/blockchain/xrpl/scripts/xrpl_client.py ledger
```

Use `ledger --transactions` to include transaction hashes from the latest
validated ledger. This can be larger than the default response.

### 6. Price Lookup

```bash
python3 ~/.hermes/skills/blockchain/xrpl/scripts/xrpl_client.py price
```

Returns XRP/USD from CoinGecko's free API.

---

## Pitfalls

- Public XRPL servers can rate-limit or have different ledger history windows.
  Use `XRPL_RPC_URL` with a trusted full-history server if you need older
  account activity.
- Reserve calculations use the server's current `reserve_base_xrp` and
  `reserve_inc_xrp` values from `server_info`, then multiply owner reserve by
  `OwnerCount`.
- Trust-line balances are from the queried account's perspective. Negative
  balances and open rippling flags are exposure signals, not automatic proof of
  a problem.
- Some issued currencies use 160-bit hex currency codes. The helper decodes
  ASCII-style codes when possible and otherwise returns the original code.
- The account review is heuristic. It does not replace wallet security review,
  issuer due diligence, or financial advice.
- This skill is read-only. It intentionally does not support signing,
  submitting transactions, or handling secrets.

---

## Verification

```bash
# Should print validated ledger, fee, reserve, and optional XRP price data
python3 ~/.hermes/skills/blockchain/xrpl/scripts/xrpl_client.py stats

# Should print account reserve and trust-line summary for a public sample address
python3 ~/.hermes/skills/blockchain/xrpl/scripts/xrpl_client.py \
  account r9cZA1mLK5R5Am25ArfXFmqgNwjZgnfk59 --no-price
```
