# Testing And Validation

Use the smallest useful validation for the touched Hermes area.

Preferred validation:

- targeted `python -m pytest` or the repo's test runner for the touched gateway surface
- contract tests around `tui_gateway/server.py`
- focused regression tests for new RPC methods, capability responses, and error envelopes

For Leonidas fork work, prioritize:

- capability negotiation tests
- planning request/response schema tests
- failure-path tests for unsupported versions, kinds, and malformed payloads

Keep validation narrow and do not broaden to unrelated platform or UI tests unless the gateway change reaches those surfaces.
