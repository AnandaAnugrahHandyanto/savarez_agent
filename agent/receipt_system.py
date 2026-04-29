"""
Hermes Receipt System - Core Module
Handles automatic generation of conversation receipts with token usage and cost tracking.
"""

import sqlite3
import json
import datetime
from pathlib import Path
from typing import Dict, Optional, List, Tuple
from dataclasses import dataclass, asdict
import logging

logger = logging.getLogger(__name__)

@dataclass
class SessionStats:
    """Session statistics for receipt generation."""
    session_id: str
    title: str
    started_at: datetime.datetime
    ended_at: Optional[datetime.datetime]
    message_count: int
    tool_call_count: int
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    reasoning_tokens: int = 0
    estimated_cost_usd: Optional[float] = None
    actual_cost_usd: Optional[float] = None
    provider: Optional[str] = None
    model: Optional[str] = None

@dataclass
class ReceiptConfig:
    """Configuration for receipt generation."""
    enabled: bool = True
    auto_generate: bool = True
    directory: str = "~/.hermes/receipts"
    retention_days: int = 30
    formats: List[str] = None
    show_cost: bool = True
    verbosity: str = "normal"  # minimal, normal, detailed
    
    def __post_init__(self):
        if self.formats is None:
            self.formats = ["json", "txt"]

