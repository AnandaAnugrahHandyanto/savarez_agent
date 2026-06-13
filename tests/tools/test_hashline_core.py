"""Unit tests for hashline core — covers User Stories 1, 2 and edge cases."""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from tools.hashline_core import (  # noqa: E402
    content_tag, parse_patch, preflight, apply_patch_text, apply_edits,
    normalize, HashlineError,
)


def _mkfile(content):
    fd, path = tempfile.mkstemp(suffix=".txt")
    os.close(fd)
    with open(path, "w") as f:
        f.write(content)
    return path


def _read(p):
    with open(p) as f:
        return f.read()


# --- tagging -------------------------------------------------------------- #

def test_content_tag_stable_across_newline_styles():
    assert content_tag("a\nb\n") == content_tag("a\r\nb\r\n")
    assert content_tag("a\nb") == content_tag("a\nb\n")  # trailing nl ignored


def test_content_tag_changes_on_content_change():
    assert content_tag("max_retries: 3") != content_tag("max_retries: 5")


# --- User Story 1: stale anchor rejection (scenario B) -------------------- #

def test_us1_stale_anchor_rejected_file_unchanged():
    # File is actually max_retries:5, model's patch anchored to the OLD content (3)
    actual = 'config = {\n    "max_retries": 5,\n}\n'
    path = _mkfile(actual)
    try:
        stale_tag = content_tag('config = {\n    "max_retries": 3,\n}\n')
        patch = f"[{path}#{stale_tag}]\nreplace 2..2:\n+    \"max_retries\": 10,\n"
        res = apply_patch_text(patch, root="/")
        assert res["ok"] is False
        assert any("stale anchor" in e for e in res["errors"])
        # file MUST be untouched
        assert _read(path) == actual
    finally:
        os.unlink(path)


def test_us1_matching_tag_applies():
    actual = 'config = {\n    "max_retries": 5,\n}\n'
    path = _mkfile(actual)
    try:
        tag = content_tag(actual)
        patch = f"[{path}#{tag}]\nreplace 2..2:\n+    \"max_retries\": 10,\n"
        res = apply_patch_text(patch, root="/")
        assert res["ok"] is True
        assert '"max_retries": 10,' in _read(path)
    finally:
        os.unlink(path)


# --- User Story 2: duplicate-line precise edit (scenario A) ---------------- #

def test_us2_edit_second_of_duplicate_lines():
    content = (
        'def save(self):\n    log.info("x")\n    self.commit()\n\n'
        'def reload(self):\n    log.info("x")\n    self.commit()\n'
    )
    path = _mkfile(content)
    try:
        tag = content_tag(content)
        # line 6 is the reload() logger
        patch = f'[{path}#{tag}]\nreplace 6..6:\n+    log.info("reloaded")\n'
        res = apply_patch_text(patch, root="/")
        assert res["ok"] is True
        out = _read(path).split("\n")
        assert out[1] == '    log.info("x")'        # first untouched
        assert out[5] == '    log.info("reloaded")'  # second changed
    finally:
        os.unlink(path)


def test_us2_edit_first_of_duplicate_lines():
    content = 'log.info("x")\nlog.info("x")\n'
    path = _mkfile(content)
    try:
        tag = content_tag(content)
        patch = f'[{path}#{tag}]\nreplace 1..1:\n+log.info("FIRST")\n'
        res = apply_patch_text(patch, root="/")
        assert res["ok"] is True
        out = _read(path).split("\n")
        assert out[0] == 'log.info("FIRST")'
        assert out[1] == 'log.info("x")'
    finally:
        os.unlink(path)


# --- operations ----------------------------------------------------------- #

def test_delete_range():
    content = "a\nb\nc\nd\n"
    path = _mkfile(content)
    try:
        tag = content_tag(content)
        res = apply_patch_text(f"[{path}#{tag}]\ndelete 2..3\n", root="/")
        assert res["ok"] is True
        assert _read(path) == "a\nd\n"
    finally:
        os.unlink(path)


