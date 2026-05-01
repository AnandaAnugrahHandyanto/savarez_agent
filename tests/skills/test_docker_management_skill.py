from __future__ import annotations

from pathlib import Path


def test_docker_management_skill_declares_preflight_verification_and_pitfalls():
    skill_path = (
        Path(__file__).resolve().parents[2]
        / "skills"
        / "devops"
        / "docker-management"
        / "SKILL.md"
    )
    text = skill_path.read_text(encoding="utf-8")

    assert "docker info >/dev/null && echo DOCKER_READY || echo DOCKER_UNAVAILABLE" in text
    assert "## Verification" in text
    assert "docker ps -a" in text
    assert "docker compose ps" in text
    assert "docker system df" in text
    assert "## Pitfalls" in text
    assert "docker compose down -v" in text
    assert "docker image prune -a" in text
