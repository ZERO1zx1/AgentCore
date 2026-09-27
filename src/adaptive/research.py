"""Web-research metadata, freshness, and source-reliability helpers.

This module is intentionally dependency-free. Real retrieval happens outside
the adaptive package; here we only track validated metadata, freshness, and
source reliability so research memories remain explainable and auditable.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.adaptive.retrieval import freshness_score, is_stale
from src.adaptive.schema import utc_now

DEFAULT_FRESHNESS_TTL_DAYS = 90
RESEARCH_SOURCE_TYPES = frozenset({"documentation", "primary", "secondary", "forum", "issue_tracker", "reference", "unknown"})

def source_id(url: str) -> str:
    """Generate a stable identifier for a research source URL."""
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]

def detect_conflicts(sources: List[ResearchSource]) -> List[Dict[str, Any]]:
    """Detect conflicting research sources by comparing confidence levels.
    
    Returns a list of conflict reports for sources with significantly
    different confidence scores on possibly related topics.
    """
    if len(sources) < 2:
        return []
    sorted_sources = sorted(sources, key=lambda s: s.confidence, reverse=True)
    conflicts = []
    for i, high in enumerate(sorted_sources):
        for low in sorted_sources[i + 1:]:
            if abs(high.confidence - low.confidence) >= 0.4:
                conflicts.append({
                    "high_confidence_url": high.url,
                    "low_confidence_url": low.url,
                    "high_confidence": high.confidence,
                    "low_confidence": low.confidence,
                    "gap": round(abs(high.confidence - low.confidence), 4),
                })
    return conflicts


@dataclass
class ResearchSource:
    """Metadata for one validated web source."""

    url: str
    title: str
    source_type: str = "unknown"
    retrieved_at: str = field(default_factory=utc_now)
    last_verified_at: str = field(default_factory=utc_now)
    confidence: float = 0.7
    freshness_ttl_days: int = DEFAULT_FRESHNESS_TTL_DAYS
    notes: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.url = str(self.url or "").strip()
        self.title = str(self.title or "").strip()
        if not self.url:
            raise ValueError("research source url is required")
        if self.source_type not in RESEARCH_SOURCE_TYPES:
            self.source_type = "unknown"
        self.confidence = float(max(0.0, min(1.0, self.confidence or 0.0)))
        self.freshness_ttl_days = int(max(1, self.freshness_ttl_days or 1))

    def summary(self) -> Dict[str, Any]:
        return {
            "url": self.url,
            "title": self.title,
            "source_type": self.source_type,
            "retrieved_at": self.retrieved_at,
            "last_verified_at": self.last_verified_at,
            "confidence": round(self.confidence, 4),
            "freshness_score": round(freshness_score(self.metadata, "research"), 4),
            "is_stale": is_stale(self.metadata, "research"),
            "notes": self.notes,
            "metadata": dict(self.metadata),
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "url": self.url,
            "title": self.title,
            "source_type": self.source_type,
            "retrieved_at": self.retrieved_at,
            "last_verified_at": self.last_verified_at,
            "confidence": round(self.confidence, 4),
            "freshness_ttl_days": self.freshness_ttl_days,
            "notes": self.notes,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ResearchSource":
        return cls(
            url=str(data.get("url", "")),
            title=str(data.get("title", "")),
            source_type=str(data.get("source_type", "unknown")),
            retrieved_at=str(data.get("retrieved_at", utc_now())),
            last_verified_at=str(data.get("last_verified_at", utc_now())),
            confidence=float(data.get("confidence", 0.7)),
            freshness_ttl_days=int(data.get("freshness_ttl_days", DEFAULT_FRESHNESS_TTL_DAYS)),
            notes=str(data.get("notes", "")),
            metadata=dict(data.get("metadata", {}) or {}),
        )


class ResearchMetadataStore:
    """Local store for validated research source metadata.

    Persists to ``<root>/.agent-memory/research-metadata.jsonl``.
    """

    def __init__(self, root: str = "."):
        self.root = Path(root).resolve()
        self.memory_dir = self.root / ".agent-memory"
        self.path = self.memory_dir / "research-metadata.jsonl"
        self.state_path = self.memory_dir / "research-state.json"

    def is_enabled(self) -> bool:
        """Check if research metadata storage is enabled."""
        if not self.state_path.exists():
            return False
        try:
            data = json.loads(self.state_path.read_text(encoding="utf-8"))
            return bool(data.get("enabled", True))
        except (OSError, ValueError, json.JSONDecodeError):
            return False

    def enable(self) -> None:
        """Enable research metadata storage."""
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        temporary = self.state_path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps({"enabled": True, "updated_at": utc_now()}, ensure_ascii=False),
            encoding="utf-8",
        )
        temporary.replace(self.state_path)

    def add_source(self, source: ResearchSource) -> Dict[str, Any]:
        """Add or update a research source."""
        from src.adaptive.schema import fingerprint
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        entry = source.to_dict()
        entry["source_id"] = source_id(source.url)
        entry["created_at"] = utc_now()
        base = {"url": entry["url"], "source_type": entry["source_type"], "confidence": entry["confidence"]}
        entry["sha256"] = fingerprint(base)
        path = self.path
        path.parent.mkdir(parents=True, exist_ok=True)
        existing: Dict[str, Dict[str, Any]] = {}
        if path.exists():
            try:
                for line in path.read_text(encoding="utf-8").splitlines():
                    if line.strip():
                        item = json.loads(line)
                        existing[item["url"]] = item
            except (OSError, ValueError, json.JSONDecodeError):
                pass
        existing[entry["url"]] = entry
        lines = [json.dumps(v, ensure_ascii=False, sort_keys=True) for v in existing.values()]
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return entry

    def list_sources(self) -> List[Dict[str, Any]]:
        """List all stored research sources."""
        if not self.path.exists():
            return []
        try:
            lines = self.path.read_text(encoding="utf-8").splitlines()
        except OSError:
            return []
        results = []
        for line in lines:
            if line.strip():
                try:
                    results.append(json.loads(line))
                except (ValueError, json.JSONDecodeError):
                    continue
        return results

    def has_source(self, url: str) -> bool:
        """Check if a source URL is already stored."""
        return any(src.get("url") == url for src in self.list_sources())

    def refresh_source(self, url: str) -> Optional[Dict[str, Any]]:
        """Refresh a source's last_verified_at timestamp."""
        from src.adaptive.schema import fingerprint
        sources = self.list_sources()
        for src in sources:
            if src.get("url") == url:
                src["last_verified_at"] = utc_now()
                base = {"url": src["url"], "source_type": src["source_type"], "confidence": src["confidence"]}
                src["sha256"] = fingerprint(base)
                lines = [json.dumps(s, ensure_ascii=False, sort_keys=True) for s in sources]
                self.path.write_text("\n".join(lines) + "\n", encoding="utf-8")
                return src
        return None

    def stale_urls(self, now: Optional[datetime] = None) -> List[str]:
        """Return URLs whose freshness_score is <= 0."""
        if now is None:
            now = datetime.now(timezone.utc)
        stale = []
        for src in self.list_sources():
            record = {
                "last_verified_at": src.get("last_verified_at", src.get("retrieved_at", utc_now())),
                "metadata": src.get("metadata", {}),
            }
            if is_stale(record, "research", now=now):
                stale.append(src["url"])
        return stale

    def export(self, path: str) -> Dict[str, Any]:
        """Export all research sources to a tamper-evident JSON file."""
        from src.adaptive.schema import fingerprint
        sources = self.list_sources()
        payload = {
            "schema_version": "1.0",
            "exported_at": utc_now(),
            "records": sources,
        }
        payload["sha256"] = fingerprint({
            "exported_at": payload["exported_at"],
            "records": payload["records"],
        })
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return {"exported": len(sources), "path": str(target)}