"""Kanban triage routing engine — map card labels to an assignee.

Phase 1 of the Hermes Kanban triage layer. The LLM specifier emits a set
of labels (and optionally a suggested assignee) for each card; this
module resolves that into the actual assignee a card should be routed to
by walking user-configured routing rules from ``~/.hermes/config.yaml``.

Design notes
------------

* Rules are evaluated in order. The first rule whose required labels
  are a **subset** of the card's labels wins. This lets users encode
  priority by ordering (e.g. put more-specific rules first).

* The LLM's suggested assignee is the **fallback** — it's only used
  when no user rule matches. Explicit user rules always override the
  model's guess.

* Validation is strict at load time so a typo in config.yaml fails
  loudly rather than silently routing every card to ``None``. The
  ``ValueError`` messages name the rule index so users can find the
  bad entry.

* Import-clean: no I/O, no global state, no side-effects at import
  time. Config is only read when ``load_routing_rules()`` is called.

Integration
-----------

The specifier (``kanban_specify.py``, parallel agent) calls
``route(labels, llm_suggested_assignee, load_routing_rules())`` after
extracting labels from the LLM response, and writes the returned
assignee back to the kanban DB when promoting the card to ``todo``.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional

import yaml

logger = logging.getLogger(__name__)


__all__ = ["route", "load_routing_rules"]


def _validate_rule(rule: Any, index: int) -> tuple[list[str], str]:
    """Validate a single routing rule. Returns (labels, assignee).

    Raises ``ValueError`` with a message pointing at ``index`` if the
    rule is malformed.
    """
    if not isinstance(rule, dict):
        raise ValueError(
            f"routing rule at index {index} must be a dict, "
            f"got {type(rule).__name__}"
        )

    if "labels" not in rule:
        raise ValueError(
            f"routing rule at index {index} is missing required key 'labels'"
        )
    if "assignee" not in rule:
        raise ValueError(
            f"routing rule at index {index} is missing required key 'assignee'"
        )

    raw_labels = rule["labels"]
    if not isinstance(raw_labels, list):
        raise ValueError(
            f"routing rule at index {index}: 'labels' must be a list, "
            f"got {type(raw_labels).__name__}"
        )
    for j, label in enumerate(raw_labels):
        if not isinstance(label, str):
            raise ValueError(
                f"routing rule at index {index}: 'labels[{j}]' must be a "
                f"string, got {type(label).__name__}"
            )

    assignee = rule["assignee"]
    if not isinstance(assignee, str):
        raise ValueError(
            f"routing rule at index {index}: 'assignee' must be a string, "
            f"got {type(assignee).__name__}"
        )

    return list(raw_labels), assignee


def route(
    labels: list[str],
    llm_suggested_assignee: Optional[str],
    routing_rules: list[dict],
) -> Optional[str]:
    """Resolve a card's assignee from its labels and user routing rules.

    Walk ``routing_rules`` in order. The first rule whose ``labels`` is
    a (non-strict) subset of the card's ``labels`` wins and its
    ``assignee`` is returned. If no rule matches, ``llm_suggested_assignee``
    is returned (which may itself be ``None``).

    Parameters
    ----------
    labels:
        The card's labels (as emitted by the LLM specifier).
    llm_suggested_assignee:
        The LLM's preferred assignee, used as fallback when no user rule
        matches. ``None`` if the LLM had no preference.
    routing_rules:
        Ordered list of ``{"labels": [...], "assignee": "..."}`` dicts,
        typically from :func:`load_routing_rules`.

    Returns
    -------
    Optional[str]
        The resolved assignee, or ``None`` if no rule matched and no
        LLM suggestion was provided.

    Raises
    ------
    ValueError
        If ``routing_rules`` is malformed (not a list, contains a
        non-dict, or any rule has the wrong shape).
    """
    if not isinstance(routing_rules, list):
        raise ValueError(
            f"routing_rules must be a list, got {type(routing_rules).__name__}"
        )

    card_labels = set(labels or [])

    for index, rule in enumerate(routing_rules):
        rule_labels, assignee = _validate_rule(rule, index)
        if set(rule_labels).issubset(card_labels):
            return assignee

    return llm_suggested_assignee


def _default_config_path() -> Path:
    """Resolve the default ``~/.hermes/config.yaml`` path.

    Imported lazily so this module stays import-clean — the
    ``hermes_constants`` module touches the filesystem at import time
    (computing ``HERMES_HOME``), and we want callers that never invoke
    ``load_routing_rules`` to pay nothing.
    """
    from hermes_constants import get_hermes_home

    return get_hermes_home() / "config.yaml"


def load_routing_rules(config_path: Optional[str] = None) -> list[dict]:
    """Load routing rules from ``triage.routing_rules`` in config.yaml.

    Returns an empty list if the config file doesn't exist, can't be
    parsed, or has no ``triage.routing_rules`` key. Each rule is
    validated as part of the lookup — a malformed rule raises
    ``ValueError`` so the user sees the problem at routing time
    instead of silently dropping rules.

    Parameters
    ----------
    config_path:
        Optional override for the config file path. When ``None``
        (the default), uses ``~/.hermes/config.yaml`` resolved via
        the standard Hermes config-path helpers.

    Returns
    -------
    list[dict]
        The list of routing rule dicts, in the order they appear in
        config.yaml. Empty list if no rules are configured.

    Raises
    ------
    ValueError
        If ``triage.routing_rules`` is present but not a list, or if
        any individual rule is malformed.
    """
    path = Path(config_path) if config_path is not None else _default_config_path()

    try:
        with open(path, encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
    except FileNotFoundError:
        return []
    except (OSError, yaml.YAMLError) as exc:
        logger.warning("triage_routing: failed to read %s: %s", path, exc)
        return []

    if not isinstance(raw, dict):
        return []

    triage_section = raw.get("triage")
    if not isinstance(triage_section, dict):
        return []

    rules = triage_section.get("routing_rules")
    if rules is None:
        return []
    if not isinstance(rules, list):
        raise ValueError(
            "triage.routing_rules must be a list, "
            f"got {type(rules).__name__}"
        )

    # Validate eagerly so callers see a bad config at load time, not
    # halfway through a sweep when one specific card hits a bad rule.
    for index, rule in enumerate(rules):
        _validate_rule(rule, index)

    return list(rules)
