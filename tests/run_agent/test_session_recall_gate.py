import json
from unittest.mock import MagicMock, patch

from run_agent import AIAgent


def _make_agent():
    agent = object.__new__(AIAgent)
    agent._session_db = MagicMock()
    agent.session_id = "sess-current"
    agent.valid_tool_names = {"session_search"}
    return agent


def test_looks_like_cross_session_query_matches_chinese_continue():
    agent = _make_agent()
    assert agent._looks_like_cross_session_query("继续，你建议的都做") is True
    assert agent._looks_like_cross_session_query("上次那个问题继续") is True
    assert agent._looks_like_cross_session_query("帮我看这个文件") is False


def test_maybe_auto_session_recall_returns_empty_when_not_triggered():
    agent = _make_agent()
    assert agent._maybe_auto_session_recall("帮我看这个文件") == ""


def test_maybe_auto_session_recall_formats_results():
    agent = _make_agent()
    payload = {
        "success": True,
        "results": [
            {
                "when": "April 16, 2026",
                "source": "feishu",
                "summary": "We fixed the compression bug and documented the outcome.",
            }
        ],
    }
    with patch("tools.session_search_tool.session_search", return_value=json.dumps(payload)):
        block = agent._maybe_auto_session_recall("继续，上次那个压缩问题")
    assert "## Session Recall" in block
    assert "compression bug" in block
    assert "April 16, 2026" in block


def test_maybe_auto_session_recall_skips_when_tool_unavailable():
    agent = _make_agent()
    agent.valid_tool_names = set()
    assert agent._maybe_auto_session_recall("继续") == ""


def test_derive_recent_session_topics_reads_titles_and_previews():
    agent = _make_agent()
    agent._session_db.list_sessions_rich.return_value = [
        {"id": "old-1", "title": "Compression bug follow-up", "preview": "", "parent_session_id": None},
        {"id": "old-2", "title": "", "preview": "QMT daily report state drift", "parent_session_id": None},
    ]
    topics = agent._derive_recent_session_topics(limit=4)
    assert "Compression bug follow-up" in topics[0]
    assert any("QMT daily report state drift" in topic for topic in topics)


def test_tokenize_recent_topic_emits_cjk_ngrams_and_words():
    agent = _make_agent()
    tokens = agent._tokenize_recent_topic("压缩问题 回写补偿")
    assert "压缩问题" in tokens
    assert "压缩" in tokens
    assert "回写" in tokens


def test_recent_topic_overlap_score_rewards_partial_chinese_overlap():
    agent = _make_agent()
    score = agent._recent_topic_overlap_score("压缩问题又出现了", "历史记录：压缩 bug 修复")
    assert score >= 3


def test_maybe_auto_session_recall_triggers_on_recent_topic_overlap_without_continue_keyword():
    agent = _make_agent()
    agent._session_db.list_sessions_rich.return_value = [
        {"id": "old-1", "title": "压缩 bug", "preview": "索引补偿回写", "parent_session_id": None}
    ]
    payload = {
        "success": True,
        "results": [
            {"when": "April 16, 2026", "source": "cli", "summary": "We already fixed the compression bug once."}
        ],
    }
    with patch("tools.session_search_tool.session_search", return_value=json.dumps(payload)):
        block = agent._maybe_auto_session_recall("压缩问题现在又复现了")
    assert "Session Recall" in block
    assert "compression bug" in block


def test_expand_recent_topic_keywords_uses_tokenizer_shards():
    agent = _make_agent()
    agent._session_db.list_sessions_rich.return_value = [
        {"id": "old-1", "title": "压缩问题回写", "preview": "recent topic overlap", "parent_session_id": None}
    ]
    keywords = agent._expand_recent_topic_keywords(limit=4)
    assert "压缩问题回写" in keywords
    assert "压缩" in keywords
    assert "overlap" in keywords
