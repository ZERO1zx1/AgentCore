"""Checkpoint Manager for Credit-Safe Agent.
Manages atomic unit checkpoints, git status/commits, and manifest persistence.
"""
import os
import json
from typing import Dict, Any, Optional
from src.checkpoint.manifest import TaskManifest

class CheckpointManager:
    def __init__(self, checkpoint_dir: str = ".agentcore/checkpoints"):
        self.checkpoint_dir = checkpoint_dir
        os.makedirs(self.checkpoint_dir, exist_ok=True)

    def get_manifest_path(self, task_id: str) -> str:
        return os.path.join(self.checkpoint_dir, f"{task_id}_manifest.json")

    def save_checkpoint(self, manifest: TaskManifest) -> str:
        path = self.get_manifest_path(manifest.task_id)
        manifest.save(path)
        return path

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
