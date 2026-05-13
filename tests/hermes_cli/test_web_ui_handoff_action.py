"""Static contract tests for the WebUI session handoff action."""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CHAT_PAGE = ROOT / "web" / "src" / "pages" / "ChatPage.tsx"


def test_chat_page_exposes_handoff_button_that_sends_handoff_command():
    source = CHAT_PAGE.read_text(encoding="utf-8")

    assert "handleHandoff" in source
    assert 'ws.send("/handoff")' in source
    assert "새 세션 이어가기 안내 만들기" in source
    assert "이동 준비" in source
    assert "세션 이동" not in source
