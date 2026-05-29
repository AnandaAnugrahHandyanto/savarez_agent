"""Shared curses-based UI components for Hermes CLI.

Used by `hermes tools` and `hermes skills` for interactive checklists.
Provides a curses multi-select with keyboard navigation, plus a
text-based numbered fallback for terminals without curses support.
"""
import sys
from typing import Any, Callable, List, Optional, Set

from hermes_cli.colors import Colors, color


def _clamp_cursor(cursor: int, item_count: int) -> int:
    """Clamp *cursor* to a valid item index for a list of *item_count*."""
    if item_count <= 0:
        return 0
    return max(0, min(cursor, item_count - 1))


def _scroll_window_for_cursor(
    cursor: int,
    scroll_offset: int,
    visible_rows: int,
    item_count: int,
) -> tuple[int, int, int]:
    """Return ``(cursor, offset, visible_rows)`` with cursor visible.

    ``visible_rows`` is coerced to at least one row so callers running inside
    very small terminals never produce negative offsets or empty ``range()``
    windows that make navigation look frozen.
    """
    visible_rows = max(1, visible_rows)
    if item_count <= 0:
        return 0, 0, visible_rows

    cursor = _clamp_cursor(cursor, item_count)
    max_offset = max(0, item_count - visible_rows)
    scroll_offset = max(0, min(scroll_offset, max_offset))

    if cursor < scroll_offset:
        scroll_offset = cursor
    elif cursor >= scroll_offset + visible_rows:
        scroll_offset = cursor - visible_rows + 1

    scroll_offset = max(0, min(scroll_offset, max_offset))
    return cursor, scroll_offset, visible_rows


def _scroll_status_text(
    cursor: int,
    scroll_offset: int,
    visible_rows: int,
    item_count: int,
) -> str:
    """Return compact footer text describing list position and overflow."""
    if item_count <= 0:
        return ""

    visible_rows = max(1, visible_rows)
    cursor = _clamp_cursor(cursor, item_count)
    parts: list[str] = []
    if scroll_offset > 0:
        parts.append("↑ more")
    parts.append(f"{cursor + 1}/{item_count}")
    if scroll_offset + visible_rows < item_count:
        parts.append("↓ more")
    return "  ".join(parts)


def _draw_footer(stdscr, row: int, max_x: int, text: str, attr=0) -> None:
    """Best-effort footer draw helper; curses errors are harmless here."""
    if row < 0 or max_x <= 1 or not text:
        return
    try:
        stdscr.addnstr(row, 0, text, max_x - 1, attr)
    except Exception:
        pass


def _draw_too_small(stdscr, max_y: int, max_x: int, message: str) -> None:
    """Tell the user a curses menu cannot render in the current viewport."""
    if max_y <= 0 or max_x <= 1:
        return
    try:
        stdscr.addnstr(max_y - 1, 0, message, max_x - 1)
    except Exception:
        pass


def flush_stdin() -> None:
    """Flush any stray bytes from the stdin input buffer.

    Must be called after ``curses.wrapper()`` (or any terminal-mode library
    like simple_term_menu) returns, **before** the next ``input()`` /
    ``getpass.getpass()`` call.  ``curses.endwin()`` restores the terminal
    but does NOT drain the OS input buffer — leftover escape-sequence bytes
    (from arrow keys, terminal mode-switch responses, or rapid keypresses)
    remain buffered and silently get consumed by the next ``input()`` call,
    corrupting user data (e.g. writing ``^[^[`` into .env files).

    On non-TTY stdin (piped, redirected) or Windows, this is a no-op.
    """
    try:
        if not sys.stdin.isatty():
            return
        import termios
        termios.tcflush(sys.stdin, termios.TCIFLUSH)
    except Exception:
        pass


