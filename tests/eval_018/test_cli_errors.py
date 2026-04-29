"""Eval 018: cli.py defines and uses a CliError subclass."""

import ast
import inspect
from pathlib import Path


def test_cli_uses_clierror() -> None:
    import cli

    assert hasattr(cli, "CliError"), "CliError class is not defined in cli module"
    assert isinstance(cli.CliError, type), "CliError must be a class"
    assert issubclass(cli.CliError, Exception), (
        "CliError must subclass Exception"
    )

    src_path = Path(inspect.getsourcefile(cli) or "")
    tree = ast.parse(src_path.read_text())

    raise_clierror_count = 0
    for node in ast.walk(tree):
        if not isinstance(node, ast.Raise) or node.exc is None:
            continue
        exc = node.exc
        if isinstance(exc, ast.Call):
            exc = exc.func
        if isinstance(exc, ast.Name) and exc.id == "CliError":
            raise_clierror_count += 1
        elif isinstance(exc, ast.Attribute) and exc.attr == "CliError":
            raise_clierror_count += 1

    assert raise_clierror_count >= 3, (
        f"Expected ≥3 `raise CliError(...)` sites in cli.py, found {raise_clierror_count}"
    )
