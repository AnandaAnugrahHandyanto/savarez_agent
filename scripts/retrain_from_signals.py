#!/usr/bin/env python3
"""Retrain classifiers from accumulated implicit signals.

Checks the implicit_signals table and retrains the routing and reasoning
effort classifiers when enough new signals have accumulated.

Usage:
    python scripts/retrain_from_signals.py [--min-signals 50] [--dry-run]

This can be run as a cron job or post-session hook.
"""

import argparse
import json
import logging
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

HERMES_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(HERMES_ROOT))


def _retrain_routing(signals, existing_synthetic_path: Path):
    """Retrain routing classifier by augmenting synthetic data with real signals."""
    from agent.routing_features import extract_features, features_to_array, feature_names

    try:
        from sklearn.linear_model import LogisticRegression
        from sklearn.model_selection import train_test_split
        from sklearn.metrics import classification_report
        import numpy as np
    except ImportError:
        logger.error("scikit-learn required: pip install scikit-learn")
        return False

    # Load existing synthetic data as base
    X = []
    y = []

    if existing_synthetic_path.exists():
        with open(existing_synthetic_path, "r") as f:
            synthetic = json.load(f)
        for item in synthetic:
            features = extract_features(item["message"], item.get("conversation_depth", 0))
            X.append(features_to_array(features))
            y.append(item["label"])
        logger.info("Loaded %d synthetic base examples", len(synthetic))

    # Add real signal data (weighted more heavily by repeating)
    real_count = 0
    for sig in signals:
        if sig.get("signal_type") != "routing_quality":
            continue
        text = sig.get("message_text", "")
        if not text:
            continue

        features = extract_features(text)
        feature_array = features_to_array(features)
        value = sig.get("signal_value", 0.5)

        label = 1 if value >= 0.5 else 0

        # Add real data points twice (double weight vs synthetic)
        X.append(feature_array)
        y.append(label)
        X.append(feature_array)
        y.append(label)
        real_count += 1

    if real_count == 0:
        logger.info("No routing quality signals to incorporate")
        return False

    logger.info("Added %d real routing signals (doubled weight)", real_count)

    X = np.array(X)
    y = np.array(y)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y,
    )

    model = LogisticRegression(max_iter=1000, class_weight="balanced", random_state=42)
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    accuracy = float((y_pred == y_test).mean())
    logger.info("Routing classifier accuracy: %.3f (with %d real signals)", accuracy, real_count)
    logger.info(classification_report(y_test, y_pred, target_names=["primary", "cheap"]))

    return model, accuracy


def _retrain_reasoning(signals, count=600):
    """Retrain reasoning effort classifier incorporating real signals."""
    # For now, just retrain from synthetic + log that signals exist
    # Full integration when we have enough diverse reasoning signals
    logger.info("Reasoning effort retraining: %d signals available (future integration)", len(signals))
    return None


def main():
    parser = argparse.ArgumentParser(description="Retrain classifiers from implicit signals")
    parser.add_argument("--min-signals", type=int, default=50,
                        help="Minimum accumulated signals before retraining (default: 50)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Check signal counts without retraining")
    args = parser.parse_args()

    from hermes_constants import get_hermes_home
    from hermes_state import SessionDB

    db = SessionDB()

    routing_count = db.count_implicit_signals("routing_quality")
    reasoning_count = db.count_implicit_signals("reasoning_effort")
    skill_count = db.count_implicit_signals("skill_match")
    total = db.count_implicit_signals()

    logger.info("Implicit signal counts:")
    logger.info("  routing_quality:  %d", routing_count)
    logger.info("  reasoning_effort: %d", reasoning_count)
    logger.info("  skill_match:      %d", skill_count)
    logger.info("  total:            %d", total)

    if args.dry_run:
        if total < args.min_signals:
            logger.info("Not enough signals yet (need %d)", args.min_signals)
        else:
            logger.info("Ready for retraining")
        db.close()
        return

    models_dir = get_hermes_home() / "models"
    synthetic_path = models_dir / "synthetic_routing_data.json"

    # Retrain routing classifier if enough signals
    if routing_count >= args.min_signals:
        routing_signals = db.get_implicit_signals("routing_quality", limit=5000)
        result = _retrain_routing(routing_signals, synthetic_path)
        if result:
            import pickle
            model, accuracy = result
            output_path = models_dir / "routing_classifier.pkl"
            with open(output_path, "wb") as f:
                pickle.dump(model, f)
            logger.info("Updated routing classifier at %s", output_path)

            meta_path = output_path.with_suffix(".json")
            if meta_path.exists():
                with open(meta_path, "r") as f:
                    meta = json.load(f)
            else:
                meta = {}
            meta["real_signals_incorporated"] = routing_count
            meta["last_retrained_from_signals"] = True
            meta["accuracy"] = accuracy
            with open(meta_path, "w") as f:
                json.dump(meta, f, indent=2)
    else:
        logger.info("Routing: need %d more signals before retraining", args.min_signals - routing_count)

    db.close()
    logger.info("Done")


if __name__ == "__main__":
    main()
