import pytest
from unittest.mock import MagicMock
from cron.obsidian_ingest import ObsidianIngest

def test_parse_knowledge_body():
    # Provide a mock db and bypass path validation logic
    ingest = ObsidianIngest(db=MagicMock(), vault_path="/tmp/fake", agent_prefix="Hermes")
    
    # 1. Test Split
    txt_with_timeline = "This is the compiled truth.\n---\nAnd here is the timeline."
    truth, timeline = ingest._parse_knowledge_body(txt_with_timeline)
    assert truth == "This is the compiled truth."
    assert timeline == "And here is the timeline."
    
    # 2. Test Split with underscores
    txt_underscores = "Compiled\n___\nTimeline"
    truth, timeline = ingest._parse_knowledge_body(txt_underscores)
    assert truth == "Compiled"
    assert timeline == "Timeline"
    
    # 3. Test Without Timeline
    txt_without = "This is just truth."
    truth, timeline = ingest._parse_knowledge_body(txt_without)
    assert truth == txt_without
    assert timeline == ""
