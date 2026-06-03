from types import SimpleNamespace

from gateway.run import _should_persist_hygiene_compression_result


def test_hygiene_compression_abort_is_not_persisted():
    """Aborted hygiene compression must not rewrite the canonical transcript."""
    messages = [
        {"role": "user", "content": "recent request"},
        {"role": "assistant", "content": "recent answer"},
    ]

    assert not _should_persist_hygiene_compression_result(
        old_session_id="sid-old",
        new_session_id="sid-old",
        original_messages=messages,
        compressed_messages=messages,
        compressor=SimpleNamespace(_last_compress_aborted=True),
    )


def test_hygiene_compression_unchanged_same_session_is_not_persisted():
    messages = [
        {"role": "user", "content": "recent request"},
        {"role": "assistant", "content": "recent answer"},
    ]

    assert not _should_persist_hygiene_compression_result(
        old_session_id="sid-old",
        new_session_id="sid-old",
        original_messages=messages,
        compressed_messages=list(messages),
        compressor=SimpleNamespace(_last_compress_aborted=False),
    )


def test_hygiene_compression_persists_rotated_session():
    messages = [{"role": "user", "content": "old"}]

    assert _should_persist_hygiene_compression_result(
        old_session_id="sid-old",
        new_session_id="sid-new",
        original_messages=messages,
        compressed_messages=messages,
        compressor=SimpleNamespace(_last_compress_aborted=False),
    )


def test_hygiene_compression_persists_changed_same_session_result():
    original = [{"role": "user", "content": "old"}]
    compressed = [{"role": "user", "content": "summary\n\nrecent"}]

    assert _should_persist_hygiene_compression_result(
        old_session_id="sid-old",
        new_session_id="sid-old",
        original_messages=original,
        compressed_messages=compressed,
        compressor=SimpleNamespace(_last_compress_aborted=False),
    )
