from __future__ import annotations

from gateway.run import _start_cron_ticker


class _FakeStopEvent:
    def __init__(self):
        self._is_set = False
        self.wait_calls: list[float] = []

    def is_set(self) -> bool:
        return self._is_set

    def set(self) -> None:
        self._is_set = True

    def wait(self, timeout=None):
        self.wait_calls.append(timeout)
        return self._is_set


def test_cron_ticker_collapses_multi_interval_overrun_to_single_immediate_catchup(monkeypatch, caplog):
    """A slow tick should trigger at most one immediate catch-up pass.

    Without the backlog collapse, a ticker that fell several intervals behind
    would spin through multiple zero-sleep iterations in a burst. That is not
    useful here because each cron tick already evaluates jobs against the
    current wall clock; we only need one immediate catch-up pass after a slow
    batch, then normal cadence should resume.
    """

    stop_event = _FakeStopEvent()
    tick_calls: list[int] = []

    def fake_tick(*, verbose, adapters, loop, sync=False):
        tick_calls.append(len(tick_calls) + 1)
        if len(tick_calls) >= 3:
            stop_event.set()

    monotonic_values = iter([
        0.0,    # next_tick_at seed
        0.0,    # loop 1 start: immediate first tick
        190.0,  # loop 1 end: fell >3 intervals behind
        190.0,  # loop 2 start: single immediate catch-up tick
        190.1,  # loop 2 end: now back within one interval
        190.1,  # loop 3 start: should sleep ~60s instead of bursting again
        190.2,  # loop 3 end
    ])

    monkeypatch.setattr("cron.scheduler.tick", fake_tick)
    monkeypatch.setattr("gateway.run.time.monotonic", lambda: next(monotonic_values))

    with caplog.at_level("DEBUG", logger="gateway.run"):
        _start_cron_ticker(stop_event, adapters=None, loop=None, interval=60)

    assert tick_calls == [1, 2, 3]
    assert stop_event.wait_calls[0] == 0.0
    assert stop_event.wait_calls[1] == 0.0
    assert stop_event.wait_calls[2] > 50.0
    assert any(
        "Cron ticker fell behind by" in record.message
        for record in caplog.records
    )