# Normalized menu actions returned by ``read_menu_key``.  Using sentinels keeps
# every menu's key-handling branch identical and free of raw escape-byte logic.
NAV_UP = "up"
NAV_DOWN = "down"
NAV_PAGE_UP = "page_up"
NAV_PAGE_DOWN = "page_down"
NAV_HOME = "home"
NAV_END = "end"
NAV_SELECT = "select"
NAV_TOGGLE = "toggle"
NAV_CANCEL = "cancel"
NAV_NONE = "none"


def read_menu_key(stdscr) -> str:
    """Read one keypress and normalize it to a menu action.

    Decodes raw arrow-key escape sequences in addition to the translated
    ``curses.KEY_*`` values.  Even with ``keypad(True)`` (which
    ``curses.wrapper`` sets), some terminals/terminfo entries deliver cursor
    keys as raw CSI/SS3 byte sequences — ``getch()`` then returns ``27`` (ESC)
    followed by e.g. ``[`` ``A``.  Treating that leading ``27`` as a cancel is
    what made the setup wizard's provider/model pickers bail to the numbered
    fallback the moment a user pressed up/down.

    Returns one of the ``NAV_*`` constants.  A lone ESC (no continuation byte
    within a short window) is the only thing that maps to ``NAV_CANCEL`` via
    the escape path; ``q`` also cancels.  Unknown sequences map to
    ``NAV_NONE`` so the caller simply ignores them rather than misfiring.
    """
    import curses

    key = stdscr.getch()

    if key in (curses.KEY_UP, ord("k")):
        return NAV_UP
    if key in (curses.KEY_DOWN, ord("j")):
        return NAV_DOWN
    if key in (curses.KEY_PPAGE, ord("b")):
        return NAV_PAGE_UP
    if key in (curses.KEY_NPAGE, ord("f")):
        return NAV_PAGE_DOWN
    if key == curses.KEY_HOME:
        return NAV_HOME
    if key == curses.KEY_END:
        return NAV_END
    if key in (curses.KEY_ENTER, 10, 13):
        return NAV_SELECT
    if key == ord(" "):
        return NAV_TOGGLE
    if key == ord("q"):
        return NAV_CANCEL

    if key == 27:  # ESC — could be a lone ESC (cancel) or an escape sequence.
        # Wait briefly for a continuation byte.  On slow PTYs (SSH/tmux) the
        # bytes of an arrow key can arrive across separate reads, so a tiny
        # timeout avoids misreading a split sequence as a bare ESC.
        try:
            stdscr.timeout(60)
            nxt = stdscr.getch()
        finally:
            stdscr.timeout(-1)  # restore blocking mode

        if nxt == -1:
            return NAV_CANCEL  # genuine lone ESC

        if nxt in (ord("["), ord("O")):  # CSI / SS3 introducer
            final = stdscr.getch()
            if final in (ord("A"), ord("k")):
                return NAV_UP
            if final in (ord("B"), ord("j")):
                return NAV_DOWN
            # Consume the tail of any other CSI sequence (e.g. ``[3~`` Delete,
            # ``[H`` Home) up to its terminator so stray bytes don't leak into
            # the next input() and corrupt it.
            while 0x20 <= final <= 0x3F:  # CSI parameter/intermediate bytes
                final = stdscr.getch()
            return NAV_NONE
        # ESC followed by some other byte we don't handle — swallow it.
        return NAV_NONE

    return NAV_NONE


# Sentinel: an on_action reducer returns this to mean "keep looping" (the
# keypress changed cursor/selection state but didn't resolve the menu).
_KEEP = object()


