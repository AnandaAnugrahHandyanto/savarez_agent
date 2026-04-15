from types import SimpleNamespace

from hermes_cli.pairing import pairing_command


class StubStore:
    def __init__(self, pending=None, approved=None, approve_result=None, revoke_result=False, cleared=0):
        self._pending = pending or []
        self._approved = approved or []
        self._approve_result = approve_result
        self._revoke_result = revoke_result
        self._cleared = cleared

    def list_pending(self):
        return self._pending

    def list_approved(self):
        return self._approved

    def approve_code(self, platform, code):
        return self._approve_result

    def revoke(self, platform, user_id):
        return self._revoke_result

    def clear_pending(self):
        return self._cleared


def test_pairing_command_usage_is_localized(monkeypatch, capsys):
    monkeypatch.setattr("gateway.pairing.PairingStore", lambda: StubStore())

    pairing_command(SimpleNamespace(pairing_action=None))

    out = capsys.readouterr().out
    assert "사용법: hermes pairing {list|approve|revoke|clear-pending}" in out
    assert "자세한 내용은 'hermes pairing --help'를 실행하세요." in out


def test_pairing_list_empty_is_localized(monkeypatch, capsys):
    monkeypatch.setattr("gateway.pairing.PairingStore", lambda: StubStore())

    pairing_command(SimpleNamespace(pairing_action="list"))

    out = capsys.readouterr().out
    assert "페어링 데이터가 없어요." in out
    assert "아직 아무도 페어링을 시도하지 않았어요~" in out


def test_pairing_list_tables_are_localized(monkeypatch, capsys):
    store = StubStore(
        pending=[{"platform": "telegram", "code": "ABCD12", "user_id": "u1", "user_name": "홍길동", "age_minutes": 5}],
        approved=[{"platform": "discord", "user_id": "u2", "user_name": "임꺽정"}],
    )
    monkeypatch.setattr("gateway.pairing.PairingStore", lambda: store)

    pairing_command(SimpleNamespace(pairing_action="list"))

    out = capsys.readouterr().out
    assert "대기 중인 페어링 요청 (1):" in out
    assert "플랫폼" in out
    assert "사용자 ID" in out
    assert "경과 시간" in out
    assert "5분 전" in out
    assert "승인된 사용자 (1):" in out


def test_pairing_approve_success_is_localized(monkeypatch, capsys):
    store = StubStore(approve_result={"user_id": "u1", "user_name": "홍길동"})
    monkeypatch.setattr("gateway.pairing.PairingStore", lambda: store)

    pairing_command(SimpleNamespace(pairing_action="approve", platform="telegram", code="abcd12"))

    out = capsys.readouterr().out
    assert "승인 완료!" in out
    assert "telegram의 사용자 홍길동 (u1)" in out
    assert "다음 메시지부터 자동으로 인식돼요." in out


def test_pairing_approve_failure_is_localized(monkeypatch, capsys):
    monkeypatch.setattr("gateway.pairing.PairingStore", lambda: StubStore(approve_result=None))

    pairing_command(SimpleNamespace(pairing_action="approve", platform="telegram", code="abcd12"))

    out = capsys.readouterr().out
    assert "코드 'ABCD12'를 찾지 못했거나 이미 만료되었어요." in out
    assert "'hermes pairing list'를 실행하세요." in out


def test_pairing_revoke_and_clear_are_localized(monkeypatch, capsys):
    monkeypatch.setattr("gateway.pairing.PairingStore", lambda: StubStore(revoke_result=True, cleared=2))

    pairing_command(SimpleNamespace(pairing_action="revoke", platform="discord", user_id="u2"))
    pairing_command(SimpleNamespace(pairing_action="clear-pending"))

    out = capsys.readouterr().out
    assert "discord의 사용자 u2 접근 권한을 철회했어요." in out
    assert "대기 중인 페어링 요청 2개를 비웠어요." in out
