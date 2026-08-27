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
        # Sort by mtime (newest first) with a deterministic tiebreaker so rapid
        # saves within the same timestamp tick still keep the truly-latest file.
        manifests.sort(key=lambda item: (os.path.getmtime(item), os.path.basename(item)), reverse=True)
        protected = os.path.abspath(protected_path) if protected_path else None
        # Cap total kept at max_manifests while guaranteeing the protected file
        # is retained. If protected isn't already in the newest N, keep N-1 of
        # the newest plus the protected one (never N+1).
        protected_in_top = protected is not None and protected in {
            os.path.abspath(m) for m in manifests[: self.max_manifests]
        }
        keep_n = self.max_manifests if protected_in_top else self.max_manifests - 1
        keep = {os.path.abspath(m) for m in manifests[:keep_n]}
        if protected is not None:
            keep.add(protected)
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
