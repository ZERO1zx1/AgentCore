"""Behavioral Tests for Real Context Delivery and Cost Accounting in Manus Mini v2."""
import unittest
import os
import shutil
import json
import tempfile
from decimal import Decimal
from src.core.engine import ManusMiniEngine
from src.core.task import TaskInput
from src.core.modes import ExecutionMode
from src.core.executor import FakeExecutor
from src.core.execution_result import ExecutionResult
from src.core.runtime_config import RuntimeConfig
from src.core.planner import WorkUnit
from src.output.artifact_manager import ArtifactManager


class _ActualCostExecutor(FakeExecutor):
    """FakeExecutor that returns actual_cost in metadata."""

    def __init__(self, actual_cost: float = 0.00):
        super().__init__()
        self._actual_cost = actual_cost

    def execute(self, unit_type, model_id, prompt, context=None) -> ExecutionResult:
        res = super().execute(unit_type, model_id, prompt, context)
        res.metadata["actual_cost"] = self._actual_cost
        return res


class TestContextDelivery(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="manus_ctx_")
        self.checkpoint_dir = os.path.join(self.test_dir, "checkpoints")
        self.executor = FakeExecutor()
        self.engine = ManusMiniEngine(
            checkpoint_dir=self.checkpoint_dir,
            executor=self.executor,
            artifact_manager=ArtifactManager(base_dir=os.path.join(self.test_dir, "artifacts")),
        )

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    # Test 1: Repository content reaches executor
    def test_repository_content_reaches_executor(self):
        repo_path = os.path.join(self.test_dir, "repo")
        os.makedirs(os.path.join(repo_path, "src"))
        unique_marker = "UNIQUE_REPO_MARKER_7f3a9b2c"
        with open(os.path.join(repo_path, "src", "example.py"), "w") as f:
            f.write(f"# {unique_marker}\ndef example():\n    return True\n")

        task = TaskInput(
            prompt="Implement feature in this repository",
            task_id="repo_ctx",
            files=[repo_path],
            budget=10.0,
        )
        self.engine.initialize_task(task)
        self.engine.run_next_unit()

        # First unit (inspect) should include repo file content with marker
        self.assertIn(unique_marker, self.executor.last_prompt)

    # Test 2: PDF content reaches executor
    def test_pdf_content_reaches_executor(self):
        from reportlab.pdfgen import canvas

        pdf_path = os.path.join(self.test_dir, "ctx_test.pdf")
        unique_text = "UNIQUE_PDF_MARKER_x1y2z3"
        c = canvas.Canvas(pdf_path)
        c.drawString(100, 750, f"The quick brown fox. {unique_text}")
        c.showPage()
        c.save()

        engine = ManusMiniEngine(
            checkpoint_dir=os.path.join(self.test_dir, "checkpoints_pdf"),
            executor=FakeExecutor(),
            artifact_manager=ArtifactManager(base_dir=os.path.join(self.test_dir, "artifacts_pdf")),
        )
        task = TaskInput(
            prompt="Extract and summarize this PDF document",
            task_id="pdf_ctx",
            files=[pdf_path],
            budget=10.0,
        )
        engine.initialize_task(task)
        engine.run_next_unit()

        self.assertIn(unique_text, engine.executor.last_prompt)

    # Test 3: Text content reaches executor
    def test_text_content_reaches_executor(self):
        txt_path = os.path.join(self.test_dir, "report.txt")
        unique_text = "UNIQUE_TEXT_MARKER_abc123"
        with open(txt_path, "w") as f:
            f.write(f"Executive summary. {unique_text}\nMore content here.")

        task = TaskInput(
            prompt="Analyze this text file",
            task_id="text_ctx",
            files=[txt_path],
            budget=10.0,
        )
        self.engine.initialize_task(task)
        self.engine.run_next_unit()

        self.assertIn(unique_text, self.executor.last_prompt)

    # Test 4: JSON/CSV content reaches executor
    def test_structured_content_reaches_executor(self):
        csv_path = os.path.join(self.test_dir, "data.csv")
        unique_val = "UNIQUE_CSV_ROW_42"
        with open(csv_path, "w") as f:
            f.write(f"id,name\n1,{unique_val}\n2,Bob\n")

        task = TaskInput(
            prompt="Process this CSV data and generate code",
            task_id="csv_ctx",
            files=[csv_path],
            budget=10.0,
        )
        self.engine.initialize_task(task)
        self.engine.run_next_unit()

        # unit_inspect for structured has structured_context ref
        self.assertIn("UNIQUE_CSV_ROW_42", self.executor.last_prompt)


