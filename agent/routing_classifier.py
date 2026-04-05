"""Learned routing classifier for cheap-vs-strong model selection.

Loads a scikit-learn model from ~/.hermes/models/routing_classifier.pkl
and provides predictions with confidence scores. Gracefully degrades
to None when the model file is missing or scikit-learn is not installed.
"""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from hermes_constants import get_hermes_home

logger = logging.getLogger(__name__)

_MODEL_PATH = get_hermes_home() / "models" / "routing_classifier.pkl"
_META_PATH = get_hermes_home() / "models" / "routing_classifier.json"
_DEFAULT_CONFIDENCE_THRESHOLD = 0.85

# Singleton state
_classifier: Optional[Any] = None
_classifier_mtime: float = 0.0
_classifier_checked_at: float = 0.0
_CHECK_INTERVAL = 60.0  # Re-check file mtime every 60 seconds


def _load_confidence_threshold() -> float:
    """Read calibrated confidence threshold from model metadata, or use default."""
    meta_path = Path(os.getenv("HERMES_ROUTING_MODEL", str(_MODEL_PATH))).with_suffix(".json")
    try:
        if meta_path.exists():
            import json
            with open(meta_path, "r") as f:
                meta = json.load(f)
            threshold = meta.get("confidence_threshold", _DEFAULT_CONFIDENCE_THRESHOLD)
            return float(threshold)
    except Exception:
        pass
    return _DEFAULT_CONFIDENCE_THRESHOLD


def get_routing_classifier() -> Optional["RoutingClassifier"]:
    """Return the cached classifier singleton, or None if unavailable.

    Hot-reloads the model if the .pkl file has been updated on disk.
    Returns None if:
    - scikit-learn is not installed
    - The model file doesn't exist
    - The model fails to load
    """
    global _classifier, _classifier_mtime, _classifier_checked_at

    now = time.time()
    if now - _classifier_checked_at < _CHECK_INTERVAL:
        return _classifier

    _classifier_checked_at = now

    model_path = Path(os.getenv("HERMES_ROUTING_MODEL", str(_MODEL_PATH)))
    if not model_path.exists():
        _classifier = None
        return None

    current_mtime = model_path.stat().st_mtime
    if _classifier is not None and current_mtime == _classifier_mtime:
        return _classifier

    # (Re)load the model
    try:
        import pickle
        with open(model_path, "rb") as f:
            model = pickle.load(f)
        threshold = _load_confidence_threshold()
        _classifier = RoutingClassifier(model, confidence_threshold=threshold)
        _classifier_mtime = current_mtime
        logger.info("Loaded routing classifier from %s (threshold=%.2f)", model_path, threshold)
        return _classifier
    except ImportError:
        logger.debug("scikit-learn not available — routing classifier disabled")
        _classifier = None
        return None
    except Exception as e:
        logger.warning("Failed to load routing classifier: %s", e)
        _classifier = None
        return None


class RoutingClassifier:
    """Wrapper around a trained sklearn model for routing predictions."""

    def __init__(self, model: Any, confidence_threshold: float = _DEFAULT_CONFIDENCE_THRESHOLD):
        self._model = model
        self._confidence_threshold = confidence_threshold

    def predict_with_confidence(
        self, features: Dict[str, float]
    ) -> Tuple[str, float]:
        """Predict routing class and return (prediction, confidence).

        Returns:
            ("cheap", 0.92) or ("primary", 0.78) etc.
        """
        from agent.routing_features import features_to_array

        feature_array = [features_to_array(features)]

        try:
            prediction = self._model.predict(feature_array)[0]
            probabilities = self._model.predict_proba(feature_array)[0]
            confidence = max(probabilities)
            label = "cheap" if prediction == 1 else "primary"
            return label, float(confidence)
        except Exception as e:
            logger.warning("Classifier prediction failed: %s", e)
            return "primary", 0.0

    def should_route_cheap(
        self,
        features: Dict[str, float],
        threshold: Optional[float] = None,
    ) -> bool:
        """Convenience: returns True if classifier is confident the message is simple.

        Uses the calibrated threshold from model metadata by default.
        """
        effective_threshold = threshold if threshold is not None else self._confidence_threshold
        label, confidence = self.predict_with_confidence(features)
        return label == "cheap" and confidence >= effective_threshold
