import pytest
import asyncio
from unittest.mock import MagicMock, patch
from agent.graph_manager import GraphManager

class MockRecord:
    def __init__(self, val):
        self.uuid = val

def test_reciprocal_rank_fusion():
    gm = GraphManager(db_path="/tmp/fake")
    
    list1 = [MockRecord("A"), MockRecord("B"), MockRecord("C")]
    list2 = [MockRecord("B"), MockRecord("D"), MockRecord("A")]
    
    # K=60. 
    # A = 1/61 + 1/63
    # B = 1/62 + 1/61
    # B has higher RRF score than A.
    
    fused = gm.reciprocal_rank_fusion([list1, list2])
    
    uuids = [x.uuid for x in fused]
    assert len(uuids) == 4
    
    # B must be highest
    assert uuids[0] == "B"
    assert uuids[1] == "A"
    assert "C" in uuids
    assert "D" in uuids

@pytest.mark.asyncio
async def test_expand_query():
    gm = GraphManager(db_path="/tmp/fake")
    
    # Mocking resolve provider to avoid env dependency in tests
    gm._resolve_provider = MagicMock(return_value=("openai", "gpt-mock", "http://mock", "key"))
    
    # Mock urllib urlopen
    mock_resp = MagicMock()
    mock_resp.read.return_value = b'{"choices": [{"message": {"content": "[\\"query var 1\\", \\"query var 2\\"]"}}]}'
    mock_resp.__enter__.return_value = mock_resp
    
    with patch("urllib.request.urlopen", return_value=mock_resp):
        expanded = await gm._expand_query("test query")
        
        # Result should contain the generated variations PLUS original query
        assert len(expanded) == 3
        assert "test query" in expanded
        assert "query var 1" in expanded
