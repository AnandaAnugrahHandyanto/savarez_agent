# Hermes Receipt System Documentation

## 📖 Overview

The Hermes Receipt System automatically generates detailed usage reports after each AI conversation. These "receipts" provide transparency into token usage, cost estimates, and session statistics.

## 🚀 Quick Start

### Enable the Receipt System

```bash
# Method 1: Use the dedicated command
hermes receipt-start

# Method 2: Enable via config
echo 'receipt:\n  enabled: true' >> ~/.hermes/config.yaml
hermes chat
```

### Basic Usage

1. Start a conversation:
   ```bash
   hermes receipt-start
   ```

2. Have your conversation as normal.

3. When you exit, a receipt will be automatically generated:
   ```
   ══════════════════════════════════════════════════════
   🤖 Hermes Session Receipt
   ══════════════════════════════════════════════════════
   📝 Session: Python Code Help
   ⏱️  Duration: 2.1 minutes
   📊 Tokens: Input 1,245 / Output 356 / Total 1,601
   💰 Estimated Cost: $0.0032
   📨 Messages: 8 | 🔧 Tool Calls: 3
   📁 Saved to: ~/.hermes/receipts/receipt_20240429_101525.json
   ```

## 📋 Features

### Automatic Receipt Generation
- ✅ Generates receipts after each conversation
- ✅ No manual intervention required
- ✅ Configurable auto-generation

### Detailed Statistics
- **Token Usage**: Input, output, cache, reasoning tokens
- **Session Info**: Duration, message count, tool calls
- **Cost Estimates**: Based on provider pricing
- **Provider Details**: Model and provider information

### Multiple Formats
- **JSON**: Machine-readable complete data
- **TXT**: Human-readable summary
- **Configurable**: Add custom formats if needed

### Management Tools
- **List receipts**: View all generated receipts
- **Search receipts**: Find receipts by session ID or date
- **Cleanup**: Automatic retention management
- **Configuration**: Flexible settings

## ⚙️ Configuration

### Configuration File
`~/.hermes/config.yaml`:
```yaml
receipt:
  # Basic settings
  enabled: true
  auto_generate: true
  
  # Storage settings
  directory: "~/.hermes/receipts"
  retention_days: 30
  formats: ["json", "txt"]
  
  # Display settings
  show_cost: true
  verbosity: "normal"  # minimal, normal, detailed
  
  # Notification settings
  notifications:
    budget_warning:
      enabled: false
      monthly_limit_usd: 50.0
      warning_percent: 80
```

### Environment Variables
```bash
export HERMES_RECEIPT_ENABLED=true
export HERMES_RECEIPT_DIRECTORY="~/my_receipts"
export HERMES_RECEIPT_RETENTION_DAYS=90
```

## 🛠️ Commands

### Slash Commands (in Hermes chat)
```
/receipt          # Generate receipt for current session
/receipt <id>     # Generate receipt for specific session
/receipts         # List all receipts (default: 20)
/receipts <N>     # List N most recent receipts
/receipt-cleanup  # Clean up old receipts
/receipt-cleanup <days>  # Clean up receipts older than N days
/receipt-config   # Show current configuration
/receipt-config <key> <value>  # Update configuration
```

### CLI Commands
```bash
# Standalone receipt management
hermes-receipt generate [--session-id ID] [--output-dir DIR]
hermes-receipt list [--limit N]
hermes-receipt cleanup [--days N]
hermes-receipt config [--show] [--set KEY VALUE]

# Integrated with Hermes
hermes receipt-start  # Start Hermes with receipt system
hermes --receipt      # Alternative syntax
```

## 📊 Receipt Format

### JSON Format (Complete Data)
```json
{
  "receipt_version": "1.0",
  "generated_at": "2024-04-29T10:15:25.123456",
  "session": {
    "id": "20240429_101525_abc123",
    "title": "Python Code Help",
    "started_at": "2024-04-29T10:10:00.000000",
    "ended_at": "2024-04-29T10:12:06.000000",
    "duration": {
      "seconds": 126.0,
      "minutes": 2.1,
      "formatted": "2.1m"
    }
  },
  "usage": {
    "tokens": {
      "input": 1245,
      "output": 356,
      "total": 1601,
      "cache_read": 0,
      "cache_write": 0,
      "reasoning": 0
    },
    "messages": 8,
    "tool_calls": 3
  },
  "cost": {
    "estimated_usd": 0.0032,
    "actual_usd": null,
    "provider": "openai",
    "model": "gpt-4"
  }
}
```

### Text Format (Human Readable)
```
==================================================
         HERMES AI CONVERSATION RECEIPT
==================================================
Session: Python Code Help
ID: 20240429_101525_abc123
Started: 2024-04-29T10:10:00
Ended: 2024-04-29T10:12:06
Duration: 2.1m
--------------------------------------------------
TOKEN USAGE:
  Input: 1,245
  Output: 356
  Total: 1,601
--------------------------------------------------
COST ESTIMATE:
  Estimated: $0.0032
  Provider: openai
  Model: gpt-4
--------------------------------------------------
ACTIVITY:
  Messages: 8
  Tool calls: 3
==================================================
Receipt generated: 2024-04-29T10:15:25.123456
==================================================
```

## 🔧 Advanced Usage

### Cost Estimation
The system estimates costs based on provider pricing tables. Currently supported:

| Provider | Model | Input (per 1M tokens) | Output (per 1M tokens) |
|----------|-------|----------------------|-----------------------|
| OpenAI | GPT-4 | $30.00 | $60.00 |
| Anthropic | Claude 3 Opus | $15.00 | $75.00 |
| DeepSeek | DeepSeek V3 | $1.00 | $2.00 |

