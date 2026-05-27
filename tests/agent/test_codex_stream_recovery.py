from types import SimpleNamespace

from agent.codex_stream_recovery import run_responses_stream_with_recovery


class _FakeStream:
    def __init__(self, events, final_response=None, final_error=None, iteration_error=None):
        self._events = list(events)
        self._final_response = final_response
        self._final_error = final_error
        self._iteration_error = iteration_error

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def __iter__(self):
        for event in self._events:
            yield event
        if self._iteration_error is not None:
            raise self._iteration_error

    def get_final_response(self):
        if self._final_error is not None:
            raise self._final_error
        return self._final_response


def test_recovers_output_item_when_sdk_parser_raises_during_iteration():
    output_item = SimpleNamespace(
        type="message",
        content=[SimpleNamespace(type="output_text", text="survived")],
    )

    final, state = run_responses_stream_with_recovery(
        lambda: _FakeStream(
            [SimpleNamespace(type="response.output_item.done", item=output_item)],
            iteration_error=TypeError("'NoneType' object is not iterable"),
        ),
        model="gpt-5.5",
    )

    assert state.recovered_from_parser_error is True
    assert final.status == "completed"
    assert final.output == [output_item]
    assert final.output_text == "survived"


def test_backfills_empty_final_output_from_text_deltas():
    final, state = run_responses_stream_with_recovery(
        lambda: _FakeStream(
            [
                SimpleNamespace(type="response.output_text.delta", delta="hel"),
                SimpleNamespace(type="response.output_text.delta", delta="lo"),
            ],
            final_response=SimpleNamespace(output=[], output_text=None, usage=None),
        ),
        model="gpt-5.5",
    )

    assert state.backfilled_final_output is True
    assert final.output[0].content[0].text == "hello"
    assert final.output_text == "hello"
