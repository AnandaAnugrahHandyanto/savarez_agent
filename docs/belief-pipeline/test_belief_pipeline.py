#!/usr/bin/env python3
"""
Test script for Hermes Agent Belief Pipeline
"""

import sys
import os

# Add the agent directory to the path
sys.path.insert(0, '/usr/local/lib/hermes-agent')

from src.belief_pipeline import (
    categorize_input, 
    auto_ground_claim, 
    format_belief_context_for_system_prompt,
    HIGH_RISK_CATEGORIES,
    ground_claim
)

def test_belief_pipeline():
    print("=== Hermes Agent Belief Pipeline Test ===\n")
    
    # Test 1: Input categorization
    print("1. Testing input categorization:")
    test_inputs = [
        "I got a job offer from Google",
        "The server is running on port 8080",
        "My preference is to use Python for this project",
        "The meeting is scheduled for 2026-05-15 at 14:30",
        "Just a general question about documentation"
    ]
    
    for user_input in test_inputs:
        result = categorize_input(user_input, HIGH_RISK_CATEGORIES)
        print(f"  Input: '{user_input}'")
        print(f"  Category: {result['category']}")
        print(f"  Requires grounding: {result['requires_grounding']}")
        print()
    
    # Test 2: Auto grounding
    print("2. Testing auto grounding:")
    for user_input in test_inputs[:3]:  # Test first 3 inputs
        result = auto_ground_claim(user_input)
        print(f"  Input: '{user_input}'")
        print(f"  Grounding result: {result}")
        print()
    
    # Test 3: Add some beliefs to the store
    print("3. Adding sample beliefs to store:")
    sample_beliefs = [
        ("I work as a software engineer at Google", "VERIFIED", "user_statement"),
        ("The server status is operational", "VERIFIED", "tool"),
        ("Python is the preferred programming language", "INFERRED", "user_statement")
    ]
    
    for claim, status, source_type in sample_beliefs:
        belief = ground_claim(claim, "test_user", source_type, status=status)
        print(f"  Added belief: {claim} [{status}]")
    
    print()
    
    # Test 4: Check beliefs
    print("4. Checking beliefs in system prompt format:")
    belief_context = format_belief_context_for_system_prompt("test_user")
    if belief_context:
        print(belief_context)
    else:
        print("  No beliefs found")
    
    print("\n=== Test Complete ===")

if __name__ == "__main__":
    test_belief_pipeline()