#!/usr/bin/env python3
"""Train the reasoning effort predictor from synthetic data.

Generates labeled (message, effort_level) pairs using heuristic rules,
trains a DecisionTree classifier, and saves to ~/.hermes/models/reasoning_effort.pkl.

Usage:
    python scripts/train_reasoning_classifier.py [--count 600] [--output PATH]

Requirements:
    pip install scikit-learn
"""

import argparse
import json
import logging
import pickle
import random
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

HERMES_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(HERMES_ROOT))


# --- Effort label: 0=low, 1=medium, 2=high ---

LOW_TEMPLATES = [
    "hello", "hi", "hey", "thanks", "ok", "got it", "yes", "no",
    "what time is it?", "how are you?", "tell me a joke",
    "continue", "go on", "next", "sounds good", "perfect",
    "cool", "nice", "awesome", "sure", "I see",
    "what is GDP?", "define entropy", "what does API stand for?",
    "translate hello to Spanish", "what's 15% of 230?",
    "convert 5 miles to km", "spell check: recieve",
    "summarize this in one line", "who wrote hamlet?",
    "what year was India founded?", "tell me more",
]

MEDIUM_TEMPLATES = [
    "explain how binary search works",
    "what's the difference between TCP and UDP?",
    "write a function to reverse a linked list",
    "how do I set up a virtual environment in Python?",
    "explain the CAP theorem briefly",
    "what are the SOLID principles?",
    "how does OAuth2 work?",
    "what are some good practices for REST API design?",
    "explain the difference between SQL and NoSQL databases",
    "write a regex to match email addresses",
    "how do I use async/await in JavaScript?",
    "what is the time complexity of quicksort?",
    "explain what a decorator does in Python",
    "how do I handle errors in Go?",
    "what's the difference between a process and a thread?",
    "explain how Git branching works",
    "how do I create a Docker container?",
    "what stocks are trending today?",
    "show me the NIFTY chart",
    "what is the current PE ratio of TCS?",
    "search for recent news about RBI policy",
    "fetch the weather forecast for Mumbai",
]

HIGH_TEMPLATES = [
    "debug this traceback: TypeError in auth middleware processing JWT tokens",
    "implement a rate limiter using the token bucket algorithm with Redis backend",
    "design the database schema for a multi-tenant SaaS application",
    "review this code for security vulnerabilities and suggest fixes",
    "analyze the time complexity of this recursive algorithm and optimize it",
    "refactor this 500-line function into testable modules",
    "compare event-driven vs request-response architecture for notifications",
    "plan the migration from monolith to microservices for our payment system",
    "investigate why the CI tests fail intermittently in Docker but pass locally",
    "build a WebSocket server handling multiple chat rooms with authentication",
    "analyze RELIANCE.NS technical indicators — RSI, MACD, Bollinger Bands for Q3",
    "compare FII and DII flows for the last quarter and explain sectoral rotation",
    "run fundamental analysis on TCS.NS including PE, PB, ROE, and earnings growth",
    "create a comprehensive test plan for the payment processing module",
    "set up a cron job that monitors RSS feeds and alerts on market-moving news",
    "write tests for the auth module, then refactor the session handling code",
    "optimize this SQL query with proper indexing: SELECT u.*, COUNT(o.id)...",
    "benchmark three sorting implementations and explain the performance differences",
    "design a portfolio allocation model balancing large-cap and mid-cap stocks",
    "plan and implement real-time notification system with WebSocket support",
]


def _generate_variations(templates, target_count):
    """Generate variations to reach target count."""
    messages = list(templates)
    while len(messages) < target_count:
        template = random.choice(templates)
        msg = template
        if random.random() < 0.3:
            msg = msg.lower()
        if random.random() < 0.2 and not msg.endswith((".", "!", "?")):
            msg += random.choice([".", "!", "?", ""])
        messages.append(msg)
    return messages[:target_count]


