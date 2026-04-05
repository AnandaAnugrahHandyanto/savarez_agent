"""Predict optimal reasoning effort level based on message complexity.

Uses a lightweight DecisionTree classifier to predict whether a query needs
low, medium, or high reasoning effort. Bootstrapped with synthetic heuristic
labels, then improved via implicit feedback signals over time.

The classifier runs locally (sklearn, no API calls) and adds negligible
latency (<1ms per prediction).
"""

from __future__ import annotations

import logging
import os
import pickle
import time
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from hermes_constants import get_hermes_home

logger = logging.getLogger(__name__)

_MODEL_PATH = get_hermes_home() / "models" / "reasoning_effort.pkl"
_META_PATH = get_hermes_home() / "models" / "reasoning_effort.json"
_DEFAULT_OVERRIDE_THRESHOLD = 0.80

# Singleton state
_predictor: Optional[Any] = None
_predictor_mtime: float = 0.0
_predictor_checked_at: float = 0.0
_CHECK_INTERVAL = 60.0

# -- Effort levels mapped to integers for classification --
EFFORT_LABELS = {"low": 0, "medium": 1, "high": 2}
EFFORT_NAMES = {0: "low", 1: "medium", 2: "high"}


def _load_override_threshold() -> float:
    """Read override threshold from model metadata."""
    try:
        if _META_PATH.exists():
            import json
            with open(_META_PATH, "r") as f:
                meta = json.load(f)
            return float(meta.get("override_threshold", _DEFAULT_OVERRIDE_THRESHOLD))
    except Exception:
        pass
    return _DEFAULT_OVERRIDE_THRESHOLD


def get_reasoning_predictor() -> Optional["ReasoningEffortPredictor"]:
    """Return the cached predictor singleton, or None if unavailable."""
    global _predictor, _predictor_mtime, _predictor_checked_at

    now = time.time()
    if now - _predictor_checked_at < _CHECK_INTERVAL:
        return _predictor

    _predictor_checked_at = now

    model_path = Path(os.getenv("HERMES_REASONING_MODEL", str(_MODEL_PATH)))
    if not model_path.exists():
        _predictor = None
        return None

    current_mtime = model_path.stat().st_mtime
    if _predictor is not None and current_mtime == _predictor_mtime:
        return _predictor

    try:
        with open(model_path, "rb") as f:
            model = pickle.load(f)
        threshold = _load_override_threshold()
        _predictor = ReasoningEffortPredictor(model, override_threshold=threshold)
        _predictor_mtime = current_mtime
        logger.info("Loaded reasoning effort predictor from %s", model_path)
        return _predictor
    except Exception as e:
        logger.warning("Failed to load reasoning effort predictor: %s", e)
        _predictor = None
        return None


class ReasoningEffortPredictor:
    """Wrapper around a trained sklearn model for reasoning effort prediction."""

    def __init__(self, model: Any, override_threshold: float = _DEFAULT_OVERRIDE_THRESHOLD):
        self._model = model
        self._override_threshold = override_threshold

    def predict(self, features: Dict[str, float]) -> Tuple[str, float]:
        """Predict reasoning effort level and return (effort, confidence).

        Returns:
            ("low", 0.95) or ("medium", 0.65) or ("high", 0.88) etc.
        """
        from agent.routing_features import features_to_array

        feature_array = [features_to_array(features)]

        try:
            prediction = self._model.predict(feature_array)[0]
            probabilities = self._model.predict_proba(feature_array)[0]
            confidence = float(max(probabilities))
            effort_name = EFFORT_NAMES.get(prediction, "medium")
            return effort_name, confidence
        except Exception as e:
            logger.warning("Reasoning effort prediction failed: %s", e)
            return "medium", 0.0

    def suggest_effort(
        self,
        features: Dict[str, float],
        current_effort: str = "medium",
    ) -> Optional[str]:
        """Suggest an effort override only when the classifier is confident.

        Returns the suggested effort level, or None if the classifier
        is not confident enough to override the configured default.
        """
        predicted_effort, confidence = self.predict(features)

        if confidence < self._override_threshold:
            return None

        if predicted_effort == current_effort:
            return None

        logger.debug(
            "Reasoning effort prediction: %s (confidence=%.2f), overriding %s",
            predicted_effort, confidence, current_effort,
        )
        return predicted_effort
