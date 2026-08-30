import tempfile
import unittest
from pathlib import Path

from src.core.context import TaskContext
from src.core.orchestrator import AdaptiveOrchestrator
from src.memory.lifecycle import LessonStatus, lesson_is_stale, transition_lesson
from src.memory.safety import SensitiveDataGate
from src.memory.store import LocalMemoryStore


class MemoryGovernanceTests(unittest.TestCase):
    def test_lifecycle_accepts_stale_transition_and_rejects_invalid_transition(self):
        lesson = {"id": "l-1", "status": "verified"}
        self.assertEqual(transition_lesson(lesson, LessonStatus.STALE, "source changed").to_status, "stale")
        with self.assertRaises(ValueError):
            transition_lesson(lesson, LessonStatus.CANDIDATE, "cannot go backwards")

    def test_fingerprint_mismatch_marks_lesson_stale(self):
        self.assertTrue(lesson_is_stale({"source_fingerprints": {"app.py": "old"}}, {"app.py": "new"}))
        self.assertFalse(lesson_is_stale({"source_fingerprints": {"app.py": "same"}}, {"app.py": "same"}))

    def test_sensitive_gate_blocks_credentials_and_personal_data(self):
        self.assertTrue(SensitiveDataGate.inspect({"evidence": "token=abc123456789012345"}))
        self.assertTrue(SensitiveDataGate.inspect({"evidence": "contact a@example.com"}))
        with self.assertRaises(ValueError):
            SensitiveDataGate.assert_safe({"evidence": "api_key=private-value"})

    def test_store_recall_respects_scope_and_fingerprint(self):
        with tempfile.TemporaryDirectory() as folder:
            store = LocalMemoryStore(folder)
            store.record_verified_lesson(scope="project-a", problem="import bug", cause="bad path", action="fix path", evidence="test passed", source_fingerprints={"app.py": "one"})
            self.assertEqual(len(store.recall("import bug", scope="project-a", source_fingerprints={"app.py": "one"})), 1)
            self.assertEqual(store.recall("import bug", scope="project-b", source_fingerprints={"app.py": "one"}), [])
            self.assertEqual(store.recall("import bug", scope="project-a", source_fingerprints={"app.py": "two"}), [])
            self.assertEqual(len(store.mark_stale_lessons({"app.py": "two"}, scope="project-a")), 1)
            self.assertEqual(store.recall("import bug", scope="project-a", source_fingerprints={"app.py": "two"}), [])

    def test_profile_persists_scope_and_task_fingerprint(self):
        context = TaskContext("t", "", "AUTO", "text", source_fingerprints={"app.py": "abc"}, metadata={"memory_scope": "team-a"})
        profile = AdaptiveOrchestrator.profile("fix app", context)
        self.assertEqual(profile.memory_scope, "team-a")
        self.assertEqual(len(profile.task_fingerprint), 64)


if __name__ == "__main__":
    unittest.main()