def test_insert_after_and_before():
    content = "a\nb\nc\n"
    path = _mkfile(content)
    try:
        tag = content_tag(content)
        res = apply_patch_text(f"[{path}#{tag}]\ninsert after 2:\n+X\n", root="/")
        assert res["ok"] is True
        assert _read(path) == "a\nb\nX\nc\n"
    finally:
        os.unlink(path)


def test_insert_head_and_tail():
    content = "b\n"
    path = _mkfile(content)
    try:
        tag = content_tag(content)
        res = apply_patch_text(f"[{path}#{tag}]\ninsert head:\n+a\n", root="/")
        assert res["ok"] is True
        assert _read(path) == "a\nb\n"
        tag2 = content_tag(_read(path))
        res2 = apply_patch_text(f"[{path}#{tag2}]\ninsert tail:\n+c\n", root="/")
        assert res2["ok"] is True
        assert _read(path) == "a\nb\nc\n"
    finally:
        os.unlink(path)


def test_multi_op_same_file_descending_apply():
    # two replaces in one file; must not shift each other
    content = "1\n2\n3\n4\n5\n"
    path = _mkfile(content)
    try:
        tag = content_tag(content)
        patch = f"[{path}#{tag}]\nreplace 1..1:\n+ONE\nreplace 5..5:\n+FIVE\n"
        res = apply_patch_text(patch, root="/")
        assert res["ok"] is True
        assert _read(path) == "ONE\n2\n3\n4\nFIVE\n"
    finally:
        os.unlink(path)


# --- edge cases ----------------------------------------------------------- #

def test_line_out_of_range_rejected():
    content = "a\nb\n"
    path = _mkfile(content)
    try:
        tag = content_tag(content)
        res = apply_patch_text(f"[{path}#{tag}]\nreplace 5..5:\n+x\n", root="/")
        assert res["ok"] is False
        assert any("out of range" in e for e in res["errors"])
        assert _read(path) == content  # untouched
    finally:
        os.unlink(path)


def test_atomic_multi_file_partial_failure():
    good = _mkfile("hello\n")
    bad = _mkfile("world\n")
    try:
        gtag = content_tag("hello\n")
        # bad uses wrong tag -> whole batch must reject, good must stay untouched
        patch = (
            f"[{good}#{gtag}]\nreplace 1..1:\n+HELLO\n"
            f"[{bad}#dead]\nreplace 1..1:\n+WORLD\n"
        )
        res = apply_patch_text(patch, root="/")
        assert res["ok"] is False
        assert _read(good) == "hello\n"   # NOT written despite being valid
        assert _read(bad) == "world\n"
    finally:
        os.unlink(good)
        os.unlink(bad)


def test_binary_rejected():
    path = _mkfile("a\x00b\n")
    try:
        res = apply_patch_text(f"[{path}#0000]\nreplace 1..1:\n+x\n", root="/")
        assert res["ok"] is False
        assert any("binary" in e for e in res["errors"])
    finally:
        os.unlink(path)


def test_empty_patch_parse_error():
    res = apply_patch_text("just some text\n", root="/")
    assert res["ok"] is False
    assert any("parse error" in e for e in res["errors"])


def test_fence_tolerance():
    content = "a\nb\n"
    path = _mkfile(content)
    try:
        tag = content_tag(content)
        patch = f"*** Begin Patch\n[{path}#{tag}]\nreplace 1..1:\n+A\n*** End Patch\n"
        res = apply_patch_text(patch, root="/")
        assert res["ok"] is True
        assert _read(path) == "A\nb\n"
    finally:
        os.unlink(path)


def test_empty_body_line():
    content = "a\nb\n"
    path = _mkfile(content)
    try:
        tag = content_tag(content)
        # lone '+' = empty line
        patch = f"[{path}#{tag}]\ninsert after 1:\n+\n"
        res = apply_patch_text(patch, root="/")
        assert res["ok"] is True
        assert _read(path) == "a\n\nb\n"
    finally:
        os.unlink(path)
