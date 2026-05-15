#!/usr/bin/env python3
"""Repair local global-cron branch after a Hermes update.

Responsibilities:
  1. verify repo path
  2. verify current branch is main or a known integration branch
  3. fetch upstream
  4. create/update feature/update-durable-global-cron branch
  5. rebase or merge upstream
  6. detect conflicts and stop
  7. run required tests
  8. if tests pass, print exact install/restart commands
  9. if tests fail, stop without restarting services

Never runs install or restart automatically.
"""
import subprocess
import sys
import os
from pathlib import Path

REPO = Path("/Users/hache/.hermes/hermes-agent")
FEATURE_BRANCH = "feature/update-durable-global-cron"
VENV_PYTHON = str(REPO / "venv" / "bin" / "python")

REQUIRED_PATTERNS = {
    "cron/jobs.py": ["class CronStore", "def global_store", "def list_visible_jobs"],
    "tools/cronjob_tools.py": ["run_as_profile", "scope"],
    "tests/cron/test_global_cron.py": ["test_global_create_requires_run_as_profile"],
}

REQUIRED_TESTS = [
    f"{VENV_PYTHON} -m pytest tests/cron/test_global_cron.py -o addopts= -q",
    f"{VENV_PYTHON} -m pytest tests/tools/test_cronjob_tools.py -o addopts= -q",
    f"{VENV_PYTHON} -m pytest tests/cron -o addopts= -q",
]


def run(cmd, cwd=REPO):
    return subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True)


def die(msg):
    print(f"\nREFUSING TO INSTALL: {msg}", file=sys.stderr)
    print("Active Hermes remains upstream main.", file=sys.stderr)
    sys.exit(1)


def main():
    # 1. Verify repo
    if not (REPO / ".git").exists():
        die(f"Not a git repository: {REPO}")

    # 2. Check branch
    branch = run("git branch --show-current").stdout.strip()
    if branch not in ("main", FEATURE_BRANCH):
        print(f"Current branch: {branch}")
        print(f"Expected: main or {FEATURE_BRANCH}")
        answer = input("Continue anyway? [y/N] ")
        if answer.lower() != "y":
            die(f"Branch {branch} is not main or {FEATURE_BRANCH}")

    # 3. Check clean worktree
    status = run("git status --porcelain").stdout.strip()
    if status:
        print("Untracked/modified files detected:")
        print(status)
        die("Worktree is not clean. Please commit or stash changes first.")

    # 4. Fetch upstream
    print("Fetching upstream...")
    r = run("git fetch origin")
    if r.returncode != 0:
        die(f"Failed to fetch upstream: {r.stderr}")

    # 5. Try rebase
    print(f"Rebasing {FEATURE_BRANCH} onto origin/main...")
    r = run(f"git checkout {FEATURE_BRANCH} 2>/dev/null || git checkout -b {FEATURE_BRANCH}")
    r = run("git rebase origin/main")
    if r.returncode != 0:
        print("\nCONFLICT DETECTED:")
        conflicts = run("git diff --name-only --diff-filter=U").stdout.strip()
        print(conflicts)
        print("\nResolve conflicts, then re-run this script.")
        die(f"Rebase conflicts in: {conflicts}")

    # 6. Verify required symbols
    print("\nVerifying required symbols...")
    missing = []
    for filepath, patterns in REQUIRED_PATTERNS.items():
        fp = REPO / filepath
        if not fp.exists():
            missing.append(f"MISSING FILE: {filepath}")
            continue
        content = fp.read_text()
        for pat in patterns:
            if pat not in content:
                missing.append(f"MISSING: {pat} in {filepath}")
    if missing:
        for m in missing:
            print(f"  {m}")
        die(f"{len(missing)} required symbols missing")

    # 7. Run tests
    print("\nRunning tests...")
    all_passed = True
    for test_cmd in REQUIRED_TESTS:
        print(f"  {test_cmd}")
        r = run(test_cmd)
        if r.returncode != 0:
            all_passed = False
            print(f"  FAILED (exit {r.returncode})")
            # Show last few lines
            for line in r.stdout.strip().split("\n")[-5:]:
                print(f"    {line}")
        else:
            short = [l for l in r.stdout.strip().split("\n") if "passed" in l or "failed" in l]
            if short:
                print(f"    {short[-1]}")

    if not all_passed:
        die("Required tests failed. Active Hermes remains upstream main.")

    # 8. Print install commands
    print("\n" + "="*70)
    print("ALL TESTS PASSED — Safe to install.")
    print("="*70)
    print(f"\nInstall commands:\n")
    print(f"  cd {REPO}")
    print(f"  git checkout {FEATURE_BRANCH}")
    print(f"  {VENV_PYTHON} -m pip install -e .")
    print(f"  hermes gateway restart    # or: launchctl kickstart -k gui/$(id -u)/ai.hermes.gateway-chat_d3c3n")
    print(f"\nVerify:")
    print(f"  hermes --version")
    print(f"  hermes cron list --visible")
    print()


if __name__ == "__main__":
    main()
