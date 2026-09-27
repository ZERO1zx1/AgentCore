"""Adaptive Memory Store.

Append-only JSONL event log at ``<root>/.agent-memory/adaptive-memory.jsonl``.

Event types:
  - memory       full MemoryRecord snapshot (create/update/approve/verify)
  - transition   status change (candidate->active/rejected, active->stale, ...)
  - feedback     a user feedback verdict on a memory_id (audit trail)

``adaptive-state.json`` holds the user-controlled enabled flag. All destructive
operations are soft (reversible) transitions. Writes are serialized per store
instance so concurrent in-process access cannot interleave partial lines.
"""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from src.adaptive.evaluation import AdaptiveEvaluation
from src.adaptive.feedback import (
    FEEDBACK_VERDICTS, apply_confidence, durable_reject, is_negative,
)
from src.adaptive.injection import scan_injection, strip_dangerous_segments
from src.adaptive.redaction import (
    REDACTED, assert_not_sensitive, contains_secret, redact_secrets,
)
from src.adaptive.retrieval import (
    MemoryRecallReport, build_citation, is_stale, rank,
)
from src.adaptive.schema import (
    MemoryDisabledError, MemoryRecord, MemoryValidationError,
    SensitiveMemoryRejected, new_memory_id, safe_component, utc_now,
)

