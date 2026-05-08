"""Tests for feishu_doc_tool and feishu_drive_tool — registration and schema validation."""

import importlib
import unittest
from unittest.mock import patch

from tools.registry import registry

# Trigger tool discovery so feishu tools get registered
feishu_doc_tool = importlib.import_module("tools.feishu_doc_tool")
feishu_drive_tool = importlib.import_module("tools.feishu_drive_tool")


class TestFeishuToolRegistration(unittest.TestCase):
    """Verify feishu tools are registered and have valid schemas."""

    EXPECTED_TOOLS = {
        "feishu_doc_read": "feishu_doc",
        "feishu_drive_list_comments": "feishu_drive",
        "feishu_drive_list_comment_replies": "feishu_drive",
        "feishu_drive_reply_comment": "feishu_drive",
        "feishu_drive_add_comment": "feishu_drive",
    }

    def test_all_tools_registered(self):
        for tool_name, toolset in self.EXPECTED_TOOLS.items():
            entry = registry.get_entry(tool_name)
            self.assertIsNotNone(entry, f"{tool_name} not registered")
            self.assertEqual(entry.toolset, toolset)

    def test_schemas_have_required_fields(self):
        for tool_name in self.EXPECTED_TOOLS:
            entry = registry.get_entry(tool_name)
            schema = entry.schema
            self.assertIn("name", schema)
            self.assertEqual(schema["name"], tool_name)
            self.assertIn("description", schema)
            self.assertIn("parameters", schema)
            self.assertIn("type", schema["parameters"])
            self.assertEqual(schema["parameters"]["type"], "object")

    def test_handlers_are_callable(self):
        for tool_name in self.EXPECTED_TOOLS:
            entry = registry.get_entry(tool_name)
            self.assertTrue(callable(entry.handler))

    def test_doc_read_schema_params(self):
        entry = registry.get_entry("feishu_doc_read")
        props = entry.schema["parameters"].get("properties", {})
        self.assertIn("doc_token", props)

    def test_drive_tools_require_file_token(self):
        for tool_name in self.EXPECTED_TOOLS:
            if tool_name == "feishu_doc_read":
                continue
            entry = registry.get_entry(tool_name)
            props = entry.schema["parameters"].get("properties", {})
            self.assertIn("file_token", props, f"{tool_name} missing file_token param")
            self.assertIn("file_type", props, f"{tool_name} missing file_type param")

    def test_availability_checks_probe_without_importing_lark_sdk(self):
        def fail_on_lark_import(name, *args, **kwargs):
            if name == "lark_oapi" or name.startswith("lark_oapi."):
                raise AssertionError("availability check must not import lark_oapi")
            return real_import(name, *args, **kwargs)

        real_import = __import__
        with patch("importlib.util.find_spec", return_value=object()):
            with patch("builtins.__import__", side_effect=fail_on_lark_import):
                self.assertTrue(feishu_doc_tool._check_feishu())
                self.assertTrue(feishu_drive_tool._check_feishu())


if __name__ == "__main__":
    unittest.main()
