"""Governance, admission, provenance, permissions, and replay contracts."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Sequence
import hashlib
import json
import re

from src.memory.safety import SensitiveDataGate


POLICY_VERSION = "adaptive-omni-memory/1.0"
SIGNAL_TOKENS = re.compile(r"[\w./:+-]{2,}", re.I)
VALIDATION_MARKERS = ("test", "pytest", "unittest", "build", "lint", "render", "passed", "sha256", "exit code", "verified")


class MemoryAction(str, Enum):
    READ = "read"
    PROPOSE = "propose"
    VERIFY = "verify"
    RETIRE = "retire"
    EXPORT = "export"
    IMPORT = "import"


ROLE_PERMISSIONS = {
    "reader": {MemoryAction.READ},
    "contributor": {MemoryAction.READ, MemoryAction.PROPOSE},
    "reviewer": {MemoryAction.READ, MemoryAction.PROPOSE, MemoryAction.VERIFY, MemoryAction.RETIRE},
    "maintainer": set(MemoryAction),
}


@dataclass(frozen=True)
class AdmissionDecision:
    accepted: bool
    score: float
    reasons: tuple[str, ...]


class LessonAdmissionPolicy:
    """Reject unsafe, vague, or unevidenced lessons before persistence."""

    def evaluate(self, lesson: Mapping[str, Any]) -> AdmissionDecision:
        reasons: list[str] = []
        required = ("scope", "problem", "cause", "action", "evidence")
        missing = [key for key in required if not str(lesson.get(key, "")).strip()]
        if missing:
            reasons.append("missing required fields: " + ", ".join(missing))
        findings = SensitiveDataGate.inspect({key: lesson.get(key, "") for key in required})
        if findings:
            reasons.append("sensitive data detected")
        action_tokens = SIGNAL_TOKENS.findall(str(lesson.get("action", "")))
        problem_tokens = SIGNAL_TOKENS.findall(str(lesson.get("problem", "")))
        evidence = str(lesson.get("evidence", "")).lower()
        if len(action_tokens) < 2 or str(lesson.get("action", "")).strip().lower() in {"fixed it", "fix it", "зассан"}:
            reasons.append("action is too general")
        if len(problem_tokens) < 2 or str(lesson.get("problem", "")).strip().lower() in {"bug fixed", "fixed it", "алдааг зассан"}:
            reasons.append("problem is too general")
        if not any(marker in evidence for marker in VALIDATION_MARKERS):
            reasons.append("evidence lacks an observable validation marker")
        if len(str(lesson.get("evidence", ""))) < 8:
            reasons.append("evidence is too short")
        score = max(0.0, 1.0 - 0.2 * len(reasons))
        return AdmissionDecision(not reasons, round(score, 2), tuple(reasons))

    def require(self, lesson: Mapping[str, Any]) -> None:
        decision = self.evaluate(lesson)
        if not decision.accepted:
            raise ValueError("lesson rejected: " + "; ".join(decision.reasons))


@dataclass(frozen=True)
class ProvenanceRecord:
    task_fingerprint: str
    source_fingerprints: Dict[str, str]
    checkpoint_id: str = ""
    validation_refs: tuple[str, ...] = ()
    artifact_refs: tuple[str, ...] = ()
    policy_version: str = POLICY_VERSION
    recorded_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"))

    def to_dict(self) -> Dict[str, Any]:
        return {"task_fingerprint": self.task_fingerprint, "source_fingerprints": dict(self.source_fingerprints),
                "checkpoint_id": self.checkpoint_id, "validation_refs": list(self.validation_refs),
                "artifact_refs": list(self.artifact_refs), "policy_version": self.policy_version,
                "recorded_at": self.recorded_at}


def evidence_freshness_score(lesson: Mapping[str, Any], current_fingerprints: Mapping[str, str],
                             current_policy_version: str = POLICY_VERSION, now: datetime | None = None) -> float:
    """Return 0..1 freshness from age, fingerprints, policy, and lifecycle."""
    if lesson.get("status") in {"stale", "retired"}:
        return 0.0
    score = 1.0
    recorded = lesson.get("source_fingerprints") or {}
    if recorded and any(current_fingerprints.get(str(path)) != str(value) for path, value in recorded.items()):
        return 0.0
    if lesson.get("policy_version", current_policy_version) != current_policy_version:
        score -= 0.25
    raw_date = lesson.get("verified_at") or lesson.get("created_at")
    if raw_date:
        try:
            created = datetime.fromisoformat(str(raw_date).replace("Z", "+00:00"))
            current = now or datetime.now(timezone.utc)
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            if current.tzinfo is None:
                current = current.replace(tzinfo=timezone.utc)
            age_days = max(0, (current - created).days)
            score -= min(0.45, age_days / 730.0)
        except ValueError:
            score -= 0.1
    return round(max(0.0, min(1.0, score)), 3)


class PermissionPolicy:
    @staticmethod
    def require(role: str, action: MemoryAction | str) -> None:
        try:
            normalized = MemoryAction(action)
        except ValueError as exc:
            raise PermissionError(f"unknown memory action: {action}") from exc
        if normalized not in ROLE_PERMISSIONS.get(role, set()):
            raise PermissionError(f"role {role!r} cannot perform memory action {normalized.value!r}")


@dataclass(frozen=True)
class ReplayStep:
    instruction: str
    validation: str
    expected_outcome: str


@dataclass(frozen=True)
class LessonRunbook:
    lesson_id: str
    preconditions: tuple[str, ...]
    steps: tuple[ReplayStep, ...]
    source_fingerprints: Dict[str, str]

    def validate(self) -> None:
        if not self.lesson_id or not self.steps:
            raise ValueError("runbook requires a lesson id and at least one step")
        for step in self.steps:
            if not step.instruction.strip() or not step.validation.strip() or not step.expected_outcome.strip():
                raise ValueError("every replay step requires instruction, validation, and expected outcome")

    def to_dict(self) -> Dict[str, Any]:
        self.validate()
        return {"lesson_id": self.lesson_id, "preconditions": list(self.preconditions),
                "source_fingerprints": dict(self.source_fingerprints),
                "steps": [step.__dict__ for step in self.steps]}


def build_runbook_from_lesson(lesson: Mapping[str, Any]) -> LessonRunbook:
    """Create a deterministic one-step replay contract from a verified lesson."""
    if lesson.get("status") != "verified":
        raise ValueError("only verified lessons can become replay runbooks")
    validation = str(lesson.get("evidence", "")).strip()
    runbook = LessonRunbook(
        lesson_id=str(lesson.get("id", "")),
        preconditions=(str(lesson.get("problem", "")).strip(),),
        source_fingerprints=dict(lesson.get("source_fingerprints") or {}),
        steps=(ReplayStep(
            instruction=str(lesson.get("action", "")).strip(),
            validation=validation,
            expected_outcome="The recorded problem no longer reproduces and validation passes.",
        ),),
    )
    runbook.validate()
    return runbook


def task_fingerprint(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
