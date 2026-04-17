from agent.recall_receipt import RecallReceipt


def test_recall_receipt_serializes_routes_winners_and_degraded_flags():
    receipt = RecallReceipt(
        receipt_id="rr-123",
        query="what did we decide about proof?",
        query_type="hybrid",
        routes=["sqlite_memory", "wiki_compiled", "session_search"],
        lanes_considered=["sqlite_memory", "wiki_compiled", "session_search", "clerk_reset"],
        lanes_used=["sqlite_memory", "session_search"],
        winning_records=[{"lane": "sqlite_memory", "content": "Never claim done without proof."}],
        suppressed_records=[{"lane": "wiki_compiled", "content": "Never claim done without proof."}],
        suppression_reasons=["source lane outranks derived lane"],
        degraded_flags=["clerk_reset_unavailable"],
        budget={"sqlite_hits": 1, "session_hits": 1},
        context_block="Relevant memory recall:\n- Never claim done without proof.",
    )

    payload = receipt.to_dict()

    assert payload["receipt_id"] == "rr-123"
    assert payload["query_type"] == "hybrid"
    assert payload["lanes_used"] == ["sqlite_memory", "session_search"]
    assert payload["suppression_reasons"] == ["source lane outranks derived lane"]
    assert payload["degraded_flags"] == ["clerk_reset_unavailable"]
