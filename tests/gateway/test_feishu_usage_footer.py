"""Tests for Feishu run-stat footer formatting in gateway responses."""

import unittest
from unittest.mock import patch

from gateway.config import Platform
from gateway.session import SessionSource


def _make_runner():
    from gateway.run import GatewayRunner

    return object.__new__(GatewayRunner)


class TestFeishuUsageFooter(unittest.TestCase):
    def test_format_elapsed_compact_keeps_subminute_precision(self):
        from gateway.run import _format_elapsed_compact

        self.assertEqual(_format_elapsed_compact(38.6), "38.6s")
        self.assertEqual(_format_elapsed_compact(38.0), "38s")

    def test_build_feishu_usage_footer_includes_run_stats(self):
        runner = _make_runner()
        source = SessionSource(platform=Platform.FEISHU, chat_id="oc_xxx", chat_type="group")

        with patch("gateway.run._resolve_gateway_model", return_value="MiniMax-M2.7"), patch(
            "agent.model_metadata.get_model_context_length", return_value=205_000
        ), patch(
            "gateway.run._resolve_runtime_agent_kwargs",
            return_value={"provider": "openai", "base_url": "", "api_key": ""},
        ):
            footer = runner._build_feishu_usage_footer(
                source=source,
                agent_result={
                    "model": "MiniMax-M2.7",
                    "input_tokens": 545,
                    "output_tokens": 904,
                    "cache_read_tokens": 48_400,
                    "cache_write_tokens": 0,
                    "last_prompt_tokens": 49_000,
                },
                response_time=38.6,
            )

        self.assertEqual(
            footer,
            "已完成 · 耗时 38.6s · MiniMax-M2.7\n"
            "↑ 545 ↓ 904 · 缓存 48.4k/0 (99%) · 上下文 49k/205k (24%)",
        )

    def test_append_feishu_usage_footer_wraps_response_with_markers(self):
        runner = _make_runner()
        source = SessionSource(platform=Platform.FEISHU, chat_id="oc_xxx", chat_type="group")

        with patch.object(
            runner,
            "_build_feishu_usage_footer",
            return_value="已完成 · 耗时 38.6s · MiniMax-M2.7\n↑ 545 ↓ 904 · 缓存 48.4k/0 (99%)",
        ):
            result = runner._append_feishu_usage_footer(
                "结果正文",
                source=source,
                agent_result={},
                response_time=38.6,
            )

        self.assertEqual(
            result,
            "[[HERMES_STATUS:completed]]\n"
            "结果正文\n\n"
            "[[HERMES_FOOTER]]\n"
            "已完成 · 耗时 38.6s · MiniMax-M2.7\n"
            "↑ 545 ↓ 904 · 缓存 48.4k/0 (99%)\n"
            "[[/HERMES_FOOTER]]",
        )
