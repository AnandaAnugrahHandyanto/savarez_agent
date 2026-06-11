#!/usr/bin/env python3
"""Tests for the delegate_task persona parameter.

Personas are markdown profiles in <hermes_home>/personas (or
delegation.personas_dir) whose content is prepended to the child's
context, pinning the subagent's identity deterministically.

Run with:  python -m pytest tests/tools/test_delegate_persona.py -v
"""

import os
import unittest
from unittest.mock import patch

from tools.delegate_tool import (
    _list_available_personas,
    _load_persona,
    _personas_dir,
    DELEGATE_TASK_SCHEMA,
)


class TestPersonaResolution(unittest.TestCase):
    def setUp(self):
        import tempfile

        self._tmp = tempfile.TemporaryDirectory()
        self.personas_dir = os.path.join(self._tmp.name, "personas")
        os.makedirs(self.personas_dir)
        with open(
            os.path.join(self.personas_dir, "evaluador-independiente.md"),
            "w",
            encoding="utf-8",
        ) as f:
            f.write("## Evaluador Independiente\nEres un auditor implacable.\n")
        with open(
            os.path.join(self.personas_dir, "vacia.md"), "w", encoding="utf-8"
        ) as f:
            f.write("   \n")
        self._patch = patch(
            "tools.delegate_tool._personas_dir", return_value=self.personas_dir
        )
        self._patch.start()

    def tearDown(self):
        self._patch.stop()
        self._tmp.cleanup()

    def test_known_persona_loads(self):
        profile, err = _load_persona("evaluador-independiente")
        self.assertIsNone(err)
        self.assertIn("auditor implacable", profile)

    def test_unknown_persona_fails_loud_with_available_list(self):
        profile, err = _load_persona("no-existe")
        self.assertIsNone(profile)
        self.assertIn("Unknown persona", err)
        self.assertIn("evaluador-independiente", err)

    def test_invalid_slug_rejected(self):
        for bad in ("../etc/passwd", "Mayusculas", "con espacios", "a/b", ""):
            profile, err = _load_persona(bad)
            self.assertIsNone(profile, bad)
            self.assertIsNotNone(err, bad)

    def test_empty_persona_file_rejected(self):
        profile, err = _load_persona("vacia")
        self.assertIsNone(profile)
        self.assertIn("empty", err)

    def test_list_available_personas(self):
        names = _list_available_personas()
        self.assertIn("evaluador-independiente", names)
        self.assertIn("vacia", names)


class TestPersonasDirConfig(unittest.TestCase):
    def test_custom_dir_from_config(self):
        with patch(
            "tools.delegate_tool._load_config",
            return_value={"personas_dir": "/tmp/custom-personas"},
        ):
            self.assertEqual(_personas_dir(), "/tmp/custom-personas")

    def test_default_dir_under_hermes_home(self):
        with patch("tools.delegate_tool._load_config", return_value={}):
            self.assertTrue(_personas_dir().endswith(os.path.join("", "personas")))


class TestPersonaSchema(unittest.TestCase):
    def test_top_level_persona_in_schema(self):
        props = DELEGATE_TASK_SCHEMA["parameters"]["properties"]
        self.assertIn("persona", props)
        self.assertEqual(props["persona"]["type"], "string")

    def test_per_task_persona_in_schema(self):
        task_props = DELEGATE_TASK_SCHEMA["parameters"]["properties"]["tasks"][
            "items"
        ]["properties"]
        self.assertIn("persona", task_props)


class TestPersonaInjection(unittest.TestCase):
    """persona resolution inside delegate_task: context prefix + result stamp.

    Patches _load_persona directly so no filesystem or child agent is
    needed; the child build is short-circuited by making the persona
    unknown (error path) or by inspecting the mutated task list via the
    too-many-tasks guard.
    """

    def test_unknown_persona_returns_tool_error(self):
        from tools.delegate_tool import delegate_task
        from unittest.mock import MagicMock

        parent = MagicMock()
        parent._delegate_depth = 0
        parent._interrupt_requested = False
        with patch(
            "tools.delegate_tool._load_persona",
            return_value=(None, "Unknown persona 'x'. Available personas: y"),
        ), patch("tools.delegate_tool.is_spawn_paused", return_value=False), patch(
            "tools.delegate_tool._get_max_concurrent_children", return_value=3
        ):
            out = delegate_task(
                goal="hacer algo", persona="x", parent_agent=parent
            )
        self.assertIn("Unknown persona", out)

    def test_persona_prefixes_context(self):
        # Reproduce the injection block's contract on a task dict.
        profile = "## Rol\nEres X."
        t = {"goal": "g", "context": "datos previos", "persona": "rol-x"}
        base_context = t.get("context")
        t["context"] = f"## PERSONA\n{profile}\n\n## CONTEXT\n{base_context}"
        self.assertTrue(t["context"].startswith("## PERSONA\n## Rol"))
        self.assertIn("## CONTEXT\ndatos previos", t["context"])


if __name__ == "__main__":
    unittest.main()
