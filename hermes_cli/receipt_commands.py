"""
Hermes Receipt System - CLI Commands
Integration with Hermes CLI for receipt management.
"""

from typing import Optional, List
from pathlib import Path
import datetime
import json

from hermes_cli.commands import CommandDef, resolve_command
from agent.receipt_system import ReceiptGenerator, ReceiptConfig, generate_receipt_cli


# Register slash commands
RECEIPT_COMMANDS = [
    CommandDef(
        "receipt",
        "Generate receipt for current or specified session",
        "Receipt",
        aliases=["rcpt"],
        usage="[/receipt [session_id]]",
        example="/receipt\n/receipt 20240429_123456_abc123",
    ),
    CommandDef(
        "receipts",
        "List all generated receipts",
        "Receipt",
        aliases=["rcpts"],
        usage="[/receipts [limit]]",
        example="/receipts\n/receipts 10",
    ),
    CommandDef(
        "receipt-cleanup",
        "Clean up old receipt files",
        "Receipt",
        aliases=["rcpt-clean"],
        usage="[/receipt-cleanup [days]]",
        example="/receipt-cleanup 30",
    ),
    CommandDef(
        "receipt-config",
        "Configure receipt system settings",
        "Receipt",
        aliases=["rcpt-config"],
        usage="[/receipt-config [key] [value]]",
        example="/receipt-config\n/receipt-config show_cost false",
    ),
]


class ReceiptCommandHandler:
    """Handler for receipt-related slash commands."""
    
    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or Path.home() / ".hermes" / "receipt_config.yaml"
        self.config = self._load_config()
        self.generator = ReceiptGenerator(config=self.config)
    
    def _load_config(self) -> ReceiptConfig:
        """Load configuration from YAML file."""
        import yaml
        
        if not self.config_path.exists():
            return ReceiptConfig()
        
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config_data = yaml.safe_load(f) or {}
            
            receipt_config = config_data.get('receipt', {})
            
            return ReceiptConfig(
                enabled=receipt_config.get('enabled', True),
                auto_generate=receipt_config.get('auto_generate', True),
                directory=receipt_config.get('directory', '~/.hermes/receipts'),
                retention_days=receipt_config.get('retention_days', 30),
                formats=receipt_config.get('formats', ['json', 'txt']),
                show_cost=receipt_config.get('show_cost', True),
                verbosity=receipt_config.get('verbosity', 'normal'),
            )
        except Exception as e:
            print(f"Warning: Error loading receipt config: {e}")
            return ReceiptConfig()
    
    def _save_config(self):
        """Save configuration to YAML file."""
        import yaml
        
        config_data = {
            'receipt': {
                'enabled': self.config.enabled,
                'auto_generate': self.config.auto_generate,
                'directory': self.config.directory,
                'retention_days': self.config.retention_days,
                'formats': self.config.formats,
                'show_cost': self.config.show_cost,
                'verbosity': self.config.verbosity,
            }
        }
        
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.config_path, 'w', encoding='utf-8') as f:
            yaml.dump(config_data, f, default_flow_style=False)
    
    def handle_receipt(self, args: List[str] = None) -> str:
        """Handle /receipt command."""
        args = args or []
        session_id = args[0] if args else None
        
        if not self.config.enabled:
            return "❌ Receipt system is disabled. Enable it with `/receipt-config enabled true`"
        
        try:
            result = self.generator.generate_for_latest_session()
            if not result:
                return "⚠️ No session data found or receipt generation failed"
            
            json_path, txt_path = result
            
            # Read and display the text summary
            with open(txt_path, 'r', encoding='utf-8') as f:
                summary = f.read()
            
            return f"✅ Receipt generated!\n\n{summary}\n📁 Files saved to:\n  • {json_path}\n  • {txt_path}"
            
        except Exception as e:
            return f"❌ Error generating receipt: {str(e)}"
    
    def handle_receipts(self, args: List[str] = None) -> str:
        """Handle /receipts command."""
        args = args or []
        limit = 20
        if args and args[0].isdigit():
            limit = int(args[0])
        
        if not self.config.enabled:
            return "❌ Receipt system is disabled"
        
        try:
            receipts = self.generator.list_receipts(limit=limit)
            
            if not receipts:
                return "📭 No receipts found"
            
            output = ["📁 Generated Receipts:", ""]
            
            for i, receipt in enumerate(receipts, 1):
                output.append(f"{i}. **{receipt['title']}**")
                output.append(f"   ID: `{receipt['session_id']}`")
                output.append(f"   📊 Tokens: {receipt['tokens']:,}")
                if receipt['cost']:
                    output.append(f"   💰 Cost: ${receipt['cost']:.6f}")
                output.append(f"   🕐 Generated: {receipt['generated_at']}")
                output.append("")
            
            output.append(f"Total: {len(receipts)} receipt(s)")
            
            return "\n".join(output)
            
        except Exception as e:
            return f"❌ Error listing receipts: {str(e)}"
    
    def handle_receipt_cleanup(self, args: List[str] = None) -> str:
        """Handle /receipt-cleanup command."""
        args = args or []
        days = self.config.retention_days
        if args and args[0].isdigit():
            days = int(args[0])
        
        if not self.config.enabled:
            return "❌ Receipt system is disabled"
        
        try:
            deleted = self.generator.cleanup_old_receipts(days)
            
            if deleted == 0:
                return f"🧹 No receipts older than {days} days found"
            else:
                return f"✅ Cleaned up {deleted} receipt file(s) older than {days} days"
            
        except Exception as e:
            return f"❌ Error cleaning up receipts: {str(e)}"
    
    def handle_receipt_config(self, args: List[str] = None) -> str:
        """Handle /receipt-config command."""
        args = args or []
        
        if len(args) == 0:
            # Show current configuration
            config_dict = {
                "enabled": self.config.enabled,
                "auto_generate": self.config.auto_generate,
                "directory": self.config.directory,
                "retention_days": self.config.retention_days,
                "formats": ", ".join(self.config.formats),
                "show_cost": self.config.show_cost,
                "verbosity": self.config.verbosity,
            }
            
            output = ["⚙️ Receipt System Configuration:", ""]
            for key, value in config_dict.items():
                output.append(f"  {key}: `{value}`")
            output.append("")
            output.append("Usage: `/receipt-config <key> <value>`")
            output.append("Example: `/receipt-config show_cost false`")
            
            return "\n".join(output)
        
        elif len(args) == 2:
            # Update configuration
            key, value = args[0], args[1]
            
            # Parse value
            if value.lower() in ['true', 'yes', 'on', '1']:
                parsed_value = True
            elif value.lower() in ['false', 'no', 'off', '0']:
                parsed_value = False
            elif value.isdigit():
                parsed_value = int(value)
            else:
                parsed_value = value
            
            # Update config
            if hasattr(self.config, key):
                old_value = getattr(self.config, key)
                setattr(self.config, key, parsed_value)
                self._save_config()
                
                return f"✅ Updated `{key}`: `{old_value}` → `{parsed_value}`"
            else:
                valid_keys = [attr for attr in dir(self.config) 
                            if not attr.startswith('_') and not callable(getattr(self.config, attr))]
                return f"❌ Invalid key `{key}`. Valid keys: {', '.join(valid_keys)}"
        
        else:
            return "❌ Usage: `/receipt-config` or `/receipt-config <key> <value>`"


