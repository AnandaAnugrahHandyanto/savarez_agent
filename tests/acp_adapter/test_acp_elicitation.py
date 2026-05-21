from types import SimpleNamespace

from acp_adapter.elicitation import supports_form_elicitation


def test_supports_form_elicitation_with_object_form():
    caps = SimpleNamespace(elicitation=SimpleNamespace(form=SimpleNamespace()))
    assert supports_form_elicitation(caps) is True


def test_supports_form_elicitation_with_dict_form():
    caps = SimpleNamespace(elicitation={"form": {}})
    assert supports_form_elicitation(caps) is True


def test_supports_form_elicitation_with_empty_elicitation_object():
    # ACP RFD-style shorthand: empty elicitation object means form supported.
    caps = SimpleNamespace(elicitation={})
    assert supports_form_elicitation(caps) is True


def test_supports_form_elicitation_missing_is_false():
    assert supports_form_elicitation(SimpleNamespace()) is False
    assert supports_form_elicitation(None) is False


def test_supports_form_elicitation_url_only_is_false():
    caps = SimpleNamespace(elicitation={"url": {}})
    assert supports_form_elicitation(caps) is False
