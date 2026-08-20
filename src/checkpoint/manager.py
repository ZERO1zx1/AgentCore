"""Checkpoint Manager for Credit-Safe Agent.
Manages atomic unit checkpoints, git status/commits, and manifest persistence.
"""
import os
import json
from typing import Dict, Any, Optional
from src.checkpoint.manifest import TaskManifest

class CheckpointManager:
    def __init__(self, checkpoint_dir: str = ".agentcore/checkpoints", max_manifests: int = 100):
        self.checkpoint_dir = checkpoint_dir
        self.max_manifests = max(1, int(max_manifests))
        os.makedirs(self.checkpoint_dir, exist_ok=True)

    def get_manifest_path(self, task_id: str) -> str:
        return os.path.join(self.checkpoint_dir, f"{task_id}_manifest.json")

    def save_checkpoint(self, manifest: TaskManifest) -> str:
        path = self.get_manifest_path(manifest.task_id)
        manifest.save(path)
        self.prune_old_checkpoints(protected_path=path)
        return path

    def prune_old_checkpoints(self, protected_path: Optional[str] = None) -> list[str]:
        """Keep the newest task manifests; a task's active manifest is protected."""
        manifests = [os.path.join(self.checkpoint_dir, name) for name in os.listdir(self.checkpoint_dir) if name.endswith("_manifest.json")]
        manifests.sort(key=lambda item: os.path.getmtime(item), reverse=True)
        protected = os.path.abspath(protected_path) if protected_path else None
        keep = set(manifests[: self.max_manifests])
        if protected: keep.add(protected)
        removed = []
        for path in manifests:
            if os.path.abspath(path) in {os.path.abspath(item) for item in keep}: continue
            try: os.remove(path); removed.append(path)
            except OSError: continue
        return removed

    def load_checkpoint(self, task_id: str) -> Optional[TaskManifest]:
        path = self.get_manifest_path(task_id)
        if os.path.exists(path):
            try:
                return TaskManifest.load(path)
            except Exception:
                return None
        return None

    def checkpoint_unit(self, manifest: TaskManifest, unit_name: str, completed: bool = True):
        if completed:
            manifest.add_completed_work(unit_name)
            manifest.progress["completed_units"] = manifest.progress.get("completed_units", 0) + 1
        self.save_checkpoint(manifest)
