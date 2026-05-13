from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
CHAT_PAGE = REPO_ROOT / "web" / "src" / "pages" / "ChatPage.tsx"


def test_chat_page_forwards_osc_window_titles_to_document_title():
    source = CHAT_PAGE.read_text(encoding="utf-8")

    assert "registerOscHandler(0" in source
    assert "registerOscHandler(2" in source
    assert "document.title" in source
