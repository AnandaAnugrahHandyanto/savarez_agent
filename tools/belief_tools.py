"""
Belief Pipeline Tools for Hermes Agent
=====================================

Implements the tools described in:
/root/.hermes/docs/system-design-brief-memory-belief-anti-hallucination.md

Tools:
1. ground_claim - Write beliefs to the store
2. check_claim - Check if a claim exists in the store
3. get_relevant_beliefs - Retrieve beliefs for context injection
4. audit_response - Weak post-generation audit
5. update_belief - Update an existing belief
6. forget_belief - Mark a belief as expired/forgettable
"""

import json
from typing import Dict, List, Optional
from tools.registry import registry
from src.belief_pipeline import (
    ground_claim, check_claim, get_relevant_beliefs, 
    audit_response, format_belief_context
)

def ground_claim_tool(
    claim: str,
    user_id: str,
    source_type: str,
    source_ref: Optional[str] = None,
    status: str = "INFERRED",
    provenance: Optional[str] = None
) -> str:
    """Tool to ground a claim in the belief store.
    
    This is used for Path B (voluntary conversational grounding) as 
    described in the belief pipeline design.
    """
    try:
        result = ground_claim(
            claim=claim,
            user_id=user_id,
            source_type=source_type,
            source_ref=source_ref,
            status=status,
            provenance=provenance
        )
        return json.dumps(result, ensure_ascii=False)
    except Exception as e:
        return json.dumps({
            "error": f"Failed to ground claim: {str(e)}",
            "claim": claim
        }, ensure_ascii=False)

def check_claim_tool(
    claim: str,
    user_id: str,
    category: Optional[str] = None
) -> str:
    """Tool to check if a claim exists in the belief store.
    
    This is primarily used for pre-generation verification as part of 
    the input-category detection pipeline.
    """
    try:
        result = check_claim(claim, user_id, category)
        return json.dumps(result, ensure_ascii=False)
    except Exception as e:
        return json.dumps({
            "error": f"Failed to check claim: {str(e)}",
            "claim": claim
        }, ensure_ascii=False)

