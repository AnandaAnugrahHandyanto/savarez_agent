"""Tests for code_index tool."""

import json
import os
import pytest
import tempfile
import time


class TestCodeIndex:
    @pytest.fixture
    def temp_project(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            src = os.path.join(tmpdir, "src")
            os.makedirs(src)
            py_file = os.path.join(src, "main.py")
            with open(py_file, "w") as f:
                f.write("class User:\n    def __init__(self, name):\n        self.name = name\n")
                f.write("\ndef hello():\n    return 'world'\n")
                f.write("\nimport os\nfrom pathlib import Path\n")
            ts_file = os.path.join(src, "types.ts")
            with open(ts_file, "w") as f:
                f.write("export interface User {\n  name: string;\n  age: number;\n}\n")
                f.write("\nexport function greet(name: string): string {\n  return `Hello ${name}`;\n}\n")
            yield tmpdir

    def test_check_requirements(self):
        from tools.code_index import check_code_index_requirements
        assert check_code_index_requirements() is True

    def test_build_index(self, temp_project):
        from tools.code_index import code_index
        output = code_index(temp_project, operation="build")
        data = json.loads(output)
        assert data["success"] is True
        assert data["operation"] == "build"
        assert data["stats"]["new_files"] >= 2
        assert data["stats"]["symbols_found"] >= 4

    def test_clear_index(self, temp_project):
        from tools.code_index import code_index
        code_index(temp_project, operation="build")
        output = code_index(temp_project, operation="clear")
        data = json.loads(output)
        assert data["success"] is True
        assert data["operation"] == "clear"

    def test_status_after_build(self, temp_project):
        from tools.code_index import code_index
        code_index(temp_project, operation="build")
        output = code_index(temp_project, operation="status")
        data = json.loads(output)
        assert data["success"] is True
        assert data["indexed"] is True
        assert data["symbols"] >= 4

    def test_status_no_index(self, temp_project):
        from tools.code_index import code_index
        output = code_index(temp_project, operation="status")
        data = json.loads(output)
        assert data["success"] is True
        assert data["indexed"] is False

    def test_project_root_not_found(self):
        from tools.code_index import code_index
        output = code_index("/nonexistent/path", operation="build")
        data = json.loads(output)
        assert data["success"] is False

    def test_build_with_file_pattern(self, temp_project):
        from tools.code_index import code_index
        output = code_index(temp_project, operation="build", file_pattern="*.ts")
        data = json.loads(output)
        assert data["success"] is True
        assert data["stats"]["new_files"] >= 1

    def test_build_targeted_path(self, temp_project):
        from tools.code_index import code_index
        src = os.path.join(temp_project, "src")
        output = code_index(temp_project, operation="build", path=src)
        data = json.loads(output)
        assert data["success"] is True
        assert data["stats"]["new_files"] >= 2


class TestCodeIndexSchema:
    def test_schema_has_required_fields(self):
        from tools.code_index import CODE_INDEX_SCHEMA
        assert CODE_INDEX_SCHEMA["name"] == "code_index"
        props = CODE_INDEX_SCHEMA["parameters"]["properties"]
        assert "project_root" in props
        assert "operation" in props
        assert props["operation"]["enum"] == ["build", "status", "clear"]


class TestExtractSymbols:
    def test_python_symbols(self):
        from tools.code_index import _extract_symbols
        content = "class Foo:\n    def bar(self):\n        pass\ndef baz():\n    pass"
        symbols = _extract_symbols(content, "python")
        names = [s["name"] for s in symbols if s["type"] in ("class", "function")]
        assert "Foo" in names
        assert "baz" in names

    def test_ts_symbols(self):
        from tools.code_index import _extract_symbols
        content = "interface User {}\nfunction greet() {}\nconst x = 1"
        symbols = _extract_symbols(content, "typescript")
        names = [s["name"] for s in symbols]
        assert "User" in names
        assert "greet" in names

    def test_go_symbols(self):
        from tools.code_index import _extract_symbols
        content = "func Hello() {}\ntype Config struct {}\nconst MaxValue = 100"
        symbols = _extract_symbols(content, "go")
        names = [s["name"] for s in symbols]
        assert "Hello" in names

    def test_rust_symbols(self):
        from tools.code_index import _extract_symbols
        content = "fn hello() {}\nstruct Config {}"
        symbols = _extract_symbols(content, "rust")
        names = [s["name"] for s in symbols]
        assert "hello" in names

    def test_detect_language(self):
        from tools.code_index import _detect_language
        assert _detect_language("test.py") == "python"
        assert _detect_language("test.ts") == "typescript"
        assert _detect_language("test.js") == "javascript"
        assert _detect_language("test.go") == "go"
        assert _detect_language("test.rs") == "rust"
        assert _detect_language("test.unknown") == "unknown"