To add custom pricing:
```yaml
receipt:
  custom_pricing:
    my_provider:
      my_model:
        input: 0.00001  # $10 per 1M tokens
        output: 0.00002 # $20 per 1M tokens
```

### Budget Monitoring
```yaml
receipt:
  notifications:
    budget_warning:
      enabled: true
      monthly_limit_usd: 50.0
      warning_percent: 80  # Warn at 80% of limit
      alert_channels:
        - console
        - email
        - webhook
```

### Team Usage Tracking
```bash
# Shared receipt directory
receipt:
  directory: "/shared/team/hermes_receipts"

# User identification
export HERMES_USER_ID="alice@company.com"
```

### Integration with Other Tools
```bash
# Export to CSV for analysis
hermes-receipt list --format csv > receipts.csv

# Send to webhook
hermes-receipt generate --webhook https://hooks.example.com/receipts

# Import into database
hermes-receipt export --database postgresql://user:pass@localhost/hermes
```

## 🧪 Testing

### Unit Tests
```bash
# Run all receipt system tests
pytest tests/test_receipt_system.py -v

# Run specific test categories
pytest tests/test_receipt_system.py::TestReceiptGenerator -v
pytest tests/test_receipt_system.py::TestReceiptCommands -v
```

### Integration Tests
```bash
# Test complete flow
python -m pytest tests/integration/test_receipt_flow.py

# Test with different configurations
python -m pytest tests/integration/test_receipt_config.py
```

### Manual Testing
```bash
# 1. Start Hermes with receipt system
hermes receipt-start

# 2. Have a short conversation
> Hello
< Hi! How can I help you?
> /exit

# 3. Verify receipt was generated
ls ~/.hermes/receipts/
cat ~/.hermes/receipts/latest.txt
```

## 🔍 Troubleshooting

### Common Issues

#### 1. Receipts not generating
```bash
# Check if system is enabled
hermes-receipt config --show | grep enabled

# Check permissions on receipts directory
ls -la ~/.hermes/receipts/

# Check database access
ls -la ~/.hermes/state.db
```

#### 2. Incorrect cost estimates
```bash
# Verify provider and model
hermes-receipt generate --verbose

# Check pricing configuration
cat ~/.hermes/config.yaml | grep -A5 "pricing"

# Manually calculate for comparison
echo "Input: 1000 tokens * $30/1M = $(echo '1000 * 30 / 1000000' | bc -l)"
```

#### 3. Missing session data
```bash
# Check if session exists in database
sqlite3 ~/.hermes/state.db "SELECT id, title FROM sessions ORDER BY started_at DESC LIMIT 5;"

# Check message count
sqlite3 ~/.hermes/state.db "SELECT COUNT(*) FROM messages WHERE session_id = 'YOUR_SESSION_ID';"
```

### Logs
```bash
# View receipt system logs
tail -f ~/.hermes/logs/receipt.log

# Debug mode
HERMES_RECEIPT_DEBUG=1 hermes receipt-start
```

## 📈 Monitoring & Analytics

### Usage Reports
```bash
# Daily summary
hermes-receipt report --period daily --format html

# Monthly cost report
hermes-receipt report --period monthly --format csv

# Custom date range
hermes-receipt report --start 2024-01-01 --end 2024-01-31
```

### Alerting
```yaml
receipt:
  alerts:
    # Cost alerts
    cost_exceeded:
      threshold: 100.0
      channel: email
    
    # Usage spikes
    usage_spike:
      percent_increase: 200
      time_window: 1h
      channel: slack
    
    # Anomaly detection
    anomaly:
      enabled: true
      channel: webhook
```

## 🔌 API Reference

### Python API
```python
from hermes.receipt import ReceiptGenerator, ReceiptConfig

# Create generator
config = ReceiptConfig(enabled=True, directory="/my/receipts")
generator = ReceiptGenerator(config=config)

# Generate receipt
receipt = generator.generate_for_session("session_id_123")

# List receipts
receipts = generator.list_receipts(limit=50)

# Cleanup
deleted = generator.cleanup_old_receipts(days=30)
```

### Webhook API
```bash
# Send receipt to webhook
curl -X POST https://api.example.com/receipts \
  -H "Content-Type: application/json" \
  -d @receipt.json
```

## 🤝 Contributing

### Adding New Features
1. **New Receipt Format**:
   - Add formatter class in `hermes/receipt/formatters/`
   - Register in `ReceiptGenerator._format_receipt()`

2. **New Cost Provider**:
   - Add pricing to `PROVIDER_PRICING` dictionary
   - Implement in `estimate_cost()` method

3. **New Notification Channel**:
   - Create handler in `hermes/receipt/notifications/`
   - Add to configuration schema

### Running Tests
```bash
# Full test suite
pytest tests/ -xvs

# With coverage
pytest tests/ --cov=hermes.receipt --cov-report=html

# Performance tests
pytest tests/performance/test_receipt_performance.py
```

### Code Style
```bash
# Format code
black hermes/receipt/
isort hermes/receipt/

# Lint
flake8 hermes/receipt/
mypy hermes/receipt/
```

## 📄 License

The Hermes Receipt System is part of the Hermes AI Assistant project, licensed under the MIT License.

## 🙏 Acknowledgements

- Thanks to all Hermes contributors
- Inspired by user feedback for cost transparency
- Built on top of Hermes' robust session tracking system

## 📞 Support

- **GitHub Issues**: [Report bugs](https://github.com/NousResearch/hermes-agent/issues)
- **Discord**: Join the [Hermes community](https://discord.gg/hermes-ai)
- **Documentation**: [Read the docs](https://hermes.ai/docs)

---

*Last updated: April 2024*  
*Version: 1.0.0*