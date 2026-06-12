"""Regression test for _extract_pricing crash on list-typed values — issue #32618."""

from __future__ import annotations

from agent.model_metadata import _extract_pricing


class TestExtractPricingListTypedValues:
    """_extract_pricing must skip list-typed pricing fields, not crash."""

    def test_list_typed_pricing_value_skipped(self) -> None:
        """zenmux.ai returns completion as list of objects — must not TypeError."""
        payload = {
            "data": [
                {
                    "id": "deepseek-v4-pro",
                    "pricing": {
                        "prompt": "0.0000001",
                        "completion": [
                            {"value": 2, "unit": "perMTokens"},
                            {"value": 8, "unit": "perMTokens"},
                        ],
                    },
                }
            ]
        }
        result = _extract_pricing(payload)
        # List-typed completion should be skipped; prompt should still be picked up
        assert result is not None
        assert "completion" not in result or isinstance(
            result["completion"], (int, float, str)
        )

    def test_normal_pricing_still_works(self) -> None:
        """String/int/float pricing values must still be extracted."""
        payload = {
            "data": [
                {
                    "id": "test-model",
                    "pricing": {
                        "prompt": "0.0000005",
                        "completion": 0.0000015,
                    },
                }
            ]
        }
        result = _extract_pricing(payload)
        assert result is not None
        assert result.get("prompt") == "0.0000005"
        assert result.get("completion") == 0.0000015
