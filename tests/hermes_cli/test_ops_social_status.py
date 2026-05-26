from pathlib import Path

from hermes_cli.ops_social_status import read_social_platform_status


def test_social_platform_status_defaults_when_missing(tmp_path):
    result = read_social_platform_status(tmp_path / "missing.json")

    assert result["ok"] is True
    assert result["mode"] == "local_read_only"
    assert result["warning"] is None
    platforms = {item["platform"]: item for item in result["platforms"]}
    assert platforms["YouTube"]["published"] == "Needs sync"
    assert platforms["TikTok"]["scheduled"] == "0"
    assert platforms["TikTok"]["status"] == "blocked"


def test_social_platform_status_merges_local_snapshot(tmp_path):
    path = tmp_path / "social-platform-status.json"
    path.write_text(
        """
        {
          "updated_at": "2026-05-26T09:30:00+08:00",
          "source": "manual-read-only-sync",
          "platforms": [
            {
              "platform": "YouTube",
              "published": 12,
              "scheduled": 3,
              "issues_private": "1 private review item",
              "status": "ok",
              "source": "YouTube local cache"
            },
            {
              "platform": "Bluesky",
              "published": 4,
              "scheduled": 0,
              "issues_private": "None",
              "status": "ok"
            }
          ]
        }
        """,
        encoding="utf-8",
    )

    result = read_social_platform_status(path)

    assert result["updated_at"] == "2026-05-26T09:30:00+08:00"
    platforms = {item["platform"]: item for item in result["platforms"]}
    assert platforms["YouTube"]["published"] == "12"
    assert platforms["YouTube"]["scheduled"] == "3"
    assert platforms["YouTube"]["issues_private"] == "1 private review item"
    assert platforms["Facebook"]["published"] == "Needs sync"
    assert platforms["Bluesky"]["published"] == "4"


def test_social_platform_status_invalid_json_fails_closed(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text("{not json", encoding="utf-8")

    result = read_social_platform_status(path)

    assert result["ok"] is True
    assert result["warning"]
    assert {item["platform"] for item in result["platforms"]} >= {"YouTube", "Facebook", "Instagram", "TikTok"}
