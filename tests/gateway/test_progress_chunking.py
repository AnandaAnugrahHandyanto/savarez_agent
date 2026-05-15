import pytest

from gateway.config import Platform
from gateway.platforms.base import BasePlatformAdapter, SendResult
from gateway.run import _send_or_update_progress_chunks


class FakeProgressAdapter:
    MAX_MESSAGE_LENGTH = 650
    truncate_message = staticmethod(BasePlatformAdapter.truncate_message)

    def __init__(self):
        self.next_id = 1
        self.sends = []
        self.edits = []
        self.deletes = []

    async def send(self, chat_id, content, reply_to=None, metadata=None):
        assert len(content) <= self.MAX_MESSAGE_LENGTH
        message_id = f"m{self.next_id}"
        self.next_id += 1
        self.sends.append(
            {
                "chat_id": chat_id,
                "content": content,
                "reply_to": reply_to,
                "metadata": metadata,
                "message_id": message_id,
            }
        )
        return SendResult(success=True, message_id=message_id)

    async def edit_message(self, chat_id, message_id, content, *, finalize=False):
        assert len(content) <= self.MAX_MESSAGE_LENGTH
        self.edits.append(
            {
                "chat_id": chat_id,
                "message_id": message_id,
                "content": content,
                "finalize": finalize,
            }
        )
        return SendResult(success=True, message_id=message_id)

    async def delete_message(self, chat_id, message_id):
        self.deletes.append((chat_id, message_id))
        return True


@pytest.mark.asyncio
async def test_chunked_progress_updates_existing_chunks_instead_of_resending():
    adapter = FakeProgressAdapter()
    message_ids = []

    first_text = "\n".join(
        [
            "📚 skill_view: nockchain",
            "📋 todo: planning 4 task(s)",
            "📖 read_file: " + "/Users/david/Desktop/stuff/nockails/README.md " * 8,
            "🔧 patch: " + "/Users/david/Desktop/stuff/nockails/crates/app/src/lib.rs " * 7,
        ]
    )

    ok = await _send_or_update_progress_chunks(
        adapter=adapter,
        chat_id="chat-1",
        content=first_text,
        message_ids=message_ids,
        reply_to="root-msg",
        metadata={"thread_id": "topic-1"},
        platform=Platform.TELEGRAM,
    )

    assert ok is True
    assert len(message_ids) > 1
    assert len(adapter.sends) == len(message_ids)
    assert adapter.sends[0]["reply_to"] == "root-msg"
    assert adapter.sends[1]["reply_to"] == message_ids[0]

    adapter.sends.clear()
    adapter.edits.clear()

    # Same rendered chunk count, but changed content. This is the case that
    # used to append a fresh `(2/2)` continuation on every update after the
    # first split instead of editing the existing two progress chunks.
    second_text = first_text.replace("crates/app", "crates/bin")
    ok = await _send_or_update_progress_chunks(
        adapter=adapter,
        chat_id="chat-1",
        content=second_text,
        message_ids=message_ids,
        reply_to="root-msg",
        metadata={"thread_id": "topic-1"},
        platform=Platform.TELEGRAM,
    )

    assert ok is True
    assert adapter.sends == []
    assert [edit["message_id"] for edit in adapter.edits] == message_ids


@pytest.mark.asyncio
async def test_chunked_progress_sends_only_new_chunks_when_chunk_count_grows():
    adapter = FakeProgressAdapter()
    message_ids = []

    base = "\n".join(f"tool_{i}: " + ("x" * 70) for i in range(8))
    ok = await _send_or_update_progress_chunks(
        adapter=adapter,
        chat_id="chat-1",
        content=base,
        message_ids=message_ids,
        reply_to="root-msg",
        metadata=None,
        platform=Platform.TELEGRAM,
    )
    assert ok is True
    initial_ids = list(message_ids)
    initial_send_count = len(adapter.sends)
    assert initial_send_count >= 1

    adapter.sends.clear()
    adapter.edits.clear()

    larger = base + "\n" + "new_tool: " + ("y" * 700)
    ok = await _send_or_update_progress_chunks(
        adapter=adapter,
        chat_id="chat-1",
        content=larger,
        message_ids=message_ids,
        reply_to="root-msg",
        metadata=None,
        platform=Platform.TELEGRAM,
    )

    assert ok is True
    assert [edit["message_id"] for edit in adapter.edits] == initial_ids
    assert len(adapter.sends) == len(message_ids) - len(initial_ids)
    if adapter.sends:
        assert adapter.sends[0]["reply_to"] == initial_ids[-1]