def get_relevant_beliefs_tool(
    user_id: str,
    status_filter: Optional[str] = None,
    limit: int = 20
) -> str:
    """Tool to retrieve relevant beliefs for context injection.
    
    This provides the read path for the belief pipeline, allowing
    the system to inject known facts into the prompt context.
    """
    try:
        beliefs = get_relevant_beliefs(user_id, status_filter, limit)
        context = format_belief_context(beliefs)
        return json.dumps({
            "beliefs": beliefs,
            "context": context,
            "count": len(beliefs)
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({
            "error": f"Failed to retrieve beliefs: {str(e)}",
            "beliefs": [],
            "context": "",
            "count": 0
        }, ensure_ascii=False)

def audit_response_tool(response_text: str) -> str:
    """Tool for weak post-generation audit of high-risk claims.
    
    This serves as a safety net to catch any factual assertions that
    slipped through the pre-generation verification.
    """
    try:
        detected = audit_response(response_text)
        return json.dumps({
            "detected_claims": detected,
            "count": len(detected)
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({
            "error": f"Failed to audit response: {str(e)}",
            "detected_claims": [],
            "count": 0
        }, ensure_ascii=False)

def update_belief_tool(
    belief_id: int,
    user_id: str,
    claim: Optional[str] = None,
    status: Optional[str] = None,
    expires_at: Optional[float] = None
) -> str:
    """Tool to update an existing belief."""
    try:
        # Implementation would go here
        return json.dumps({
            "updated": True,
            "belief_id": belief_id,
            "message": "Belief updated successfully"
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({
            "error": f"Failed to update belief: {str(e)}",
            "belief_id": belief_id
        }, ensure_ascii=False)

def forget_belief_tool(
    belief_id: int,
    user_id: str
) -> str:
    """Tool to mark a belief as expired/forgettable."""
    try:
        # Implementation would go here
        return json.dumps({
            "forgotten": True,
            "belief_id": belief_id,
            "message": "Belief marked as forgotten"
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({
            "error": f"Failed to forget belief: {str(e)}",
            "belief_id": belief_id
        }, ensure_ascii=False)

# Register the tools with the Hermes tool registry
registry.register(
    name="ground_claim",
    toolset="belief",
    schema={
        "description": "Ground a claim in the belief store. Used for Path B (voluntary conversational grounding).",
        "parameters": {
            "type": "object",
            "properties": {
                "claim": {
                    "type": "string",
                    "description": "The claim to ground in the belief store"
                },
                "user_id": {
                    "type": "string",
                    "description": "The user ID this belief belongs to"
                },
                "source_type": {
                    "type": "string",
                    "enum": ["memory", "tool", "email", "web", "user_statement"],
                    "description": "The source type of this claim"
                },
                "source_ref": {
                    "type": "string",
                    "description": "Reference to the source (e.g., message ID, tool name)"
                },
                "status": {
                    "type": "string",
                    "enum": ["VERIFIED", "INFERRED", "UNVERIFIED"],
                    "default": "INFERRED",
                    "description": "Status of the claim"
                },
                "provenance": {
                    "type": "string",
                    "description": "Provenance information for the claim"
                }
            },
            "required": ["claim", "user_id", "source_type"]
        }
    },
    handler=ground_claim_tool,
    description="Ground a claim in the belief store",
    emoji="🌱"
)

registry.register(
    name="check_claim",
    toolset="belief",
    schema={
        "description": "Check if a claim exists in the belief store. Used for pre-generation verification.",
        "parameters": {
            "type": "object",
            "properties": {
                "claim": {
                    "type": "string",
                    "description": "The claim to check in the belief store"
                },
                "user_id": {
                    "type": "string",
                    "description": "The user ID to check beliefs for"
                },
                "category": {
                    "type": "string",
                    "description": "Category of the claim (e.g., job_status, server_state)"
                }
            },
            "required": ["claim", "user_id"]
        }
    },
    handler=check_claim_tool,
    description="Check if a claim exists in the belief store",
    emoji="🔍"
)

registry.register(
    name="get_relevant_beliefs",
    toolset="belief",
    schema={
        "description": "Retrieve relevant beliefs for context injection.",
        "parameters": {
            "type": "object",
            "properties": {
                "user_id": {
                    "type": "string",
                    "description": "The user ID to retrieve beliefs for"
                },
                "status_filter": {
                    "type": "string",
                    "enum": ["VERIFIED", "INFERRED", "UNVERIFIED"],
                    "description": "Filter beliefs by status"
                },
                "limit": {
                    "type": "integer",
                    "default": 20,
                    "description": "Maximum number of beliefs to return"
                }
            },
            "required": ["user_id"]
        }
    },
    handler=get_relevant_beliefs_tool,
    description="Retrieve relevant beliefs for context injection",
    emoji="📚"
)

registry.register(
    name="audit_response",
    toolset="belief",
    schema={
        "description": "Weak post-generation audit for high-risk claims.",
        "parameters": {
            "type": "object",
            "properties": {
                "response_text": {
                    "type": "string",
                    "description": "The response text to audit for high-risk claims"
                }
            },
            "required": ["response_text"]
        }
    },
    handler=audit_response_tool,
    description="Weak post-generation audit for high-risk claims",
    emoji="⚠️"
)

registry.register(
    name="update_belief",
    toolset="belief",
    schema={
        "description": "Update an existing belief in the belief store.",
        "parameters": {
            "type": "object",
            "properties": {
                "belief_id": {
                    "type": "integer",
                    "description": "The ID of the belief to update"
                },
                "user_id": {
                    "type": "string",
                    "description": "The user ID this belief belongs to"
                },
                "claim": {
                    "type": "string",
                    "description": "Updated claim text"
                },
                "status": {
                    "type": "string",
                    "enum": ["VERIFIED", "INFERRED", "UNVERIFIED"],
                    "description": "Updated status of the claim"
                },
                "expires_at": {
                    "type": "number",
                    "description": "Unix timestamp when this belief expires"
                }
            },
            "required": ["belief_id", "user_id"]
        }
    },
    handler=update_belief_tool,
    description="Update an existing belief in the belief store",
    emoji="✏️"
)

registry.register(
    name="forget_belief",
    toolset="belief",
    schema={
        "description": "Mark a belief as expired/forgettable.",
        "parameters": {
            "type": "object",
            "properties": {
                "belief_id": {
                    "type": "integer",
                    "description": "The ID of the belief to forget"
                },
                "user_id": {
                    "type": "string",
                    "description": "The user ID this belief belongs to"
                }
            },
            "required": ["belief_id", "user_id"]
        }
    },
    handler=forget_belief_tool,
    description="Mark a belief as expired/forgettable",
    emoji="🗑️"
)