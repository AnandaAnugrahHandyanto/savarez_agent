"""Tests for shared curses menu scrolling helpers."""

from hermes_cli.curses_ui import _scroll_status_text, _scroll_window_for_cursor


def test_scroll_window_moves_offset_down_to_keep_cursor_visible():
    cursor, offset, visible = _scroll_window_for_cursor(
        cursor=7,
        scroll_offset=0,
        visible_rows=5,
        item_count=20,
    )

    assert cursor == 7
    assert offset == 3
    assert visible == 5


def test_scroll_window_clamps_tiny_viewport_and_offsets():
    cursor, offset, visible = _scroll_window_for_cursor(
        cursor=99,
        scroll_offset=99,
        visible_rows=-4,
        item_count=3,
    )

    assert cursor == 2
    assert offset == 2
    assert visible == 1


def test_scroll_window_handles_empty_lists():
    cursor, offset, visible = _scroll_window_for_cursor(
        cursor=4,
        scroll_offset=5,
        visible_rows=10,
        item_count=0,
    )

    assert (cursor, offset, visible) == (0, 0, 10)


def test_scroll_status_text_shows_position_and_more_indicators():
    assert (
        _scroll_status_text(cursor=5, scroll_offset=2, visible_rows=4, item_count=10)
        == "↑ more  6/10  ↓ more"
    )


def test_scroll_status_text_empty_is_blank():
    assert _scroll_status_text(cursor=0, scroll_offset=0, visible_rows=4, item_count=0) == ""
