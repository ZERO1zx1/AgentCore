"""Refined behavioral tests for AgentCore v2."""
import unittest
import os
import shutil
import tempfile
from decimal import Decimal
from src.core.engine import AgentCoreEngine
from src.core.task import TaskInput
from src.core.modes import ExecutionMode
from src.core.executor import FakeExecutor


class TestAgentCoreV2Refined(unittest.TestCase):
    def setUp(self):
        self.test_dir = ".test_agentcore_refined"
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
        os.makedirs(self.test_dir, exist_ok=True)
        self.checkpoint_dir = os.path.join(self.test_dir, "checkpoints")
        self.engine = AgentCoreEngine(checkpoint_dir=self.checkpoint_dir)

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_budget_unit_formatting(self):
        engine = AgentCoreEngine(checkpoint_dir=os.path.join(self.test_dir, "chk_fmt"))
        task = TaskInput(prompt="Format test", task_id="fmt", budget_unit="EUR")
        engine.initialize_task(task)
        self.assertEqual(engine.budget_manager.format_amount(1.5), "1.50 EUR")

    def test_decimal_safety_and_resume(self):
        task_id = "decimal_resume"
        engine1 = AgentCoreEngine(checkpoint_dir=self.checkpoint_dir)
        task = TaskInput(prompt="Test Decimal resume", task_id=task_id, budget=10.0)
        engine1.initialize_task(task)
        engine1.run_next_unit()
        self.assertIsInstance(engine1.budget_manager.used_budget, Decimal)

        engine2 = AgentCoreEngine(checkpoint_dir=self.checkpoint_dir)
        task_resume = TaskInput(prompt="Test Decimal resume", task_id=task_id, resume_task_id=task_id)
        engine2.initialize_task(task_resume)
        self.assertIsInstance(engine2.budget_manager.used_budget, Decimal)

    def test_end_to_end_resume_flow(self):
        task_id = "resume_flow"
        engine1 = AgentCoreEngine(checkpoint_dir=self.checkpoint_dir)
        task = TaskInput(prompt="Resume flow", task_id=task_id, budget=10.0)
        engine1.initialize_task(task)
        engine1.run_next_unit()
        completed = list(engine1.current_manifest.completed_work)

        engine2 = AgentCoreEngine(checkpoint_dir=self.checkpoint_dir)
        task_resume = TaskInput(prompt="Resume flow", task_id=task_id, resume_task_id=task_id)
        engine2.initialize_task(task_resume)
        self.assertEqual(engine2.current_manifest.completed_work, completed)

    def test_execution_mode_behavior_difference(self):
        # FULL mode with normal budget should include P4 units
        repo_path = os.path.join(self.test_dir, "mode_repo")
        os.makedirs(os.path.join(repo_path, "src"), exist_ok=True)
        with open(os.path.join(repo_path, "src", "main.py"), "w") as f:
            f.write("def main():\n    pass\n")

        engine_full = AgentCoreEngine(checkpoint_dir=os.path.join(self.test_dir, "checkpoints_full"))
        task_full = TaskInput(
            prompt="Polish repository",
            task_id="full_mode",
            files=[repo_path],
            execution_mode=ExecutionMode.FULL,
            budget=10.0,
        )
        engine_full.initialize_task(task_full)
        eligible_full = engine_full.work_units
        self.assertTrue(any(u.priority == "P4" for u in eligible_full))

        # CREDIT_SAFE mode should still plan P4 units, but scheduler skips them under CRITICAL budget
        engine_cs = AgentCoreEngine(checkpoint_dir=os.path.join(self.test_dir, "checkpoints_cs"))
        task_cs = TaskInput(
            prompt="Tight budget for repo",
            task_id="cs_mode",
            files=[repo_path],
            execution_mode=ExecutionMode.CREDIT_SAFE,
            budget=0.5,
        )
        engine_cs.initialize_task(task_cs)
        # Verify P4 units exist in plan
        self.assertTrue(any(u.priority == "P4" for u in engine_cs.work_units))
        # Simulate CRITICAL budget state and verify scheduler skips optional P4
        from src.core.planner import Scheduler
        engine_cs.budget_manager.record_usage(0.38)
        eligible = Scheduler.get_eligible_units(
            engine_cs.work_units,
            engine_cs.current_manifest.completed_work,
            engine_cs.current_manifest.execution_mode,
            "CRITICAL",
        )
        # No eligible P4 optional units under CRITICAL
        self.assertFalse(any(u.priority == "P4" and u.optional for u in eligible))


if __name__ == "__main__":
    unittest.main()