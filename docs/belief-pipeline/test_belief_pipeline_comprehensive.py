#!/usr/bin/env python3
"""
Multi-Agent Review System for Hermes Agent Belief Pipeline
"""

import sys
import os
import json
import subprocess
from typing import Dict, List, Any

# Add the agent directory to the path
sys.path.insert(0, '/usr/local/lib/hermes-agent')

from src.belief_pipeline import (
    categorize_input, 
    auto_ground_claim, 
    format_belief_context_for_system_prompt,
    HIGH_RISK_CATEGORIES,
    ground_claim,
    check_claim,
    get_relevant_beliefs
)

class ReviewAgent:
    """Base class for review agents"""
    
    def __init__(self, name: str, focus_area: str):
        self.name = name
        self.focus_area = focus_area
        self.findings = []
        self.concerns = []
        
    def add_finding(self, finding: str):
        """Add a finding to the agent's report"""
        self.findings.append(finding)
        
    def add_concern(self, concern: str):
        """Add a concern to the agent's report"""
        self.concerns.append(concern)
        
    def generate_report(self) -> Dict[str, Any]:
        """Generate the agent's report"""
        return {
            "agent_name": self.name,
            "focus_area": self.focus_area,
            "findings": self.findings,
            "concerns": self.concerns,
            "overall_assessment": self._assess_overall()
        }
        
    def _assess_overall(self) -> str:
        """Generate overall assessment based on findings and concerns"""
        if len(self.concerns) == 0:
            return "PASS"
        elif len(self.concerns) <= 2:
            return "WARNING"
        else:
            return "FAIL"

class InputCategorizationAgent(ReviewAgent):
    """Agent to review input categorization accuracy"""
    
    def __init__(self):
        super().__init__("Input Categorization Agent", "Input Classification Accuracy")
        
    def review(self, test_scenarios: List[Dict]):
        """Review input categorization for test scenarios"""
        self.add_finding("Testing input categorization for various scenarios")
        
        for scenario in test_scenarios:
            input_text = scenario["input"]
            expected_category = scenario["expected_category"]
            requires_grounding = scenario["requires_grounding"]
            
            # Test categorization
            result = categorize_input(input_text, HIGH_RISK_CATEGORIES)
            actual_category = result["category"]
            actual_grounding = result["requires_grounding"]
            
            if actual_category == expected_category:
                self.add_finding(f"✓ Correctly categorized '{input_text}' as {actual_category}")
            else:
                self.add_concern(f"✗ Incorrectly categorized '{input_text}' as {actual_category}, expected {expected_category}")
                
            if actual_grounding == requires_grounding:
                self.add_finding(f"✓ Correct grounding requirement for '{input_text}': {actual_grounding}")
            else:
                self.add_concern(f"✗ Incorrect grounding requirement for '{input_text}': {actual_grounding}, expected {requires_grounding}")

class BeliefStoreAgent(ReviewAgent):
    """Agent to review belief store functionality"""
    
    def __init__(self):
        super().__init__("Belief Store Agent", "SQLite FTS5 Database Functionality")
        
    def review(self):
        """Review belief store operations"""
        self.add_finding("Testing belief store functionality")
        
        # Test storing beliefs
        try:
            belief1 = ground_claim("The server is running normally", "test_user", "tool", status="VERIFIED")
            belief2 = ground_claim("I work at Google", "test_user", "user_statement", status="VERIFIED")
            belief3 = ground_claim("Python is preferred", "test_user", "user_statement", status="INFERRED")
            
            self.add_finding("✓ Successfully stored multiple beliefs with different statuses")
        except Exception as e:
            self.add_concern(f"✗ Failed to store beliefs: {str(e)}")
            return
            
        # Test retrieving beliefs
        try:
            beliefs = get_relevant_beliefs("test_user", limit=10)
            if len(beliefs) >= 3:
                self.add_finding(f"✓ Successfully retrieved {len(beliefs)} beliefs")
            else:
                self.add_concern(f"✗ Only retrieved {len(beliefs)} beliefs, expected at least 3")
        except Exception as e:
            self.add_concern(f"✗ Failed to retrieve beliefs: {str(e)}")
            
        # Test checking claims
        try:
            check_result = check_claim("server is running", "test_user")
            if check_result["status"] in ["VERIFIED", "INFERRED"]:
                self.add_finding("✓ Successfully checked existing claim")
            else:
                self.add_concern("✗ Failed to find existing claim in check")
        except Exception as e:
            self.add_concern(f"✗ Error checking claim: {str(e)}")