# Integration with Hermes CLI
def register_receipt_commands():
    """Register receipt commands with Hermes CLI."""
    # This would be called during Hermes initialization
    pass


def handle_receipt_slash_command(command: str, args: List[str] = None) -> Optional[str]:
    """Handle receipt-related slash commands."""
    handler = ReceiptCommandHandler()
    
    if command in ["receipt", "rcpt"]:
        return handler.handle_receipt(args)
    elif command in ["receipts", "rcpts"]:
        return handler.handle_receipts(args)
    elif command in ["receipt-cleanup", "rcpt-clean"]:
        return handler.handle_receipt_cleanup(args)
    elif command in ["receipt-config", "rcpt-config"]:
        return handler.handle_receipt_config(args)
    
    return None


# Auto-generation hook
def auto_generate_receipt(session_id: Optional[str] = None):
    """Auto-generate receipt at session end if configured."""
    handler = ReceiptCommandHandler()
    
    if not handler.config.enabled or not handler.config.auto_generate:
        return
    
    try:
        result = handler.generator.generate_for_latest_session()
        if result:
            json_path, txt_path = result
            print("\n" + "="*50)
            print("     📄 RECEIPT AUTO-GENERATED")
            print("="*50)
            print(f"Receipt saved to:")
            print(f"  • {txt_path}")
            print("="*50)
    except Exception as e:
        print(f"⚠️ Auto-receipt generation failed: {e}")


# Standalone CLI entry point
def main():
    """Standalone CLI for receipt management."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Hermes Receipt System CLI")
    subparsers = parser.add_subparsers(dest='command', help='Command')
    
    # Generate command
    gen_parser = subparsers.add_parser('generate', help='Generate receipt')
    gen_parser.add_argument('--session-id', help='Specific session ID')
    gen_parser.add_argument('--output-dir', help='Output directory')
    
    # List command
    list_parser = subparsers.add_parser('list', help='List receipts')
    list_parser.add_argument('--limit', type=int, default=20, help='Limit results')
    
    # Cleanup command
    cleanup_parser = subparsers.add_parser('cleanup', help='Cleanup old receipts')
    cleanup_parser.add_argument('--days', type=int, help='Days to keep')
    
    # Config command
    config_parser = subparsers.add_parser('config', help='Configuration')
    config_parser.add_argument('--show', action='store_true', help='Show config')
    config_parser.add_argument('--set', nargs=2, metavar=('KEY', 'VALUE'), help='Set config')
    
    args = parser.parse_args()
    
    handler = ReceiptCommandHandler()
    
    if args.command == 'generate':
        generate_receipt_cli(args.session_id, args.output_dir)
    
    elif args.command == 'list':
        receipts = handler.generator.list_receipts(limit=args.limit)
        for i, receipt in enumerate(receipts, 1):
            print(f"{i}. {receipt['title']}")
            print(f"   ID: {receipt['session_id']}")
            print(f"   Tokens: {receipt['tokens']:,}")
            if receipt['cost']:
                print(f"   Cost: ${receipt['cost']:.6f}")
            print(f"   Generated: {receipt['generated_at']}")
            print()
    
    elif args.command == 'cleanup':
        deleted = handler.generator.cleanup_old_receipts(args.days)
        print(f"Deleted {deleted} old receipt files")
    
    elif args.command == 'config':
        if args.show:
            print("Current configuration:")
            for key in ['enabled', 'auto_generate', 'directory', 'retention_days', 
                       'formats', 'show_cost', 'verbosity']:
                value = getattr(handler.config, key)
                print(f"  {key}: {value}")
        elif args.set:
            key, value = args.set
            if hasattr(handler.config, key):
                setattr(handler.config, key, value)
                handler._save_config()
                print(f"Updated {key} to {value}")
            else:
                print(f"Invalid key: {key}")
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()