from gateway.run import (
    _extract_research_progress_lines,
    _looks_like_manual_research_request,
    _normalize_research_rigor,
    _tool_progress_label,
)


def test_normalize_research_rigor_detects_inline_tier():
    assert _normalize_research_rigor("Rigor tier: Deep") == "deep"
    assert _normalize_research_rigor("standard") == "standard"


def test_manual_research_request_heuristic_matches_target_cases():
    assert _looks_like_manual_research_request(
        "Research whether Dripos is better than the competition"
    )
    assert _looks_like_manual_research_request(
        "Research what most researchers believe will happen in 10 years with AI"
    )
    assert _looks_like_manual_research_request(
        "Research bagel places near my home that's open right now"
    )


def test_tool_progress_label_is_abstract():
    assert _tool_progress_label("web_search") == "🌐 browsing"
    assert _tool_progress_label("terminal") == "🛠️ tinkering"
    assert _tool_progress_label("session_search") == "🧠 remembering"


def test_extract_research_progress_lines_returns_last_three_labels():
    output = "\n".join([
        "┊ 📚 skill evidence-report-publishing 0.0s",
        "┊ 💻 $ which hermes && pwd && whoami 0.8s",
        "┊ 🌐 web_search some query 1.2s",
        "┊ 💻 $ python verify.py 0.4s",
    ])
    assert _extract_research_progress_lines(output, limit=3) == [
        "🛠️ tinkering",
        "🌐 browsing",
        "🛠️ tinkering",
    ]