class ReceiptGenerator:
    """Generates receipts from session data."""
    
    # Provider pricing (tokens per USD)
    # These are example rates, should be configurable
    PROVIDER_PRICING = {
        "openai": {
            "gpt-4": {"input": 1/30_000, "output": 1/60_000},  # $30/1M input, $60/1M output
        },
        "anthropic": {
            "claude-3-opus": {"input": 1/15_000, "output": 1/75_000},
        },
        "deepseek": {
            "deepseek-v3": {"input": 1/1_000_000, "output": 1/2_000_000},  # $1/1M input, $0.5/1M output
        }
    }
    
    def __init__(self, db_path: Optional[Path] = None, config: Optional[ReceiptConfig] = None):
        self.db_path = db_path or Path.home() / ".hermes" / "state.db"
        self.config = config or ReceiptConfig()
        self.receipts_dir = Path(self.config.directory).expanduser()
        self.receipts_dir.mkdir(parents=True, exist_ok=True)
    
    def get_session_stats(self, session_id: Optional[str] = None) -> Optional[SessionStats]:
        """Retrieve session statistics from database."""
        if not self.db_path.exists():
            logger.warning(f"Database not found: {self.db_path}")
            return None
        
        try:
            conn = sqlite3.connect(str(self.db_path))
            conn.row_factory = sqlite3.Row
            
            if session_id:
                query = """
                    SELECT * FROM sessions 
                    WHERE id = ?
                """
                params = (session_id,)
            else:
                query = """
                    SELECT * FROM sessions 
                    ORDER BY started_at DESC 
                    LIMIT 1
                """
                params = ()
            
            cursor = conn.execute(query, params)
            row = cursor.fetchone()
            
            if not row:
                return None
            
            # Calculate duration
            started_at = datetime.datetime.fromtimestamp(row['started_at'])
            ended_at = None
            if row['ended_at']:
                ended_at = datetime.datetime.fromtimestamp(row['ended_at'])
            
            # Estimate cost if not already calculated
            estimated_cost = row['estimated_cost_usd']
            if estimated_cost is None and row['billing_provider'] and row['billing_mode']:
                estimated_cost = self.estimate_cost(
                    provider=row['billing_provider'],
                    model=row['billing_mode'],
                    input_tokens=row['input_tokens'] or 0,
                    output_tokens=row['output_tokens'] or 0
                )
            
            stats = SessionStats(
                session_id=row['id'],
                title=row['title'] or "Untitled Session",
                started_at=started_at,
                ended_at=ended_at,
                message_count=row['message_count'] or 0,
                tool_call_count=row['tool_call_count'] or 0,
                input_tokens=row['input_tokens'] or 0,
                output_tokens=row['output_tokens'] or 0,
                cache_read_tokens=row['cache_read_tokens'] or 0,
                cache_write_tokens=row['cache_write_tokens'] or 0,
                reasoning_tokens=row['reasoning_tokens'] or 0,
                estimated_cost_usd=estimated_cost,
                actual_cost_usd=row['actual_cost_usd'],
                provider=row['billing_provider'],
                model=row['billing_mode']
            )
            
            conn.close()
            return stats
            
        except sqlite3.Error as e:
            logger.error(f"Database error: {e}")
            return None
    
    def estimate_cost(self, provider: str, model: str, input_tokens: int, output_tokens: int) -> Optional[float]:
        """Estimate cost based on provider pricing."""
        if not provider or not model:
            return None
        
        provider_lower = provider.lower()
        model_lower = model.lower()
        
        # Find matching pricing
        for prov_key, models in self.PROVIDER_PRICING.items():
            if prov_key in provider_lower:
                for model_key, rates in models.items():
                    if model_key in model_lower:
                        input_cost = input_tokens * rates.get("input", 0)
                        output_cost = output_tokens * rates.get("output", 0)
                        return input_cost + output_cost
        
        # Default fallback: $0.001 per 1K tokens
        return (input_tokens + output_tokens) * 0.001 / 1000
    
    def generate_receipt(self, stats: SessionStats) -> Dict:
        """Generate receipt data from session statistics."""
        if not stats:
            return {}
        
        # Calculate duration
        duration = None
        if stats.ended_at:
            duration_seconds = (stats.ended_at - stats.started_at).total_seconds()
            duration = {
                "seconds": duration_seconds,
                "minutes": round(duration_seconds / 60, 1),
                "formatted": self._format_duration(duration_seconds)
            }
        
        # Prepare receipt data
        receipt = {
            "receipt_version": "1.0",
            "generated_at": datetime.datetime.now().isoformat(),
            "session": {
                "id": stats.session_id,
                "title": stats.title,
                "started_at": stats.started_at.isoformat(),
                "ended_at": stats.ended_at.isoformat() if stats.ended_at else None,
                "duration": duration,
            },
            "usage": {
                "tokens": {
                    "input": stats.input_tokens,
                    "output": stats.output_tokens,
                    "total": stats.input_tokens + stats.output_tokens,
                    "cache_read": stats.cache_read_tokens,
                    "cache_write": stats.cache_write_tokens,
                    "reasoning": stats.reasoning_tokens,
                },
                "messages": stats.message_count,
                "tool_calls": stats.tool_call_count,
            },
            "cost": {
                "estimated_usd": stats.estimated_cost_usd,
                "actual_usd": stats.actual_cost_usd,
                "provider": stats.provider,
                "model": stats.model,
            },
            "metadata": {
                "hermes_version": "1.0.0",  # Should be dynamically retrieved
                "receipt_system_version": "1.0",
            }
        }
        
        return receipt
    
    def save_receipt(self, receipt_data: Dict, session_id: str) -> Tuple[Path, Path]:
        """Save receipt to files."""
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        base_name = f"hermes_receipt_{timestamp}_{session_id[:8]}"
        
        # Save JSON
        json_path = self.receipts_dir / f"{base_name}.json"
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(receipt_data, f, ensure_ascii=False, indent=2)
        
        # Save text summary
        txt_path = self.receipts_dir / f"{base_name}.txt"
        with open(txt_path, 'w', encoding='utf-8') as f:
            f.write(self._format_text_summary(receipt_data))
        
        return json_path, txt_path
    
    def _format_duration(self, seconds: float) -> str:
        """Format duration in human-readable format."""
        if seconds < 60:
            return f"{seconds:.1f}s"
        elif seconds < 3600:
            minutes = seconds / 60
            return f"{minutes:.1f}m"
        else:
            hours = seconds / 3600
            return f"{hours:.1f}h"
    
    def _format_text_summary(self, receipt: Dict) -> str:
        """Format receipt as human-readable text."""
        session = receipt["session"]
        usage = receipt["usage"]
        cost = receipt["cost"]
        
        lines = []
        lines.append("=" * 50)
        lines.append("         HERMES AI CONVERSATION RECEIPT")
        lines.append("=" * 50)
        
        # Session info
        lines.append(f"Session: {session['title']}")
        lines.append(f"ID: {session['id']}")
        lines.append(f"Started: {session['started_at']}")
        if session['ended_at']:
            lines.append(f"Ended: {session['ended_at']}")
        if session['duration']:
            lines.append(f"Duration: {session['duration']['formatted']}")
        
        lines.append("-" * 50)
        
        # Token usage
        tokens = usage["tokens"]
        lines.append("TOKEN USAGE:")
        lines.append(f"  Input: {tokens['input']:,}")
        lines.append(f"  Output: {tokens['output']:,}")
        lines.append(f"  Total: {tokens['total']:,}")
        
        if tokens['cache_read'] > 0:
            lines.append(f"  Cache read: {tokens['cache_read']:,}")
        if tokens['cache_write'] > 0:
            lines.append(f"  Cache write: {tokens['cache_write']:,}")
        if tokens['reasoning'] > 0:
            lines.append(f"  Reasoning: {tokens['reasoning']:,}")
        
        lines.append("-" * 50)
        
        # Cost
        if cost['estimated_usd'] is not None and self.config.show_cost:
            lines.append("COST ESTIMATE:")
            lines.append(f"  Estimated: ${cost['estimated_usd']:.6f}")
            if cost['actual_usd'] is not None:
                lines.append(f"  Actual: ${cost['actual_usd']:.6f}")
            if cost['provider']:
                lines.append(f"  Provider: {cost['provider']}")
            if cost['model']:
                lines.append(f"  Model: {cost['model']}")
            lines.append("-" * 50)
        
        # Activity
        lines.append("ACTIVITY:")
        lines.append(f"  Messages: {usage['messages']}")
        lines.append(f"  Tool calls: {usage['tool_calls']}")
        
        lines.append("=" * 50)
        lines.append(f"Receipt generated: {receipt['generated_at']}")
        lines.append("=" * 50)
        
        return "\n".join(lines)
    
    def generate_for_latest_session(self) -> Optional[Tuple[Path, Path]]:
        """Generate receipt for the latest session."""
        stats = self.get_session_stats()
        if not stats:
            logger.warning("No session data found")
            return None
        
        receipt_data = self.generate_receipt(stats)
        if not receipt_data:
            return None
        
        return self.save_receipt(receipt_data, stats.session_id)
    
    def list_receipts(self, limit: int = 20) -> List[Dict]:
        """List all receipts in the directory."""
        receipts = []
        
        for json_file in sorted(self.receipts_dir.glob("*.json"), reverse=True):
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                receipts.append({
                    "path": str(json_file),
                    "session_id": data["session"]["id"],
                    "title": data["session"]["title"],
                    "generated_at": data["generated_at"],
                    "tokens": data["usage"]["tokens"]["total"],
                    "cost": data["cost"]["estimated_usd"],
                })
                
                if len(receipts) >= limit:
                    break
                    
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning(f"Error reading receipt {json_file}: {e}")
                continue
        
        return receipts
    
    def cleanup_old_receipts(self, days: Optional[int] = None) -> int:
        """Clean up receipts older than specified days."""
        retention_days = days or self.config.retention_days
        cutoff_time = datetime.datetime.now() - datetime.timedelta(days=retention_days)
        
        deleted_count = 0
        
        for file_type in ["*.json", "*.txt"]:
            for file_path in self.receipts_dir.glob(file_type):
                if datetime.datetime.fromtimestamp(file_path.stat().st_mtime) < cutoff_time:
                    try:
                        file_path.unlink()
                        deleted_count += 1
                    except OSError as e:
                        logger.warning(f"Error deleting {file_path}: {e}")
        
        return deleted_count


