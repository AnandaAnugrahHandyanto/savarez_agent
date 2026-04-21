from __future__ import annotations

PROJECT_DIRNAME = "people-manager"
REGISTRY_FILENAME = "registry.json"
REPORTS_DIRNAME = "reports"
TEAM_SNAPSHOTS_DIRNAME = "team-snapshots"
VERSION = 1

RATING_BUCKETS = ("strong", "solid", "uneven", "concerning", "unknown")
TRAJECTORY_VALUES = ("rising", "flat", "declining", "unclear")
SCOPE_FIT_VALUES = ("under-scoped", "well-matched", "over-scoped", "unclear")
CONFIDENCE_VALUES = ("high", "medium", "low")

ACTION_NEW_REPORT = "new_report"
ACTION_UPDATE = "update"
ACTION_ONE_ON_ONE = "one_on_one"
ACTION_ASSESSMENT = "assessment"
ACTION_TODO_REPORT = "todo_report"
ACTION_TODO_MANAGER = "todo_manager"
ACTION_PREP = "prep"
ACTION_RESCHEDULE_ONCE = "reschedule_once"
ACTION_REVIEW = "review"
ACTION_TEAM_SCAN = "team_scan"
ACTION_CHALLENGE = "challenge"
ACTION_TEAM_QUESTION = "team_question"

SUPPORTED_WORKSPACE = "people"
