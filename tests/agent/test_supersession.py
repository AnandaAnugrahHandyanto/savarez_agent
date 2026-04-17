from agent.supersession import suppress_derived_records


def test_source_lane_outranks_derived_lane_when_content_matches():
    winners, suppressed, reasons = suppress_derived_records(
        [
            {"lane": "sqlite_memory", "content": "Never use flattery or padding."},
            {"lane": "wiki_compiled", "content": "Never use flattery or padding."},
            {"lane": "session_search", "content": "We decided to verify before claiming done."},
        ]
    )

    assert [record["lane"] for record in winners] == ["sqlite_memory", "session_search"]
    assert [record["lane"] for record in suppressed] == ["wiki_compiled"]
    assert reasons == ["source lane outranks derived lane"]
