#!/usr/bin/env python3
"""
Savarez rebranding script.
Changes all user-facing Savarez branding to Savarez across the codebase.
"""
import os
import re
import glob

SAVAREZ_ROOT = "/root/savarez"

BRAND_MAP = [
    # (old_text, new_text)
    # User-facing strings only — NOT internal identifiers
    ("Savarez AI Agent", "Savarez AI Agent"),
    ("Savarez AI agent", "Savarez AI agent"),
    ("savarez agent", "savarez agent"),
    ("Savarez Gateway", "Savarez Gateway"),
    ("savarez gateway", "savarez gateway"),
    ("Savarez Service", "Savarez Service"),
    ("savarez.service", "savarez.service"),
    ("savarez systemd service", "savarez systemd service"),
    # Config paths
    ("~/.savarez/", "~/.savarez/"),
    ("~/.savarez", "~/.savarez"),
    ("$HOME/.savarez", "$HOME/.savarez"),
    ("SAVAREZ_HOME", "SAVAREZ_HOME"),  # env var name
    # CLI commands in docs / help strings only
    ("`savarez`", "`savarez`"),
    # CLI usage examples
    ("savarez setup", "savarez setup"),
    ("savarez model", "savarez model"),
    ("savarez doctor", "savarez doctor"),
    ("savarez config", "savarez config"),
    ("savarez chat", "savarez chat"),
    ("savarez auth", "savarez auth"),
    ("savarez cron", "savarez cron"),
    ("savarez gateway", "savarez gateway"),
    ("savarez dashboard", "savarez dashboard"),
    ("savarez update", "savarez update"),
    ("savarez uninstall", "savarez uninstall"),
    ("savarez status", "savarez status"),
    ("savarez tools", "savarez tools"),
    ("savarez skills", "savarez skills"),
    ("savarez sessions", "savarez sessions"),
    ("savarez profile", "savarez profile"),
    ("savarez webhook", "savarez webhook"),
    ("savarez plugins", "savarez plugins"),
    ("savarez mcp", "savarez mcp"),
    ("savarez logs", "savarez logs"),
    ("savarez send", "savarez send"),
    ("savarez --help", "savarez --help"),
    ("savarez --version", "savarez --version"),
    # Banner / branding in code comments
    ("# Savarez AI Agent", "# Savarez AI Agent"),
    ("\"\"\"Savarez AI Agent", "\"\"\"Savarez AI Agent"),
    ("Savarez AI Agent", "Savarez AI Agent"),
    ("Savarez is a", "Savarez is a"),
    ("The Savarez", "The Savarez"),
    # NOTE: We do NOT rename hermes_cli (Python package) because that would break imports.
]

EXCLUDE_DIRS = {'.git', '__pycache__', 'node_modules', '.venv', 'venv', 'dist', 'build', '.next', 'out'}

def should_skip(path):
    parts = path.split('/')
    for p in parts:
        if p in EXCLUDE_DIRS:
            return True
    return False

def rebrand_file(filepath):
    if should_skip(filepath):
        return 0
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
    except:
        return 0
    
    # Only process text files
    if '\0' in content:
        return 0
    
    original = content
    count = 0
    
    # Apply brand replacements
    for old, new in BRAND_MAP:
        if old in content:
            content = content.replace(old, new)
            count += 1
    
    if content != original:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
    return count

def main():
    total_changes = 0
    total_files = 0
    
    for root, dirs, files in os.walk(SAVAREZ_ROOT):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        for fname in files:
            fpath = os.path.join(root, fname)
            changes = rebrand_file(fpath)
            if changes > 0:
                total_changes += changes
                total_files += 1
                print(f"[{changes:3d}] {os.path.relpath(fpath, SAVAREZ_ROOT)}")
    
    print(f"\nTotal: {total_files} files modified, {total_changes} replacements")

if __name__ == "__main__":
    main()
