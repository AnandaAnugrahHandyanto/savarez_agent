from __future__ import annotations

import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import install_penpot_design_to_code_rollout as installer


class PenpotDesignToCodeRolloutTests(unittest.TestCase):
    def read(self, relative: str) -> str:
        return (ROOT / relative).read_text(encoding="utf-8")

    def test_frontend_agent_requires_penpot_reference_and_browser_proof(self) -> None:
        text = self.read("agents/frontend-agent-manager.md")

        for expected in (
            "Penpot",
            "reference screenshot",
            "desktop and mobile",
            "console",
            "visual critique",
            "Animation",
        ):
            self.assertIn(expected, text)

    def test_backend_agent_supports_ui_state_contracts(self) -> None:
        text = self.read("agents/backend-agent-manager.md")

        for expected in (
            "loading, empty, error, partial, stale, long-content, disabled, and success",
            "predictable errors",
            "idempotency",
            "frontend visual",
            "rollback",
        ):
            self.assertIn(expected, text)

    def test_penpot_runbook_contains_mcp_safety_gates(self) -> None:
        text = self.read("docs/runbooks/penpot-design-to-code.md")

        for expected in (
            "Remote MCP",
            "http://localhost:4401/mcp",
            "scripts/start_penpot_mcp.ps1",
            "npx -y @penpot/mcp@stable",
            "read-only",
            "Do not commit MCP keys",
            "Flex/Grid",
            "CSS-friendly token names",
            "intended-change summary",
        ):
            self.assertIn(expected, text)

    def test_visual_qa_runbook_blocks_code_only_ui_completion(self) -> None:
        text = self.read("docs/runbooks/frontend-visual-qa.md")

        for expected in (
            "desktop",
            "mobile",
            "console",
            "keyboard",
            "accessibility",
            "screenshot comparison",
            "Do not report UI ready from code inspection alone",
        ):
            self.assertIn(expected, text)

    def test_coding_routing_covers_design_backend_and_blue_boundaries(self) -> None:
        text = self.read("docs/runbooks/coding-agent-routing.md")

        for expected in (
            "Penpot",
            "Route concept/reference work to frontend-eng",
            "Route data/API contract work to backend-eng",
            "backend contract, frontend implementation, and visual QA",
            "Blue/GHL customer-facing behavior remains under Blue/GHL doctrine",
        ):
            self.assertIn(expected, text)

    def test_verification_script_reports_without_installing(self) -> None:
        tmp = ROOT / "tmp" / "tests" / "penpot-tooling-check"
        if tmp.exists():
            shutil.rmtree(tmp)
        tmp.mkdir(parents=True)
        (tmp / "components.json").write_text(json.dumps({"style": "default"}), encoding="utf-8")

        result = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "check_penpot_frontend_tooling.py"),
                "--project",
                str(tmp),
                "--json",
            ],
            check=True,
            capture_output=True,
            text=True,
        )

        report = json.loads(result.stdout)
        self.assertIn("node", report["checks"])
        self.assertIn("npm", report["checks"])
        self.assertEqual(report["checks"]["shadcn"]["status"], "present")
        self.assertFalse(report["mutates"])
        self.assertIn("does not install packages", " ".join(report["guidance"]))
        self.assertIn("scripts/start_penpot_mcp.ps1", " ".join(report["guidance"]))

    def test_live_skill_installer_copies_references_and_patches_skills(self) -> None:
        home = ROOT / "tmp" / "tests" / "penpot-installer-home"
        if home.exists():
            shutil.rmtree(home)

        skill_paths = [
            home / "skills/software-development/coding-agent-routing/SKILL.md",
            home / "profiles/backend-eng/skills/software-development/coding-agent-routing/SKILL.md",
            home / "profiles/frontend-eng/skills/software-development/coding-agent-routing/SKILL.md",
            home / "profiles/coder/skills/software-development/coding-agent-routing/SKILL.md",
            home / "skills/software-development/frontend-engineer/SKILL.md",
            home / "profiles/frontend-eng/skills/software-development/frontend-engineer/SKILL.md",
            home / "skills/software-development/backend-engineer/SKILL.md",
            home / "profiles/backend-eng/skills/software-development/backend-engineer/SKILL.md",
        ]
        for path in skill_paths:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("# Skill\n\nExisting body.\n", encoding="utf-8")

        result = installer.install(ROOT, home)

        self.assertEqual(result["status"], "installed")
        self.assertTrue(
            (
                home
                / "skills/autonomous-ai-agents/hermes-agent/references/penpot-design-to-code.md"
            ).is_file()
        )
        self.assertIn(
            "Penpot Design-To-Code Routing",
            (home / "skills/software-development/coding-agent-routing/SKILL.md").read_text(
                encoding="utf-8"
            ),
        )
        self.assertIn(
            "Penpot Design-To-Code Lane",
            (home / "skills/software-development/frontend-engineer/SKILL.md").read_text(
                encoding="utf-8"
            ),
        )
        self.assertIn(
            "Backend-For-Frontend Lane",
            (home / "skills/software-development/backend-engineer/SKILL.md").read_text(
                encoding="utf-8"
            ),
        )

    def test_penpot_mcp_launcher_keeps_runner_isolated_and_no_token_storage(self) -> None:
        text = self.read("scripts/start_penpot_mcp.ps1")

        self.assertIn("tmp\\penpot-mcp-runner", text)
        self.assertIn("@penpot/mcp@stable", text)
        self.assertIn("esbuild: true", text)
        self.assertIn("sharp: true", text)
        self.assertIn("corepack pnpm", text)
        self.assertIn("http://localhost:4401/mcp", text)
        self.assertNotIn("userToken", text)


if __name__ == "__main__":
    unittest.main()
