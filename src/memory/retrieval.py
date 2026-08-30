"""Hybrid retrieval, explanations, conflict detection, and deduplication."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, Mapping, Optional, Protocol, Sequence
import math
import re
import hashlib

from src.memory.governance import evidence_freshness_score


TOKEN_RE = re.compile(r"[\w./:+-]{2,}", re.I)


class SemanticBackend(Protocol):
    """Optional offline embedding backend; ONNX implementations can satisfy this contract."""
    name: str
    def similarity(self, query: str, document: str) -> float: ...


class LocalHashEmbeddingBackend:
    """Dependency-free offline vector backend for opt-in local retrieval.

    It hashes word and character n-grams into a fixed vector. This is less
    capable than a trained ONNX embedding model, but private, deterministic,
    cheap, and useful as a concrete fallback implementation.
    """
    name = "local-hash-embedding-v1"

    def __init__(self, dimensions: int = 256):
        if dimensions < 32:
            raise ValueError("embedding dimensions must be at least 32")
        self.dimensions = dimensions

    def _vector(self, text: str) -> list[float]:
        normalized = re.sub(r"\s+", " ", text.lower()).strip()
        words = TOKEN_RE.findall(normalized)
        features = words + [normalized[index:index + 3] for index in range(max(0, len(normalized) - 2))]
        vector = [0.0] * self.dimensions
        for feature in features:
            digest = hashlib.blake2b(feature.encode("utf-8"), digest_size=4).digest()
            bucket = int.from_bytes(digest, "big") % self.dimensions
            vector[bucket] += 1.0
        magnitude = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / magnitude for value in vector]

    def similarity(self, query: str, document: str) -> float:
        left, right = self._vector(query), self._vector(document)
        return max(0.0, min(1.0, sum(a * b for a, b in zip(left, right))))


@dataclass(frozen=True)
class ScoreBreakdown:
    lexical: float
    semantic: float
    confidence: float
    freshness: float
    total: float


@dataclass(frozen=True)
class RecallExplanation:
    lesson_id: str
    selected: bool
    reasons: tuple[str, ...]
    scores: ScoreBreakdown


@dataclass(frozen=True)
class DryRunReport:
    query: str
    scope: str | None
    semantic_backend: str | None
    explanations: tuple[RecallExplanation, ...]
    conflicts: tuple[Dict[str, Any], ...] = ()

    def to_dict(self) -> Dict[str, Any]:
        return {"query": self.query, "scope": self.scope, "semantic_backend": self.semantic_backend,
                "explanations": [{"lesson_id": item.lesson_id, "selected": item.selected,
                                  "reasons": list(item.reasons), "scores": item.scores.__dict__}
                                 for item in self.explanations], "conflicts": list(self.conflicts)}


class HybridRetrievalEngine:
    def __init__(self, semantic_backend: SemanticBackend | None = None, lexical_weight: float = 0.65,
                 semantic_weight: float = 0.35):
        self.semantic_backend = semantic_backend
        self.lexical_weight = lexical_weight
        self.semantic_weight = semantic_weight

    @staticmethod
    def lesson_text(lesson: Mapping[str, Any]) -> str:
        return " ".join(str(lesson.get(key, "")) for key in ("problem", "cause", "action", "scope")) + " " + " ".join(lesson.get("tags", []))

    def score(self, query: str, lesson: Mapping[str, Any], confidence: float,
              current_fingerprints: Mapping[str, str]) -> ScoreBreakdown:
        query_tokens = set(TOKEN_RE.findall(query.lower()))
        lesson_tokens = set(TOKEN_RE.findall(self.lesson_text(lesson).lower()))
        lexical = len(query_tokens & lesson_tokens) / max(1, len(query_tokens | lesson_tokens))
        semantic = 0.0
        if self.semantic_backend is not None:
            semantic = max(0.0, min(1.0, float(self.semantic_backend.similarity(query, self.lesson_text(lesson)))))
        freshness = evidence_freshness_score(lesson, current_fingerprints)
        retrieval = self.lexical_weight * lexical
        if self.semantic_backend is not None:
            retrieval += self.semantic_weight * semantic
        total = retrieval * 0.65 + confidence * 0.2 + freshness * 0.15
        return ScoreBreakdown(round(lexical, 4), round(semantic, 4), round(confidence, 4), freshness, round(total, 4))


class ConflictDetector:
    NEGATIONS = {"not", "never", "avoid", "disable", "remove", "skip", "do not", "don't"}

    @classmethod
    def detect(cls, lessons: Sequence[Mapping[str, Any]]) -> list[Dict[str, Any]]:
        conflicts: list[Dict[str, Any]] = []
        for idx, left in enumerate(lessons):
            for right in lessons[idx + 1:]:
                problem_left = set(TOKEN_RE.findall(str(left.get("problem", "")).lower()))
                problem_right = set(TOKEN_RE.findall(str(right.get("problem", "")).lower()))
                overlap = len(problem_left & problem_right) / max(1, len(problem_left | problem_right))
                if overlap < 0.25:
                    continue
                action_left = str(left.get("action", "")).lower()
                action_right = str(right.get("action", "")).lower()
                left_negative = any(token in action_left for token in cls.NEGATIONS)
                right_negative = any(token in action_right for token in cls.NEGATIONS)
                action_tokens_left = set(TOKEN_RE.findall(action_left))
                action_tokens_right = set(TOKEN_RE.findall(action_right))
                action_overlap = len(action_tokens_left & action_tokens_right) / max(1, len(action_tokens_left | action_tokens_right))
                if left_negative != right_negative or action_overlap < 0.12:
                    conflicts.append({"lesson_ids": [left.get("id"), right.get("id")],
                                      "reason": "similar problem with contradictory or materially different actions",
                                      "problem_overlap": round(overlap, 3), "requires_resolution": True})
        return conflicts

    @staticmethod
    def resolve_as_hints(lessons: Sequence[Mapping[str, Any]],
                         conflicts: Sequence[Mapping[str, Any]]) -> tuple[list[Dict[str, Any]], list[Dict[str, Any]]]:
        """Suppress lower-ranked contradictory hints and retain an audit record."""
        by_id = {str(item.get("id")): dict(item) for item in lessons}
        suppressed: set[str] = set()
        resolved = []
        for conflict in conflicts:
            ids = [str(item) for item in conflict.get("lesson_ids", []) if str(item) in by_id]
            if len(ids) < 2:
                resolved.append(dict(conflict))
                continue
            ranked_ids = sorted(ids, key=lambda item: float(by_id[item].get("score", 0)), reverse=True)
            chosen = ranked_ids[0]
            suppressed.update(ranked_ids[1:])
            item = dict(conflict)
            item.update({"chosen_hint_id": chosen, "suppressed_hint_ids": ranked_ids[1:],
                         "resolution": "current workspace and validation evidence must verify chosen hint"})
            resolved.append(item)
        return [item for item in by_id.values() if str(item.get("id")) not in suppressed], resolved


class LessonDeduplicator:
    @staticmethod
    def clusters(lessons: Sequence[Mapping[str, Any]], threshold: float = 0.72) -> list[Dict[str, Any]]:
        remaining = [dict(item) for item in lessons]
        clusters: list[Dict[str, Any]] = []
        while remaining:
            seed = remaining.pop(0)
            seed_tokens = set(TOKEN_RE.findall(HybridRetrievalEngine.lesson_text(seed).lower()))
            matches = [seed]
            keep = []
            for item in remaining:
                tokens = set(TOKEN_RE.findall(HybridRetrievalEngine.lesson_text(item).lower()))
                similarity = len(seed_tokens & tokens) / max(1, len(seed_tokens | tokens))
                (matches if similarity >= threshold else keep).append(item)
            remaining = keep
            if len(matches) > 1:
                canonical = max(matches, key=lambda x: (x.get("status") == "verified", x.get("confidence", 0), x.get("created_at", "")))
                clusters.append({"canonical_id": canonical.get("id"), "lesson_ids": [x.get("id") for x in matches]})
        return clusters
