import gateway.run as gateway_run
from agent.display import set_tool_preview_max_len


def teardown_function():
    set_tool_preview_max_len(0)


def test_all_mode_keeps_compact_default_when_tool_preview_length_is_zero():
    set_tool_preview_max_len(0)
    preview = (
        'python -m pytest tests/gateway/test_verbose_command.py::'
        'TestVerboseCommand::test_enabled_cycles_mode '
        '-q --tb=short --maxfail=1 --disable-warnings --color=no'
    )

    msg = gateway_run._build_tool_progress_message(
        'terminal',
        preview=preview,
        progress_mode='all',
    )

    assert '...' in msg
    assert preview not in msg


def test_verbose_mode_does_not_truncate_args_when_tool_preview_length_is_zero():
    set_tool_preview_max_len(0)
    args = {
        'command': (
            'bash -lc "echo segment1=abcdefghijklmnopqrstuvwxyz0123456789 '
            '&& echo segment2=abcdefghijklmnopqrstuvwxyz0123456789 '
            '&& echo segment3=abcdefghijklmnopqrstuvwxyz0123456789 '
            '&& echo segment4=abcdefghijklmnopqrstuvwxyz0123456789 '
            '&& echo segment5=abcdefghijklmnopqrstuvwxyz0123456789 '
            '&& echo segment6=abcdefghijklmnopqrstuvwxyz0123456789"'
        ),
        'timeout': 300,
        'workdir': '/tmp/example',
    }

    msg = gateway_run._build_tool_progress_message(
        'terminal',
        args=args,
        progress_mode='verbose',
    )

    payload = msg.split('\n', 1)[1]
    assert '...' not in msg
    assert 'segment1=abcdefghijklmnopqrstuvwxyz0123456789' in payload
    assert 'segment6=abcdefghijklmnopqrstuvwxyz0123456789' in payload


def test_positive_tool_preview_length_still_truncates_with_ellipsis():
    set_tool_preview_max_len(40)
    preview = 'x' * 80

    msg = gateway_run._build_tool_progress_message(
        'terminal',
        preview=preview,
        progress_mode='new',
    )

    assert '"' + ('x' * 37) + '..."' in msg