def generate_dataset(count=600):
    """Generate balanced synthetic dataset for reasoning effort classification."""
    per_class = count // 3
    remainder = count - per_class * 3

    low_msgs = _generate_variations(LOW_TEMPLATES, per_class)
    medium_msgs = _generate_variations(MEDIUM_TEMPLATES, per_class)
    high_msgs = _generate_variations(HIGH_TEMPLATES, per_class + remainder)

    dataset = []
    for msg in low_msgs:
        depth = random.choice([0, 0, 1])
        dataset.append({"message": msg, "label": 0, "conversation_depth": depth})
    for msg in medium_msgs:
        depth = random.choice([0, 1, 2, 3])
        dataset.append({"message": msg, "label": 1, "conversation_depth": depth})
    for msg in high_msgs:
        depth = random.choice([0, 1, 2, 3, 4, 5])
        dataset.append({"message": msg, "label": 2, "conversation_depth": depth})

    random.shuffle(dataset)
    return dataset


def main():
    parser = argparse.ArgumentParser(description="Train reasoning effort classifier")
    parser.add_argument("--count", type=int, default=600,
                        help="Total examples to generate (default: 600)")
    parser.add_argument("--output", type=str, default=None,
                        help="Output .pkl path (default: ~/.hermes/models/reasoning_effort.pkl)")
    parser.add_argument("--test-size", type=float, default=0.2,
                        help="Fraction for testing (default: 0.2)")
    parser.add_argument("--seed", type=int, default=42,
                        help="Random seed (default: 42)")
    args = parser.parse_args()

    random.seed(args.seed)

    try:
        from sklearn.tree import DecisionTreeClassifier
        from sklearn.model_selection import train_test_split
        from sklearn.metrics import classification_report
        import numpy as np
    except ImportError:
        logger.error("scikit-learn is required: pip install scikit-learn")
        sys.exit(1)

    from hermes_constants import get_hermes_home
    from agent.routing_features import extract_features, features_to_array, feature_names

    dataset = generate_dataset(args.count)

    X = []
    y = []
    for item in dataset:
        features = extract_features(item["message"], item.get("conversation_depth", 0))
        X.append(features_to_array(features))
        y.append(item["label"])

    X = np.array(X)
    y = np.array(y)

    names = feature_names()
    class_names = ["low", "medium", "high"]

    n_low = int((y == 0).sum())
    n_med = int((y == 1).sum())
    n_high = int((y == 2).sum())
    logger.info("Class balance: low=%d, medium=%d, high=%d", n_low, n_med, n_high)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=args.test_size, random_state=args.seed, stratify=y,
    )

    model = DecisionTreeClassifier(
        max_depth=5,
        class_weight="balanced",
        random_state=args.seed,
    )
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    logger.info("\nClassification Report:")
    logger.info(classification_report(y_test, y_pred, target_names=class_names))

    # Feature importances
    logger.info("Feature Importances:")
    for name, imp in sorted(zip(names, model.feature_importances_), key=lambda x: x[1], reverse=True):
        if imp > 0.01:
            logger.info("  %-25s %.4f", name, imp)

    # Calibrate override threshold
    test_proba = model.predict_proba(X_test)
    best_threshold = 0.80
    for candidate in [0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90]:
        max_probs = np.max(test_proba, axis=1)
        confident_mask = max_probs >= candidate
        if confident_mask.sum() == 0:
            continue
        confident_accuracy = (y_pred[confident_mask] == y_test[confident_mask]).mean()
        coverage = confident_mask.mean()
        logger.info("  threshold=%.2f  accuracy=%.3f  coverage=%.3f", candidate, confident_accuracy, coverage)
        if confident_accuracy >= 0.90 and coverage > 0.10:
            best_threshold = candidate
            break

    logger.info("Selected override threshold: %.2f", best_threshold)

    # Save model
    output_path = Path(args.output) if args.output else get_hermes_home() / "models" / "reasoning_effort.pkl"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "wb") as f:
        pickle.dump(model, f)
    logger.info("\nModel saved to %s", output_path)

    # Save metadata
    meta_path = output_path.with_suffix(".json")
    meta = {
        "training_samples": len(X_train),
        "test_samples": len(X_test),
        "override_threshold": best_threshold,
        "feature_names": names,
        "accuracy": float((y_pred == y_test).mean()),
        "class_balance": {"low": n_low, "medium": n_med, "high": n_high},
    }
    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=2)
    logger.info("Metadata saved to %s", meta_path)


if __name__ == "__main__":
    main()
