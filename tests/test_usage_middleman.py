from agent.usage_middleman import build_compact_usage_table


def test_build_compact_usage_table_is_fixed_width_and_includes_sections():
    lines = build_compact_usage_table(
        model="anthropic/claude-sonnet-4.6",
        provider="openrouter",
        input_tokens=113_992,
        output_tokens=24_160,
        cache_read_tokens=3_573_909,
        cache_write_tokens=334_317,
        total_tokens=4_046_378,
        cost_usd=3.0302,
        cost_status="estimated",
        duration_str="26m",
        context_tokens=105_471,
        context_length=1_000_000,
        api_calls=50,
        balance_rows=[
            ("openrouter", "Credits balance: $44.48"),
            ("maritaca", "Saldo: R$ 118,96"),
        ],
        quota_sections=[
            ("claude code", [("Current session", 55.0, "in 3h 10m")]),
            (
                "codex / openai",
                [
                    ("5h limit", 0.0, "in 5h 26m"),
                    ("weekly", 100.0, "in 1d 21h"),
                ],
            ),
        ],
    )

    assert lines[0] == "#" * 79
    assert lines[-1] == "#" * 79
    assert all(len(line) == 79 for line in lines)
    assert any("Usage  openrouter / anthropic/claude-sonnet-4.6" in line for line in lines)
    assert any("session" in line for line in lines)
    assert any("balances" in line for line in lines)
    assert any("claude code" in line for line in lines)
    assert any("codex / openai" in line for line in lines)
    assert any("[███████" in line for line in lines)


def test_build_compact_usage_table_wraps_long_values_without_breaking_edges():
    lines = build_compact_usage_table(
        model="local/really-long-model-name-that-should-be-truncated-cleanly",
        provider="custom-provider-with-a-very-long-name",
        input_tokens=10,
        output_tokens=5,
        cache_read_tokens=0,
        cache_write_tokens=0,
        total_tokens=15,
        cost_usd=None,
        cost_status="unknown",
        duration_str="5m",
        context_tokens=200,
        context_length=400,
        api_calls=1,
        balance_rows=[
            (
                "openrouter",
                "Credits balance: $123.45 and a deliberately long trailing explanation that must wrap safely",
            )
        ],
        quota_sections=[],
    )

    assert all(len(line) == 79 for line in lines)
    assert all(line.startswith("#") and line.endswith("#") for line in lines)
    assert any("Credits balance: $123.45" in line for line in lines)
    assert any("deliberately long" in line for line in lines)
    assert any("trailing explanation" in line for line in lines)
