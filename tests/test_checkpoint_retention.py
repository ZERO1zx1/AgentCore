"""Regression tests: checkpoint retention never exceeds max_manifests."""
import os
import tempfile

from src.checkpoint.manager import CheckpointManager
from src.checkpoint.manifest import TaskManifest


def _ids(d):
    return {f for f in os.listdir(d) if f.endswith("_manifest.json")}


def test_retention_never_exceeds_max_with_protected():
    with tempfile.TemporaryDirectory() as d:
        cm = CheckpointManager(checkpoint_dir=d, max_manifests=3)
        for i in range(10):
            m = TaskManifest(task_id=f"t{i}", input_type="text", sources=[])
            cm.save_checkpoint(m)  # each save protects its own manifest
        files = _ids(d)
        assert len(files) <= 3
        # The most recent task must survive.
        assert "t9_manifest.json" in files


def test_protected_manifest_kept_within_cap():
    """The explicitly protected manifest is always retained, and the total
    kept never exceeds max_manifests (older non-protected ones are pruned)."""
    with tempfile.TemporaryDirectory() as d:
        cm = CheckpointManager(checkpoint_dir=d, max_manifests=3)
        for i in range(3):
            m = TaskManifest(task_id=f"a{i}", input_type="text", sources=[])
            m.save(cm.get_manifest_path(f"a{i}"))
        for i in range(3, 5):
            m = TaskManifest(task_id=f"a{i}", input_type="text", sources=[])
            m.save(cm.get_manifest_path(f"a{i}"))
        # Protect the oldest manifest at prune time.
        old_path = cm.get_manifest_path("a0")
        cm.prune_old_checkpoints(protected_path=old_path)
        files = _ids(d)
        assert len(files) <= 3
        assert "a0_manifest.json" in files  # protected kept
