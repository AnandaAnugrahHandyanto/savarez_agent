"""SPC-CTX context engine plugin for Hermes Agent.

Bridge to the hermes_spc_plugin package installed from
/Users/blitz/dev_ops/self-evolving/context-engine-py/src.
"""
from agent.context_engine import ContextEngine
from hermes_spc_plugin import SPCContextEngine, load_engine, register

# Register SPCContextEngine as a virtual subclass of ContextEngine so that
# isinstance / issubclass checks in the fallback discovery path succeed.
ContextEngine.register(SPCContextEngine)

__all__ = ["SPCContextEngine", "load_engine", "register"]
