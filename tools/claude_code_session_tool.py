#!/usr/bin/env python3
"""
Claude Code Session Tool - 直接运行 Claude Code CLI 实现实时流式输出

使用 CLI 的 --output-format stream-json 模式，直接捕获实时事件。
"""
import asyncio
import json
import logging
import os
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

CLAUDE_CODE_SESSION_SCHEMA = {
    "name": "claude_code_session",
    "description": (
        "直接启动 Claude Code 会话执行任务。\n\n"
        "功能:\n"
        "- 执行自然语言任务\n"
        "- 自动处理工具调用 (write_file, Bash, Read 等)\n"
        "- 支持自定义工作目录\n"
        "- 实时流式输出_progress\n\n"
        "使用场景:\n"
        "- 需要 Claude Code 完成复杂任务\n"
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "prompt": {
                "type": "string",
                "description": "要执行的自然语言任务描述",
            },
            "workdir": {
                "type": "string",
                "description": "工作目录 (默认: /Users/zoe/workspace)",
            },
            "model": {
                "type": "string",
                "description": "模型名称 (默认: MiniMax-M2.7-highspeed)",
            },
        },
        "required": ["prompt"],
    },
}


def _build_session_callbacks(parent_agent):
    """构建回调函数，连接 Session 到 Hermes 的 SSE 流"""
    
    progress_cb = getattr(parent_agent, "tool_progress_callback", None)
    
    def on_event(event_type: str, tool_name: str = None, preview: str = None, **kwargs):
        if progress_cb is None:
            return
        try:
            progress_cb(event_type, function_name=tool_name or "claude_code_session", preview=preview)
        except Exception as e:
            logger.debug(f"Callback error: {e}")
    
    return on_event


class LineReader:
    """异步按行读取，支持任意大小的行"""
    def __init__(self, stream):
        self._stream = stream
        self._buf = b""
    
    async def readline(self, timeout=30):
        """读取一行，支持任意长度的行"""
        while True:
            # 查找换行符
            idx = self._buf.find(b'\n')
            if idx >= 0:
                line = self._buf[:idx].decode('utf-8', errors='replace')
                self._buf = self._buf[idx+1:]
                return line
            
            # 没有换行符，读取更多数据
            try:
                chunk = await asyncio.wait_for(
                    self._stream.read(4096),
                    timeout=timeout
                )
                if not chunk:
                    # 流结束
                    if self._buf:
                        line = self._buf.decode('utf-8', errors='replace')
                        self._buf = b""
                        return line
                    return None
                self._buf += chunk
            except asyncio.TimeoutError:
                # 超时不意味结束，可能是长行，继续等待
                if self._buf:
                    # 有数据但没有换行符，可能是超长的 thinking 内容
                    # 强制返回当前缓冲区作为一行
                    line = self._buf.decode('utf-8', errors='replace')
                    self._buf = b""
                    return line
                raise


async def _run_claude_cli_stream(prompt: str, workdir: str, model: str, on_event) -> str:
    """
    直接运行 Claude Code CLI，捕获实时流式输出
    """
    # 构建环境
    env = os.environ.copy()
    env["ANTHROPIC_BASE_URL"] = "https://api.minimaxi.com/anthropic"
    env["ANTHROPIC_AUTH_TOKEN"] = os.environ.get(
        "ANTHROPIC_AUTH_TOKEN", 
        "sk-cp-mLEmph6vmCfosE6D2DSX0fvOf3nK5-dJElSa8ehNynDGtHZfG2Q6YFkthugj35urQViLMvyfUWTOcfrfADFT9AlJQI3mfVh4wP1hKSzhNKjA1Xos9wSimWs"
    )
    env["ANTHROPIC_MODEL"] = model
    
    # Claude CLI 路径
    claude_path = "/Users/zoe/.local/bin/claude"
    
    # 启动 CLI
    proc = await asyncio.create_subprocess_exec(
        claude_path,
        "-p",
        "--verbose",
        "--output-format", "stream-json",
        "--permission-mode", "bypassPermissions",
        prompt,
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=workdir,
        env=env,
    )
    
    all_text = []
    tool_results = []
    result_text = ""
    reader = LineReader(proc.stdout)
    
    # 读取流
    while True:
        try:
            line = await reader.readline(timeout=60)
        except asyncio.TimeoutError:
            on_event("subagent_progress", preview="(读取超时，继续等待...)")
            continue
        except Exception as e:
            logger.debug(f"Read error: {e}")
            break
        
        if not line:
            break
        
        try:
            msg = json.loads(line.strip())
        except:
            # 不是有效的 JSON，可能是 thinking 内容跨行了
            # 尝试作为纯文本处理
            if line.strip():
                logger.debug(f"Non-JSON line: {line[:100]}")
            continue
        
        msg_type = msg.get("type")
        
        if msg_type == "assistant":
            content = msg.get("message", {}).get("content", [])
            for block in content:
                if block.get("type") == "thinking":
                    thinking = block.get("thinking", "")[:100]
                    if thinking:
                        on_event("subagent_progress", preview=f"思考: {thinking}...")
                elif block.get("type") == "text":
                    text = block.get("text", "")
                    if text:
                        all_text.append(text)
                        on_event("subagent_progress", preview=text[:200])
                elif block.get("type") == "tool_use":
                    tool_name = block.get("name", "unknown")
                    on_event("tool.started", tool_name=tool_name, preview=f"调用工具: {tool_name}")
        elif msg_type == "user":
            content = msg.get("message", {}).get("content", [])
            for block in content:
                if block.get("type") == "tool_result":
                    result = block.get("content", "")
                    tool_results.append(result)
                    on_event("subagent_progress", preview=f"结果: {result[:100]}...")
        elif msg_type == "result":
            result_text = msg.get("result", "")
            break
    
    await proc.wait()
    
    return result_text or "\n".join(all_text)


async def _claude_code_session_impl(args: Dict[str, Any], parent_agent) -> str:
    """
    Claude Code 会话的实际异步实现
    直接运行 CLI 实现实时流式输出
    """
    prompt = args.get("prompt", "")
    if not prompt:
        return json.dumps({"error": "prompt 是必填参数"})
    
    workdir = args.get("workdir", "/Users/zoe/workspace")
    model = args.get("model") or os.getenv("ANTHROPIC_MODEL", "MiniMax-M2.7-highspeed")
    
    # 构建回调
    on_event = _build_session_callbacks(parent_agent)
    
    on_event("subagent_progress", preview="启动 Claude Code CLI...")
    
    try:
        result = await asyncio.wait_for(
            _run_claude_cli_stream(prompt, workdir, model, on_event),
            timeout=300.0
        )
        on_event("tool.completed", tool_name="claude_code_session", preview="完成")
        return json.dumps({"result": result, "status": "completed"})
    except asyncio.TimeoutError:
        return json.dumps({"error": "会话超时 (5分钟)"})
    except Exception as e:
        logger.exception("Claude Code session error")
        return json.dumps({"error": f"会话错误: {str(e)}"})


def _handle_claude_code_session(args: Dict[str, Any], **kw: Any):
    """工具处理器"""
    parent_agent = kw.get("parent_agent")
    return _claude_code_session_impl(args, parent_agent)


# 注册工具
from tools.registry import registry

registry.register(
    name="claude_code_session",
    toolset="claude",
    schema=CLAUDE_CODE_SESSION_SCHEMA,
    handler=_handle_claude_code_session,
    is_async=True,
    emoji="🤖",
)
