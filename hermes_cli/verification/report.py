from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

CheckStatus = Literal["passed", "failed", "partial", "not_run"]
ReportStatus = Literal["passed", "failed", "partial", "not_run"]


@dataclass
class VerificationArtifact:
    kind: str
    path: str
    description: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class VerificationCheck:
    name: str
    kind: str
    status: CheckStatus
    command: str | None = None
    exit_code: int | None = None
    duration_seconds: float | None = None
    stdout_tail: str | None = None
    stderr_tail: str | None = None
    message: str | None = None
    artifacts: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class VerificationReport:
    repo: str
    task_type: str | None = None
    branch: str | None = None
    sha: str | None = None
    dirty: bool | None = None
    changed_files: list[str] = field(default_factory=list)
    checks: list[VerificationCheck] = field(default_factory=list)
    artifacts: list[VerificationArtifact] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @property
    def status(self) -> ReportStatus:
        if not self.checks:
            return "not_run"
        statuses = {check.status for check in self.checks}
        if "failed" in statuses:
            return "failed"
        if statuses & {"partial", "not_run"}:
            return "partial"
        if self.limitations:
            return "partial"
        return "passed"

    def add_check(self, check: VerificationCheck) -> None:
        self.checks.append(check)

    def add_artifact(self, artifact: VerificationArtifact) -> None:
        self.artifacts.append(artifact)

    def add_limitation(self, limitation: str) -> None:
        if limitation not in self.limitations:
            self.limitations.append(limitation)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "repo": self.repo,
            "task_type": self.task_type,
            "branch": self.branch,
            "sha": self.sha,
            "dirty": self.dirty,
            "changed_files": self.changed_files,
            "generated_at": self.generated_at,
            "checks": [check.to_dict() for check in self.checks],
            "artifacts": [artifact.to_dict() for artifact in self.artifacts],
            "limitations": self.limitations,
        }

    def to_markdown(self) -> str:
        lines = [
            "# Verification Report",
            "",
            f"Status: {self.status}",
            f"Repo: `{self.repo}`",
        ]
        if self.task_type:
            lines.append(f"Task type: `{self.task_type}`")
        if self.branch or self.sha:
            lines.append(f"Git: `{self.branch or 'unknown'}` @ `{self.sha or 'unknown'}`")
        if self.dirty is not None:
            lines.append(f"Dirty: {str(self.dirty).lower()}")
        if self.changed_files:
            lines.extend(["", "## Changed files", ""])
            lines.extend(f"- `{path}`" for path in self.changed_files)
        if self.checks:
            lines.extend(["", "## Checks", ""])
            for check in self.checks:
                detail = f"- {check.status}: {check.name} ({check.kind})"
                if check.command:
                    detail += f" — `{check.command}`"
                if check.exit_code is not None:
                    detail += f" exit={check.exit_code}"
                if check.message:
                    detail += f" — {check.message}"
                lines.append(detail)
        if self.artifacts:
            lines.extend(["", "## Artifacts", ""])
            for artifact in self.artifacts:
                desc = f" — {artifact.description}" if artifact.description else ""
                lines.append(f"- {artifact.kind}: `{artifact.path}`{desc}")
        if self.limitations:
            lines.extend(["", "## Limitations", ""])
            lines.extend(f"- {limitation}" for limitation in self.limitations)
        lines.append("")
        return "\n".join(lines)
