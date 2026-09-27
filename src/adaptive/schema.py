"""Memory record schema for the Adaptive Memory system.

Every memory record follows a fixed, forward-compatible schema. Records are
stored as JSONL events; new events never rewrite older ones (append-only), so
all changes remain auditable and reversible.
"""

from __future__ import annotations

import hashlib
import json
import re
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

SCHEMA_VERSION = "1.0"

# Memory categories (never mix scopes across categories).
MEMORY_CATEGORIES = frozenset({
    "user", "project", "task", "skill", "research", "feedback",
})

# Lifecycle statuses. "candidate" means "awaiting user approval".
MEMORY_STATUSES = frozenset({"active", "stale", "rejected", "deleted"})

SOURCE_TYPES = frozenset({
    "user", "task", "skill", "research", "feedback", "import", "system",
})

# Days after which an unverified record of a category is considered stale.
DEFAULT_TTL_DAYS = {
    "user": 365,
    "project": 365,
    "task": 90,
    "skill": 180,
    "research": 90,
    "feedback": 180,
}


class MemoryError(RuntimeError):
    """Base class for adaptive-memory errors."""


class MemoryDisabledError(MemoryError):
    """Raised when memory is disabled but a write/read is attempted."""


class MemoryValidationError(MemoryError):
    """Raised when a memory record fails schema validation."""


class SensitiveMemoryRejected(MemoryError):
    """Raised when content contains highly sensitive personal information."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_time(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def safe_component(value: str) -> str:
    """Sanitize a scope/task component for safe keys.

    Accepts both ``/`` and ``\\`` separators plus path-tricky characters.
    Prevents cross-project leakage through scope keys and path traversal.
    """
    name = re.sub(r"[^A-Za-z0-9._-]", "_", str(value or ""))
    name = name.strip("._")
    return name[:120] or "memory"


def new_memory_id() -> str:
    return "mem-" + hashlib.sha256(
        (utc_now() + secrets.token_hex(8)).encode("utf-8")
    ).hexdigest()[:16]


def fingerprint(payload: Dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()


@dataclass
class MemoryRecord:
    memory_id: str
    category: str
    scope: str
    title: str
    content: str
    source_type: str = "user"
    source_task_id: str = ""
    source_url: str = ""
    source_title: str = ""
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)
    last_verified_at: str = field(default_factory=utc_now)
    confidence: float = 0.5
    user_approved: bool = False
    tags: List[str] = field(default_factory=list)
    version: int = 1
    supersedes: List[str] = field(default_factory=list)
    status: str = "candidate"
    schema_version: str = SCHEMA_VERSION
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.category = str(self.category).lower()
        self.status = str(self.status).lower()
        if self.category not in MEMORY_CATEGORIES:
            raise MemoryValidationError(f"unknown memory category: {self.category}")
        if self.status not in MEMORY_STATUSES and self.status != "candidate":
            raise MemoryValidationError(f"unknown memory status: {self.status}")
        self.confidence = float(max(0.0, min(1.0, float(self.confidence or 0.0))))
        self.tags = [str(tag).strip() for tag in (self.tags or []) if str(tag).strip()]
        self.version = int(self.version or 1)
        if not self.memory_id:
            raise MemoryValidationError("memory_id is required")
        if not str(self.title).strip():
            raise MemoryValidationError("title is required")
        if not str(self.content).strip():
            raise MemoryValidationError("content is required")
        if self.scope == "":
            self.scope = "global"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "memory_id": self.memory_id,
            "category": self.category,
            "scope": self.scope,
            "title": self.title,
            "content": self.content,
            "source_type": self.source_type,
            "source_task_id": self.source_task_id,
            "source_url": self.source_url,
            "source_title": self.source_title,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "last_verified_at": self.last_verified_at,
            "confidence": round(self.confidence, 4),
            "user_approved": bool(self.user_approved),
            "tags": list(self.tags),
            "version": self.version,
            "supersedes": list(self.supersedes),
            "status": self.status,
            "schema_version": self.schema_version,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MemoryRecord":
        return cls(
            memory_id=str(data.get("memory_id", "")),
            category=str(data.get("category", "project")),
            scope=str(data.get("scope", "global")),
            title=str(data.get("title", "")),
            content=str(data.get("content", "")),
            source_type=str(data.get("source_type", "user")),
            source_task_id=str(data.get("source_task_id", "")),
            source_url=str(data.get("source_url", "")),
            source_title=str(data.get("source_title", "")),
            created_at=str(data.get("created_at", utc_now())),
            updated_at=str(data.get("updated_at", utc_now())),
            last_verified_at=str(data.get("last_verified_at", utc_now())),
            confidence=float(data.get("confidence", 0.5)),
            user_approved=bool(data.get("user_approved", False)),
            tags=list(data.get("tags", []) or []),
            version=int(data.get("version", 1)),
            supersedes=list(data.get("supersedes", []) or []),
            status=str(data.get("status", "candidate")),
            schema_version=str(data.get("schema_version", SCHEMA_VERSION)),
            metadata=dict(data.get("metadata", {}) or {}),
        )

    def to_event(self, event: str = "memory") -> Dict[str, Any]:
        payload = {"event": event}
        payload.update(self.to_dict())
        return payload