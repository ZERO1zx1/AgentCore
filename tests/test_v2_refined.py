import unittest
import os
import shutil
from decimal import Decimal
from src.core.engine import ManusMiniEngine
from src.core.task import TaskInput
from src.core.modes import ExecutionMode
from src.budget.state import BudgetState, BudgetManager
from src.core.executor import FakeExecutor
from src.checkpoint.manifest import TaskManifest

class TestManusMiniV2Refined(unittest.TestCase):
    def setUp(self):
        self.test_dir = ".test_manus_mini_refined"
        os.makedirs(self.test_dir, exist_ok=True)
        self.checkpoint_dir = os.path.join(self.test_dir, "checkpoints")
        self.engine = ManusMiniEngine(checkpoint_dir=self.checkpoint_dir)

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_decimal_safety_and_resume(self):
        task_id = "decimal_test"
        task = TaskInput(
            prompt="Test Decimal resume",
            task_id=task_id,
            budget=10.0,
            budget_unit="credits"
        )
        self.engine.initialize_task(task)
        self.engine.run_next_unit() # Execute one unit
        
        # Verify initial used is Decimal
        self.assertIsInstance(self.engine.budget_manager.used_budget, Decimal)
        
        # Resume in new engine
        engine2 = ManusMiniEngine(checkpoint_dir=self.checkpoint_dir)
        task_resume = TaskInput(prompt="Test Decimal resume", task_id=task_id, resume_task_id=task_id)
        engine2.initialize_task(task_resume)
        
        # Verify resumed used is still handled as Decimal
        self.assertIsInstance(engine2.budget_manager.used_budget, Decimal)
        self.assertEqual(engine2.budget_manager.used_budget, Decimal('0.01'))
        
        # Execute another unit
        success = engine2.run_next_unit()
        self.assertTrue(success)
        self.assertIsInstance(engine2.budget_manager.used_budget, Decimal)

    def test_budget_unit_formatting(self):
        # USD
        bm_usd = BudgetManager(initial_budget=10.0, budget_unit="USD")
        self.assertEqual(bm_usd.format_amount(10.0), "$10.00")
        
        # Credits
        bm_cred = BudgetManager(initial_budget=100.0, budget_unit="credits")
        self.assertEqual(bm_cred.format_amount(100.0), "100.00 credits")

    def test_execution_mode_behavior_difference(self):
        # CREDIT_SAFE mode should skip optional P4 units if budget is not NORMAL
        task_id = "mode_test"
        task = TaskInput(
            prompt="Test mode difference with repository",  # trigger repo plan which has unit_polish
            task_id=task_id,
            budget=0.5,  # Low budget
            execution_mode=ExecutionMode.CREDIT_SAFE,
            repository=".",  # Use current dir as repository to trigger repo plan
        )
        self.engine.initialize_task(task)
        
        # Spend some to trigger CONSERVE/CRITICAL
        self.engine.budget_manager.record_usage(0.3)
        self.engine.current_manifest.budget_info.update(self.engine.budget_manager.to_dict())
        
        # Run until completion
        report = self.engine.run_to_completion()
        
        # Verify P4 polish unit exists (repo plan includes it)
        if any(u.id == "unit_polish" for u in self.engine.work_units):
            self.assertNotIn("unit_polish", self.engine.current_manifest.completed_work)
        
        # FULL mode with normal budget should attempt P4 if it can
        engine_full = ManusMiniEngine(checkpoint_dir=os.path.join(self.test_dir, "checkpoints_full"))
        task_full = TaskInput(
            prompt="Test mode difference with repository",
            task_id="mode_test_full",
            budget=10.0,
            execution_mode=ExecutionMode.FULL,
            repository=".",
        )
        engine_full.initialize_task(task_full)
        engine_full.run_to_completion()
        if any(u.id == "unit_polish" for u in engine_full.work_units):
            self.assertIn("unit_polish", engine_full.current_manifest.completed_work)

    def test_end_to_end_resume_flow(self):
        task_id = "e2e_resume"
        # 1. Start task with tight budget
        task = TaskInput(
            prompt="E2E Resume Test",
            task_id=task_id,
            budget=0.03, # Enough for ~2 units (0.01 each + reserve)
            execution_mode=ExecutionMode.AUTO
        )
        self.engine.initialize_task(task)
        report1 = self.engine.run_to_completion()
        
        self.assertIn(self.engine.current_manifest.status, ["PARTIALLY_COMPLETED", "COMPLETED"])
        completed_count = len(self.engine.current_manifest.completed_work)
        self.assertLess(completed_count, len(self.engine.work_units))
        
        # 2. Resume with more budget
        engine2 = ManusMiniEngine(checkpoint_dir=self.checkpoint_dir)
        task_resume = TaskInput(
            prompt="E2E Resume Test",
            task_id=task_id,
            resume_task_id=task_id,
            budget=5.0 # Increased budget
        )
        engine2.initialize_task(task_resume)
        # Update budget in manifest for resumed task
        engine2.budget_manager.initial_budget = Decimal("5.0")
        engine2.current_manifest.budget_info.update(engine2.budget_manager.to_dict())
        
        report2 = engine2.run_to_completion()
        
        self.assertEqual(engine2.current_manifest.status, "COMPLETED")
        self.assertEqual(len(engine2.current_manifest.completed_work), len(engine2.work_units))
        # Ensure units 1-N were not rerun (completed_units should match total_units)
        self.assertEqual(engine2.current_manifest.progress["completed_units"], len(engine2.work_units))

if __name__ == "__main__":
    unittest.main()