def _run_curses_menu(
    *,
    initial_cursor,
    item_count,
    draw_header,
    draw_row,
    on_action,
    reserve_bottom=1,
    draw_footer=None,
    footer_text_fn=None,
    extra_color_pairs=False,
    fallback,
    cancel_value,
) -> Any:
    """Shared curses single-/multi-select event loop.

    Owns every piece the public menus otherwise duplicate: the non-TTY guard,
    ``curses.wrapper`` setup (cursor hide + color pairs), the per-frame
    ``clear``/``getmaxyx``/``refresh`` cycle, scroll-offset math, row
    iteration, extended navigation, ``flush_stdin``, and the
    ``KeyboardInterrupt`` / curses-unavailable fallback. Per-menu behavior is
    supplied as callbacks so checklist, radio-list, and single-select menus
    share the same scroll and key handling.

    Callbacks / params:
        draw_header(stdscr, max_y, max_x) -> int
            Draw the title/hint/description rows. Returns the first screen row
            index where the scrollable item list should start.
        draw_row(stdscr, y, idx, is_cursor, max_x) -> None
            Draw one item row.
        on_action(action, cursor) -> value
            Reducer for SELECT/TOGGLE/CANCEL. Return ``_KEEP`` to continue the
            loop; return anything else to resolve the menu with that value.
            Cursor movement, paging, and Home/End are handled by the driver.
        reserve_bottom: number of bottom screen rows kept clear of items.
        draw_footer(stdscr, max_y, max_x) -> None
            Optional legacy footer painter. Drawn when ``footer_text_fn`` is not
            provided; its row budget must be included in ``reserve_bottom``.
        footer_text_fn(cursor, scroll_offset, visible_rows) -> str
            Optional bottom-row text supplier for scroll/status hints.
        extra_color_pairs: also init pair 3 (dim gray) for status bars.
        fallback() -> value
            Called when curses errors out on a real TTY (curses unavailable).
        cancel_value: returned on non-TTY stdin, ESC/cancel, or KeyboardInterrupt.
    """
    # Non-TTY (piped/redirected stdin): curses and input() both hang or spin,
    # so return the cancel value directly — matching the pre-refactor guard in
    # each menu (the numbered fallback is only for curses errors on a real TTY).
    if not sys.stdin.isatty():
        return cancel_value

    try:
        import curses
        result_holder = [_KEEP]

        def _draw(stdscr):
            curses.curs_set(0)
            if curses.has_colors():
                curses.start_color()
                curses.use_default_colors()
                curses.init_pair(1, curses.COLOR_GREEN, -1)
                curses.init_pair(2, curses.COLOR_YELLOW, -1)
                if extra_color_pairs or footer_text_fn is not None or draw_footer is not None:
                    curses.init_pair(
                        3, 8 if curses.COLORS > 8 else curses.COLOR_WHITE, -1
                    )
            cursor = initial_cursor
            scroll_offset = 0

            while True:
                stdscr.clear()
                max_y, max_x = stdscr.getmaxyx()

                items_start = draw_header(stdscr, max_y, max_x)

                raw_visible_rows = max_y - items_start - reserve_bottom
                if raw_visible_rows <= 0:
                    _draw_too_small(
                        stdscr,
                        max_y,
                        max_x,
                        "Terminal too small; enlarge window or press q",
                    )
                    stdscr.refresh()
                    action = read_menu_key(stdscr)
                    if action == NAV_CANCEL:
                        result_holder[0] = cancel_value
                        return
                    continue

                cursor, scroll_offset, visible_rows = _scroll_window_for_cursor(
                    cursor, scroll_offset, raw_visible_rows, item_count
                )

                for draw_i, i in enumerate(
                    range(scroll_offset, min(item_count, scroll_offset + visible_rows))
                ):
                    y = draw_i + items_start
                    if y >= max_y - reserve_bottom:
                        break
                    draw_row(stdscr, y, i, i == cursor, max_x)

                if footer_text_fn is not None:
                    footer_text = footer_text_fn(cursor, scroll_offset, visible_rows)
                    footer_attr = curses.A_DIM
                    if curses.has_colors():
                        footer_attr |= curses.color_pair(3)
                    _draw_footer(stdscr, max_y - 1, max_x, footer_text, footer_attr)
                elif draw_footer is not None:
                    draw_footer(stdscr, max_y, max_x)

                stdscr.refresh()
                action = read_menu_key(stdscr)

                if action == NAV_UP and item_count:
                    cursor = (cursor - 1) % item_count
                elif action == NAV_DOWN and item_count:
                    cursor = (cursor + 1) % item_count
                elif action == NAV_PAGE_UP and item_count:
                    cursor = max(0, cursor - visible_rows)
                elif action == NAV_PAGE_DOWN and item_count:
                    cursor = min(item_count - 1, cursor + visible_rows)
                elif action == NAV_HOME and item_count:
                    cursor = 0
                elif action == NAV_END and item_count:
                    cursor = item_count - 1
                elif action in (NAV_SELECT, NAV_TOGGLE, NAV_CANCEL):
                    outcome = on_action(action, cursor)
                    if outcome is not _KEEP:
                        result_holder[0] = outcome
                        return

        curses.wrapper(_draw)
        flush_stdin()
        return result_holder[0] if result_holder[0] is not _KEEP else cancel_value

    except KeyboardInterrupt:
        return cancel_value
    except Exception:
        return fallback()