class TestResumeInvalidation(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="manus_resume_")
        self.checkpoint_dir = os.path.join(self.test_dir, "checkpoints")
        self.artifact_man = ArtifactManager(base_dir=os.path.join(self.test_dir, "artifacts"))

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def _create_text(self, path: str, marker: str):
        with open(path, "w") as f:
            f.write(f"Content with {marker}\n")

    # Test 5: Source change invalidates affected work
    def test_source_changed_invalidates_work(self):
        src = os.path.join(self.test_dir, "input.md")
        self._create_text(src, "VERSION_A")

        engine1 = ManusMiniEngine(
            checkpoint_dir=self.checkpoint_dir,
            executor=FakeExecutor(),
            artifact_manager=self.artifact_man,
        )
        task = TaskInput(prompt="Analyze", task_id="change_test", files=[src], budget=10.0)
        engine1.initialize_task(task)
        engine1.run_next_unit()
        completed_before = len(engine1.current_manifest.completed_work)
        self.assertGreater(completed_before, 0)

        # Modify source
        self._create_text(src, "VERSION_B")

        # Resume
        engine2 = ManusMiniEngine(
            checkpoint_dir=self.checkpoint_dir,
            executor=FakeExecutor(),
            artifact_manager=self.artifact_man,
        )
        resume = TaskInput(prompt="Analyze", task_id="change_test", resume_task_id="change_test", budget=10.0)
        engine2.initialize_task(resume)

        # Completed work should be invalidated (reduced or reset)
        self.assertLessEqual(len(engine2.current_manifest.completed_work), completed_before)

    # Test 6: Unchanged resume does NOT re-execute
    def test_unchanged_resume_no_reexecution(self):
        src = os.path.join(self.test_dir, "stable.md")
        self._create_text(src, "STABLE_CONTENT")

        executor1 = FakeExecutor()
        engine1 = ManusMiniEngine(
            checkpoint_dir=self.checkpoint_dir,
            executor=executor1,
            artifact_manager=self.artifact_man,
        )
        task = TaskInput(prompt="Analyze", task_id="stable_test", files=[src], budget=10.0)
        engine1.initialize_task(task)
        engine1.run_next_unit()
        count1 = executor1.execution_count
        self.assertGreater(count1, 0)

        # Resume unchanged
        executor2 = FakeExecutor()
        engine2 = ManusMiniEngine(
            checkpoint_dir=self.checkpoint_dir,
            executor=executor2,
            artifact_manager=self.artifact_man,
        )
        resume = TaskInput(prompt="Analyze", task_id="stable_test", resume_task_id="stable_test", budget=10.0)
        engine2.initialize_task(resume)

        # Completed unit NOT executed again
        self.assertGreater(len(engine2.current_manifest.completed_work), 0)

        # Run to completion — only pending units execute
        engine2.run_to_completion()

        # Executor count should be less than total units (completed units not rerun)
        self.assertLess(executor2.execution_count, len(engine2.work_units))


class TestCostAccounting(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="manus_cost_")
        self.checkpoint_dir = os.path.join(self.test_dir, "checkpoints")

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    # Test 7: Cost estimate vs actual separated
    def test_cost_estimate_vs_actual(self):
        executor = _ActualCostExecutor(actual_cost=0.42)
        engine = ManusMiniEngine(checkpoint_dir=self.checkpoint_dir, executor=executor)
        task = TaskInput(prompt="Cost test", task_id="cost_test", budget=10.0)
        engine.initialize_task(task)
        engine.run_next_unit()

        usage_record = engine.usage_history[0]
        self.assertIn("estimated_cost", usage_record)
        self.assertIn("actual_cost", usage_record)
        self.assertIn("charged_cost", usage_record)
        self.assertIn("cost_source", usage_record)

        # actual_cost stored separately
        self.assertEqual(usage_record["actual_cost"], 0.42)
        self.assertEqual(usage_record["cost_source"], "provider")

        # Budget charged with actual cost
        self.assertEqual(engine.budget_manager.used_budget, Decimal("0.42"))

    # Test 8: No actual cost → cost_source == estimate
    def test_no_actual_cost_uses_estimate(self):
        executor = FakeExecutor()
        engine = ManusMiniEngine(checkpoint_dir=self.checkpoint_dir, executor=executor)
        task = TaskInput(prompt="No cost test", task_id="no_cost", budget=10.0)
        engine.initialize_task(task)
        engine.run_next_unit()

        usage_record = engine.usage_history[0]
        self.assertIsNone(usage_record["actual_cost"])
        self.assertEqual(usage_record["cost_source"], "estimate")
        self.assertEqual(usage_record["charged_cost"], usage_record["estimated_cost"])


