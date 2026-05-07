import os
import json
from pathlib import Path
from eclose.perception.base import BasePerceptionAgent
from eclose.events.events import PerceptionSource


class ProjectPerceptionAgent(BasePerceptionAgent):
    """Perception agent that understands the user's project environment."""

    def __init__(self, project_path: str = None):
        super().__init__(name="ProjectPerception", source=PerceptionSource.PROJECT)
        self.project_path = project_path or os.getcwd()

    async def _感知(self) -> dict:
        """Perceive project structure, tech stack, and user behavior."""
        return {
            "project_path": self.project_path,
            "tech_stack": self._detect_tech_stack(),
            "structure": self._analyze_structure(),
            "recent_tasks": self._get_recent_tasks(),
            "patterns": self._detect_patterns(),
        }

    def _detect_tech_stack(self) -> dict:
        """Detect technology stack from project files."""
        tech_stack = {"languages": [], "frameworks": [], "dependencies": []}
        project_root = Path(self.project_path)

        # Detect language from file extensions
        for ext in ["*.py", "*.ts", "*.js", "*.go", "*.rs"]:
            files = list(project_root.rglob(ext))
            if files:
                lang = ext[2:]  # Remove *
                if lang == "ts":
                    lang = "TypeScript"
                elif lang == "js":
                    lang = "JavaScript"
                tech_stack["languages"].append(lang)

        # Detect frameworks from dependencies
        dep_files = [
            project_root / "requirements.txt",
            project_root / "pyproject.toml",
            project_root / "package.json",
            project_root / "go.mod",
        ]
        for dep_file in dep_files:
            if dep_file.exists():
                if dep_file.name == "pyproject.toml":
                    tech_stack["frameworks"].append("Python")
                elif dep_file.name == "package.json":
                    tech_stack["frameworks"].append("Node.js")

        return tech_stack

    def _analyze_structure(self) -> dict:
        """Analyze project directory structure."""
        project_root = Path(self.project_path)
        structure = {
            "has_tests": bool(list(project_root.rglob("test_*.py"))),
            "has_docs": bool(list(project_root.rglob("docs"))),
            "has_readme": (project_root / "README.md").exists(),
            "module_count": len(list(project_root.rglob("__init__.py"))),
        }
        return structure

    def _get_recent_tasks(self) -> list[dict]:
        """Get recent task patterns from hermes history."""
        # TODO: Integrate with hermes_state.py for session history
        return []

    def _detect_patterns(self) -> dict:
        """Detect working patterns from project."""
        return {
            "git_commits": self._count_git_commits(),
        }

    def _count_git_commits(self) -> int:
        """Count recent git commits."""
        import subprocess
        try:
            result = subprocess.run(
                ["git", "rev-list", "--count", "HEAD"],
                cwd=self.project_path,
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                return int(result.stdout.strip())
        except Exception:
            pass
        return 0