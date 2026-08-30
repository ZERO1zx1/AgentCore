"""Lesson lifecycle primitives for Adaptive Omni Agent local learning."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Mapping


class LessonStatus(str, Enum):
    CANDIDATE = "candidate"
    VERIFIED = "verified"
    STALE = "stale"
    RETIRED = "retired"


ACTIVE_LESSON_STATUSES = frozenset({LessonStatus.CANDIDATE.value, LessonStatus.VERIFIED.value})


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class LessonTransition:
    lesson_id: str
    from_status: str
    to_status: str
    changed_at: str
    reason: str

    def to_event(self) -> Dict[str, str]:
        return {"event": "lesson_transition", "lesson_id": self.lesson_id, "from_status": self.from_status,
                "to_status": self.to_status, "changed_at": self.changed_at, "reason": self.reason}


def transition_lesson(lesson: Mapping[str, Any], to_status: LessonStatus | str, reason: str) -> LessonTransition:
    """Create a validated, append-only lifecycle transition event."""
    current = str(lesson.get("status", LessonStatus.CANDIDATE.value))
    target = LessonStatus(to_status).value
    allowed = {
        LessonStatus.CANDIDATE.value: {LessonStatus.VERIFIED.value, LessonStatus.RETIRED.value},
        LessonStatus.VERIFIED.value: {LessonStatus.STALE.value, LessonStatus.RETIRED.value},
        LessonStatus.STALE.value: {LessonStatus.VERIFIED.value, LessonStatus.RETIRED.value},
        LessonStatus.RETIRED.value: set(),
    }
    if target not in allowed.get(current, set()):
        raise ValueError(f"invalid lesson transition: {current} -> {target}")
    if not lesson.get("id"):
        raise ValueError("lesson id is required for a transition")
    if not reason or not reason.strip():
        raise ValueError("transition reason is required")
    return LessonTransition(str(lesson["id"]), current, target, utc_now(), reason.strip())


def lesson_is_stale(lesson: Mapping[str, Any], current_fingerprints: Mapping[str, str]) -> bool:
    """Return true only when recorded source fingerprints no longer match."""
    recorded = lesson.get("source_fingerprints") or {}
    if not isinstance(recorded, Mapping) or not recorded:
        return False
    return any(current_fingerprints.get(str(path)) != str(fingerprint) for path, fingerprint in recorded.items())
