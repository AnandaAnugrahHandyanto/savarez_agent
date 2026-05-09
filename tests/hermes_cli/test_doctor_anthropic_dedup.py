"""Regression: anthropic ProviderProfile must not duplicate the dedicated
Anthropic doctor check via the generic Bearer-auth loop (issue #22346).
"""

from __future__ import annotations

import hermes_cli.doctor as doctor


def test_anthropic_excluded_from_generic_apikey_loop(monkeypatch):
    monkeypatch.setattr(doctor, "_APIKEY_PROVIDERS_CACHE", None, raising=False)

    providers = doctor._build_apikey_providers_list()

    labels = {entry[0].lower() for entry in providers}
    # Tuple shape: (display_label, env_vars, models_url, base_env, supports_models_endpoint)
    # An "anthropic"-shaped entry would mean the generic loop will re-check
    # Anthropic with Bearer auth and produce a 404 duplicate.
    assert "anthropic" not in labels
    assert all("anthropic" not in label for label in labels)


def test_known_static_providers_still_present(monkeypatch):
    monkeypatch.setattr(doctor, "_APIKEY_PROVIDERS_CACHE", None, raising=False)
    providers = doctor._build_apikey_providers_list()

    labels = {entry[0] for entry in providers}
    for required in ("Z.AI / GLM", "DeepSeek", "Hugging Face", "MiniMax"):
        assert required in labels, f"missing {required} from apikey providers"


def test_dedup_set_includes_anthropic_canonical():
    """Source-level guard: 'anthropic' must remain in the canonical skip set
    so future ProviderProfile reorderings still skip it.
    """
    import inspect

    src = inspect.getsource(doctor._build_apikey_providers_list)
    assert (
        '_known_canonical.add("anthropic")' in src
        or "_known_canonical.add('anthropic')" in src
    )
