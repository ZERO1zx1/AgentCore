"""Sanitized, schema-versioned knowledge pack export and import."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Sequence
import hashlib
import json

from src.memory.governance import MemoryAction, PermissionPolicy, POLICY_VERSION
from src.memory.safety import MemoryPoisoningGate, SensitiveDataGate


PACK_SCHEMA_VERSION = "1.0"


@dataclass(frozen=True)
class KnowledgePack:
    scope: str
    lessons: tuple[Dict[str, Any], ...]
    schema_version: str = PACK_SCHEMA_VERSION
    policy_version: str = POLICY_VERSION

    def payload(self) -> Dict[str, Any]:
        base = {"schema_version": self.schema_version, "policy_version": self.policy_version,
                "scope": self.scope, "lessons": list(self.lessons)}
        digest = hashlib.sha256(json.dumps(base, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
        return {**base, "sha256": digest}


def export_pack(path: str | Path, lessons: Sequence[Mapping[str, Any]], *, scope: str, role: str) -> Path:
    PermissionPolicy.require(role, MemoryAction.EXPORT)
    clean: list[Dict[str, Any]] = []
    for lesson in lessons:
        if lesson.get("status") != "verified" or lesson.get("scope") != scope:
            continue
        values = {key: lesson.get(key, "") for key in ("problem", "cause", "action", "evidence", "tags")}
        SensitiveDataGate.assert_safe(values)
        MemoryPoisoningGate.assert_safe(values)
        clean.append({key: value for key, value in dict(lesson).items() if key not in {"feedback", "personal_data"}})
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(KnowledgePack(scope, tuple(clean)).payload(), indent=2, ensure_ascii=False), encoding="utf-8")
    return target


def import_pack(path: str | Path, *, expected_scope: str, role: str) -> list[Dict[str, Any]]:
    PermissionPolicy.require(role, MemoryAction.IMPORT)
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("schema_version") != PACK_SCHEMA_VERSION or data.get("scope") != expected_scope:
        raise ValueError("knowledge pack schema or scope mismatch")
    supplied = data.get("sha256", "")
    base = {key: data[key] for key in ("schema_version", "policy_version", "scope", "lessons")}
    actual = hashlib.sha256(json.dumps(base, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
    if supplied != actual:
        raise ValueError("knowledge pack integrity check failed")
    lessons = []
    for lesson in data.get("lessons", []):
        values = {key: lesson.get(key, "") for key in ("problem", "cause", "action", "evidence", "tags")}
        SensitiveDataGate.assert_safe(values)
        MemoryPoisoningGate.assert_safe(values)
        lessons.append(dict(lesson))
    return lessons