def curses_checklist(
    title: str,
    items: List[str],
    selected: Set[int],
    *,
    cancel_returns: Set[int] | None = None,
    status_fn: Optional[Callable[[Set[int]], str]] = None,
) -> Set[int]:
    """Curses multi-select checklist. Returns set of selected indices.

    Args:
        title: Header line displayed above the checklist.
        items: Display labels for each row.
        selected: Indices that start checked (pre-selected).
        cancel_returns: Returned on ESC/q. Defaults to the original *selected*.
        status_fn: Optional callback ``f(chosen_indices) -> str`` whose return
            value is rendered on the bottom row of the terminal.  Use this for
            live aggregate info (e.g. estimated token counts).
    """
    if cancel_returns is None:
        cancel_returns = set(selected)

    chosen = set(selected)

    def _draw_header(stdscr, max_y, max_x):
        import curses
        try:
            hattr = curses.A_BOLD
            if curses.has_colors():
                hattr |= curses.color_pair(2)
            stdscr.addnstr(0, 0, title, max_x - 1, hattr)
            stdscr.addnstr(
                1, 0,
                "  ↑↓/j/k navigate  PgUp/PgDn page  Home/End jump  SPACE toggle  ENTER confirm  ESC cancel",
                max_x - 1, curses.A_DIM,
            )
        except curses.error:
            pass
        return 3

    def _draw_row(stdscr, y, i, is_cursor, max_x):
        import curses
        check = "✓" if i in chosen else " "
        arrow = "→" if is_cursor else " "
        line = f" {arrow} [{check}] {items[i]}"
        attr = curses.A_NORMAL
        if is_cursor:
            attr = curses.A_BOLD
            if curses.has_colors():
                attr |= curses.color_pair(1)
        try:
            stdscr.addnstr(y, 0, line, max_x - 1, attr)
        except curses.error:
            pass

    def _footer_text(cursor, scroll_offset, visible_rows):
        scroll_text = _scroll_status_text(
            cursor, scroll_offset, visible_rows, len(items)
        )
        if status_fn is None:
            return scroll_text
        try:
            status_text = status_fn(chosen)
        except Exception:
            status_text = ""
        if status_text and scroll_text:
            return f"{status_text}   {scroll_text}"
        return status_text or scroll_text

    def _on_action(action, cursor):
        if action == NAV_TOGGLE:
            chosen.symmetric_difference_update({cursor})
            return _KEEP
        if action == NAV_SELECT:
            return set(chosen)
        return cancel_returns  # NAV_CANCEL

    return _run_curses_menu(
        initial_cursor=0,
        item_count=len(items),
        draw_header=_draw_header,
        draw_row=_draw_row,
        on_action=_on_action,
        reserve_bottom=1,
        footer_text_fn=_footer_text,
        extra_color_pairs=True,
        fallback=lambda: _numbered_fallback(title, items, selected, cancel_returns, status_fn),
        cancel_value=cancel_returns,
    )


