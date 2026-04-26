import sys
from unittest.mock import patch


def test_main_routes_skills_create_arguments():
    import hermes_cli.main as main

    argv = [
        "hermes",
        "skills",
        "create",
        "my-skill",
        "Initial",
        "description",
        "here",
    ]

    with patch.object(sys, "argv", argv), patch("hermes_cli.skills_hub.do_create") as mock_create:
        main.main()

    mock_create.assert_called_once_with("my-skill", "Initial description here")
