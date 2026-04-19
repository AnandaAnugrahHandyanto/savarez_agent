#!/usr/bin/env python3
"""
Pre-commit hook helper script to check if test files exist for changed source files.

This script checks if test files exist when source files are modified,
encouraging test-driven development practices.
"""

import subprocess
import sys
from pathlib import Path


def get_changed_files():
    """Get list of staged Python files."""
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"],
        capture_output=True,
        text=True
    )
    return [f for f in result.stdout.strip().split("\n") if f.endswith(".py")]


def find_test_file(source_file: Path) -> Path | None:
    """Find the corresponding test file for a source file."""
    # Map source paths to test paths
    if source_file.name.startswith("test_"):
        return None  # Already a test file
    
    # Common patterns
    test_patterns = [
        # tests/test_<module>.py
        Path("tests") / f"test_{source_file.stem}.py",
        # tests/<module>/test_<function>.py
        Path("tests") / source_file.stem / f"test_{source_file.stem}.py",
        # tests/<parent>/<module>/test_*.py
        Path("tests") / source_file.parent.name / f"test_{source_file.stem}.py",
    ]
    
    # Special mappings for tools
    if "tools/" in str(source_file):
        tool_name = source_file.stem.replace("_tool", "").replace("_tools", "")
        test_patterns.append(Path("tests/tools") / f"test_{tool_name}.py")
        test_patterns.append(Path("tests/tools") / f"test_{source_file.stem}.py")
    
    # Special mappings for gateway
    if "gateway/" in str(source_file):
        test_patterns.append(Path("tests/gateway") / f"test_{source_file.stem}.py")
    
    # Special mappings for agent
    if "agent/" in str(source_file):
        test_patterns.append(Path("tests/agent") / f"test_{source_file.stem}.py")
    
    # Check if any test file exists
    for pattern in test_patterns:
        if pattern.exists():
            return pattern
    
    return None


def main():
    """Main entry point."""
    changed_files = get_changed_files()
    
    if not changed_files:
        print("No Python files changed.")
        return 0
    
    missing_tests = []
    
    for file_path in changed_files:
        # Skip test files, __init__.py, and non-project files
        if (
            file_path.startswith("tests/") or
            "__init__.py" in file_path or
            file_path.startswith("scripts/") or
            file_path.startswith("docs/") or
            "conftest.py" in file_path
        ):
            continue
        
        source_file = Path(file_path)
        if not source_file.exists():
            continue
        
        test_file = find_test_file(source_file)
        if test_file is None:
            missing_tests.append((file_path, None))
    
    if missing_tests:
        print("\n⚠️  Warning: Some changed source files may be missing tests:")
        print("=" * 60)
        for source, test in missing_tests:
            print(f"  Source: {source}")
            suggested = f"tests/test_{Path(source).stem}.py"
            print(f"  Suggested test: {suggested}")
            print()
        print("=" * 60)
        print("Consider adding tests for these changes following TDD practices.")
        print("See TESTING.md for guidelines.\n")
        
        # Don't fail the commit, just warn
        return 0
    
    print("✅ All changed source files have corresponding tests.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