def curses_radiolist(
    title: str,
    items: List[str],
    selected: int = 0,
    *,
    cancel_returns: int | None = None,
    description: str | None = None,
) -> int:
    """Curses single-select radio list. Returns the selected index.

    Args:
        title: Header line displayed above the list.
        items: Display labels for each row.
        selected: Index that starts selected (pre-selected).
        cancel_returns: Returned on ESC/q. Defaults to the original *selected*.
        description: Optional multi-line text shown between the title and
            the item list.  Useful for context that should survive the
            curses screen clear.
    """
    if cancel_returns is None:
        cancel_returns = selected

    desc_lines: list[str] = []
    if description:
        desc_lines = description.splitlines()

    def _draw_header(stdscr, max_y, max_x):
        import curses
        row = 0
        try:
            hattr = curses.A_BOLD
            if curses.has_colors():
                hattr |= curses.color_pair(2)
            stdscr.addnstr(row, 0, title, max_x - 1, hattr)
            row += 1

            # Description lines
            for dline in desc_lines:
                if row >= max_y - 1:
                    break
                stdscr.addnstr(row, 0, dline, max_x - 1, curses.A_NORMAL)
                row += 1

            stdscr.addnstr(
                row, 0,
                "  \u2191\u2193/j/k navigate  PgUp/PgDn page  Home/End jump  ENTER/SPACE select  ESC cancel",
                max_x - 1, curses.A_DIM,
            )
            row += 1
        except curses.error:
            pass
        # One blank row between the hint and the item list.
        return row + 1

    def _draw_row(stdscr, y, i, is_cursor, max_x):
        import curses
        radio = "\u25cf" if i == selected else "\u25cb"
        arrow = "\u2192" if is_cursor else " "
        line = f" {arrow} ({radio}) {items[i]}"
        attr = curses.A_NORMAL
        if is_cursor:
            attr = curses.A_BOLD
            if curses.has_colors():
                attr |= curses.color_pair(1)
        try:
            stdscr.addnstr(y, 0, line, max_x - 1, attr)
        except curses.error:
            pass

    def _on_action(action, cursor):
        if action in (NAV_SELECT, NAV_TOGGLE):
            return cursor
        return cancel_returns  # NAV_CANCEL

    return _run_curses_menu(
        initial_cursor=selected,
        item_count=len(items),
        draw_header=_draw_header,
        draw_row=_draw_row,
        on_action=_on_action,
        reserve_bottom=1,
        footer_text_fn=lambda cursor, scroll_offset, visible_rows: _scroll_status_text(
            cursor, scroll_offset, visible_rows, len(items)
        ),
        extra_color_pairs=True,
        fallback=lambda: _radio_numbered_fallback(title, items, selected, cancel_returns),
        cancel_value=cancel_returns,
    )


def _radio_numbered_fallback(
    title: str,
    items: List[str],
    selected: int,
    cancel_returns: int,
) -> int:
    """Text-based numbered fallback for radio selection."""
    print(color(f"\n  {title}", Colors.YELLOW))
    print(color("  Select by number, Enter to confirm.\n", Colors.DIM))

    for i, label in enumerate(items):
        marker = color("(\u25cf)", Colors.GREEN) if i == selected else "(\u25cb)"
        print(f"  {marker} {i + 1:>2}. {label}")
    print()
    try:
        val = input(color(f"  Choice [default {selected + 1}]: ", Colors.DIM)).strip()
        if not val:
            return selected
        idx = int(val) - 1
        if 0 <= idx < len(items):
            return idx
        return selected
    except (ValueError, KeyboardInterrupt, EOFError):
        return cancel_returns


