"""Artifact Manager for AgentCore.
Persists real execution results to disk inside the task's .agentcore structure.
Manifest entries always point to REAL files.
"""
import os
import re
import json
from typing import Dict, Any, List, Optional


def sanitize_filename(name: str) -> str:
    """Sanitize a filename, removing path separators and dangerous characters."""
    name = os.path.basename(name)  # strip any directory components
    name = re.sub(r'[^A-Za-z0-9._-]', "_", name)
    name = name.strip("._")
    return name or "artifact"


class ArtifactManager:
    def __init__(self, base_dir: str = ".agentcore/tasks"):
        self.base_dir = base_dir

    def task_dir(self, task_id: str) -> str:
        safe = sanitize_filename(task_id)
        return os.path.join(self.base_dir, safe)

    def context_dir(self, task_id: str) -> str:
        return os.path.join(self.task_dir(task_id), "context")

    def artifacts_dir(self, task_id: str) -> str:
        return os.path.join(self.task_dir(task_id), "artifacts")

    def checkpoints_dir(self, task_id: str) -> str:
        return os.path.join(self.task_dir(task_id), "checkpoints")

    def _ensure_dir(self, path: str) -> str:
        # Prevent path traversal: ensure the resolved path stays under base_dir
        resolved = os.path.abspath(path)
        base = os.path.abspath(self.base_dir)
        if not resolved.startswith(base + os.sep) and resolved != base:
            raise ValueError(f"Refusing to write outside artifact base dir: {resolved}")
        os.makedirs(resolved, exist_ok=True)
        return resolved

    def _resolve_under_task(self, task_id: str, category: str, filename: str) -> str:
        safe_name = sanitize_filename(filename)
        dir_path = self._ensure_dir(os.path.join(self.task_dir(task_id), category))
        return os.path.join(dir_path, safe_name)

    def write_text(self, task_id: str, filename: str, content: str) -> str:
        path = self._resolve_under_task(task_id, "artifacts", filename)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return path

    def write_code(self, task_id: str, filename: str, code: str) -> str:
        safe_name = sanitize_filename(filename)
        if not safe_name.endswith(".py"):
            safe_name += ".py"
        return self.write_text(task_id, safe_name, code)

    def write_json(self, task_id: str, filename: str, data: Dict[str, Any]) -> str:
        safe_name = sanitize_filename(filename)
        if not safe_name.endswith(".json"):
            safe_name += ".json"
        path = self._resolve_under_task(task_id, "artifacts", safe_name)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return path

    def write_context(self, task_id: str, filename: str, content: str) -> str:
        path = self._resolve_under_task(task_id, "context", filename)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return path

    def resolve_task_dir(self, task_id: str) -> str:
        return self._ensure_dir(self.task_dir(task_id))