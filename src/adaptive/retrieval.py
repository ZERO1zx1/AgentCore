"""Retrieval, scope detection, ranking, and citation building."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence

from src.adaptive.schema import DEFAULT_TTL_DAYS, parse_time, utc_now

TOKEN_RE = re.compile(r"[a-z0-9_./:+-]{2,}", re.I)


def detect_task_scope(context) -> str:
    """Derive a stable scope key from a TaskContext.

    Repository-based tasks get a project-scoped key; everything else is
    'global'. Values pass through schema.safe_component before any use in a
    file-system path.
    """
    metadata = getattr(context, "metadata", {}) or {}
    explicit = metadata.get("memory_scope") or metadata.get("adaptive_scope")
    if explicit:
        return str(explicit)
    repo = getattr(context, "repository_context", {}) or {}
    path = str(repo.get("path", ""))
    if path:
        digest = hashlib.sha256(path.encode("utf-8")).hexdigest()[:12]
        return f"project:{digest}"
    return "global"


def _jaccard(left, right):
    if not left or not right:
        return 0.0
    return len(left & right) / max(1, len(left | right))


def freshness_score(record: Dict[str, Any], category: str, now: Optional[datetime] = None) -> float:
    """0..1 recency-of-verification score using the category TTL."""
    now = now or datetime.now(timezone.utc)
    ttl_days = float(DEFAULT_TTL_DAYS.get(category, 180))
    raw = record.get("last_verified_at") or record.get("created_at") or utc_now()
    last = parse_time(raw)
    if last is None:
        return 0.5
    age_days = max(0.0, (now - last).total_seconds() / 86400.0)
    return max(0.0, min(1.0, 1.0 - age_days / ttl_days))


def is_stale(record: Dict[str, Any], category: str, now: Optional[datetime] = None) -> bool:
    return freshness_score(record, category, now) <= 0.0


def rank(records: Sequence[Dict[str, Any]], query: str, scope: Optional[str] = None,
         now: Optional[datetime] = None) -> List[Dict[str, Any]]:
    """Score active records by relevance, scope, approval, confidence, recency.

    Returns records sorted by descending score, each augmented with "score".
    """
    now = now or datetime.now(timezone.utc)
    query_tokens = set(TOKEN_RE.findall(query.lower()))
    scored = []
    for record in records:
        category = str(record.get("category", "project"))
        text = " ".join(str(record.get(k, "")) for k in ("title", "content"))
        text += " " + " ".join(record.get("tags", []) or [])
        tokens = set(TOKEN_RE.findall(text.lower()))
        relevance = _jaccard(query_tokens, tokens)
        scope_ok = (not scope) or record.get("scope") == scope or record.get("scope") == "global"
        created = parse_time(record.get("created_at")) or now
        age_days = max(0.0, (now - created).total_seconds() / 86400.0)
        recency = max(0.0, 1.0 - age_days / 730.0)
        trust = (0.45 * relevance
                 + 0.15 * float(record.get("confidence", 0.5))
                 + 0.15 * freshness_score(record, category, now)
                 + 0.10 * recency
                 + (0.10 if scope_ok else 0.0)
                 + (0.05 if record.get("user_approved") else 0.0))
        scored.append((trust, relevance, record))
    scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return [dict(item[2], score=round(item[0], 4)) for item in scored]


def build_citation(record: Dict[str, Any]) -> str:
    """One-line, transparent citation for memory use in a response."""
    source = str(record.get("source_type", "user"))
    if record.get("source_url"):
        source += f" <{record.get('source_url')}>"
    elif record.get("source_task_id"):
        source += f" (task {record.get('source_task_id')})"
    return (
        f"[memory {record.get('memory_id')} | {record.get('category')}/{record.get('scope')} "
        f"| confidence {record.get('confidence')} | source {source}] "
        f"{record.get('title')}"
    )


@dataclass(frozen=True)
class MemoryRecallReport:
    query: str
    scope: Optional[str]
    disabled: bool
    matches: tuple
    conflicts: tuple = ()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "scope": self.scope,
            "disabled": self.disabled,
            "matches": list(self.matches),
            "conflicts": list(self.conflicts),
        }