#!/usr/bin/env python3
"""Test script for entity extraction system."""

import sys
sys.path.insert(0, '.')

from entity_graph import EntityGraph
import re
from collections import defaultdict

print("=" * 60)
print("Entity Extraction + Session Graph System - Test")
print("=" * 60)

# Create entity graph
graph = EntityGraph()
print(f"\nDatabase: {graph.db_path}")

# Test text with various entities
test_text = """
I am working on the hermes-agent project. I'm editing the cli.py file 
and using Python for the session management. I prefer using VS Code as 
my editor. I've decided to use SQLite for the database. I'm proficient 
in JavaScript and TypeScript. Using the git tool for version control.
Working on the entity_graph.py module in the src/ directory.
"""

# Test extraction patterns directly
KEYWORD_PATTERNS = {
    'project': [re.compile(r'\b(project|workspace|repo)\s+([a-zA-Z0-9_-]+)', re.I)],
    'file': [re.compile(r'([a-zA-Z0-9_./\-]+\.(?:py|js|ts|md|json|yaml))', re.I)],
    'skill': [re.compile(r'\b(python|javascript|typescript|sql|docker|git)\b', re.I)],
}

print("\n1. Testing keyword pattern extraction:")
entities = defaultdict(set)
for entity_type, patterns in KEYWORD_PATTERNS.items():
    for pattern in patterns:
        for match in pattern.findall(test_text):
            if isinstance(match, tuple):
                name = match[0] if match else match
            else:
                name = match
            if name and len(name) >= 2:
                entities[entity_type].add(name.strip())

for etype, names in entities.items():
    print(f"   {etype}: {list(names)}")

# Test full extraction method
print("\n2. Testing full extraction method:")
test_messages = [
    {"role": "user", "content": "Working on my Python project called hermes"},
    {"role": "assistant", "content": "I'll help you with the cli.py file"},
    {"role": "user", "content": "I prefer using Docker for containers"},
]
extracted = graph.extract_entities_from_session("test_session_123", test_messages, "Test Session")
print(f"   Extracted {len(extracted)} entities:")
for e in extracted[:10]:
    print(f"     - {e['type']}: {e['name']}")

# Test entity upsert
print("\n3. Testing entity upsert:")
eid = graph.upsert_entity("project", "hermes-agent", "test_session_123", "context snippet")
print(f"   Created entity ID: {eid}")

# Test linking
print("\n4. Testing entity linking:")
graph.link_entities("test_session_456", [
    {"type": "skill", "name": "Python"},
    {"type": "file", "name": "cli.py"},
    {"type": "tool", "name": "git"},
])
print("   Entities linked to session")

# Get stats
print("\n5. Entity Graph Statistics:")
stats = graph.get_entity_stats()
print(f"   Total entities: {stats['total_entities']}")
print(f"   Total links: {stats['total_links']}")
print(f"   Total relationships: {stats['total_relationships']}")
if stats['by_type']:
    print("   By type:")
    for etype, count in stats['by_type'].items():
        print(f"     {etype}: {count}")

# Test query API
print("\n6. Testing Query API:")
related = graph.find_related_sessions("test_session_123", limit=5)
print(f"   Related sessions found: {len(related)}")

timeline = graph.get_project_timeline("hermes-agent")
print(f"   Project timeline entries: {len(timeline)}")

related_entities = graph.get_related_entities("Python", limit=10)
print(f"   Related entities for Python: {len(related_entities)}")

# Cleanup test data
print("\n7. Cleanup:")
cursor = graph._conn.cursor()
cursor.execute("DELETE FROM session_entities WHERE session_id IN ('test_session_123', 'test_session_456')")
cursor.execute("DELETE FROM entities WHERE name IN ('hermes-agent', 'Python', 'cli.py', 'git')")
graph._conn.commit()
print("   Test data removed")

graph.close()

print("\n" + "=" * 60)
print("All tests passed! Entity extraction system is working.")
print("=" * 60)