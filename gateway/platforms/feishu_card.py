"""Feishu Interactive Card builder.

Constructs card JSON for FeishuAdapter — handles content → card element
conversion, markdown table parsing, tool semantic mapping, and footer
field formatting. Only imported by feishu.py; no upstream dependencies.
"""
from __future__ import annotations


def format_token_count(value: int) -> str:
    if value < 0:
        value = 0
    if value < 1000:
        return str(value)
    if value < 1_000_000:
        return f"{value / 1000:.1f}k"
    return f"{value / 1_000_000:.1f}M"
