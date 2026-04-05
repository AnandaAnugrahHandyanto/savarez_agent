#!/usr/bin/env python3
"""Generate synthetic training data for the routing classifier.

Creates labeled (message, routing_label) pairs using the existing heuristic
rules as ground truth for clear-cut cases, plus hand-crafted boundary examples.
Outputs to ~/.hermes/models/synthetic_routing_data.json.

Usage:
    python scripts/generate_synthetic_routing_data.py [--count 500] [--output PATH]

After generating data, train the model with:
    python scripts/train_routing_classifier.py --from-synthetic
"""

import argparse
import json
import logging
import random
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

HERMES_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(HERMES_ROOT))

# --- Message templates ---

# Messages that should definitely route to the CHEAP model
CHEAP_TEMPLATES = [
    # Greetings
    "hello", "hi", "hey", "hi there", "good morning", "good evening",
    "hey there!", "howdy", "what's up", "sup", "yo",
    # Simple questions
    "what time is it?", "how are you?", "what's the weather like?",
    "what day is today?", "who are you?", "what can you do?",
    "tell me a joke", "thanks", "thank you", "ok", "got it",
    "yes", "no", "sure", "sounds good", "perfect", "great",
    # Simple factual lookups
    "what is the capital of France?",
    "how many continents are there?",
    "what does HTML stand for?",
    "who wrote Romeo and Juliet?",
    "what year did India gain independence?",
    "what is photosynthesis?",
    "define entropy",
    "what is GDP?",
    "explain supply and demand briefly",
    "what is a mutex?",
    "what does API stand for?",
    "what is a REST API?",
    # Short commands
    "translate hello to Spanish",
    "summarize this in one sentence",
    "what's 15% of 230?",
    "convert 5 miles to kilometers",
    "spell check: recieve",
    # Casual conversation
    "I'm bored", "that's interesting", "tell me more",
    "I didn't know that", "cool", "nice", "awesome",
    "what do you think?", "any suggestions?",
    "can you help me?", "I need help",
    # Simple status checks
    "what was the last thing we discussed?",
    "where were we?",
    "continue",
    "go on",
    "next",
]

# Messages that should definitely route to the PRIMARY (strong) model
PRIMARY_TEMPLATES = [
    # Debugging
    "I'm getting a traceback when I run pytest — here's the error: {error}",
    "Debug this error: TypeError: cannot unpack non-sequence NoneType",
    "My app crashes with a segfault when processing large files, help me investigate",
    "The stacktrace shows a null pointer exception in the auth middleware",
    "I'm seeing intermittent failures in CI — the test passes locally but fails in Docker",
    # Implementation
    "Implement a binary search tree with insert, delete, and rebalancing",
    "Write a Python decorator that caches function results with TTL expiry",
    "Create a REST API endpoint for user authentication with JWT tokens",
    "Implement a rate limiter using the token bucket algorithm",
    "Build a WebSocket server that handles multiple chat rooms",
    # Architecture & Design
    "Design the database schema for a multi-tenant SaaS application",
    "Compare event-driven vs request-response architecture for our notification system",
    "Review this architecture and suggest improvements for scalability",
    "How should we structure the microservices to handle 10k requests per second?",
    "Plan the migration from monolith to microservices",
    # Code review & analysis
    "Review this code for security vulnerabilities and performance issues",
    "Analyze this algorithm's time complexity and suggest optimizations",
    "Refactor this 500-line function into smaller, testable units",
    "Benchmark these three sorting implementations and explain the results",
    # Finance analysis (complex)
    "Analyze RELIANCE.NS technical indicators — RSI, MACD, and Bollinger Bands for the last 3 months",
    "Compare FII and DII flows for Q3 and explain the sectoral rotation pattern",
    "Run a fundamental analysis on TCS.NS including PE, PB, ROE, and earnings growth",
    "What's the correlation between NIFTY and crude oil prices over the last year?",
    "Build a portfolio allocation model balancing large-cap and mid-cap Indian stocks",
    "Analyze quarterly earnings for INFY.NS vs WIPRO.NS — who's growing faster?",
    "What does the current RSI and MACD crossover signal for Bank Nifty?",
    # Multi-step tasks
    "Set up a cron job that runs every 4 hours to check RSS feeds and alert on market-moving news",
    "Write tests for the authentication module, then refactor the session handling",
    "Create a Docker compose setup with PostgreSQL, Redis, and the API server",
    # Long-form with code
    """Here's my current code:
```python
def process_data(items):
    results = []
    for item in items:
        if item.get('status') == 'active':
            transformed = transform(item)
            results.append(transformed)
    return results
```
Optimize this for large datasets and add error handling""",
    """I have this SQL query that's slow:
```sql
SELECT u.*, COUNT(o.id) as order_count
FROM users u LEFT JOIN orders o ON u.id = o.user_id
WHERE u.created_at > '2024-01-01'
GROUP BY u.id HAVING COUNT(o.id) > 5
```
Help me optimize it with proper indexing""",
    # Planning & delegation
    "Plan the implementation of a real-time notification system with WebSocket support",
    "Delegate the frontend and backend tasks for the dashboard redesign",
    "Create a test plan for the payment processing module",
]

