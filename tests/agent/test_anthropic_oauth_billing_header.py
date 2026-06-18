"""Verify the OAuth billing-attribution system block.

The genuine Claude Code / Agent-SDK CLI sends an ``x-anthropic-billing-header``
text block as the FIRST entry of the system array
(``cc_version=...; cc_entrypoint=sdk-cli;``). Anthropic's billing gate uses it
to route OAuth/subscription requests to the plan's usage limits. Without it,
tool-bearing requests are classified as a generic third-party app and rejected
with HTTP 400 "Third-party apps now draw from extra usage, not plan limits."
"""


def _build(is_oauth, system=None, tools=None):
    from agent.anthropic_adapter import build_anthropic_kwargs

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": "Hi"})
    return build_anthropic_kwargs(
        model="claude-sonnet-4-6",
        messages=messages,
        tools=tools,
        max_tokens=4096,
        reasoning_config=None,
        is_oauth=is_oauth,
    )


def _is_billing_block(block):
    return (
        isinstance(block, dict)
        and block.get("type") == "text"
        and "x-anthropic-billing-header" in block.get("text", "")
        and "cc_entrypoint=sdk-cli" in block.get("text", "")
    )


class TestAnthropicOAuthBillingHeader:
    def test_billing_block_is_first_on_oauth(self):
        kwargs = _build(is_oauth=True, system="You are a helpful assistant.")
        system = kwargs["system"]
        assert isinstance(system, list)
        assert _is_billing_block(system[0])
        # Claude Code identity prefix follows the billing header.
        assert system[1]["text"].startswith("You are Claude Code")

    def test_billing_block_present_with_no_user_system(self):
        kwargs = _build(is_oauth=True)
        assert _is_billing_block(kwargs["system"][0])

    def test_billing_block_present_with_tools(self):
        kwargs = _build(
            is_oauth=True,
            tools=[{
                "type": "function",
                "function": {"name": "read_file", "description": "x", "parameters": {}},
            }],
        )
        assert _is_billing_block(kwargs["system"][0])

    def test_no_billing_block_on_non_oauth(self):
        kwargs = _build(is_oauth=False, system="You are a helpful assistant.")
        system = kwargs.get("system")
        blocks = system if isinstance(system, list) else ([system] if system else [])
        assert not any(_is_billing_block(b) for b in blocks)
