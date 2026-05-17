import json
import unittest
from decimal import Decimal
from unittest.mock import MagicMock, patch
from tools.usage_tool import get_usage_tool

class TestUsageTool(unittest.TestCase):
    def test_get_usage_tool(self):
        agent = MagicMock()
        agent.model = "gpt-4o"
        agent.provider = "openai"
        agent.session_input_tokens = 1000
        agent.session_output_tokens = 500
        agent.session_cache_read_tokens = 200
        agent.session_cache_write_tokens = 100
        agent.session_api_calls = 5
        agent.context_limit = 128000
        agent.last_context_tokens = 10000
        agent.base_url = "https://api.openai.com/v1"
        agent.api_key = "sk-test"

        with patch("agent.usage_pricing.estimate_usage_cost") as mock_cost:
            from agent.usage_pricing import CostResult
            mock_cost.return_value = CostResult(
                amount_usd=Decimal("0.05"),
                status="calculated", 
                source="official_docs_snapshot",
                label="Test Label"
            )
            result_json = get_usage_tool(agent=agent)
        
        result = json.loads(result_json)

        self.assertEqual(result["model"], "gpt-4o")
        self.assertEqual(result["tokens"]["total"], 1800)
        self.assertEqual(result["context"]["percent"], 8)
        self.assertEqual(result["api_calls"], 5)
        self.assertEqual(result["cost"]["amount_usd"], 0.05)


if __name__ == "__main__":
    unittest.main()
