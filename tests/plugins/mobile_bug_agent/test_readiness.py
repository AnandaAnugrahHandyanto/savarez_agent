from __future__ import annotations

from plugins.mobile_bug_agent.config import (
    LinearConfig,
    MonicaConfig,
    ProofConfig,
    RepoConfig,
    SlackConfig,
    VerificationConfig,
)
from plugins.mobile_bug_agent.readiness import check_monica_readiness


def _code_rollout_config() -> MonicaConfig:
    return MonicaConfig(
        enabled=True,
        rollout_mode="local_fix_only",
        slack=SlackConfig(
            bot_user_ids=("U_MONICA",),
            allowed_channels=("D123MONICA",),
            approver_user_ids=("U_APPROVER",),
        ),
        linear=LinearConfig(team_id="team-id"),
        repo=RepoConfig(url="git@github.com:acme/mobile.git"),
        verification=VerificationConfig(commands=("npm test",)),
        proof=ProofConfig(
            enabled=True,
            required_for_done=True,
            commands=("npm run monica:proof",),
            platform_order=("ios",),
        ),
    )


def test_readiness_warns_when_simctl_probe_fails_even_if_xcode_tools_exist():
    report = check_monica_readiness(
        config=_code_rollout_config(),
        environ={
            "MONICA_SLACK_BOT_TOKEN": "xoxb-token",
            "MONICA_SLACK_APP_TOKEN": "xapp-token",
            "LINEAR_API_KEY": "lin-key",
        },
        which=lambda name: f"/usr/bin/{name}",
        module_available=lambda name: True,
        command_succeeds=lambda command: command != ("xcrun", "--find", "simctl"),
    )

    assert report.ready is True
    assert any(issue.code == "ios_proof_tooling" for issue in report.warnings)


def test_readiness_accepts_ios_proof_when_simctl_probe_passes():
    report = check_monica_readiness(
        config=_code_rollout_config(),
        environ={
            "MONICA_SLACK_BOT_TOKEN": "xoxb-token",
            "MONICA_SLACK_APP_TOKEN": "xapp-token",
            "LINEAR_API_KEY": "lin-key",
        },
        which=lambda name: f"/usr/bin/{name}",
        module_available=lambda name: True,
        command_succeeds=lambda _command: True,
    )

    warning_codes = {issue.code for issue in report.warnings}
    assert report.ready is True
    assert "ios_proof_tooling" not in warning_codes