# CLI integration function
def generate_receipt_cli(session_id: Optional[str] = None, output_dir: Optional[str] = None):
    """CLI entry point for receipt generation."""
    import sys
    
    config = ReceiptConfig()
    if output_dir:
        config.directory = output_dir
    
    generator = ReceiptGenerator(config=config)
    
    if session_id:
        stats = generator.get_session_stats(session_id)
    else:
        stats = generator.get_session_stats()
    
    if not stats:
        print("No session data found")
        sys.exit(1)
    
    receipt_data = generator.generate_receipt(stats)
    json_path, txt_path = generator.save_receipt(receipt_data, stats.session_id)
    
    # Print summary
    print("\n" + "="*50)
    print("     HERMES CONVERSATION RECEIPT")
    print("="*50)
    print(f"📝 Session: {stats.title}")
    
    if stats.ended_at:
        duration = (stats.ended_at - stats.started_at).total_seconds()
        print(f"⏱️  Duration: {generator._format_duration(duration)}")
    
    print(f"\n📊 Token Usage:")
    print(f"   Input: {stats.input_tokens:,}")
    print(f"   Output: {stats.output_tokens:,}")
    print(f"   Total: {stats.input_tokens + stats.output_tokens:,}")
    
    if stats.estimated_cost_usd and config.show_cost:
        print(f"\n💰 Estimated Cost: ${stats.estimated_cost_usd:.6f}")
    
    print(f"\n📨 Messages: {stats.message_count}")
    print(f"🔧 Tool Calls: {stats.tool_call_count}")
    print("="*50)
    
    print(f"\n📁 Receipt saved to:")
    print(f"  JSON: {json_path}")
    print(f"  Text: {txt_path}")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Generate Hermes conversation receipts")
    parser.add_argument("--session-id", help="Specific session ID")
    parser.add_argument("--output-dir", help="Output directory")
    parser.add_argument("--list", action="store_true", help="List all receipts")
    parser.add_argument("--cleanup", type=int, help="Clean up receipts older than N days")
    
    args = parser.parse_args()
    
    if args.list:
        generator = ReceiptGenerator()
        receipts = generator.list_receipts()
        for i, receipt in enumerate(receipts, 1):
            print(f"{i}. {receipt['title']}")
            print(f"   ID: {receipt['session_id']}")
            print(f"   Tokens: {receipt['tokens']:,}")
            if receipt['cost']:
                print(f"   Cost: ${receipt['cost']:.6f}")
            print(f"   Generated: {receipt['generated_at']}")
            print()
    elif args.cleanup:
        generator = ReceiptGenerator()
        deleted = generator.cleanup_old_receipts(args.cleanup)
        print(f"Deleted {deleted} old receipt files")
    else:
        generate_receipt_cli(args.session_id, args.output_dir)