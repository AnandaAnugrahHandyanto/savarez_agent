# 企业微信流式输出支持

## 背景

hermes-agent 的 streaming 框架通过 `GatewayStreamConsumer` 实现渐进式消息编辑：先发一条消息，然后不断 edit 更新内容。Telegram、Discord、Slack 都支持这种模式。

企业微信 AI Bot WebSocket 协议原生支持流式回复，通过同一个 `stream.id` 发送多个 chunk（`finish: false`），最后一个 `finish: true`。但之前 WeCom adapter 没有实现 `edit_message`，导致 streaming 降级为一次性发送。

本次改动将企业微信的原生 stream 协议接入 stream consumer 框架。

## 修改文件

### 1. `gateway/platforms/wecom.py`

#### `__init__` — 新增流式状态追踪

```python
self._active_streams: Dict[str, Tuple[str, str]] = {}  # message_id -> (reply_req_id, stream_id)
```

#### `_send_reply_stream` — 重构签名

```python
async def _send_reply_stream(
    self, reply_req_id: str, content: str,
    stream_id: Optional[str] = None, finish: bool = True,
) -> Dict[str, Any]:
```

- `stream_id` 为空时自动生成，兼容原有调用
- `finish=False`（中间 chunk）：fire-and-forget，直接 `_send_json` 不等 ACK
- `finish=True`（最终 chunk）：通过 `_send_reply_request` 等待 ACK 确认

#### `send` — 支持流式首帧

通过 `metadata["streaming"]` 判断是否由 stream consumer 调用：

- `streaming=True`：首帧以 `finish=False` 发送，将 `(reply_req_id, stream_id)` 存入 `_active_streams`
- `streaming=False`（默认）：行为不变，一次性 `finish=True` 发送

#### `edit_message` — 新增

```python
async def edit_message(self, chat_id: str, message_id: str, content: str) -> SendResult:
```

从 `_active_streams` 取出 `(reply_req_id, stream_id)`，发送 `finish=False` 的 stream chunk。stream consumer 每次调用 edit 时传入的是全量累积文本。

#### `finalize_stream` — 新增

```python
async def finalize_stream(self, chat_id: str, message_id: str, content: str) -> SendResult:
```

发送最后一个 `finish=True` 的 chunk，清理 `_active_streams` 中的状态。

### 2. `gateway/stream_consumer.py`

#### `__init__` — 新增 `reply_to` 参数

```python
def __init__(self, adapter, chat_id, config=None, metadata=None, reply_to=None):
```

#### `_send_or_edit` — 首次发送传递 `reply_to` 和 `streaming` 标记

```python
_meta = dict(self.metadata) if self.metadata else {}
_meta["streaming"] = True
result = await self.adapter.send(
    chat_id=self.chat_id, content=text,
    reply_to=self.reply_to, metadata=_meta,
)
```

#### `run` — 三处 finalize 调用

| 场景 | 处理 |
|------|------|
| `got_done=True` | 调用 `finalize_stream` 发送最终 chunk |
| `got_segment_break`（工具调用边界） | 先 finalize 当前 stream，再重置状态 |
| `CancelledError` | best-effort finalize |

### 3. `gateway/run.py`

创建 stream consumer 时传入 `reply_to=event_message_id`：

```python
_stream_consumer = GatewayStreamConsumer(
    adapter=_adapter, chat_id=source.chat_id,
    config=_consumer_cfg,
    metadata={"thread_id": _progress_thread_id} if _progress_thread_id else None,
    reply_to=event_message_id,
)
```

### 4. `config.yaml`

```yaml
streaming:
  enabled: true
```

## 数据流

```
用户消息 (req_id: abc123)
    │
    ▼
stream_consumer.on_delta("你")
    │
    ▼ _send_or_edit (首次)
adapter.send(reply_to="msg_id", metadata={"streaming": True})
    │  → _send_reply_stream(req_id="abc123", stream_id="stream-xxx", finish=False)
    │  → _active_streams["abc123"] = ("abc123", "stream-xxx")
    │  → 返回 message_id="abc123"
    │
stream_consumer.on_delta("你好")
    │
    ▼ _send_or_edit (编辑)
adapter.edit_message(message_id="abc123", content="你好")
    │  → _send_reply_stream(req_id="abc123", stream_id="stream-xxx", finish=False)
    │
    ... 更多 delta ...
    │
stream_consumer: got_done=True
    │
    ▼
adapter.finalize_stream(message_id="abc123", content="你好，有什么可以帮你的？")
    │  → _send_reply_stream(req_id="abc123", stream_id="stream-xxx", finish=True)
    │  → 清理 _active_streams
```

## 企业微信 WebSocket 协议参考

每个 stream chunk 的 payload 结构：

```json
{
  "cmd": "aibot.respond.msg",
  "headers": { "req_id": "<原始消息的 req_id>" },
  "body": {
    "msgtype": "stream",
    "stream": {
      "id": "<同一个 stream_id>",
      "finish": false,
      "content": "<全量文本>"
    }
  }
}
```

- 同一个 `stream.id` 的所有 chunk 会被企业微信客户端合并显示
- `content` 是全量文本（不是增量 delta）
- 最后一个 chunk 设置 `finish: true`
