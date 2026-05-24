from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import coding_profile_dispatch_smoke as smoke


class CodingProfileDispatchSmokeTests(unittest.TestCase):
    def test_profile_strategy_eval_scenarios_are_registered(self) -> None:
        for scenario in (
            "coder-mixed-routing",
            "backend-api-data-quality",
            "frontend-real-app-quality",
            "frontend-critique-quality",
            "backend-real-repo-seeded",
            "coder-real-repo-seeded",
            "frontend-real-repo-seeded",
            "frontend-penpot-reference",
            "backend-for-frontend-contract",
            "coder-penpot-fullstack-routing",
        ):
            with self.subTest(scenario=scenario):
                self.assertIn(scenario, smoke.SCENARIOS)
                self.assertIn("expected_summary", smoke.SCENARIOS[scenario])
                self.assertTrue(smoke.SCENARIOS[scenario]["required_files"])

    def test_new_eval_scenarios_preserve_profile_boundaries(self) -> None:
        self.assertEqual(smoke.SCENARIOS["coder-mixed-routing"]["profile"], "coder")
        self.assertEqual(
            smoke.SCENARIOS["backend-api-data-quality"]["profile"], "backend-eng"
        )
        self.assertEqual(
            smoke.SCENARIOS["frontend-real-app-quality"]["profile"], "frontend-eng"
        )
        self.assertEqual(
            smoke.SCENARIOS["frontend-critique-quality"]["profile"], "frontend-eng"
        )
        self.assertEqual(
            smoke.SCENARIOS["backend-real-repo-seeded"]["profile"], "backend-eng"
        )
        self.assertEqual(
            smoke.SCENARIOS["coder-real-repo-seeded"]["profile"], "coder"
        )
        self.assertEqual(
            smoke.SCENARIOS["frontend-real-repo-seeded"]["profile"], "frontend-eng"
        )
        self.assertEqual(
            smoke.SCENARIOS["frontend-penpot-reference"]["profile"], "frontend-eng"
        )
        self.assertEqual(
            smoke.SCENARIOS["backend-for-frontend-contract"]["profile"], "backend-eng"
        )
        self.assertEqual(
            smoke.SCENARIOS["coder-penpot-fullstack-routing"]["profile"], "coder"
        )
        for scenario in smoke.SCENARIOS.values():
            skills = scenario["skills"]
            self.assertNotIn("blue-ghl-operator", skills)

    def test_real_repo_seeded_eval_has_fixture_files(self) -> None:
        for name in (
            "backend-real-repo-seeded",
            "coder-real-repo-seeded",
            "frontend-real-repo-seeded",
        ):
            with self.subTest(name=name):
                scenario = smoke.SCENARIOS[name]
                self.assertTrue(scenario["verify_in_fixture"])
                self.assertTrue(scenario["fixture_files"])

        self.assertIn(
            "approval_api.py",
            smoke.SCENARIOS["backend-real-repo-seeded"]["fixture_files"],
        )
        self.assertIn(
            "backend/approval_api.py",
            smoke.SCENARIOS["coder-real-repo-seeded"]["fixture_files"],
        )
        self.assertIn(
            "index.html",
            smoke.SCENARIOS["frontend-real-repo-seeded"]["fixture_files"],
        )

    def test_browser_eval_scenarios_define_expected_heading(self) -> None:
        self.assertEqual(
            smoke.SCENARIOS["frontend-browser-quality"]["browser_check"]["heading"],
            "Approval Queue",
        )
        self.assertEqual(
            smoke.SCENARIOS["frontend-real-app-quality"]["browser_check"]["heading"],
            "Approval Workbench",
        )
        self.assertEqual(
            smoke.SCENARIOS["frontend-critique-quality"]["browser_check"]["heading"],
            "Approval Review",
        )
        self.assertEqual(
            smoke.SCENARIOS["frontend-penpot-reference"]["browser_check"]["heading"],
            "Penpot Reference Console",
        )

    def test_penpot_rollout_eval_scenarios_lock_design_and_contract_gates(self) -> None:
        frontend = smoke.SCENARIOS["frontend-penpot-reference"]
        self.assertIn("Penpot reference", frontend["body"])
        self.assertIn("desktop and mobile", frontend["body"])
        self.assertIn("visual QA", frontend["body"])
        self.assertIn("tokens", frontend["body"])

        backend = smoke.SCENARIOS["backend-for-frontend-contract"]
        self.assertIn("loading", backend["body"])
        self.assertIn("empty", backend["body"])
        self.assertIn("error", backend["body"])
        self.assertIn("stale", backend["body"])
        self.assertIn("idempotent", backend["body"])

        mixed = smoke.SCENARIOS["coder-penpot-fullstack-routing"]
        self.assertIn("Penpot concept", mixed["body"])
        self.assertIn("backend contract", mixed["body"])
        self.assertIn("frontend implementation", mixed["body"])
        self.assertIn("Blue/GHL", mixed["body"])

    def test_prepare_kanban_env_isolates_live_task_context(self) -> None:
        old_home = os.environ.get("HERMES_KANBAN_HOME")
        old_task = os.environ.get("HERMES_KANBAN_TASK")
        try:
            os.environ["HERMES_KANBAN_TASK"] = "live-task"

            smoke.prepare_kanban_env(Path("tmp/tests/coding-dispatch-env"), "eval-board")

            self.assertEqual(
                os.environ["HERMES_KANBAN_HOME"],
                str(Path("tmp/tests/coding-dispatch-env")),
            )
            self.assertEqual(os.environ["HERMES_KANBAN_BOARD"], "eval-board")
            self.assertNotIn("HERMES_KANBAN_TASK", os.environ)
        finally:
            if old_home is None:
                os.environ.pop("HERMES_KANBAN_HOME", None)
            else:
                os.environ["HERMES_KANBAN_HOME"] = old_home
            if old_task is None:
                os.environ.pop("HERMES_KANBAN_TASK", None)
            else:
                os.environ["HERMES_KANBAN_TASK"] = old_task


if __name__ == "__main__":
    unittest.main()