def curses_single_select(
    title: str,
    items: List[str],
    default_index: int = 0,
    *,
    cancel_label: str = "Cancel",
) -> int | None:
    """Curses single-select menu. Returns selected index or None on cancel.

    Works inside prompt_toolkit because curses.wrapper() restores the terminal
    safely, unlike simple_term_menu which conflicts with /dev/tty.
    """
    all_items = list(items) + [cancel_label]
    cancel_idx = len(items)

    def _draw_header(stdscr, max_y, max_x):
        import curses
        try:
            hattr = curses.A_BOLD
            if curses.has_colors():
                hattr |= curses.color_pair(2)
            stdscr.addnstr(0, 0, title, max_x - 1, hattr)
            stdscr.addnstr(
                1, 0,
                "  ↑↓/j/k navigate  PgUp/PgDn page  Home/End jump  ENTER confirm  ESC/q cancel",
                max_x - 1, curses.A_DIM,
            )
        except curses.error:
            pass
        return 3

    def _draw_row(stdscr, y, i, is_cursor, max_x):
        import curses
        arrow = "→" if is_cursor else " "
        line = f" {arrow} {all_items[i]}"
        attr = curses.A_NORMAL
        if is_cursor:
            attr = curses.A_BOLD
            if curses.has_colors():
                attr |= curses.color_pair(1)
        try:
            stdscr.addnstr(y, 0, line, max_x - 1, attr)
        except curses.error:
            pass

    def _on_action(action, cursor):
        if action == NAV_SELECT:
            # Selecting the synthetic cancel row resolves to None, mirroring
            # the old post-loop ``>= cancel_idx`` guard.
            return None if cursor >= cancel_idx else cursor
        if action == NAV_CANCEL:
            return None
        return _KEEP  # NAV_TOGGLE — no-op for this menu

    return _run_curses_menu(
        initial_cursor=min(default_index, len(all_items) - 1),
        item_count=len(all_items),
        draw_header=_draw_header,
        draw_row=_draw_row,
        on_action=_on_action,
        reserve_bottom=1,
        footer_text_fn=lambda cursor, scroll_offset, visible_rows: _scroll_status_text(
            cursor, scroll_offset, visible_rows, len(all_items)
        ),
        extra_color_pairs=True,
        fallback=lambda: _numbered_single_fallback(title, all_items, cancel_idx),
        cancel_value=None,
    )


def _numbered_single_fallback(
    title: str,
    items: List[str],
    cancel_idx: int,
) -> int | None:
    """Text-based numbered fallback for single-select."""
    print(f"\n  {title}\n")
    for i, label in enumerate(items, 1):
        print(f"  {i}. {label}")
    print()
    try:
        val = input(f"  Choice [1-{len(items)}]: ").strip()
        if not val:
            return None
        idx = int(val) - 1
        if 0 <= idx < len(items) and idx < cancel_idx:
            return idx
        if idx == cancel_idx:
            return None
    except (ValueError, KeyboardInterrupt, EOFError):
        pass
    return None


def _numbered_fallback(
    title: str,
    items: List[str],
    selected: Set[int],
    cancel_returns: Set[int],
    status_fn: Optional[Callable[[Set[int]], str]] = None,
) -> Set[int]:
    """Text-based toggle fallback for terminals without curses."""
    chosen = set(selected)
    print(color(f"\n  {title}", Colors.YELLOW))
    print(color("  Toggle by number, Enter to confirm.\n", Colors.DIM))

    while True:
        for i, label in enumerate(items):
            marker = color("[✓]", Colors.GREEN) if i in chosen else "[ ]"
            print(f"  {marker} {i + 1:>2}. {label}")
        if status_fn:
            status_text = status_fn(chosen)
            if status_text:
                print(color(f"\n  {status_text}", Colors.DIM))
        print()
        try:
            val = input(color("  Toggle # (or Enter to confirm): ", Colors.DIM)).strip()
            if not val:
                break
            idx = int(val) - 1
            if 0 <= idx < len(items):
                chosen.symmetric_difference_update({idx})
        except (ValueError, KeyboardInterrupt, EOFError):
            return cancel_returns
        print()

    return chosen
