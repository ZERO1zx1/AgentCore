"""Feedback learning: verdicts, confidence deltas, and durable-change rules."""

from __future__ import annotations

from typing import Dict, Optional

USEFUL = "useful"
PARTIALLY_USEFUL = "partially_useful"
INCORRECT = "incorrect"
TRY_ANOTHER = "try_another_approach"
REMEMBER_PREFERENCE = "remember_preference"
FORGET_RESULT = "forget_result"

FEEDBACK_VERDICTS = frozenset({
    USEFUL, PARTIALLY_USEFUL, INCORRECT, TRY_ANOTHER, REMEMBER_PREFERENCE, FORGET_RESULT,
})

# One feedback event adjusts confidence by a bounded delta.
CONFIDENCE_DELTAS: Dict[str, float] = {
    USEFUL: 0.10,
    PARTIALLY_USEFUL: 0.03,
    INCORRECT: -0.15,
    TRY_ANOTHER: -0.05,
    REMEMBER_PREFERENCE: 0.05,
    FORGET_RESULT: -0.10,
}

NEGATIVE_VERDICTS = frozenset({INCORRECT, TRY_ANOTHER, FORGET_RESULT})


def apply_confidence(confidence: float, verdict: str) -> float:
    delta = CONFIDENCE_DELTAS.get(verdict, 0.0)
    return max(0.0, min(1.0, float(confidence) + delta))


def is_negative(verdict: str) -> bool:
    return verdict in NEGATIVE_VERDICTS


def durable_reject(negative_count: int, confidence: float,
                   threshold: int = 2, floor: float = 0.15) -> bool:
    """Repeated negative evidence is required before auto-rejecting a record."""
    return int(negative_count) >= threshold and float(confidence) <= floor