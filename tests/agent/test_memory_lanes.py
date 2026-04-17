from agent.memory_lanes import get_lane, list_lanes


def test_lane_registry_declares_all_continuity_lanes():
    lane_names = {lane.name for lane in list_lanes()}

    assert {
        "sqlite_memory",
        "wiki_compiled",
        "session_search",
        "clerk_reset",
        "chain_of_shells",
        "file_anchors",
    }.issubset(lane_names)


def test_wiki_lane_is_derived_and_sqlite_lane_is_authoritative():
    sqlite_lane = get_lane("sqlite_memory")
    wiki_lane = get_lane("wiki_compiled")

    assert sqlite_lane.derived is False
    assert sqlite_lane.authority == "canonical"
    assert wiki_lane.derived is True
    assert wiki_lane.authority == "derived"
