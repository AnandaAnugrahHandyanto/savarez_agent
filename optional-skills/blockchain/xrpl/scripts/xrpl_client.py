#!/usr/bin/env python3
"""
XRP Ledger CLI Tool for Hermes Agent.

Read-only helper for XRPL JSON-RPC data: account reserves, trust lines,
recent activity, transaction details, ledger stats, fees, and XRP price.
Uses only Python standard library.
"""

import argparse
import datetime as dt
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional, Tuple


RPC_URL = os.environ.get("XRPL_RPC_URL", "https://s1.ripple.com:51234/")
COINGECKO_XRP_PRICE_URL = (
    "https://api.coingecko.com/api/v3/simple/price"
    "?ids=ripple&vs_currencies=usd"
)

DROPS_PER_XRP = Decimal("1000000")
ADDRESS_RE = re.compile(r"^r[1-9A-HJ-NP-Za-km-z]{24,34}$")
TX_HASH_RE = re.compile(r"^[0-9A-Fa-f]{64}$")
HEX_CURRENCY_RE = re.compile(r"^[0-9A-Fa-f]{40}$")
RIPPLE_EPOCH_OFFSET = 946684800


def print_json(obj: Any) -> None:
    print(json.dumps(obj, indent=2, sort_keys=False))


def _short(value: str, front: int = 8, back: int = 6) -> str:
    if not isinstance(value, str) or len(value) <= front + back + 3:
        return value
    return f"{value[:front]}...{value[-back:]}"


def _decimal_or_none(value: Any) -> Optional[Decimal]:
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _decimal_to_float(value: Optional[Decimal], places: str = "0.000001") -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value.quantize(Decimal(places)))
    except InvalidOperation:
        return float(value)


def drops_to_xrp(drops: Any) -> Optional[float]:
    value = _decimal_or_none(drops)
    if value is None:
        return None
    return _decimal_to_float(value / DROPS_PER_XRP)


def _validate_address(address: str) -> None:
    if not ADDRESS_RE.match(address):
        sys.exit(f"Invalid XRPL classic address: {address}")


def _validate_tx_hash(tx_hash: str) -> None:
    if not TX_HASH_RE.match(tx_hash):
        sys.exit("Invalid XRPL transaction hash: expected 64 hex characters")


