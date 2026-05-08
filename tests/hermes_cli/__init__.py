"""Test package helper.

Avoid shadowing the real `hermes_cli` package so imports like
`from hermes_cli import __version__, __release_date__` still succeed when
pytest puts `tests/` early on `sys.path`.
"""

__version__ = "0.12.0"
__release_date__ = "2026.4.30"