class SystemIntegrationAgent(ReviewAgent):
    """Agent to review system integration"""
    
    def __init__(self):
        super().__init__("System Integration Agent", "Hermes Agent Integration")
        
    def review(self):
        """Review system integration"""
        self.add_finding("Testing system integration components")
        
        # Test system prompt injection
        try:
            belief_context = format_belief_context_for_system_prompt("test_user")
            if belief_context and "<belief_context>" in belief_context:
                self.add_finding("✓ Belief context formatting for system prompt working")
            else:
                self.add_concern("✗ Belief context not properly formatted for system prompt")
        except Exception as e:
            self.add_concern(f"✗ Error formatting belief context: {str(e)}")

class GroundingPipelineAgent(ReviewAgent):
    """Agent to review grounding pipeline"""
    
    def __init__(self):
        super().__init__("Grounding Pipeline Agent", "Automatic Claim Grounding")
        
    def review(self, test_scenarios: List[Dict]):
        """Review grounding pipeline for test scenarios"""
        self.add_finding("Testing grounding pipeline functionality")
        
        for scenario in test_scenarios:
            input_text = scenario["input"]
            expected_grounding = scenario["requires_grounding"]
            
            # Test automatic grounding
            try:
                grounding_result = auto_ground_claim(input_text)
                should_ground = not grounding_result["is_supported"]
                
                if should_ground == expected_grounding:
                    self.add_finding(f"✓ Correct grounding decision for '{input_text}': {should_ground}")
                else:
                    self.add_concern(f"✗ Incorrect grounding decision for '{input_text}': {should_ground}, expected {expected_grounding}")
            except Exception as e:
                self.add_concern(f"✗ Error in grounding for '{input_text}': {str(e)}")

class PerformanceAgent(ReviewAgent):
    """Agent to review system performance"""
    
    def __init__(self):
        super().__init__("Performance Agent", "System Performance Metrics")
        
    def review(self):
        """Review performance aspects"""
        self.add_finding("Testing performance characteristics")
        
        # Test import performance
        try:
            import time
            start_time = time.time()
            from src.belief_pipeline import categorize_input
            import_time = time.time() - start_time
            
            if import_time < 1.0:  # Should import in under 1 second
                self.add_finding(f"✓ Module import time acceptable: {import_time:.3f}s")
            else:
                self.add_concern(f"✗ Module import time too slow: {import_time:.3f}s")
        except Exception as e:
            self.add_concern(f"✗ Error testing import performance: {str(e)}")

def create_test_scenarios() -> List[Dict]:
    """Create test scenarios for evaluation"""
    return [
        {
            "input": "I received a job offer from Google",
            "expected_category": "job_status",
            "requires_grounding": True
        },
        {
            "input": "The production server is down",
            "expected_category": "server_state", 
            "requires_grounding": True
        },
        {
            "input": "The database is configured on port 5432",
            "expected_category": "configuration",
            "requires_grounding": True
        },
        {
            "input": "The meeting is on 2026-06-15 at 14:30",
            "expected_category": "specific_numbers",
            "requires_grounding": True
        },
        {
            "input": "Write a poem about technology",
            "expected_category": "general",
            "requires_grounding": False
        },
        {
            "input": "What is the weather today?",
            "expected_category": "general",
            "requires_grounding": False
        }
    ]

