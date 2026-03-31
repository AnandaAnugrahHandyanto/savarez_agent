"""Tests for MiniMax M2.7 model upgrade.

Validates that MiniMax-M2.7 and MiniMax-M2.7-highspeed are correctly
registered across all model catalogs: provider model lists, context
window metadata, and OpenRouter model references.
"""

import ast
import re
import pytest


# ---------------------------------------------------------------------------
# Helpers – parse Python source ASTs to extract model lists without importing
# ---------------------------------------------------------------------------

def _extract_dict_literal(source: str, variable_name: str) -> dict:
    """Extract a top-level dict assignment from Python source."""
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == variable_name:
                    return ast.literal_eval(node.value)
    raise ValueError(f"{variable_name!r} not found")


def _read(path: str) -> str:
    with open(path) as f:
        return f.read()


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------

class TestMiniMaxM27ContextWindows:
    """model_metadata.py should list M2.7 context windows."""

    @pytest.fixture(autouse=True)
    def load_metadata(self):
        src = _read("agent/model_metadata.py")
        # Parse DEFAULT_CONTEXT_LENGTHS – it's the second dict (bare model IDs)
        tree = ast.parse(src)
        dicts = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for t in node.targets:
                    if isinstance(t, ast.Name) and "CONTEXT" in t.id:
                        dicts[t.id] = ast.literal_eval(node.value)
        self.default_ctx = dicts.get("DEFAULT_CONTEXT_LENGTHS", {})

    def test_m27_in_context_lengths(self):
        assert "minimax-m2.7" in self.default_ctx
        assert self.default_ctx["minimax-m2.7"] == 204800

    def test_m27_highspeed_in_context_lengths(self):
        assert "minimax-m2.7-highspeed" in self.default_ctx
        assert self.default_ctx["minimax-m2.7-highspeed"] == 204800

    def test_m25_still_present(self):
        assert "minimax-m2.5" in self.default_ctx


class TestMiniMaxM27ProviderModels:
    """main.py _PROVIDER_MODELS should list M2.7 for both minimax providers."""

    @pytest.fixture(autouse=True)
    def load_provider_models(self):
        src = _read("hermes_cli/main.py")
        # Extract _PROVIDER_MODELS dict using regex since it's deeply nested
        # Find the assignment and parse just that portion
        match = re.search(r'_PROVIDER_MODELS\s*=\s*\{', src)
        assert match, "_PROVIDER_MODELS not found in main.py"
        start = match.start()
        # Find matching closing brace
        depth = 0
        for i, c in enumerate(src[start:], start):
            if c == '{':
                depth += 1
            elif c == '}':
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
        self.provider_models = ast.literal_eval(src[start + len("_PROVIDER_MODELS = "):end])

    def test_minimax_has_m27(self):
        models = self.provider_models["minimax"]
        assert "MiniMax-M2.7" in models
        assert "MiniMax-M2.7-highspeed" in models

    def test_minimax_cn_has_m27(self):
        models = self.provider_models["minimax-cn"]
        assert "MiniMax-M2.7" in models
        assert "MiniMax-M2.7-highspeed" in models

    def test_m27_listed_before_m25(self):
        """M2.7 should appear before M2.5 (newest first)."""
        models = self.provider_models["minimax"]
        idx_m27 = models.index("MiniMax-M2.7")
        idx_m25 = models.index("MiniMax-M2.5")
        assert idx_m27 < idx_m25

    def test_minimax_still_has_m25(self):
        models = self.provider_models["minimax"]
        assert "MiniMax-M2.5" in models
        assert "MiniMax-M2.5-highspeed" in models

    def test_minimax_cn_still_has_m25(self):
        models = self.provider_models["minimax-cn"]
        assert "MiniMax-M2.5" in models


class TestMiniMaxM27OpenRouter:
    """models.py should reference M2.7 on OpenRouter."""

    def test_openrouter_uses_m27(self):
        src = _read("hermes_cli/models.py")
        assert 'minimax/minimax-m2.7' in src
        # Should NOT have the old m2.5 OpenRouter reference
        # (the tuple entry, not the bare ID list)
        assert '("minimax/minimax-m2.5"' not in src


class TestMiniMaxM27BareIDs:
    """models.py opencode-zen / opencode-go bare ID lists should include M2.7."""

    def test_opencode_zen_has_m27(self):
        src = _read("hermes_cli/models.py")
        # Find opencode-zen list
        match = re.search(r'"opencode-zen":\s*\[([^\]]+)\]', src, re.DOTALL)
        assert match, "opencode-zen not found in models.py"
        block = match.group(1)
        assert '"minimax-m2.7"' in block

    def test_opencode_go_has_m27(self):
        src = _read("hermes_cli/models.py")
        match = re.search(r'"opencode-go":\s*\[([^\]]+)\]', src, re.DOTALL)
        assert match, "opencode-go not found in models.py"
        block = match.group(1)
        assert '"minimax-m2.7"' in block


class TestMiniMaxM27AuxiliaryDefaults:
    """auxiliary_client.py should default to M2.7-highspeed."""

    def test_auxiliary_defaults_m27(self):
        src = _read("agent/auxiliary_client.py")
        assert 'MiniMax-M2.7-highspeed' in src


# ---------------------------------------------------------------------------
# Integration-style tests (still file-based, no network)
# ---------------------------------------------------------------------------

class TestMiniMaxM27CrossFileConsistency:
    """Cross-file consistency: all M2.7 references should agree."""

    def test_model_metadata_has_both_canonical_and_bare(self):
        src = _read("agent/model_metadata.py")
        assert '"MiniMax-M2.7"' in src
        assert '"MiniMax-M2.7-highspeed"' in src
        assert '"minimax-m2.7"' in src
        assert '"minimax-m2.7-highspeed"' in src

    def test_context_window_is_204k(self):
        """All MiniMax M2.7 context windows should be 204800."""
        src = _read("agent/model_metadata.py")
        for line in src.splitlines():
            if "m2.7" in line.lower() and ":" in line:
                assert "204800" in line, f"Wrong context window: {line.strip()}"

    def test_provider_models_match_between_files(self):
        """minimax provider lists in main.py and models.py should both have M2.7."""
        main_src = _read("hermes_cli/main.py")
        models_src = _read("hermes_cli/models.py")

        for src, filename in [(main_src, "main.py"), (models_src, "models.py")]:
            match = re.search(r'"minimax":\s*\[([^\]]+)\]', src, re.DOTALL)
            assert match, f"minimax provider not found in {filename}"
            block = match.group(1)
            assert "M2.7" in block, f"M2.7 missing from minimax in {filename}"
