#!/usr/bin/env python3
"""Check exact text in add_provider warning"""
with open('agent/memory_manager.py') as f:
    content = f.read()
idx = content.find("Rejected memory")
print(repr(content[idx:idx+200]))
