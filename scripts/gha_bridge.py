#!/usr/bin/env python3
import os
import json
import subprocess
import sys
from pathlib import Path

def run_hermes_command(command_parts, env):
    print(f"--- Running Hermes: {' '.join(command_parts)} ---")
    # Pass custom env to subprocess
    result = subprocess.run(command_parts, capture_output=True, text=True, env=env)
    return result

def main():
    # 1. Environment Detection
    event_name = os.environ.get("GITHUB_EVENT_NAME")
    event_path = os.environ.get("GITHUB_EVENT_PATH")
    workspace = os.environ.get("GITHUB_WORKSPACE", ".")

    if not event_path or not os.path.exists(event_path):
        print("Error: GITHUB_EVENT_PATH not set or file missing. This script should run within GitHub Actions.")
        sys.exit(1)

    # 2. Parse Event Payload
    with open(event_path, "r") as f:
        event_payload = json.load(f)

    query = ""
    if event_name == "issue_comment":
        query = event_payload.get("comment", {}).get("body", "")
    elif event_name == "issues":
        # Check if it's a new issue or edited
        query = event_payload.get("issue", {}).get("body", "")
        if not query:
            query = event_payload.get("issue", {}).get("title", "")
    elif event_name == "pull_request":
        # Focus on PR title/body for the query
        pr = event_payload.get("pull_request", {})
        query = f"{pr.get('title', '')}\n\n{pr.get('body', '')}"
    elif event_name == "workflow_dispatch":
        query = event_payload.get("inputs", {}).get("query", "")

    if not query:
        print(f"No actionable query found in event: {event_name}")
        sys.exit(0)

    print(f"Detected Event: {event_name}")
    print(f"Query: {query[:100]}..." if len(query) > 100 else f"Query: {query}")

    # 3. Prepare Environment
    # Use workspace-local .hermes for easy caching
    hermes_home = Path(workspace) / ".hermes"
    hermes_home.mkdir(parents=True, exist_ok=True)

    current_env = os.environ.copy()
    current_env["HERMES_HOME"] = str(hermes_home)
    current_env["HERMES_YOLO_MODE"] = "1"
    current_env["HERMES_INTERACTIVE"] = "0"
    current_env["PYTHONUNBUFFERED"] = "1"

    # 4. Execution
    # Note: We assume 'hermes' command is available (installed in previous step of workflow)
    # We use 'chat' command in quiet mode to get direct output
    cmd = ["hermes", "chat", query, "--quiet"]

    # Dry run check (useful for testing the bridge itself)
    if os.environ.get("HERMES_BRIDGE_DRY_RUN") == "1":
        print("[DRY RUN] Would execute command.")
        print(f"Env HERMES_HOME: {current_env['HERMES_HOME']}")
        sys.exit(0)

    result = run_hermes_command(cmd, current_env)

    # 5. Output Handling
    if result.returncode != 0:
        print("--- Hermes Execution Error ---")
        print(result.stderr)
        sys.exit(result.returncode)

    print("--- Hermes Response ---")
    print(result.stdout)

    # Optional: If we want to post back to the issue/PR,
    # we would need to use GITHUB_TOKEN and GitHub API here.
    # For now, we print to stdout which GHA captures in logs.

if __name__ == "__main__":
    main()
