import json
import os
import tempfile
import unittest
from pathlib import Path

from src.checkpoint.manifest import TaskManifest
from src.core.context import TaskContext
from src.core.engine import AgentCoreEngine
from src.core.executor import FakeExecutor
from src.core.orchestrator import AdaptiveOrchestrator
from src.core.planner import Planner
from src.core.task import TaskInput
from src.ingestion.router import InputRouter
from src.models.router import ModelRouter
from src.output.artifact_manager import ArtifactManager


class ThreeSkillOrchestrationTest(unittest.TestCase):
    def test_adaptive_profile_activates_three_public_skills(self):
        context = TaskContext("t", "", "AUTO", "text", source_types={".": "repository"}, repository_context={"extensions": {".py": 2, ".png": 1}, "file_tree": ["app.py", "logo.png"]})
        profile = AdaptiveOrchestrator.profile("fix the app", context)
        self.assertEqual(profile.active_skills, ["adaptive-omni-agent", "code-engineer", "credit-safe-agent"])
        self.assertEqual(profile.memory_policy, "evidence-first-bounded-local-lessons")
        self.assertIn("memory_policy", profile.to_dict())
        self.assertIn("code", profile.artifact_types)
        self.assertIn("image", profile.artifact_types)

    def test_code_engineer_still_uses_credit_controller(self):
        context = TaskContext("t", "", "AUTO", "text")
        profile = AdaptiveOrchestrator.profile("repair this", context, "code-engineer")
        self.assertEqual(profile.active_skills, ["code-engineer", "credit-safe-agent"])

    def test_asset_input_builds_multimodal_plan(self):
        with tempfile.TemporaryDirectory() as folder:
            image = Path(folder) / "sample.png"; image.write_bytes(b"not-a-real-png-but-valid-metadata")
            context = InputRouter.route("asset", [str(image)])
            profile = AdaptiveOrchestrator.profile("inspect image", context)
            context.orchestration = profile.to_dict()
            units = Planner.plan_task("inspect image", [str(image)], context, profile.to_dict())
            transform = next(unit for unit in units if unit.id == "unit_transform")
            self.assertIn("multimodal", transform.required_capabilities)
            self.assertEqual(transform.metadata["skill_role"], "code-engineer")

    def test_manifest_v3_roundtrip_preserves_route(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "manifest.json"
            manifest = TaskManifest("t", "text", [])
            manifest.orchestration = {"primary_skill": "adaptive-omni-agent", "active_skills": ["adaptive-omni-agent", "code-engineer", "credit-safe-agent"]}
            manifest.save(str(path)); loaded = TaskManifest.load(str(path))
            self.assertEqual(loaded.schema_version, "3.0")
            self.assertEqual(loaded.orchestration["primary_skill"], "adaptive-omni-agent")

    def test_engine_persists_skill_route_and_memory_hits(self):
        with tempfile.TemporaryDirectory() as folder:
            repo = Path(folder) / "repo"; repo.mkdir(); (repo / "app.py").write_text("print('ok')", encoding="utf-8")
            memory = repo / ".agent-memory"; memory.mkdir();
            (memory / "lessons.jsonl").write_text(json.dumps({"event":"lesson","id":"l-1","created_at":"2026-01-01Z","scope":"project","problem":"python app bug","cause":"bad import","action":"fix import","evidence":"tests pass","tags":["python"],"status":"verified"})+"\n", encoding="utf-8")
            engine = AgentCoreEngine(checkpoint_dir=str(Path(folder)/"checkpoints"), executor=FakeExecutor(), artifact_manager=ArtifactManager(str(Path(folder)/"tasks")), repo_root=str(repo))
            manifest = engine.initialize_task(TaskInput(prompt="fix python app bug", task_id="t", repository=str(repo), budget=10))
            self.assertEqual(manifest.orchestration["primary_skill"], "adaptive-omni-agent")
            self.assertEqual(manifest.orchestration["memory_hit_ids"], ["l-1"])
            self.assertEqual(manifest.orchestration["memory_policy"], "evidence-first-bounded-local-lessons")
            self.assertIn("Primary skill: adaptive-omni-agent", engine._build_execution_prompt(engine.work_units[0]))

    def test_model_router_returns_capable_model(self):
        model = ModelRouter().get_model_for_task("code", required_capabilities=["coding"])
        self.assertIsNotNone(model)
        self.assertIn("coding", model.capabilities)

    def test_multimodal_asset_reaches_executor_as_verified_attachment(self):
        with tempfile.TemporaryDirectory() as folder:
            image = Path(folder) / "sample.png"
            image.write_bytes(b"real-binary-payload")
            executor = FakeExecutor()
            engine = AgentCoreEngine(
                checkpoint_dir=str(Path(folder) / "checkpoints"),
                executor=executor,
                artifact_manager=ArtifactManager(str(Path(folder) / "tasks")),
                repo_root=folder,
            )
            engine.initialize_task(TaskInput(prompt="inspect image", task_id="asset-run", files=[str(image)], budget=10))
            self.assertTrue(engine.run_next_unit())
            attachment = executor.last_context["attachments"][0]
            self.assertEqual(attachment["content_mode"], "path")
            self.assertEqual(attachment["modality"], "image")
            self.assertEqual(attachment["path"], str(image.resolve()))
            self.assertEqual(attachment["size"], len(b"real-binary-payload"))
            self.assertNotIn("real-binary-payload", executor.last_prompt)

    def test_credit_safe_skips_asset_over_attachment_budget(self):
        from src.core.runtime_config import RuntimeConfig
        from src.core.planner import WorkUnit

        with tempfile.TemporaryDirectory() as folder:
            image = Path(folder) / "large.png"
            image.write_bytes(b"12345")
            context = InputRouter.route("asset", [str(image)])
            context.execution_mode = "CREDIT_SAFE"
            resolver = AgentCoreEngine(runtime_config=RuntimeConfig(max_attachment_bytes_credit_safe=4)).context_resolver
            unit = WorkUnit("u", "transform", "P0", "inspect", context_refs=["asset_context"])
            self.assertEqual(resolver.resolve_attachments(context, unit), [])


if __name__ == "__main__": unittest.main()
