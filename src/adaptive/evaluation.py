"""Local evaluation layer with deterministic, non-destructive recommendations."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.adaptive.schema import utc_now

DEFAULTS: Dict[str, Any] = {
    "tasks_completed": 0,
    "memories_created": 0,
    "memories_approved": 0,
    "memories_rejected": 0,
    "recall_events": 0,
    "recall_hits": 0,
    "corrections": 0,
    "feedback_events": 0,
    "repeated_errors": 0,
    "stale_records": 0,
    "research_verified_sources": 0,
    "skill_success": {},
    "skill_failures": {},
    "research_sources": {},
}


class AdaptiveEvaluation:
    """Counters stored locally in ``adaptive-evaluation.json``.

    Evaluation only *recommends* improvements; it never rewrites core code,
    security rules, or system policies.
    """

    def __init__(self, path: str = ".agent-memory/adaptive-evaluation.json"):
        self.path = Path(path)
        self.data: Dict[str, Any] = json.loads(json.dumps(DEFAULTS))
        self._load()

    def _load(self) -> None:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return
        if not isinstance(raw, dict):
            return
        for key, value in DEFAULTS.items():
            if key in raw:
                self.data[key] = raw[key]

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(self.data, indent=2, sort_keys=True), encoding="utf-8"
        )
        temporary.replace(self.path)

    def record_task(self, *, success: bool) -> "AdaptiveEvaluation":
        self.data["tasks_completed"] = int(self.data.get("tasks_completed", 0)) + 1
        if not success:
            self.data["repeated_errors"] = int(self.data.get("repeated_errors", 0)) + 1
        self.save()
        return self

    def record_memory(self, *, approved: bool) -> "AdaptiveEvaluation":
        self.data["memories_created"] = int(self.data.get("memories_created", 0)) + 1
        if approved:
            self.data["memories_approved"] = int(self.data.get("memories_approved", 0)) + 1
        else:
            self.data["memories_rejected"] = int(self.data.get("memories_rejected", 0)) + 1
        self.save()
        return self

    def record_recall(self, *, hits: int = 0) -> "AdaptiveEvaluation":
        self.data["recall_events"] = int(self.data.get("recall_events", 0)) + 1
        self.data["recall_hits"] = int(self.data.get("recall_hits", 0)) + int(hits)
        self.save()
        return self

    def record_correction(self) -> "AdaptiveEvaluation":
        self.data["corrections"] = int(self.data.get("corrections", 0)) + 1
        self.save()
        return self

    def record_feedback(self) -> "AdaptiveEvaluation":
        self.data["feedback_events"] = int(self.data.get("feedback_events", 0)) + 1
        self.save()
        return self

    def record_stale(self, count: int = 1) -> "AdaptiveEvaluation":
        self.data["stale_records"] = int(self.data.get("stale_records", 0)) + int(count)
        self.save()
        return self

    def record_skill(self, *, skill: str, success: bool) -> "AdaptiveEvaluation":
        bucket = "skill_success" if success else "skill_failures"
        table = self.data.setdefault(bucket, {})
        key = str(skill)
        table[key] = int(table.get(key, 0)) + 1
        self.save()
        return self

    # --- Reads ---------------------------------------------------------------
    def summary(self) -> Dict[str, Any]:
        data = self.data
        ratio = lambda a, b: round(a / b, 4) if b else 0.0
        return {
            "tasks_completed": data["tasks_completed"],
            "memories_created": data["memories_created"],
            "memory_approval_rate": ratio(data["memories_approved"], data["memories_created"]),
            "memories_rejected_candidates": data["memories_rejected"],
            "recall_events": data["recall_events"],
            "recall_hits": data["recall_hits"],
            "corrections": data["corrections"],
            "feedback_events": data["feedback_events"],
            "repeated_errors": data["repeated_errors"],
            "stale_records": data["stale_records"],
            "research_verified_sources": data["research_verified_sources"],
            "skill_success": dict(data.get("skill_success", {})),
            "skill_failures": dict(data.get("skill_failures", {})),
            "research_sources": dict(data.get("research_sources", {})),
        }

    def recommendations(self) -> List[str]:
        """Deterministic suggestions derived from local counters only."""
        data = self.data
        out: List[str] = []
        if data["recall_events"] and data["recall_hits"] / max(1, data["recall_events"]) < 0.3:
            out.append("Retrieval precision is low: review ranking weights or project scope keys.")
        if data["repeated_errors"] >= 3:
            out.append("Repeated errors observed: consider reviewing the affected task/skill route.")
        if data["stale_records"] >= 5:
            out.append("Stale memory is accumulating: verify or retire unused records.")
        worst = None
        table = data.get("research_sources", {})
        for key, entry in table.items():
            if entry.get("failed"):
                if worst is None or entry["failed"] > worst[1]:
                    worst = (key, entry["failed"])
        if worst:
            out.append(f"Research source {worst[0]} failed {worst[1]} time(s): verify or drop it.")
        if data.get("skill_failures") and not data.get("skill_success"):
            out.append("All recorded skill outcomes failed: review skill selection before reuse.")
        if not out:
            out.append("No corrective recommendations; keep collecting local evidence.")
        return out

    def record_research(self, *, source_url: str, verified: bool) -> "AdaptiveEvaluation":
        table = self.data.setdefault("research_sources", {})
        entry = table.setdefault(str(source_url), {"verified": 0, "failed": 0, "hits": 0})
        entry["verified" if verified else "failed"] = int(
            entry.get("verified" if verified else "failed", 0)
        ) + 1
        if verified:
            self.data["research_verified_sources"] = int(
                self.data.get("research_verified_sources", 0)
            ) + 1
        self.save()
        return self