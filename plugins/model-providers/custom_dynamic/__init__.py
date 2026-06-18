"""Custom / dynamic-models provider profile.

Sibling of the ``custom`` plugin. Same wire shape (OpenAI-compatible
endpoint, user-supplied base_url, ``think=false`` + ``num_ctx`` support
for Ollama-class servers), but a distinct provider id so picker rows
and ``custom_providers[]`` entries declare *dynamic* intent up front:
the runtime always probes ``GET {base_url}/models`` for the model
catalog instead of using whatever the config pins.

Design doc: ``20260613_hermes-custom-dynamic-provider-design.md`` §2.
"""

from providers import register_provider

from plugins.model_providers.custom import CustomProfile


custom_dynamic = CustomProfile(
    name="custom_dynamic",
    display_name="Custom (dynamic)",
    description="Custom endpoint with live /models discovery (llama-swap, local Ollama, Bifrost)",
    aliases=(),  # no aliases — `custom_dynamic` is opted-in explicitly
    env_vars=(),
    base_url="",
    default_max_tokens=65536,
)

register_provider(custom_dynamic)
