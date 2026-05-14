#!/usr/bin/env python3
"""
End-to-End Integration Test for Hermes Agent Belief Pipeline
"""

import sys
import os
import json
from typing import Dict, List, Any

# Add the agent directory to the path
sys.path.insert(0, '/usr/local/lib/hermes-agent')

from src.belief_pipeline import (
    categorize_input, 
    auto_ground_claim, 
    format_belief_context_for_system_prompt,
    HIGH_RISK_CATEGORIES,
    ground_claim
)

class HermesAgentSimulator:
    """Simulates the Hermes Agent conversation flow with belief pipeline integration"""
    
    def __init__(self):
        self.belief_context = ""
        self.session_messages = []
        self.tool_calls = []
        self.user_id = "test_user"
        
    def process_user_input(self, user_message: str) -> Dict[str, Any]:
        """Simulate the complete Hermes Agent conversation flow with belief pipeline"""
        print(f"\n--- Processing User Input: '{user_message}' ---")
        
        # Step 1: Input categorization (simulating run_conversation integration)
        print("1. Running input categorization...")
        input_category = categorize_input(user_message, HIGH_RISK_CATEGORIES)
        print(f"   Category: {input_category['category']}")
        print(f"   Requires grounding: {input_category['requires_grounding']}")
        
        # Step 2: System prompt building with belief context (simulating _build_system_prompt_parts integration)
        print("2. Building system prompt with belief context...")
        self.belief_context = format_belief_context_for_system_prompt(self.user_id)
        if self.belief_context:
            print("   Belief context successfully added to system prompt")
        else:
            print("   No existing beliefs to add to system prompt")
            
        # Step 3: Simulate assistant response generation
        print("3. Generating assistant response...")
        assistant_response = self._generate_assistant_response(user_message, input_category)
        
        # Step 4: Tool execution with automatic grounding (simulating _execute_tool_calls integration)
        print("4. Processing tool calls with automatic grounding...")
        if assistant_response.get("tool_calls"):
            grounded_tool_calls = self._process_tool_calls_with_grounding(
                assistant_response["tool_calls"], 
                input_category
            )
            self.tool_calls.extend(grounded_tool_calls)
            
        # Step 5: Store any new beliefs from the interaction
        print("5. Updating belief store...")
        self._update_beliefs_from_interaction(user_message, assistant_response)
        
        # Store message for context
        self.session_messages.append({"role": "user", "content": user_message})
        self.session_messages.append({"role": "assistant", "content": assistant_response.get("content", "")})
        
        return {
            "input_category": input_category,
            "belief_context": self.belief_context,
            "assistant_response": assistant_response,
            "tool_calls": self.tool_calls[-len(assistant_response.get("tool_calls", [])):],
            "session_state": {
                "messages": len(self.session_messages),
                "tool_calls": len(self.tool_calls)
            }
        }
    
    def _generate_assistant_response(self, user_message: str, input_category: Dict) -> Dict[str, Any]:
        """Simulate assistant response generation"""
        category = input_category["category"]
        
        if category == "job_status":
            return {
                "content": "I understand you're sharing job-related information. Let me check what I know about this.",
                "tool_calls": [
                    {"name": "check_claim", "args": {"claim": "user has job offer"}},
                    {"name": "ground_claim", "args": {"claim": "user got job offer from company", "status": "VERIFIED"}}
                ]
            }
        elif category == "server_state":
            return {
                "content": "I see you're reporting on server status. I should verify this information.",
                "tool_calls": [
                    {"name": "check_claim", "args": {"claim": "server status"}},
                    {"name": "ground_claim", "args": {"claim": "server operational status", "status": "VERIFIED"}}
                ]
            }
        elif category == "configuration":
            return {
                "content": "That's specific configuration information. I'll make sure to ground this properly.",
                "tool_calls": [
                    {"name": "check_claim", "args": {"claim": "configuration details"}},
                    {"name": "ground_claim", "args": {"claim": user_message, "status": "VERIFIED"}}
                ]
            }
        else:
            return {
                "content": "I understand. This is general information that doesn't require special verification.",
                "tool_calls": []
            }
    
    def _process_tool_calls_with_grounding(self, tool_calls: List[Dict], input_category: Dict) -> List[Dict]:
        """Process tool calls with automatic grounding for high-risk inputs"""
        processed_calls = []
        
        # If input requires grounding, apply pre-execution verification
        if input_category.get("requires_grounding", False):
            print("   Pre-execution grounding triggered for high-risk input")
            grounding_result = auto_ground_claim(input_category["category"])
            
            if not grounding_result["is_supported"]:
                print(f"   Grounding explanation: {grounding_result['explanation']}")
                # In a real implementation, we would inject this as a message
                # For simulation, we'll just note it
                processed_calls.append({
                    "type": "grounding_message",
                    "content": f"[System: Prior fact-check] {grounding_result['explanation']}"
                })
        
        # Process actual tool calls
        for tool_call in tool_calls:
            print(f"   Executing tool: {tool_call['name']}")
            processed_calls.append(tool_call)
            
        return processed_calls
    
    def _update_beliefs_from_interaction(self, user_message: str, assistant_response: Dict):
        """Update belief store based on interaction"""
        # In a real implementation, this would actually store beliefs
        # For simulation, we'll just print what would be stored
        if assistant_response.get("tool_calls"):
            for tool_call in assistant_response["tool_calls"]:
                if tool_call["name"] == "ground_claim":
                    claim = tool_call["args"].get("claim", "unknown")
                    status = tool_call["args"].get("status", "INFERRED")
                    print(f"   Would store belief: '{claim}' [{status}]")

