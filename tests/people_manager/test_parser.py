from people_manager.parser import parse_message


def test_parse_new_report():
    parsed = parse_message("New report: Alice Chen - Head of IR - own investor cadence")

    assert parsed is not None
    assert parsed.action == "new_report"
    assert parsed.report_name == "Alice Chen"
    assert parsed.role_title == "Head of IR"
    assert parsed.body == "own investor cadence"
    assert parsed.is_mutating is True


def test_parse_update():
    parsed = parse_message("Update Alice Chen: shipped investor memo")

    assert parsed is not None
    assert parsed.action == "update"
    assert parsed.report_name == "Alice Chen"
    assert parsed.body == "shipped investor memo"


def test_parse_one_on_one():
    parsed = parse_message("1:1 Alice Chen: seems stretched")

    assert parsed is not None
    assert parsed.action == "one_on_one"
    assert parsed.report_name == "Alice Chen"


def test_parse_multiline_one_on_one_preserves_body():
    parsed = parse_message("1:1 Alice Chen:\n- blocked on investor follow-up\n- needs decision by Friday")

    assert parsed is not None
    assert parsed.action == "one_on_one"
    assert parsed.report_name == "Alice Chen"
    assert parsed.body == "- blocked on investor follow-up\n- needs decision by Friday"


def test_parse_assessment():
    parsed = parse_message("Assessment Alice Chen: solid operator but reactive")

    assert parsed is not None
    assert parsed.action == "assessment"
    assert parsed.report_name == "Alice Chen"


def test_parse_todo_for_report():
    parsed = parse_message("Todo Alice Chen: send investor segmentation draft")

    assert parsed is not None
    assert parsed.action == "todo_report"
    assert parsed.report_name == "Alice Chen"
    assert parsed.body == "send investor segmentation draft"


def test_parse_todo_for_me():
    parsed = parse_message("Todo for me on Alice Chen: define clearer mandate")

    assert parsed is not None
    assert parsed.action == "todo_manager"
    assert parsed.report_name == "Alice Chen"
    assert parsed.body == "define clearer mandate"


def test_parse_prep():
    parsed = parse_message("Prep Alice Chen")

    assert parsed is not None
    assert parsed.action == "prep"
    assert parsed.report_name == "Alice Chen"
    assert parsed.is_mutating is False


def test_parse_review():
    parsed = parse_message("Review Alice Chen")

    assert parsed is not None
    assert parsed.action == "review"
    assert parsed.report_name == "Alice Chen"


def test_parse_team_scan():
    parsed = parse_message("Team scan")

    assert parsed is not None
    assert parsed.action == "team_scan"
    assert parsed.report_name is None


def test_parse_challenge():
    parsed = parse_message("Challenge my view of Alice Chen")

    assert parsed is not None
    assert parsed.action == "challenge"
    assert parsed.report_name == "Alice Chen"


def test_parse_under_manage_prompt():
    parsed = parse_message("Am I under-managing anyone?")

    assert parsed is not None
    assert parsed.action == "team_question"
    assert parsed.prompt_variant == "under_managing"


def test_parse_adhoc_one_on_one_prep_variants():
    parsed = parse_message("1o1 prep Fiona")
    assert parsed is not None
    assert parsed.action == "prep"
    assert parsed.report_name == "Fiona"
    assert parsed.prompt_variant == "short"

    parsed = parse_message("1:1 Thomas")
    assert parsed is not None
    assert parsed.action == "prep"
    assert parsed.report_name == "Thomas"
    assert parsed.prompt_variant == "short"

    parsed = parse_message("Prep Alice Chen")
    assert parsed is not None
    assert parsed.action == "prep"
    assert parsed.prompt_variant == "short"



def test_parse_reschedule_once_phrase():
    parsed = parse_message("Alex 1:1 rescheduled (one-off) to tomorrow 2:45pm")

    assert parsed is not None
    assert parsed.action == "reschedule_once"
    assert parsed.report_name == "Alex"
    assert parsed.body == "tomorrow 2:45pm"
    assert parsed.is_mutating is True



def test_parse_unknown_returns_none():
    assert parse_message("Alice seems good") is None