class AdaptiveMemoryStore:
    """Local, privacy-first memory store with approval-gated writes."""

    def __init__(self, root: str = ".", enabled: bool = True,
                 max_bytes: int = 4 * 1024 * 1024,
                 evaluation: Optional[AdaptiveEvaluation] = None):
        self.root = Path(root).resolve()
        self.memory_dir = self.root / ".agent-memory"
        self.path = self.memory_dir / "adaptive-memory.jsonl"
        self.state_path = self.memory_dir / "adaptive-state.json"
        self.eval_path = self.memory_dir / "adaptive-evaluation.json"
        self.max_bytes = max_bytes
        self._default_enabled = bool(enabled)
        self._write_lock = threading.RLock()
        self.evaluation = evaluation or AdaptiveEvaluation(self.eval_path)

    # ------------------------------------------------------------------ state
    def is_enabled(self) -> bool:
        if not self.state_path.exists():
            return self._default_enabled
        try:
            data = json.loads(self.state_path.read_text(encoding="utf-8"))
            return bool(data.get("enabled", True))
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return self._default_enabled

    def set_enabled(self, enabled: bool) -> bool:
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        temporary = self.state_path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps({"enabled": bool(enabled), "updated_at": utc_now()}),
            encoding="utf-8",
        )
        temporary.replace(self.state_path)
        return bool(enabled)

    def _load_state(self) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, List[Dict[str, Any]]]]:
        """Return (records_by_id, feedback_by_id) rebuilt from the event log."""
        if not self.path.exists() or self.path.stat().st_size > self.max_bytes:
            return {}, {}
        records: Dict[str, Dict[str, Any]] = {}
        feedback: Dict[str, List[Dict[str, Any]]] = {}
        try:
            lines = self.path.read_text(encoding="utf-8").splitlines()
        except OSError:
            return {}, {}
        for line in lines:
            try:
                event = json.loads(line)
            except (json.JSONDecodeError, TypeError):
                continue  # failure recovery: skip corrupt lines
            if not isinstance(event, dict):
                continue
            etype = event.get("event")
            mid = event.get("memory_id")
            if etype == "memory" and mid:
                records[mid] = dict(event)
            elif etype == "transition" and mid and mid in records:
                records[mid]["status"] = event.get("to_status", records[mid].get("status"))
                records[mid]["updated_at"] = event.get("changed_at", records[mid].get("updated_at"))
                if event.get("reason"):
                    records[mid].setdefault("metadata", {})
                    records[mid]["metadata"]["last_transition_reason"] = event["reason"]
            elif etype == "feedback" and mid:
                feedback.setdefault(mid, []).append(event)
        return records, feedback

    def _append_event(self, event: Dict[str, Any]) -> None:
        with self._write_lock:
            self.memory_dir.mkdir(parents=True, exist_ok=True)
            data = (json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")
            fd = os.open(self.path, os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o600)
            try:
                os.write(fd, data)
                os.fsync(fd)
            finally:
                os.close(fd)

    def _apply_memory_event(self, record: MemoryRecord,
                            event: str = "memory") -> Dict[str, Any]:
        self._append_event(record.to_event(event))
        return record.to_dict()
# --------------------------------------------------------------- creation
    def create_memory(
        self,
        category: str,
        scope: str,
        title: str,
        content: str,
        *,
        source_type: str = "user",
        source_task_id: str = "",
        source_url: str = "",
        source_title: str = "",
        tags: Optional[List[str]] = None,
        confidence: float = 0.5,
        user_approved: bool = False,
        auto_approve: bool = False,
        supersedes: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Create one memory record.

        By default the record is stored as a *candidate* that requires explicit
        user approval before it can influence responses. Pass ``auto_approve``
        only when the user explicitly asked to remember something.
        """
        if not self.is_enabled():
            raise MemoryDisabledError("adaptive memory is disabled")

        full = f"{title}\n{content}"
        redacted, findings = redact_secrets(full)
        assert_not_sensitive(full)

        cleaned, removed = strip_dangerous_segments(content)
        meta = dict(metadata or {})
        if findings:
            meta["redactions"] = findings
        if removed:
            meta["injection_line_removals"] = removed
        flags = scan_injection(content)
        if flags:
            meta["injection_flags"] = [item["id"] for item in flags]

        approved = bool(auto_approve or user_approved)
        record = MemoryRecord(
            memory_id=new_memory_id(),
            category=category,
            scope=str(scope).strip() or "global",
            title=title,
            content=cleaned,
            source_type=source_type,
            source_task_id=source_task_id,
            source_url=source_url,
            source_title=source_title,
            confidence=float(confidence),
            user_approved=approved,
            tags=list(tags or []),
            status="active" if approved else "candidate",
            metadata=meta,
        )
        superseded = list(supersedes or [])
        old_records, _ = self._load_state()

        # Mark superseded records stale (audit trail preserved).
        for old_id in superseded:
            old = old_records.get(old_id)
            if old and old.get("status") not in ("stale", "rejected", "deleted"):
                self._transition(old, "stale", f"superseded by {record.memory_id}")
        if superseded:
            record.supersedes = superseded

        saved = self._apply_memory_event(record)
        self._refresh_evaluation_counters()
        return saved

    def _refresh_evaluation_counters(self) -> None:
        try:
            records, _ = self._load_state()
            if records:
                self.evaluation.data["memories_created"] = len(records)
                self.evaluation.data["memories_approved"] = sum(
                    1 for r in records.values() if r.get("user_approved"))
                self.evaluation.data["memories_rejected"] = sum(
                    1 for r in records.values() if r.get("status") == "rejected")
                self.evaluation.save()
        except Exception:
            pass

    # ---------------------------------------------------- lifecycle controls
    def _require_record(self, memory_id: str,
                        records: Dict[str, Any]) -> Dict[str, Any]:
        if memory_id not in records:
            raise MemoryValidationError(f"memory not found: {memory_id}")
        return records[memory_id]

    def approve_memory(self, memory_id: str) -> Dict[str, Any]:
        records, _ = self._load_state()
        record = self._require_record(memory_id, records)
        if record.get("status") != "candidate":
            raise MemoryValidationError(
                f"memory {memory_id} is not a candidate (status={record.get('status')})")
        record["user_approved"] = True
        self._append_event({"event": "memory", **record})
        self._transition(record, "active", "approved by user")
        self._refresh_evaluation_counters()
        return record

    def reject_memory(self, memory_id: str,
                      reason: str = "rejected by user") -> Dict[str, Any]:
        records, _ = self._load_state()
        record = self._require_record(memory_id, records)
        if record.get("status") == "deleted":
            raise MemoryValidationError(f"memory {memory_id} is already deleted")
        self._transition(record, "rejected", reason)
        self._refresh_evaluation_counters()
        return record

    def verify_memory(self, memory_id: str) -> Dict[str, Any]:
        records, _ = self._load_state()
        record = self._require_record(memory_id, records)
        record["last_verified_at"] = utc_now()
        record["updated_at"] = utc_now()
        self._append_event({"event": "memory", **record})
        return record

    def correct_memory(self, memory_id: str, *,
                       content: Optional[str] = None,
                       title: Optional[str] = None,
                       tags: Optional[List[str]] = None,
                       confidence: Optional[float] = None,
                       scope: Optional[str] = None) -> Dict[str, Any]:
        """Create a corrected version; the old record is superseded (stale)."""
        records, _ = self._load_state()
        old = self._require_record(memory_id, records)
        new_content = content if content is not None else old.get("content", "")
        full = f"{old.get('title', '')}\n{new_content}"
        redacted, findings = redact_secrets(full)
        assert_not_sensitive(full)
        cleaned, _ = strip_dangerous_segments(new_content)
        meta = dict(old.get("metadata", {}) or {})
        if findings:
            meta["redactions"] = findings
        created = self.create_memory(
            category=old["category"],
            scope=scope or old.get("scope", "global"),
            title=title or old.get("title", ""),
            content=cleaned,
            source_type=old.get("source_type", "user"),
            source_task_id=old.get("source_task_id", ""),
            source_url=old.get("source_url", ""),
            source_title=old.get("source_title", ""),
            tags=list(tags if tags is not None else old.get("tags", []) or []),
            confidence=float(confidence if confidence is not None
                             else old.get("confidence", 0.5)),
            user_approved=bool(old.get("user_approved", False)),
            auto_approve=bool(old.get("user_approved", False)),
            supersedes=[memory_id],
            metadata=dict(meta),
        )
        self.evaluation.record_correction()
        return created

    def delete_memory(self, memory_id: str, hard: bool = False) -> bool:
        """Soft-delete a memory (reversible). ``hard`` rewrites the log."""
        records, _ = self._load_state()
        self._require_record(memory_id, records)
        if not hard:
            record = self._require_record(memory_id, records)
            self._transition(record, "deleted", "deleted by user")
            self._refresh_evaluation_counters()
            return True
        with self._write_lock:
            kept = []
            for line in self.path.read_text(encoding="utf-8").splitlines():
                try:
                    event = json.loads(line)
                except (json.JSONDecodeError, TypeError):
                    continue
                if isinstance(event, dict) and event.get("memory_id") == memory_id:
                    continue
                kept.append(line)
            body = "\n".join(kept)
            self.path.write_text(body + ("\n" if kept else ""), encoding="utf-8")
        return True

    def clear_project(self, scope: str) -> int:
        records, _ = self._load_state()
        count = 0
        for record in records.values():
            if (record.get("scope") == scope
                    and record.get("status") not in ("deleted", "rejected")):
                self._transition(record, "deleted", f"cleared project scope: {scope}")
                count += 1
        self._refresh_evaluation_counters()
        return count

    def clear_all(self, confirmed: bool = False) -> int:
        if not confirmed:
            raise MemoryValidationError("clear_all requires confirmed=True")
        records, _ = self._load_state()
        count = 0
        for record in records.values():
            if record.get("status") in ("active", "candidate", "stale"):
                self._transition(record, "deleted", "cleared all memory")
                count += 1
        self._refresh_evaluation_counters()
        return count

    def forget_task(self, task_id: str) -> int:
        records, _ = self._load_state()
        count = 0
        for record in records.values():
            if record.get("status") in ("deleted", "rejected"):
                continue
            relates = (
                record.get("source_task_id") == task_id
                or record.get("scope") == f"task:{safe_component(task_id)}"
            )
            if relates:
                self._transition(record, "deleted", f"forgot task: {task_id}")
                count += 1
        self._refresh_evaluation_counters()
# ------------------------------------------------------------- reads
    def list_memories(self, category: Optional[str] = None,
                      scope: Optional[str] = None,
                      status: Optional[str] = None,
                      limit: int = 100) -> List[Dict[str, Any]]:
        records, _ = self._load_state()
        results = []
        for record in records.values():
            if category and record.get("category") != category:
                continue
            if scope and record.get("scope") != scope:
                continue
            if status and record.get("status") != status:
                continue
            results.append(dict(record))
        results.sort(key=lambda r: r.get("updated_at", ""), reverse=True)
        return results[: max(1, int(limit))]

    def inspect(self, memory_id: str) -> Dict[str, Any]:
        records, feedback = self._load_state()
        record = self._require_record(memory_id, records)
        return {
            "memory": dict(record),
            "feedback": list(feedback.get(memory_id, [])),
            "citation": build_citation(record),
        }

    def recall(self, query: str, *, scope: Optional[str] = None,
               category: Optional[str] = None, limit: int = 5,
               include_stale: bool = False,
               include_rejected: bool = False,
               record_recall: bool = True) -> Tuple[List[Dict[str, Any]], MemoryRecallReport]:
        """Return (matches, report). Only approved active memories are used."""
        if not self.is_enabled():
            report = MemoryRecallReport(query, scope, True, ())
            if record_recall:
                self.evaluation.record_recall(hits=0)
            return [], report
        records, _ = self._load_state()
        candidates = []
        for record in records.values():
            status = record.get("status")
            if status == "rejected" and include_rejected:
                pass
            elif status == "stale":
                if not include_stale:
                    continue
            elif status != "active":
                continue
            if category and record.get("category") != category:
                continue
            if scope and record.get("scope") != scope and record.get("scope") != "global":
                continue
            candidates.append(dict(record))
        ranked = rank(candidates, query, scope=scope)
        selected = ranked[: max(1, int(limit))]
        conflicts = self._conflicts_between(selected)
        matches = []
        for item in selected:
            entry = {
                "memory_id": item["memory_id"],
                "category": item.get("category"),
                "scope": item.get("scope"),
                "title": item.get("title"),
                "content": str(item.get("content", ""))[:500],
                "confidence": item.get("confidence"),
                "user_approved": item.get("user_approved"),
                "source_type": item.get("source_type"),
                "source_url": item.get("source_url", ""),
                "source_task_id": item.get("source_task_id", ""),
                "last_verified_at": item.get("last_verified_at"),
                "score": item.get("score"),
                "reasons": [
                    f"scope={'match' if (not scope or item.get('scope') in (scope, 'global')) else 'other'}",
                    f"approved={bool(item.get('user_approved'))}",
                    f"confidence={item.get('confidence')}",
                ],
                "citation": build_citation(item),
            }
            matches.append(entry)
        if record_recall:
            self.evaluation.record_recall(hits=len(matches))
        report = MemoryRecallReport(query, scope, False, tuple(matches), tuple(conflicts))
        return matches, report

    def _conflicts_between(self, records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Show conflicts between selected records on the same scope/category."""
        from src.adaptive.retrieval import TOKEN_RE as _TOKEN_RE
        conflicts = []
        for i in range(len(records)):
            for j in range(i + 1, len(records)):
                left, right = records[i], records[j]
                if left.get("scope") != right.get("scope"):
                    continue
                if left.get("category") != right.get("category"):
                    continue
                a = set(_TOKEN_RE.findall(
                    f"{left.get('title')} {left.get('content')}".lower()))
                b = set(_TOKEN_RE.findall(
                    f"{right.get('title')} {right.get('content')}".lower()))
                overlap = len(a & b) / max(1, len(a | b))
                if overlap >= 0.35 and left.get("content") != right.get("content"):
                    preferred = max(left, right, key=lambda r: (
                        r.get("user_approved", False), r.get("created_at", "")))
                    conflicts.append({
                        "memory_ids": [left["memory_id"], right["memory_id"]],
                        "overlap": round(overlap, 3),
                        "note": "conflicting memories: prefer newer approved information",
                        "prefer": preferred["memory_id"],
                    })
        return conflicts

    def record_feedback(self, memory_id: str, verdict: str, *,
                        evidence: str = "", task_id: str = "") -> Dict[str, Any]:
        """Record user feedback, adjust confidence, and audit it."""
        if verdict not in FEEDBACK_VERDICTS:
            raise MemoryValidationError(f"unknown feedback verdict: {verdict}")
        records, _ = self._load_state()
        record = self._require_record(memory_id, records)
        old_confidence = float(record.get("confidence", 0.5))
        new_confidence = apply_confidence(old_confidence, verdict)
        record["confidence"] = new_confidence
        record["updated_at"] = utc_now()
        meta = record.setdefault("metadata", {})
        if is_negative(verdict):
            meta["negative_feedback"] = int(meta.get("negative_feedback", 0)) + 1
        else:
            meta["positive_feedback"] = int(meta.get("positive_feedback", 0)) + 1
        self._append_event({"event": "memory", **record})
        self._append_event({
            "event": "feedback",
            "memory_id": memory_id,
            "verdict": verdict,
            "evidence": str(evidence)[:500],
            "task_id": task_id,
            "created_at": utc_now(),
        })
        if durable_reject(int(meta.get("negative_feedback", 0)),
                          float(record.get("confidence", 0.5))) \
                and not record.get("user_approved"):
            self._transition(record, "rejected",
                             "repeated negative feedback without user approval")
        self.evaluation.record_feedback()
        return record

    def mark_stale_by_age(self, now=None) -> List[str]:
        """Persist stale transitions for active records past their category TTL."""
        from src.adaptive.retrieval import is_stale as _is_stale
        records, _ = self._load_state()
        stale_ids = []
        for record in records.values():
            if record.get("status") != "active":
                continue
            category = record.get("category", "project")
            if _is_stale(record, category, now):
                self._transition(record, "stale", "past category freshness TTL")
                stale_ids.append(record["memory_id"])
        if stale_ids:
            self.evaluation.record_stale(len(stale_ids))
        return stale_ids

    def stats(self) -> Dict[str, Any]:
        records, _ = self._load_state()
        counts = {status: 0 for status in
                  ("active", "candidate", "stale", "rejected", "deleted")}
        by_category = {}
        for record in records.values():
            status = record.get("status", "candidate")
            counts[status] = counts.get(status, 0) + 1
            cat = record.get("category", "project")
            by_category[cat] = by_category.get(cat, 0) + 1
        return {
            "enabled": self.is_enabled(),
            "path": str(self.path),
            "total_records": len(records),
            "by_status": counts,
            "by_category": by_category,
            "stale_count": counts.get("stale", 0),
            "bytes": self.path.stat().st_size if self.path.exists() else 0,
        }
# --------------------------------------------------------------- export/import
    def export(self, path: str, *, scope: Optional[str] = None,
               category: Optional[str] = None) -> Dict[str, Any]:
        """Export selected records as a schema-versioned, tamper-evident file."""
        if not self.is_enabled():
            raise MemoryDisabledError("adaptive memory is disabled")
        records, _ = self._load_state()
        selected = []
        for record in records.values():
            if scope and record.get("scope") != scope:
                continue
            if category and record.get("category") != category:
                continue
            if record.get("status") == "deleted":
                continue
            selected.append({key: record.get(key) for key in (
                "memory_id", "category", "scope", "title", "content",
                "source_type", "source_task_id", "source_url", "source_title",
                "created_at", "updated_at", "last_verified_at", "confidence",
                "user_approved", "tags", "version", "supersedes", "status",
                "schema_version", "metadata")})
        from src.adaptive.schema import SCHEMA_VERSION, fingerprint
        base = {
            "schema_version": SCHEMA_VERSION,
            "exported_at": utc_now(),
            "scope": scope,
            "category": category,
            "records": selected,
        }
        payload = {**base, "sha256": fingerprint(base)}
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(payload, indent=2, ensure_ascii=False),
                          encoding="utf-8")
        return {"exported": len(selected), "path": str(target)}

    def import_memories(self, path: str, *, scope: Optional[str] = None) -> List[str]:
        """Import a trusted export file after re-running all safety gates."""
        if not self.is_enabled():
            raise MemoryDisabledError("adaptive memory is disabled")
        from src.adaptive.schema import SCHEMA_VERSION, fingerprint
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        if data.get("schema_version") != SCHEMA_VERSION:
            raise MemoryValidationError(
                f"unsupported schema: {data.get('schema_version')}")
        base = {key: data[key] for key in (
            "schema_version", "exported_at", "scope", "category", "records")}
        if data.get("sha256") != fingerprint(base):
            raise MemoryValidationError("export integrity check failed")
        existing, _ = self._load_state()
        imported = []
        for record in data.get("records", []):
            full_text = f"{record.get('title', '')}\n{record.get('content', '')}"
            redacted, findings = redact_secrets(full_text)
            assert_not_sensitive(full_text)
            cleaned, _ = strip_dangerous_segments(record.get("content", ""))
            meta = dict(record.get("metadata", {}) or {})
            if findings:
                meta["redactions"] = findings
            memory_id = str(record.get("memory_id", ""))
            if memory_id in existing:
                memory_id = new_memory_id()
            rec = MemoryRecord(
                memory_id=memory_id,
                category=str(record.get("category", "project")),
                scope=str(scope or record.get("scope", "global")),
                title=str(record.get("title", "")),
                content=cleaned,
                source_type=str(record.get("source_type", "import")),
                source_task_id=str(record.get("source_task_id", "")),
                source_url=str(record.get("source_url", "")),
                source_title=str(record.get("source_title", "")),
                created_at=str(record.get("created_at", utc_now())),
                updated_at=str(record.get("updated_at", utc_now())),
                last_verified_at=str(record.get("last_verified_at", utc_now())),
                confidence=float(record.get("confidence", 0.5)),
                user_approved=bool(record.get("user_approved", False)),
                tags=list(record.get("tags", []) or []),
                version=int(record.get("version", 1)),
                supersedes=list(record.get("supersedes", []) or []),
                status=str(record.get("status", "candidate")),
                metadata=meta,
            )
            if rec.status == "active" and not rec.user_approved:
                rec.status = "candidate"
            self._apply_memory_event(rec)
            imported.append(rec.memory_id)
        self._refresh_evaluation_counters()
        return imported