# Error snippets to inject into templates
ERROR_SNIPPETS = [
    "AttributeError: 'NoneType' object has no attribute 'split'",
    "ConnectionRefusedError: [Errno 111] Connection refused",
    "ImportError: No module named 'missing_package'",
    "KeyError: 'expected_field'",
    "RuntimeError: CUDA out of memory",
    "sqlite3.OperationalError: database is locked",
    "TimeoutError: The read operation timed out",
    "ValueError: invalid literal for int() with base 10: 'abc'",
]


def _generate_variations(templates: list[str], target_count: int) -> list[str]:
    """Generate variations of templates to reach target count."""
    messages = list(templates)

    while len(messages) < target_count:
        template = random.choice(templates)

        # Substitute {error} placeholders
        if "{error}" in template:
            error = random.choice(ERROR_SNIPPETS)
            msg = template.format(error=error)
        else:
            msg = template

        # Random case variation for cheap messages
        if random.random() < 0.3:
            msg = msg.lower()
        elif random.random() < 0.1:
            msg = msg.upper()

        # Random trailing punctuation
        if random.random() < 0.2 and not msg.endswith((".", "!", "?")):
            msg += random.choice([".", "!", "?", ""])

        messages.append(msg)

    return messages[:target_count]


def generate_dataset(count: int = 500) -> list[dict]:
    """Generate a balanced synthetic dataset for routing classification.

    Returns list of {message, label, conversation_depth, source} dicts.
    Label: 1 = safe to route cheap, 0 = needs primary model.
    """
    cheap_count = count // 2
    primary_count = count - cheap_count

    cheap_messages = _generate_variations(CHEAP_TEMPLATES, cheap_count)
    primary_messages = _generate_variations(PRIMARY_TEMPLATES, primary_count)

    dataset = []

    for msg in cheap_messages:
        depth = random.choice([0, 0, 0, 1, 1, 2])
        dataset.append({
            "message": msg,
            "label": 1,
            "conversation_depth": depth,
            "source": "synthetic_cheap",
        })

    for msg in primary_messages:
        depth = random.choice([0, 1, 2, 3, 4, 5])
        dataset.append({
            "message": msg,
            "label": 0,
            "conversation_depth": depth,
            "source": "synthetic_primary",
        })

    random.shuffle(dataset)
    return dataset


def main():
    parser = argparse.ArgumentParser(description="Generate synthetic routing training data")
    parser.add_argument("--count", type=int, default=500,
                        help="Total number of examples to generate (default: 500)")
    parser.add_argument("--output", type=str, default=None,
                        help="Output JSON path (default: ~/.hermes/models/synthetic_routing_data.json)")
    parser.add_argument("--seed", type=int, default=42,
                        help="Random seed for reproducibility (default: 42)")
    args = parser.parse_args()

    random.seed(args.seed)

    from hermes_constants import get_hermes_home

    output_path = Path(args.output) if args.output else get_hermes_home() / "models" / "synthetic_routing_data.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    dataset = generate_dataset(args.count)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(dataset, f, indent=2, ensure_ascii=False)

    cheap_count = sum(1 for d in dataset if d["label"] == 1)
    primary_count = len(dataset) - cheap_count

    logger.info("Generated %d synthetic examples:", len(dataset))
    logger.info("  cheap-safe:     %d", cheap_count)
    logger.info("  needs-primary:  %d", primary_count)
    logger.info("Saved to: %s", output_path)
    logger.info("")
    logger.info("Next step: train the classifier with:")
    logger.info("  python scripts/train_routing_classifier.py --from-synthetic")


if __name__ == "__main__":
    main()
