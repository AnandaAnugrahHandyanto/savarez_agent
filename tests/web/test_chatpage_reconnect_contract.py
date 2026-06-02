from pathlib import Path


CHAT_PAGE = Path(__file__).resolve().parents[2] / "web" / "src" / "pages" / "ChatPage.tsx"


def test_dashboard_chat_reconnects_after_clean_pty_close():
    source = CHAT_PAGE.read_text()

    # A clean /api/pty close currently renders "[session ended]". The browser
    # chat must not stay permanently dead there: on mobile/Tailscale WebSockets
    # can drop when the tab sleeps or the network blips, and then keystrokes are
    # discarded because wsRef is null. Keep a reconnection state bump in the
    # normal onclose path so the ChatPage effect remounts the PTY automatically.
    assert "ptyReconnectSeq" in source
    assert "setPtyReconnectSeq" in source
    assert "reconnectTimerRef" in source
    assert "[session ended — reconnecting…]" in source
    assert "setTimeout" in source and "setPtyReconnectSeq((seq) => seq + 1)" in source
    assert "[channel, resumeParam, ptyReconnectSeq]" in source
