from cli import HermesCLI


def _make_cli_stub():
    cli = HermesCLI.__new__(HermesCLI)
    cli._model_picker_state = None
    return cli


def test_model_picker_provider_wraps_up_from_top_to_bottom():
    cli = _make_cli_stub()
    cli._model_picker_state = {
        "stage": "provider",
        "providers": [{"slug": "a"}, {"slug": "b"}],
        "selected": 0,
    }

    cli._move_model_picker_selection(-1)

    # providers(2) + cancel => last index 2
    assert cli._model_picker_state["selected"] == 2


def test_model_picker_provider_wraps_down_from_bottom_to_top():
    cli = _make_cli_stub()
    cli._model_picker_state = {
        "stage": "provider",
        "providers": [{"slug": "a"}, {"slug": "b"}],
        "selected": 2,
    }

    cli._move_model_picker_selection(1)

    assert cli._model_picker_state["selected"] == 0


def test_model_picker_model_wraps_up_from_top_to_bottom():
    cli = _make_cli_stub()
    cli._model_picker_state = {
        "stage": "model",
        "model_list": ["m1", "m2", "m3"],
        "selected": 0,
    }

    cli._move_model_picker_selection(-1)

    # model_list(3) + back + cancel => last index 4
    assert cli._model_picker_state["selected"] == 4


def test_model_picker_model_wraps_down_from_bottom_to_top():
    cli = _make_cli_stub()
    cli._model_picker_state = {
        "stage": "model",
        "model_list": ["m1", "m2", "m3"],
        "selected": 4,
    }

    cli._move_model_picker_selection(1)

    assert cli._model_picker_state["selected"] == 0
