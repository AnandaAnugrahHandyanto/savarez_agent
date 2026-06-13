"""Integration tests for patch tool mode='hashline' path.

Exercises ShellFileOperations.patch_hashline (diff/lint/safety reuse) plus
a regression check that mode='replace' fuzzy editing is unaffected.
"""
import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from tools.file_operations import ShellFileOperations
from tools import hashline_core as hl


class LocalEnv:
    def __init__(self, cwd):
        self.cwd = cwd

    def execute(self, command, cwd=None, timeout=None, stdin_data=None, **kw):
        p = subprocess.run(command, shell=True, cwd=cwd or self.cwd,
                           capture_output=True, text=True, input=stdin_data,
                           timeout=timeout)
        return {"output": p.stdout + p.stderr, "returncode": p.returncode}


def _ops(tmpdir):
    return ShellFileOperations(LocalEnv(tmpdir), cwd=tmpdir)


def test_hashline_valid_edit():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "a.py")
        open(path, "w").write("retries = 3\ntimeout = 30\n")
        ops = _ops(d)
        tag = hl.content_tag(open(path).read())
        res = ops.patch_hashline(f"[{path}#{tag}]\nreplace 1:\n+retries = 5\n")
        assert res.success, res.error
        assert open(path).read() == "retries = 5\ntimeout = 30\n"
        assert path in res.files_modified


def test_hashline_stale_rejected():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "a.py")
        open(path, "w").write("LIMIT = 100\n")
        ops = _ops(d)
        stale_tag = hl.content_tag("LIMIT = 10\n")
        res = ops.patch_hashline(f"[{path}#{stale_tag}]\nreplace 1:\n+LIMIT = 50\n")
        assert not res.success
        assert "stale anchor" in (res.error or "")
        assert open(path).read() == "LIMIT = 100\n"


def test_hashline_duplicate_lines_precise():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "a.py")
        content = 'log("x")\nlog("x")\n'
        open(path, "w").write(content)
        ops = _ops(d)
        tag = hl.content_tag(content)
        res = ops.patch_hashline(f'[{path}#{tag}]\nreplace 2:\n+log("SECOND")\n')
        assert res.success, res.error
        assert open(path).read() == 'log("x")\nlog("SECOND")\n'


def test_hashline_atomic_multifile():
    with tempfile.TemporaryDirectory() as d:
        p1 = os.path.join(d, "a.py"); open(p1, "w").write("a\n")
        p2 = os.path.join(d, "b.py"); open(p2, "w").write("b\n")
        ops = _ops(d)
        t1 = hl.content_tag("a\n")
        patch = f"[{p1}#{t1}]\nreplace 1:\n+A\n[{p2}#dead]\nreplace 1:\n+B\n"
        res = ops.patch_hashline(patch)
        assert not res.success
        assert open(p1).read() == "a\n"
        assert open(p2).read() == "b\n"


def test_replace_mode_still_works():
    """Regression: fuzzy replace is unaffected by hashline addition."""
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "a.py")
        open(path, "w").write("x = 1\ny = 2\n")
        ops = _ops(d)
        res = ops.patch_replace(path, old_string="x = 1", new_string="x = 42")
        assert res.success, res.error
        assert "x = 42" in open(path).read()


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-v"]))
