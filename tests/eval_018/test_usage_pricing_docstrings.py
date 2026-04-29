"""Eval 018: every class defined in agent/usage_pricing.py has a docstring.

We check via AST rather than ``inspect.getdoc`` because dataclasses
auto-generate a __doc__ string from the signature; the prompt is asking
the agent to add an explicit class-level docstring.
"""

import ast
import inspect
from pathlib import Path

import agent.usage_pricing as usage_pricing


def test_classes_have_docstrings() -> None:
    src = Path(inspect.getsourcefile(usage_pricing) or "").read_text()
    tree = ast.parse(src)
    missing: list[str] = []
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        if not node.body:
            missing.append(node.name)
            continue
        first = node.body[0]
        if not (
            isinstance(first, ast.Expr)
            and isinstance(first.value, ast.Constant)
            and isinstance(first.value.value, str)
            and first.value.value.strip()
        ):
            missing.append(node.name)
    assert not missing, (
        f"Classes without explicit docstrings in agent/usage_pricing.py: {missing}"
    )