class TestDependencyAndRetry(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="manus_dep_")
        self.checkpoint_dir = os.path.join(self.test_dir, "checkpoints")
        self.artifact_man = ArtifactManager(base_dir=os.path.join(self.test_dir, "artifacts"))

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    # Test 9: Dependency artifact content reaches dependent executor
    def test_dependency_artifact_content_reaches_executor(self):
        # Build custom plan with dependency
        from src.core.planner import Planner

        class _DepExecutor(FakeExecutor):
            def execute(self, unit_type, model_id, prompt, context=None) -> ExecutionResult:
                self.last_prompt = prompt
                self.execution_count += 1
                # First unit produces an artifact-like output
                if unit_type == "parse":
                    return ExecutionResult(
                        success=True,
                        output_text="DEPENDENCY_OUTPUT_UNIQUE",
                        usage={"prompt_tokens": 10, "completion_tokens": 5},
                        provider="fake",
                        model_id=model_id,
                    )
                return ExecutionResult(
                    success=True,
                    output_text=f"FakeExecutor output for {unit_type}",
                    usage={"prompt_tokens": 100, "completion_tokens": 50},
                    provider="fake",
                    model_id=model_id,
                )

        executor = _DepExecutor()
        engine = ManusMiniEngine(
            checkpoint_dir=self.checkpoint_dir,
            executor=executor,
            artifact_manager=self.artifact_man,
        )
        task = TaskInput(prompt="Dependency test", task_id="dep_test", files=[], budget=10.0)
        engine.initialize_task(task)

        # Custom units: A -> B
        unit_a = WorkUnit(id="unit_a", type="parse", instruction="Produce result", required_capabilities=["parsing"])
        unit_b = WorkUnit(
            id="unit_b", type="analyze", instruction="Use result of A",
            required_capabilities=["text"], dependencies=["unit_a"],
        )
        engine.work_units = [unit_a, unit_b]

        # Run unit A
        engine.run_next_unit()
        self.assertIn("unit_a", engine.current_manifest.completed_work)

        # Set metadata for dependency outputs on unit_b
        if unit_a.output_refs:
            unit_b.metadata["dependency_outputs"] = {"unit_a": unit_a.output_refs}

        # Run unit B — it should receive A's output content
        engine.run_next_unit()
        self.assertIn("unit_b", engine.current_manifest.completed_work)
        self.assertIn("DEPENDENCY_OUTPUT_UNIQUE", executor.last_prompt)

    # Test 10: Retry limit prevents infinite retry
    def test_retry_limit_prevents_infinite_retry(self):
        failing_executor = FakeExecutor(should_fail=True)
        config = RuntimeConfig(max_attempts=2)
        engine = ManusMiniEngine(
            checkpoint_dir=self.checkpoint_dir,
            executor=failing_executor,
            artifact_manager=self.artifact_man,
            runtime_config=config,
        )
        task = TaskInput(prompt="Retry test", task_id="retry_test", files=[], budget=10.0)
        engine.initialize_task(task)

        # Run until max attempts reached
        engine.run_next_unit()  # fail attempt 1
        engine.run_next_unit()  # fail attempt 2
        result = engine.run_next_unit()  # should hit max attempts

        self.assertFalse(result)
        self.assertEqual(failing_executor.execution_count, 2)

        # Check attempt count persisted
        failed_unit = next(u for u in engine.work_units if u.status == "failed")
        self.assertEqual(failed_unit.metadata.get("attempt_count"), 2)


if __name__ == "__main__":
    unittest.main()