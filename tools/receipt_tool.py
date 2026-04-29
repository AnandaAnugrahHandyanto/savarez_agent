"""
Receipt Tool for Hermes
Provides tool interface for receipt generation.
"""

from typing import Optional
import json
from pathlib import Path

from ..agent.receipt_system import ReceiptGenerator, ReceiptConfig


class ReceiptTool:
    """Tool for generating conversation receipts."""
    
    name = "generate_receipt"
    description = "Generate a receipt for the current or specified session"
    parameters = {
        "type": "object",
        "properties": {
            "session_id": {
                "type": "string",
                "description": "Optional session ID (defaults to latest session)"
            },
            "output_dir": {
                "type": "string",
                "description": "Optional output directory"
            }
        }
    }
    
    def __init__(self):
        self.config = ReceiptConfig()
        self.generator = ReceiptGenerator(config=self.config)
    
    def run(self, session_id: Optional[str] = None, output_dir: Optional[str] = None):
        """Generate a receipt."""
        if output_dir:
            self.config.directory = output_dir
            self.generator = ReceiptGenerator(config=self.config)
        
        result = self.generator.generate_for_latest_session()
        
        if not result:
            return {"error": "No session data found or generation failed"}
        
        json_path, txt_path = result
        
        # Read the text summary
        with open(txt_path, 'r', encoding='utf-8') as f:
            summary = f.read()
        
        return {
            "success": True,
            "summary": summary,
            "files": {
                "json": str(json_path),
                "text": str(txt_path)
            }
        }


# Tool registration
def register_tool(tool_registry):
    """Register the receipt tool."""
    tool_registry.register(ReceiptTool())