def run_comprehensive_review():
    """Run the comprehensive multi-agent review"""
    print("=== Hermes Agent Belief Pipeline Comprehensive Review ===\n")
    
    # Create test scenarios
    test_scenarios = create_test_scenarios()
    
    # Initialize review agents
    agents = [
        InputCategorizationAgent(),
        BeliefStoreAgent(),
        SystemIntegrationAgent(),
        GroundingPipelineAgent(),
        PerformanceAgent()
    ]
    
    # Run reviews
    for agent in agents:
        print(f"Executing review by {agent.name}...")
        if hasattr(agent, 'review'):
            if agent.name == "Input Categorization Agent" or agent.name == "Grounding Pipeline Agent":
                agent.review(test_scenarios)
            else:
                agent.review()
        else:
            agent.add_concern("No review method implemented")
        print(f"Completed review by {agent.name}\n")
    
    # Generate individual reports
    reports = []
    for agent in agents:
        report = agent.generate_report()
        reports.append(report)
        
    # Generate consolidated report
    consolidated = generate_consolidated_report(reports)
    
    return reports, consolidated

def generate_consolidated_report(reports: List[Dict]) -> Dict:
    """Generate a consolidated report from individual agent reports"""
    consolidated = {
        "overall_status": "PASS",
        "total_agents": len(reports),
        "passed_agents": 0,
        "warning_agents": 0,
        "failed_agents": 0,
        "agent_reports": reports,
        "summary": ""
    }
    
    # Count agent statuses
    for report in reports:
        status = report["overall_assessment"]
        if status == "PASS":
            consolidated["passed_agents"] += 1
        elif status == "WARNING":
            consolidated["warning_agents"] += 1
        else:
            consolidated["failed_agents"] += 1
    
    # Determine overall status
    if consolidated["failed_agents"] > 0:
        consolidated["overall_status"] = "FAIL"
    elif consolidated["warning_agents"] > 0:
        consolidated["overall_status"] = "WARNING"
    else:
        consolidated["overall_status"] = "PASS"
        
    # Generate summary
    summary_parts = []
    summary_parts.append(f"Review completed by {consolidated['total_agents']} agents")
    summary_parts.append(f"PASS: {consolidated['passed_agents']} agents")
    summary_parts.append(f"WARNING: {consolidated['warning_agents']} agents")
    summary_parts.append(f"FAIL: {consolidated['failed_agents']} agents")
    summary_parts.append(f"Overall Status: {consolidated['overall_status']}")
    
    consolidated["summary"] = ", ".join(summary_parts)
    
    return consolidated

def main():
    """Main function to run the comprehensive review"""
    try:
        # Run the comprehensive review
        individual_reports, consolidated_report = run_comprehensive_review()
        
        # Display results
        print("=== INDIVIDUAL AGENT REPORTS ===\n")
        for report in individual_reports:
            print(f"Agent: {report['agent_name']}")
            print(f"Focus: {report['focus_area']}")
            print(f"Assessment: {report['overall_assessment']}")
            print("Findings:")
            for finding in report['findings']:
                print(f"  ✓ {finding}")
            if report['concerns']:
                print("Concerns:")
                for concern in report['concerns']:
                    print(f"  ✗ {concern}")
            print()
        
        print("=== CONSOLIDATED REPORT ===\n")
        print(consolidated_report["summary"])
        print()
        
        # Save reports to files
        with open("/root/belief_pipeline_agent_reviews.json", "w") as f:
            json.dump(individual_reports, f, indent=2)
            
        with open("/root/belief_pipeline_consolidated_report.json", "w") as f:
            json.dump(consolidated_report, f, indent=2)
            
        print("Reports saved to:")
        print("  - /root/belief_pipeline_agent_reviews.json")
        print("  - /root/belief_pipeline_consolidated_report.json")
        
    except Exception as e:
        print(f"Error during review: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()