from hermes_cli.recall import format_recall_receipt_summary


def test_format_recall_receipt_summary_surfaces_lanes_and_flags():
    text = format_recall_receipt_summary(
        {
            "query_type": "hybrid",
            "routes": ["sqlite_memory", "session_search"],
            "lanes_used": ["sqlite_memory", "session_search"],
            "winning_records": [{"lane": "sqlite_memory"}, {"lane": "session_search"}],
            "suppressed_records": [{"lane": "wiki_compiled"}],
            "degraded_flags": ["clerk_reset_unavailable"],
        }
    )

    assert "query_type=hybrid" in text
    assert "lanes_used=sqlite_memory,session_search" in text
    assert "suppressed=1" in text
    assert "degraded=clerk_reset_unavailable" in text
