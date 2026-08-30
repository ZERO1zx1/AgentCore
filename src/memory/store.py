"""Evidence-first local lesson store owned by Adaptive Omni Agent."""
import json
import re
import hashlib
import os
import secrets
from pathlib import Path
from typing import Any, Dict, List

from src.memory.lifecycle import ACTIVE_LESSON_STATUSES, LessonStatus, lesson_is_stale, utc_now
from src.memory.safety import MemoryPoisoningGate, SensitiveDataGate
from src.memory.governance import LessonAdmissionPolicy, MemoryAction, PermissionPolicy, POLICY_VERSION, ProvenanceRecord, evidence_freshness_score
from src.memory.retrieval import ConflictDetector, DryRunReport, HybridRetrievalEngine, LessonDeduplicator, RecallExplanation

TOKEN_RE = re.compile(r"[a-z0-9_./:+-]{2,}", re.I)


class LocalMemoryStore:
    def __init__(self, root: str = ".", max_bytes: int = 512 * 1024, semantic_backend=None):
        self.path = Path(root).resolve() / ".agent-memory" / "lessons.jsonl"
        self.max_bytes = max_bytes
        self.retrieval = HybridRetrievalEngine(semantic_backend)
        self.admission = LessonAdmissionPolicy()

    def recall(self, query: str, limit: int = 5, scope: str | None = None,
               source_fingerprints: Dict[str, str] | None = None, role: str = "reader") -> List[Dict[str, Any]]:
        PermissionPolicy.require(role, MemoryAction.READ)
        matches, _ = self.recall_with_report(query, limit, scope, source_fingerprints)
        return matches

    def _load_state(self):
        if not self.path.exists() or self.path.stat().st_size > self.max_bytes:
            return {}, {}
        lessons: Dict[str, Dict[str, Any]] = {}
        feedback: Dict[str, List[Dict[str, Any]]] = {}
        try:
            lines = self.path.read_text(encoding="utf-8").splitlines()
        except OSError:
            return {}, {}
        for line in lines:
            try: event = json.loads(line)
            except (json.JSONDecodeError, TypeError): continue
            if event.get("event") == "lesson" and event.get("id"): lessons[event["id"]] = event
            elif event.get("event") == "feedback" and event.get("lesson_id"): feedback.setdefault(event["lesson_id"], []).append(event)
            elif event.get("event") == "lesson_transition" and event.get("lesson_id") in lessons:
                lessons[event["lesson_id"]]["status"] = event.get("to_status", lessons[event["lesson_id"]].get("status"))
            elif event.get("event") == "lesson_annotation" and event.get("lesson_id") in lessons:
                lessons[event["lesson_id"]].update({key: value for key, value in event.items() if key in {"outcome"}})
        return lessons, feedback

    def recall_with_report(self, query: str, limit: int = 5, scope: str | None = None,
                           source_fingerprints: Dict[str, str] | None = None,
                           role: str = "reader"):
        PermissionPolicy.require(role, MemoryAction.READ)
        lessons, feedback = self._load_state()
        current_fingerprints = source_fingerprints or {}
        query_tokens = set(TOKEN_RE.findall(query.lower()))
        ranked = []
        explanations = []
        for lesson in lessons.values():
            reasons = []
            if lesson.get("status") not in ACTIVE_LESSON_STATUSES:
                explanations.append(RecallExplanation(lesson["id"], False, ("inactive lifecycle status",), self.retrieval.score(query, lesson, 0, current_fingerprints)))
                continue
            if scope and lesson.get("scope") != scope:
                explanations.append(RecallExplanation(lesson["id"], False, ("scope mismatch",), self.retrieval.score(query, lesson, 0, current_fingerprints)))
                continue
            if source_fingerprints and lesson_is_stale(lesson, source_fingerprints):
                explanations.append(RecallExplanation(lesson["id"], False, ("source fingerprint mismatch",), self.retrieval.score(query, lesson, 0, current_fingerprints)))
                continue
            text = " ".join(str(lesson.get(k, "")) for k in ("problem", "cause", "action", "scope")) + " " + " ".join(lesson.get("tags", []))
            overlap = len(query_tokens & set(TOKEN_RE.findall(text.lower())))
            confidence = .65 if lesson.get("status") == "verified" else .35
            for item in feedback.get(lesson["id"], []): confidence += .08 if item.get("result") == "success" else -.22
            confidence = max(0.0, min(1.0, confidence))
            scores = self.retrieval.score(query, lesson, confidence, current_fingerprints)
            if scores.lexical <= 0 and scores.semantic <= 0:
                explanations.append(RecallExplanation(lesson["id"], False, ("no lexical or semantic match",), scores))
                continue
            reasons.append(f"lexical={scores.lexical}")
            if self.retrieval.semantic_backend is not None: reasons.append(f"semantic={scores.semantic}")
            reasons.extend((f"confidence={scores.confidence}", f"freshness={scores.freshness}"))
            ranked.append((scores.total, lesson.get("created_at", ""), lesson, scores, tuple(reasons), confidence))
        ranked.sort(key=lambda item: (item[0], item[1]), reverse=True)
        selected_ids = {item[2]["id"] for item in ranked[:limit]}
        for _, _, lesson, scores, reasons, _ in ranked:
            explanations.append(RecallExplanation(lesson["id"], lesson["id"] in selected_ids, reasons, scores))
        matches = [{"id": lesson["id"], "problem": lesson.get("problem", ""), "cause": lesson.get("cause", ""),
                    "action": lesson.get("action", ""), "evidence": lesson.get("evidence", ""),
                    "confidence": round(confidence, 2), "freshness": scores.freshness,
                    "scope": lesson.get("scope", "project"), "status": lesson.get("status"),
                    "outcome": lesson.get("outcome", "success"), "score": scores.total}
                   for _, _, lesson, scores, _, confidence in ranked[:limit]]
        conflicts = ConflictDetector.detect(matches)
        matches, conflicts = ConflictDetector.resolve_as_hints(matches, conflicts)
        report = DryRunReport(query, scope, getattr(self.retrieval.semantic_backend, "name", None), tuple(explanations), tuple(conflicts))
        return matches, report

    def mark_stale_lessons(self, source_fingerprints: Dict[str, str], scope: str | None = None,
                           role: str = "maintainer") -> List[str]:
        """Append stale transitions for verified lessons whose source evidence changed."""
        PermissionPolicy.require(role, MemoryAction.RETIRE)
        if not self.path.exists():
            return []
        lessons: Dict[str, Dict[str, Any]] = {}
        for line in self.path.read_text(encoding="utf-8").splitlines():
            try:
                event = json.loads(line)
            except (json.JSONDecodeError, TypeError):
                continue
            if event.get("event") == "lesson" and event.get("id"):
                lessons[event["id"]] = event
            elif event.get("event") == "lesson_transition" and event.get("lesson_id") in lessons:
                lessons[event["lesson_id"]]["status"] = event.get("to_status", lessons[event["lesson_id"]].get("status"))
        stale_ids = []
        for lesson in lessons.values():
            if lesson.get("status") != LessonStatus.VERIFIED.value or (scope and lesson.get("scope") != scope):
                continue
            policy_changed = bool(lesson.get("policy_version")) and lesson.get("policy_version") != POLICY_VERSION
            if lesson_is_stale(lesson, source_fingerprints) or policy_changed:
                transition = {"event": "lesson_transition", "lesson_id": lesson["id"], "from_status": LessonStatus.VERIFIED.value,
                              "to_status": LessonStatus.STALE.value, "changed_at": utc_now(),
                              "reason": "memory policy version changed" if policy_changed else "recorded source fingerprints changed"}
                with self.path.open("a", encoding="utf-8", newline="\n") as handle:
                    handle.write(json.dumps(transition, ensure_ascii=False, sort_keys=True) + "\n")
                stale_ids.append(lesson["id"])
        return stale_ids

    def record_verified_lesson(self, *, scope: str, problem: str, cause: str, action: str,
                               evidence: str, tags: List[str] | None = None,
                               source_fingerprints: Dict[str, str] | None = None,
                               task_fingerprint: str = "",
                               provenance: ProvenanceRecord | None = None,
                               role: str = "maintainer") -> Dict[str, Any]:
        """Persist a verified lesson after the caller has supplied real success evidence.

        This method intentionally cannot record candidate or negative lessons: those
        require an explicit review workflow rather than automatic task completion.
        """
        PermissionPolicy.require(role, MemoryAction.VERIFY)
        fields = {"scope": scope, "problem": problem, "cause": cause, "action": action, "evidence": evidence,
                  "tags": " ".join(tags or [])}
        SensitiveDataGate.assert_safe(fields)
        MemoryPoisoningGate.assert_safe(fields)
        self.admission.require(fields)
        digest = hashlib.sha256((problem + cause + action).encode("utf-8")).hexdigest()[:10]
        event = {"event": "lesson", "id": f"l-{digest}-{secrets.token_hex(2)}", "created_at": utc_now(),
                 "scope": scope.strip(), "status": LessonStatus.VERIFIED.value, "tags": sorted(set(tags or [])),
                 "problem": problem.strip(), "cause": cause.strip(), "action": action.strip(), "evidence": evidence.strip(),
                 "source_fingerprints": dict(source_fingerprints or {}), "task_fingerprint": task_fingerprint,
                 "policy_version": POLICY_VERSION, "verified_at": utc_now()}
        if provenance is not None:
            event["provenance"] = provenance.to_dict()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = (json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")
        fd = os.open(self.path, os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o600)
        try:
            os.write(fd, data); os.fsync(fd)
        finally:
            os.close(fd)
        return event

    def duplicate_clusters(self, scope: str | None = None, role: str = "reader") -> List[Dict[str, Any]]:
        PermissionPolicy.require(role, MemoryAction.READ)
        lessons, _ = self._load_state()
        active = [item for item in lessons.values() if item.get("status") in ACTIVE_LESSON_STATUSES
                  and (scope is None or item.get("scope") == scope)]
        return LessonDeduplicator.clusters(active)

    def record_reviewed_negative_lesson(self, *, scope: str, problem: str, cause: str, action: str,
                                        evidence: str, tags: List[str] | None = None,
                                        source_fingerprints: Dict[str, str] | None = None,
                                        task_fingerprint: str = "",
                                        role: str = "reviewer") -> Dict[str, Any]:
        """Persist a human-reviewed failure lesson to prevent repeated bad routes.

        Failure information is never written automatically. A caller must first
        establish the evidence and decide that the lesson is reusable.
        """
        event = self.record_verified_lesson(
            scope=scope, problem=problem, cause=cause, action=action, evidence=evidence,
            tags=tags, source_fingerprints=source_fingerprints, task_fingerprint=task_fingerprint,
            role=role,
        )
        event["outcome"] = "failure"
        # Rewrite is avoided: append an outcome annotation that preserves the audit trail.
        annotation = {"event": "lesson_annotation", "lesson_id": event["id"], "outcome": "failure", "created_at": utc_now()}
        with self.path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(annotation, ensure_ascii=False, sort_keys=True) + "\n")
        return event
