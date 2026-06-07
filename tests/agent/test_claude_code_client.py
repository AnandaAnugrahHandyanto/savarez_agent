from __future__ import annotations

import io
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from agent.claude_code_client import ClaudeCodeClient


class _FakeProcess:
    def __init__(self, *, stdout: str, stderr: str = '', returncode: int = 0) -> None:
        self.stdin = None
        self.stdout = io.StringIO(stdout)
        self.stderr = io.StringIO(stderr)
        self.returncode = returncode
        self._polls = 0
        self.killed = False

    def poll(self):
        self._polls += 1
        return self.returncode

    def kill(self):
        self.killed = True
        self.returncode = -9

    def terminate(self):
        self.returncode = -15

    def wait(self, timeout=None):
        return self.returncode


def test_build_command_uses_claude_print_json_defaults(tmp_path: Path) -> None:
    client = ClaudeCodeClient(acp_cwd=str(tmp_path))

    cmd = client._build_command('hello', model='sonnet')

    assert cmd[:5] == ['claude', '--print', '--output-format', 'json', '--tools']
    assert '--model' in cmd
    assert 'sonnet' in cmd
    assert cmd[-1] == 'hello'


def test_create_completion_maps_json_result_to_openai_shape(tmp_path: Path) -> None:
    payload = {
        'type': 'result',
        'subtype': 'success',
        'is_error': False,
        'result': 'ok',
        'usage': {
            'input_tokens': 2,
            'cache_read_input_tokens': 3,
            'cache_creation_input_tokens': 5,
            'output_tokens': 7,
        },
    }
    client = ClaudeCodeClient(command='claude', args=['--print', '--output-format', 'json'], acp_cwd=str(tmp_path))

    with patch('agent.claude_code_client.subprocess.Popen', return_value=_FakeProcess(stdout=json.dumps(payload))):
        response = client.chat.completions.create(
            model='sonnet',
            messages=[{'role': 'user', 'content': 'say ok'}],
        )

    assert response.choices[0].message.content == 'ok'
    assert response.choices[0].finish_reason == 'stop'
    assert response.usage.prompt_tokens == 10
    assert response.usage.completion_tokens == 7


def test_create_completion_extracts_xml_tool_calls(tmp_path: Path) -> None:
    payload = {
        'type': 'result',
        'subtype': 'success',
        'is_error': False,
        'result': '<tool_call>{"id":"call_1","type":"function","function":{"name":"terminal","arguments":"{\\"command\\":\\"pwd\\"}"}}</tool_call>',
    }
    client = ClaudeCodeClient(command='claude', args=['--print', '--output-format', 'json'], acp_cwd=str(tmp_path))

    with patch('agent.claude_code_client.subprocess.Popen', return_value=_FakeProcess(stdout=json.dumps(payload))):
        response = client.chat.completions.create(
            model='sonnet',
            messages=[{'role': 'user', 'content': 'run pwd'}],
        )

    assert response.choices[0].finish_reason == 'tool_calls'
    assert response.choices[0].message.tool_calls[0].function.name == 'terminal'


def test_run_prompt_missing_cli_raises_clear_error(tmp_path: Path) -> None:
    client = ClaudeCodeClient(command='missing-claude', args=[], acp_cwd=str(tmp_path))

    with patch('agent.claude_code_client.subprocess.Popen', side_effect=FileNotFoundError):
        with pytest.raises(RuntimeError, match='Could not start Claude Code CLI command'):
            client._run_prompt('hello', model='sonnet', timeout_seconds=1)


def test_run_prompt_nonzero_exit_raises(tmp_path: Path) -> None:
    client = ClaudeCodeClient(command='claude', args=['--print', '--output-format', 'json'], acp_cwd=str(tmp_path))

    with patch('agent.claude_code_client.subprocess.Popen', return_value=_FakeProcess(stdout='', stderr='boom', returncode=1)):
        with pytest.raises(RuntimeError, match='Claude Code CLI failed: boom'):
            client._run_prompt('hello', model='sonnet', timeout_seconds=1)
