"""Read-only runtime adapter for adaptive-local-memory JSONL stores."""
import json
import re
from pathlib import Path
from typing import Any, Dict, List

TOKEN_RE = re.compile(r"[a-z0-9_./:+-]{2,}", re.I)


class LocalMemoryStore:
    def __init__(self, root: str = ".", max_bytes: int = 512 * 1024):
        self.path = Path(root).resolve() / ".agent-memory" / "lessons.jsonl"
        self.max_bytes = max_bytes

    def recall(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        if not self.path.exists() or self.path.stat().st_size > self.max_bytes:
            return []
        lessons: Dict[str, Dict[str, Any]] = {}
        feedback: Dict[str, List[Dict[str, Any]]] = {}
        try:
            lines = self.path.read_text(encoding="utf-8").splitlines()
        except OSError:
            return []
        for line in lines:
            try: event = json.loads(line)
            except (json.JSONDecodeError, TypeError): continue
            if event.get("event") == "lesson" and event.get("id"): lessons[event["id"]] = event
            elif event.get("event") == "feedback" and event.get("lesson_id"): feedback.setdefault(event["lesson_id"], []).append(event)
        query_tokens = set(TOKEN_RE.findall(query.lower()))
        ranked = []
        for lesson in lessons.values():
            text = " ".join(str(lesson.get(k, "")) for k in ("problem", "cause", "action", "scope")) + " " + " ".join(lesson.get("tags", []))
            overlap = len(query_tokens & set(TOKEN_RE.findall(text.lower())))
            if not overlap: continue
            confidence = .65 if lesson.get("status") == "verified" else .35
            for item in feedback.get(lesson["id"], []): confidence += .08 if item.get("result") == "success" else -.22
            ranked.append((overlap, max(0.0, min(1.0, confidence)), lesson))
        ranked.sort(key=lambda item: (item[0], item[1], item[2].get("created_at", "")), reverse=True)
        return [{"id": lesson["id"], "problem": lesson.get("problem", ""), "cause": lesson.get("cause", ""), "action": lesson.get("action", ""), "evidence": lesson.get("evidence", ""), "confidence": round(confidence, 2)} for _, confidence, lesson in ranked[:limit]]
