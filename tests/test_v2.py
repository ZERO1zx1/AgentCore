import unittest
import os
import shutil
from src.core.engine import ManusMiniEngine
from src.core.task import TaskInput
from src.core.modes import ExecutionMode
from src.budget.state import BudgetState
from decimal import Decimal

class TestManusMiniV2(unittest.TestCase):
    def setUp(self):
        self.test_dir = ".test_manus_mini"
        os.makedirs(self.test_dir, exist_ok=True)
        self.engine = ManusMiniEngine(checkpoint_dir=os.path.join(self.test_dir, "checkpoints"))

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_engine_initialization_and_flow(self):
        task = TaskInput(
            prompt="Build a website from API docs",
            task_id="task_v2_001",
            files=["api.pdf"],
            execution_mode=ExecutionMode.CREDIT_SAFE,
            budget=5.0
        )
        
        manifest = self.engine.initialize_task(task)
        self.assertEqual(manifest.task_id, "task_v2_001")
        self.assertEqual(manifest.budget_info["execution_mode"], "CREDIT_SAFE")
        
        # Execute steps
        success = self.engine.execute_step("inspect_pdf", "parse", 0.1)
        self.assertTrue(success)
        self.assertEqual(self.engine.budget_manager.used_budget, Decimal('0.1'))
        
        success = self.engine.execute_step("generate_code", "code", 0.5)
        self.assertTrue(success)
        
        # Test budget exhaustion (forced)
        self.engine.budget_manager.record_usage(4.0) # Total 4.6 used, $0.4 left (under $0.75 reserve)
        self.assertEqual(self.engine.budget_manager.evaluate_state(), BudgetState.EMERGENCY)
        
        # Should not allow new expensive step
        success = self.engine.execute_step("expensive_validation", "complex", 0.5)
        self.assertFalse(success)
        self.assertEqual(self.engine.current_manifest.status, "paused_budget")

    def test_resumability(self):
        task_id = "resume_test"
        task1 = TaskInput(prompt="Task 1", task_id=task_id, budget=10.0)
        self.engine.initialize_task(task1)
        self.engine.execute_step("step1", "parse", 1.0)
        
        # New engine instance
        engine2 = ManusMiniEngine(checkpoint_dir=os.path.join(self.test_dir, "checkpoints"))
        task2 = TaskInput(prompt="Task 1", task_id=task_id, resume_task_id=task_id)
        manifest = engine2.initialize_task(task2)
        
        self.assertEqual(manifest.budget_info["used"], 1.0)
        self.assertIn("step1", manifest.completed_work)

if __name__ == "__main__":
    unittest.main()
