import pytest

from plugins.google_meet import meet_bot
from plugins.google_meet.realtime.openai_client import RealtimeSession


class FakeLocator:
    def __init__(self, page, label, visible=True, click_hides=False):
        self.page = page
        self.label = label
        self.visible = visible
        self.click_hides = click_hides
        self.click_count = 0

    @property
    def first(self):
        return self

    def count(self):
        return 1 if self.visible else 0

    def is_visible(self):
        return self.visible

    def scroll_into_view_if_needed(self, timeout=None):
        return None

    def click(self, timeout=None, force=False):
        self.click_count += 1
        self.page.actions.append(self.label)
        if self.click_hides:
            self.visible = False


class FakePage:
    def __init__(self, locators):
        self.locators = locators
        self.actions = []
        self.wait_calls = []

    def get_by_role(self, role, name=None, exact=False):
        key = str(name)
        if key not in self.locators:
            return FakeLocator(self, key, visible=False)
        return self.locators[key]

    def wait_for_timeout(self, ms):
        self.wait_calls.append(ms)


class DummyState:
    def __init__(self):
        self.lobby_waiting = False
        self.calls = []

    def set(self, **kwargs):
        self.calls.append(kwargs)
        for key, value in kwargs.items():
            setattr(self, key, value)


def test_click_join_handles_ask_to_join_and_sets_lobby_waiting(monkeypatch):
    page = FakePage(
        {
            "Ask to join": FakeLocator(None, "Ask to join", visible=True, click_hides=True),
            "Join now": FakeLocator(None, "Join now", visible=False),
            "Continue without microphone": FakeLocator(None, "Continue without microphone", visible=False),
            "Use microphone": FakeLocator(None, "Use microphone", visible=False),
        }
    )
    for locator in page.locators.values():
        locator.page = page
    state = DummyState()
    monkeypatch.setattr(meet_bot, "_detect_admission", lambda _page: False)

    meet_bot._click_join(page, state, retries=2)

    assert page.actions == ["Ask to join"]
    assert state.lobby_waiting is True
    assert page.wait_calls == []


def test_click_join_retries_join_now_when_first_click_does_not_admit(monkeypatch):
    page = FakePage(
        {
            "Join now": FakeLocator(None, "Join now", visible=True),
            "Ask to join": FakeLocator(None, "Ask to join", visible=False),
            "Continue without microphone": FakeLocator(None, "Continue without microphone", visible=False),
            "Use microphone": FakeLocator(None, "Use microphone", visible=False),
        }
    )
    for locator in page.locators.values():
        locator.page = page
    state = DummyState()
    detect_calls = {"n": 0}

    def fake_detect(_page):
        detect_calls["n"] += 1
        return detect_calls["n"] >= 2

    monkeypatch.setattr(meet_bot, "_detect_admission", fake_detect)

    meet_bot._click_join(page, state, retries=3)

    assert page.actions == ["Join now", "Join now"]
    assert detect_calls["n"] == 2
    assert state.lobby_waiting is False


def test_speak_uses_tts_first(monkeypatch, tmp_path):
    session = RealtimeSession(api_key="sk-test", audio_sink_path=tmp_path / "speaker.pcm")
    session._ws = object()

    called = {"tts": 0}

    def fake_tts(text, timeout):
        called["tts"] += 1
        return {"ok": True, "bytes_written": 1234, "duration_ms": 12.3}

    def fail_realtime(*args, **kwargs):
        raise AssertionError("realtime fallback should not be used when TTS succeeds")

    monkeypatch.setattr(session, "_speak_via_tts", fake_tts)
    monkeypatch.setattr(session, "_send_json", fail_realtime)

    result = session.speak("Testing 1,2,3!!", timeout=5.0)

    assert called["tts"] == 1
    assert result["bytes_written"] == 1234


def test_click_join_dismisses_mic_prompt_before_join(monkeypatch):
    page = FakePage(
        {
            "Continue without microphone": FakeLocator(None, "Continue without microphone", visible=True, click_hides=True),
            "Use microphone": FakeLocator(None, "Use microphone", visible=False),
            "Join now": FakeLocator(None, "Join now", visible=True),
            "Ask to join": FakeLocator(None, "Ask to join", visible=False),
        }
    )
    for locator in page.locators.values():
        locator.page = page
    state = DummyState()
    monkeypatch.setattr(meet_bot, "_detect_admission", lambda _page: True)

    meet_bot._click_join(page, state, retries=1)

    assert page.actions == ["Continue without microphone", "Join now"]
    assert state.lobby_waiting is False
