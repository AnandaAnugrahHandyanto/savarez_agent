"""Small read-only utility tools for low-latency gateway quick chat."""

from __future__ import annotations

import ast
import json
import math
import operator
from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from tools.registry import registry


SAFE_TIME_SCHEMA = {
    "name": "safe_time",
    "description": (
        "Return the current date/time for a requested IANA timezone. "
        "Read-only and deterministic apart from the clock."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "timezone": {
                "type": "string",
                "description": "IANA timezone name such as UTC, Asia/Seoul, or Australia/Sydney. Defaults to UTC.",
                "default": "UTC",
            }
        },
    },
}

SAFE_CALCULATOR_SCHEMA = {
    "name": "safe_calculator",
    "description": (
        "Evaluate a simple arithmetic expression safely. Supports numbers, "
        "parentheses, +, -, *, /, //, %, **, and constants pi, e, tau."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "expression": {
                "type": "string",
                "description": "Arithmetic expression to evaluate, for example '(12.5 * 3) / 2'.",
            }
        },
        "required": ["expression"],
    },
}

_BIN_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_UNARY_OPS = {ast.UAdd: operator.pos, ast.USub: operator.neg}
_CONSTANTS = {"pi": math.pi, "e": math.e, "tau": math.tau}
_MAX_EXPRESSION_CHARS = 200
_MAX_ABS_VALUE = 1e100
_MAX_ABS_EXPONENT = 12


def _json(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True)


def safe_time_tool(tz_name: str | None = None) -> str:
    requested = (tz_name or "UTC").strip() or "UTC"
    try:
        tz = timezone.utc if requested.upper() == "UTC" else ZoneInfo(requested)
    except ZoneInfoNotFoundError:
        return _json({"ok": False, "error": f"Unknown timezone: {requested}"})

    now = datetime.now(tz)
    return _json(
        {
            "ok": True,
            "timezone": requested,
            "iso": now.isoformat(timespec="seconds"),
            "unix": int(now.timestamp()),
            "utc_iso": now.astimezone(timezone.utc).isoformat(timespec="seconds"),
        }
    )


def _guard_number(value: float | int) -> float | int:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError("Only numeric arithmetic is supported")
    if not math.isfinite(float(value)):
        raise ValueError("Result is not finite")
    if abs(float(value)) > _MAX_ABS_VALUE:
        raise ValueError("Result magnitude is too large")
    return value


def _eval_node(node: ast.AST) -> float | int:
    if isinstance(node, ast.Expression):
        return _eval_node(node.body)
    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
            raise ValueError("Only numeric constants are supported")
        return _guard_number(node.value)
    if isinstance(node, ast.Name):
        if node.id in _CONSTANTS:
            return _CONSTANTS[node.id]
        raise ValueError(f"Unknown constant: {node.id}")
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY_OPS:
        return _guard_number(_UNARY_OPS[type(node.op)](_eval_node(node.operand)))
    if isinstance(node, ast.BinOp) and type(node.op) in _BIN_OPS:
        left = _eval_node(node.left)
        right = _eval_node(node.right)
        if isinstance(node.op, ast.Pow) and abs(float(right)) > _MAX_ABS_EXPONENT:
            raise ValueError("Exponent is too large")
        return _guard_number(_BIN_OPS[type(node.op)](left, right))
    raise ValueError("Unsupported expression")


def safe_calculator_tool(expression: str) -> str:
    expr = str(expression or "").strip()
    if not expr:
        return _json({"ok": False, "error": "Expression is required"})
    if len(expr) > _MAX_EXPRESSION_CHARS:
        return _json({"ok": False, "error": "Expression is too long"})
    try:
        parsed = ast.parse(expr, mode="eval")
        result = _eval_node(parsed)
    except ZeroDivisionError:
        return _json({"ok": False, "error": "Division by zero"})
    except Exception as exc:
        return _json({"ok": False, "error": str(exc)})

    return _json({"ok": True, "expression": expr, "result": result})


registry.register(
    name="safe_time",
    toolset="quick_chat",
    schema=SAFE_TIME_SCHEMA,
    handler=lambda args, **kw: safe_time_tool(args.get("timezone", "UTC")),
    emoji="🕒",
)

registry.register(
    name="safe_calculator",
    toolset="quick_chat",
    schema=SAFE_CALCULATOR_SCHEMA,
    handler=lambda args, **kw: safe_calculator_tool(args.get("expression", "")),
    emoji="🧮",
)