def _http_json(url: str, timeout: int = 15, retries: int = 2) -> Any:
    for attempt in range(retries + 1):
        req = urllib.request.Request(
            url,
            headers={
                "Accept": "application/json",
                "User-Agent": "HermesAgent-XRPL/1.0",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.load(resp)
        except urllib.error.HTTPError as exc:
            if exc.code in (429, 500, 502, 503, 504) and attempt < retries:
                time.sleep(1.5 * (attempt + 1))
                continue
            return None
        except Exception:
            return None
    return None


def rpc(method: str, params: Optional[Dict[str, Any]] = None, retries: int = 2) -> Dict[str, Any]:
    payload = json.dumps({
        "method": method,
        "params": [params or {}],
        "id": 1,
        "jsonrpc": "2.0",
    }).encode()

    for attempt in range(retries + 1):
        req = urllib.request.Request(
            RPC_URL,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "HermesAgent-XRPL/1.0",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                body = json.load(resp)
        except urllib.error.HTTPError as exc:
            if exc.code in (429, 500, 502, 503, 504) and attempt < retries:
                time.sleep(1.5 * (attempt + 1))
                continue
            sys.exit(f"XRPL RPC HTTP error: {exc}")
        except urllib.error.URLError as exc:
            sys.exit(f"XRPL RPC connection error: {exc}")

        if "error" in body:
            sys.exit(f"XRPL RPC error: {body['error']}")

        result = body.get("result")
        if not isinstance(result, dict):
            sys.exit(f"Unexpected XRPL RPC response for {method}")

        if result.get("status") == "error" or result.get("error"):
            message = result.get("error_message") or result.get("error") or "unknown error"
            sys.exit(f"XRPL {method} error: {message}")

        return result

    sys.exit(f"XRPL RPC failed after retries: {method}")


def fetch_xrp_price() -> Optional[float]:
    data = _http_json(COINGECKO_XRP_PRICE_URL, timeout=10)
    if isinstance(data, dict):
        price = data.get("ripple", {}).get("usd")
        if isinstance(price, (int, float)):
            return float(price)
    return None


def _server_info() -> Dict[str, Any]:
    result = rpc("server_info")
    info = result.get("info")
    return info if isinstance(info, dict) else result


def _reserve_values(info: Optional[Dict[str, Any]] = None) -> Dict[str, Optional[float]]:
    info = info or _server_info()
    ledger = info.get("validated_ledger") or info.get("closed_ledger") or {}
    base = _decimal_or_none(ledger.get("reserve_base_xrp"))
    inc = _decimal_or_none(ledger.get("reserve_inc_xrp"))
    return {
        "base_xrp": _decimal_to_float(base),
        "owner_xrp": _decimal_to_float(inc),
    }


def _ripple_time_to_iso(value: Any) -> Optional[str]:
    if not isinstance(value, int):
        return None
    return dt.datetime.fromtimestamp(
        value + RIPPLE_EPOCH_OFFSET,
        tz=dt.timezone.utc,
    ).isoformat().replace("+00:00", "Z")


def _currency_label(code: Any) -> str:
    if not isinstance(code, str):
        return str(code)
    if HEX_CURRENCY_RE.match(code):
        try:
            decoded = bytes.fromhex(code).rstrip(b"\x00").decode("ascii", "ignore").strip()
            return decoded or code
        except ValueError:
            return code
    return code


def _normalize_amount(amount: Any) -> Dict[str, Any]:
    if isinstance(amount, str):
        return {
            "type": "xrp",
            "drops": amount,
            "xrp": drops_to_xrp(amount),
        }
    if isinstance(amount, dict):
        return {
            "type": "issued",
            "currency": _currency_label(amount.get("currency")),
            "issuer": amount.get("issuer"),
            "value": amount.get("value"),
        }
    return {"type": "unknown", "raw": amount}


def _tx_payload(item: Dict[str, Any]) -> Dict[str, Any]:
    tx = item.get("tx") or item.get("tx_json") or item.get("transaction") or item
    return tx if isinstance(tx, dict) else {}


def _tx_meta(item: Dict[str, Any]) -> Dict[str, Any]:
    meta = item.get("meta") or item.get("metaData") or item.get("metadata") or {}
    return meta if isinstance(meta, dict) else {}


def _summarize_tx(item: Dict[str, Any]) -> Dict[str, Any]:
    tx = _tx_payload(item)
    meta = _tx_meta(item)
    amount = tx.get("Amount") if "Amount" in tx else tx.get("DeliverMax")

    return {
        "hash": tx.get("hash") or item.get("hash"),
        "type": tx.get("TransactionType"),
        "account": tx.get("Account"),
        "destination": tx.get("Destination"),
        "ledger_index": item.get("ledger_index") or tx.get("ledger_index"),
        "validated": item.get("validated"),
        "result": meta.get("TransactionResult"),
        "fee_xrp": drops_to_xrp(tx.get("Fee")) if tx.get("Fee") else None,
        "date": _ripple_time_to_iso(tx.get("date")),
        "amount": _normalize_amount(amount) if amount is not None else None,
    }


def fetch_lines(account: str, limit: int) -> Tuple[List[Dict[str, Any]], bool]:
    if limit <= 0:
        return [], False

    lines: List[Dict[str, Any]] = []
    marker = None

    while len(lines) < limit:
        page_limit = min(400, max(10, limit - len(lines)))
        params: Dict[str, Any] = {
            "account": account,
            "ledger_index": "validated",
            "limit": page_limit,
        }
        if marker is not None:
            params["marker"] = marker

        result = rpc("account_lines", params)
        batch = result.get("lines", [])
        if isinstance(batch, list):
            lines.extend(batch)

        marker = result.get("marker")
        if not marker:
            break

    truncated = marker is not None
    return lines[:limit], truncated


def fetch_activity(account: str, limit: int) -> Tuple[List[Dict[str, Any]], bool]:
    if limit <= 0:
        return [], False

    params = {
        "account": account,
        "ledger_index_min": -1,
        "ledger_index_max": -1,
        "binary": False,
        "forward": False,
        "limit": min(max(limit, 1), 100),
    }
    result = rpc("account_tx", params)
    transactions = result.get("transactions", [])
    if not isinstance(transactions, list):
        transactions = []
    return transactions[:limit], result.get("marker") is not None


def _normalize_line(line: Dict[str, Any]) -> Dict[str, Any]:
    balance = str(line.get("balance", "0"))
    return {
        "peer": line.get("account"),
        "currency": _currency_label(line.get("currency")),
        "balance": balance,
        "limit": line.get("limit"),
        "limit_peer": line.get("limit_peer"),
        "no_ripple": bool(line.get("no_ripple", False)),
        "no_ripple_peer": bool(line.get("no_ripple_peer", False)),
        "quality_in": line.get("quality_in"),
        "quality_out": line.get("quality_out"),
    }


def summarize_lines(lines: List[Dict[str, Any]]) -> Dict[str, Any]:
    nonzero: List[Dict[str, Any]] = []
    currency_counts: Dict[str, int] = {}
    negative_count = 0
    rippling_open_count = 0

    for raw in lines:
        line = _normalize_line(raw)
        currency = line["currency"]
        currency_counts[currency] = currency_counts.get(currency, 0) + 1

        balance_dec = _decimal_or_none(line["balance"]) or Decimal("0")
        if balance_dec != 0:
            nonzero.append(line)
        if balance_dec < 0:
            negative_count += 1
        if line.get("no_ripple") is False:
            rippling_open_count += 1

    nonzero_sorted = sorted(
        nonzero,
        key=lambda item: abs(_decimal_or_none(item.get("balance")) or Decimal("0")),
        reverse=True,
    )

    return {
        "total_fetched": len(lines),
        "nonzero_balances": len(nonzero),
        "negative_balances": negative_count,
        "rippling_open_lines": rippling_open_count,
        "currencies": currency_counts,
        "top_nonzero": nonzero_sorted[:10],
    }


def build_risk_hints(
    balance_xrp: Optional[float],
    spendable_xrp: Optional[float],
    owner_count: int,
    line_summary: Dict[str, Any],
) -> List[str]:
    hints: List[str] = []

    if spendable_xrp is not None and spendable_xrp < 1:
        hints.append("Spendable XRP is below 1 after the current reserve estimate.")
    if owner_count >= 20:
        hints.append("OwnerCount is high; many ledger objects increase reserve lockup.")
    if line_summary.get("rippling_open_lines", 0) > 0:
        hints.append("Some trust lines have NoRipple disabled from this account's side.")
    if line_summary.get("negative_balances", 0) > 0:
        hints.append("Some trust-line balances are negative from this account's perspective.")
    if balance_xrp == 0:
        hints.append("Account has zero XRP balance in the latest validated account data.")
    if not hints:
        hints.append("No obvious reserve or trust-line exposure hints from fetched data.")

    return hints


def cmd_stats(args: argparse.Namespace) -> None:
    info = _server_info()
    ledger = info.get("validated_ledger") or info.get("closed_ledger") or {}
    fee = rpc("fee")
    reserves = _reserve_values(info)
    price = None if args.no_price else fetch_xrp_price()

    print_json({
        "network": "xrp-ledger-mainnet",
        "rpc_url": RPC_URL,
        "server_state": info.get("server_state"),
        "build_version": info.get("build_version"),
        "validated_ledger": {
            "seq": ledger.get("seq"),
            "hash": ledger.get("hash"),
            "age_seconds": ledger.get("age"),
            "base_fee_xrp": ledger.get("base_fee_xrp"),
            "reserve_base_xrp": reserves.get("base_xrp"),
            "reserve_inc_xrp": reserves.get("owner_xrp"),
        },
        "load_factor": info.get("load_factor"),
        "fee": {
            "current_ledger_size": fee.get("current_ledger_size"),
            "expected_ledger_size": fee.get("expected_ledger_size"),
            "drops": fee.get("drops"),
            "levels": fee.get("levels"),
        },
        "xrp_price_usd": price,
    })


def cmd_account(args: argparse.Namespace) -> None:
    _validate_address(args.address)

    info = _server_info()
    reserves = _reserve_values(info)
    account_result = rpc("account_info", {
        "account": args.address,
        "ledger_index": "validated",
        "signer_lists": True,
    })
    account_data = account_result.get("account_data", {})

    lines, lines_truncated = fetch_lines(args.address, args.lines_limit)
    transactions, tx_truncated = fetch_activity(args.address, args.tx_limit)
    line_summary = summarize_lines(lines)

    balance_xrp = drops_to_xrp(account_data.get("Balance"))
    owner_count = int(account_data.get("OwnerCount") or 0)
    base_reserve = reserves.get("base_xrp")
    owner_reserve = reserves.get("owner_xrp")
    required_reserve = None
    spendable = None
    if base_reserve is not None and owner_reserve is not None:
        required_reserve = base_reserve + (owner_count * owner_reserve)
        if balance_xrp is not None:
            spendable = round(balance_xrp - required_reserve, 6)

    price = None if args.no_price else fetch_xrp_price()
    value_usd = round(balance_xrp * price, 2) if balance_xrp is not None and price else None

    print_json({
        "account": args.address,
        "ledger_index": account_result.get("ledger_index") or account_result.get("ledger_current_index"),
        "xrp_balance": balance_xrp,
        "xrp_value_usd": value_usd,
        "sequence": account_data.get("Sequence"),
        "flags": account_data.get("Flags"),
        "owner_count": owner_count,
        "reserve": {
            "base_xrp": base_reserve,
            "owner_reserve_xrp": owner_reserve,
            "required_xrp": round(required_reserve, 6) if required_reserve is not None else None,
            "spendable_xrp_estimate": spendable,
        },
        "trust_lines": {
            **line_summary,
            "truncated": lines_truncated,
        },
        "recent_activity": {
            "count": len(transactions),
            "truncated": tx_truncated,
            "transactions": [_summarize_tx(item) for item in transactions],
        },
        "risk_hints": build_risk_hints(balance_xrp, spendable, owner_count, line_summary),
    })


def cmd_lines(args: argparse.Namespace) -> None:
    _validate_address(args.address)
    lines, truncated = fetch_lines(args.address, args.limit)
    print_json({
        "account": args.address,
        "count": len(lines),
        "truncated": truncated,
        "summary": summarize_lines(lines),
        "lines": [_normalize_line(line) for line in lines],
    })


def cmd_activity(args: argparse.Namespace) -> None:
    _validate_address(args.address)
    transactions, truncated = fetch_activity(args.address, args.limit)
    print_json({
        "account": args.address,
        "count": len(transactions),
        "truncated": truncated,
        "transactions": [_summarize_tx(item) for item in transactions],
    })


def cmd_tx(args: argparse.Namespace) -> None:
    _validate_tx_hash(args.hash)
    result = rpc("tx", {
        "transaction": args.hash,
        "binary": False,
    })
    print_json({
        "hash": args.hash.upper(),
        "summary": _summarize_tx(result),
        "raw": result,
    })


def cmd_ledger(args: argparse.Namespace) -> None:
    result = rpc("ledger", {
        "ledger_index": "validated",
        "transactions": bool(args.transactions),
        "expand": False,
    })
    ledger = result.get("ledger", {})
    transactions = ledger.get("transactions") if isinstance(ledger, dict) else None
    print_json({
        "ledger_index": result.get("ledger_index") or ledger.get("ledger_index"),
        "ledger_hash": result.get("ledger_hash") or ledger.get("ledger_hash"),
        "close_time": _ripple_time_to_iso(ledger.get("close_time")) if isinstance(ledger, dict) else None,
        "transaction_count": len(transactions) if isinstance(transactions, list) else None,
        "ledger": ledger,
    })


def cmd_price(_args: argparse.Namespace) -> None:
    print_json({
        "asset": "XRP",
        "price_usd": fetch_xrp_price(),
        "source": "CoinGecko simple price API",
    })


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="xrpl_client.py",
        description="Read-only XRP Ledger query tool for Hermes Agent",
    )
    parser.add_argument(
        "--rpc-url",
        default=None,
        help="Override XRPL JSON-RPC endpoint for this run",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    p_stats = sub.add_parser("stats", help="Show live XRPL ledger, fee, reserve, and price data")
    p_stats.add_argument("--no-price", action="store_true", help="Skip CoinGecko price lookup")
    p_stats.set_defaults(func=cmd_stats)

    p_account = sub.add_parser("account", help="Review account balance, reserves, trust lines, and activity")
    p_account.add_argument("address")
    p_account.add_argument("--lines-limit", type=int, default=50)
    p_account.add_argument("--tx-limit", type=int, default=10)
    p_account.add_argument("--no-price", action="store_true", help="Skip CoinGecko price lookup")
    p_account.set_defaults(func=cmd_account)

    p_lines = sub.add_parser("lines", help="List account trust lines")
    p_lines.add_argument("address")
    p_lines.add_argument("--limit", type=int, default=50)
    p_lines.set_defaults(func=cmd_lines)

    p_activity = sub.add_parser("activity", help="List recent transactions affecting an account")
    p_activity.add_argument("address")
    p_activity.add_argument("--limit", type=int, default=10)
    p_activity.set_defaults(func=cmd_activity)

    p_tx = sub.add_parser("tx", help="Inspect a transaction by hash")
    p_tx.add_argument("hash")
    p_tx.set_defaults(func=cmd_tx)

    p_ledger = sub.add_parser("ledger", help="Show the latest validated ledger")
    p_ledger.add_argument("--transactions", action="store_true", help="Include transaction hashes")
    p_ledger.set_defaults(func=cmd_ledger)

    p_price = sub.add_parser("price", help="Show XRP/USD price")
    p_price.set_defaults(func=cmd_price)

    return parser


def main() -> None:
    global RPC_URL
    parser = build_parser()
    args = parser.parse_args()
    if args.rpc_url:
        RPC_URL = args.rpc_url
    args.func(args)


if __name__ == "__main__":
    main()
