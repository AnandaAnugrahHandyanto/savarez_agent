"""Eval 018: every public function in tools/file_tools.py has annotations."""

import inspect

import tools.file_tools as file_tools


def test_public_functions_typed() -> None:
    untyped: list[str] = []
    for name, fn in inspect.getmembers(file_tools, inspect.isfunction):
        if name.startswith("_"):
            continue
        if inspect.getmodule(fn) is not file_tools:
            continue
        sig = inspect.signature(fn)
        if sig.return_annotation is inspect.Signature.empty:
            untyped.append(f"{name}: missing return annotation")
            continue
        for pname, param in sig.parameters.items():
            if pname == "self":
                continue
            if param.kind in (
                inspect.Parameter.VAR_POSITIONAL,
                inspect.Parameter.VAR_KEYWORD,
            ):
                continue
            if param.annotation is inspect.Parameter.empty:
                untyped.append(f"{name}({pname}): missing annotation")
    assert not untyped, "\n".join(untyped)
