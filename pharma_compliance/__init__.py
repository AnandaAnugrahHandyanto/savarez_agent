"""
Pharma Compliance Agent — multimodal QQbot handler.

Handles text, voice (STT), and photo (Vision+OCR+EXIF) messages for
pharmaceutical representative visit compliance tracking.
"""

__version__ = "1.0.0"


def register(ctx):
    """Register the pharma compliance plugin with Hermes plugin system.

    Called by the Hermes plugin loader at startup.  Registers a single
    ``pre_gateway_dispatch`` hook that intercepts incoming QQbot messages
    before they reach the Agent.
    """
    from pharma_compliance.plugin_adapter import PharmaCompliancePlugin

    plugin = PharmaCompliancePlugin()
    ctx.register_hook("pre_gateway_dispatch", plugin.on_gateway_dispatch)
