import pytest

from hermes_cli.commands import _sanitize_telegram_command_name


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("/foo-bar", "foo_bar"),
        ("foo-bar", "foo_bar"),
        ("foo/bar", "foobar"),
        ("a+b", "ab"),
        ("A+B", "ab"),
        ("_weird", "c__weird"),
        ("9lives", "c_9lives"),
        ("a" * 33, "a" * 32),
        ("_" + "a" * 31, "c__" + "a" * 29),
        ("+++", ""),
        ("---", "c____"),
        ("", ""),
        ("/", ""),
    ],
)
def test_sanitize_telegram_command_name(raw, expected):
    assert _sanitize_telegram_command_name(raw) == expected