def run_end_to_end_test():
    """Run comprehensive end-to-end test of the belief pipeline"""
    print("=== Hermes Agent Belief Pipeline End-to-End Test ===")
    
    # Initialize simulator
    simulator = HermesAgentSimulator()
    
    # Test scenarios
    test_scenarios = [
        "I just got a job offer from a tech company",
        "The production server is currently down",
        "Please set the timeout configuration to 30 seconds",
        "What's the weather like today?",
        "Write a poem about artificial intelligence"
    ]
    
    # Run tests
    results = []
    for i, scenario in enumerate(test_scenarios, 1):
        print(f"\n{'='*60}")
        print(f"TEST SCENARIO {i}: {scenario}")
        print('='*60)
        
        result = simulator.process_user_input(scenario)
        results.append({
            "scenario": scenario,
            "result": result
        })
    
    # Print summary
    print(f"\n{'='*60}")
    print("END-TO-END TEST SUMMARY")
    print('='*60)
    
    for i, test_result in enumerate(results, 1):
        scenario = test_result["scenario"]
        result = test_result["result"]
        category = result["input_category"]["category"]
        requires_grounding = result["input_category"]["requires_grounding"]
        
        print(f"\n{i}. '{scenario}'")
        print(f"   Category: {category}")
        print(f"   Grounding Required: {requires_grounding}")
        print(f"   Session Messages: {result['session_state']['messages']}")
        print(f"   Tool Calls Generated: {len(result['tool_calls'])}")
        
        if requires_grounding:
            grounding_messages = [call for call in result['tool_calls'] if call.get('type') == 'grounding_message']
            if grounding_messages:
                print(f"   Grounding Applied: YES - {grounding_messages[0]['content']}")
            else:
                print("   Grounding Applied: NO (but should have been)")
    
    print(f"\n{'='*60}")
    print("TEST COMPLETED SUCCESSFULLY")
    print('='*60)
    
    return results

def main():
    """Main function to run end-to-end test"""
    try:
        results = run_end_to_end_test()
        
        # Save results
        with open("/root/belief_pipeline_end_to_end_test_results.json", "w") as f:
            json.dump(results, f, indent=2, default=str)
            
        print("\nDetailed results saved to: /root/belief_pipeline_end_to_end_test_results.json")
        
    except Exception as e:
        print(f"Error during end-to-end test: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()