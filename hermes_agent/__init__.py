"""UCPM-specific code for the hermes agent runtime.

This package is namespaced separately from the upstream `hermes`/`hermes_cli`
modules so it can be carried through upstream rebases without conflicts.
Everything UCPM-specific (per-property loops, SOP-driven procedures, the
agent personas defined in `paperclip-UCPM/companies/ucpm-default/SOP.md`)
lives here.
"""

__version__ = "0.1.0"
