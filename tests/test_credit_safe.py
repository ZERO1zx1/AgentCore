import unittest
import os
import shutil
import json
from decimal import Decimal
from src.budget.state import BudgetManager, BudgetState
from src.models.router import ModelRegistry
from src.checkpoint.manifest import TaskManifest
from src.checkpoint.manager import CheckpointManager

class TestCreditSafeAgent(unittest.TestCase):
    def setUp(self):
        self.test_dir = "/home/ubuntu/manus-mini-skill/.test_checkpoints"
        os.makedirs(self.test_dir, exist_ok=True)
        self.checkpoint_manager = CheckpointManager(checkpoint_dir=self.test_dir)

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_budget_state_transitions(self):
        # Initial $10.0 budget, 15% reserve ($1.5)
        bm = BudgetManager(initial_budget=10.0, emergency_reserve_ratio=0.15)
        
        # NORMAL state
        self.assertEqual(bm.evaluate_state(), BudgetState.NORMAL)
        
        # Spend $6.0 -> $4.0 remaining (40% remaining) -> CONSERVE state (threshold 0.50)
        bm.record_usage(6.0)
        self.assertEqual(bm.evaluate_state(), BudgetState.CONSERVE)
        
        # Spend $2.0 -> $2.0 remaining (20% remaining) -> CRITICAL state (threshold 0.25)
        bm.record_usage(2.0)
        self.assertEqual(bm.evaluate_state(), BudgetState.CRITICAL)
        
        # Spend $0.6 -> $1.4 remaining (under $1.5 reserve) -> EMERGENCY state
        bm.record_usage(0.6)
        self.assertEqual(bm.evaluate_state(), BudgetState.EMERGENCY)
        
        # Spend $1.4 -> $0.0 remaining -> EXHAUSTED state
        bm.record_usage(1.4)
        self.assertEqual(bm.evaluate_state(), BudgetState.EXHAUSTED)

    def test_emergency_reserve_protection(self):
        # Initial $10.0 budget, 15% reserve ($1.5)
        bm = BudgetManager(initial_budget=10.0, emergency_reserve_ratio=0.15)
        
        # NORMAL: Can afford both required and optional
        self.assertTrue(bm.can_afford(1.0, is_optional=False))
        self.assertTrue(bm.can_afford(1.0, is_optional=True))
        
        # CRITICAL: $2.0 remaining
        bm.record_usage(8.0)
        self.assertEqual(bm.evaluate_state(), BudgetState.CRITICAL)
        self.assertTrue(bm.can_afford(0.1, is_optional=False))
        self.assertFalse(bm.can_afford(0.1, is_optional=True)) # Optional work blocked in CRITICAL
        
        # EMERGENCY: $1.2 remaining (under $1.5 reserve)
        bm.record_usage(0.8)
        self.assertEqual(bm.evaluate_state(), BudgetState.EMERGENCY)
        self.assertFalse(bm.can_afford(0.1, is_optional=False)) # All new paid work blocked in EMERGENCY

    def test_model_routing(self):
        # Normal state routing
        self.assertEqual(ModelRegistry.get_model_for_task("summarize", "NORMAL")["id"], "gpt-3.5-cheap")
        self.assertEqual(ModelRegistry.get_model_for_task("code", "NORMAL")["id"], "gpt-4o")
        self.assertEqual(ModelRegistry.get_model_for_task("vision", "NORMAL")["id"], "gpt-4o-reasoning")
        
        # Conserve/Critical state routing (downgrading)
        self.assertEqual(ModelRegistry.get_model_for_task("code", "CRITICAL")["id"], "gpt-4o-mini")
        self.assertEqual(ModelRegistry.get_model_for_task("vision", "CRITICAL")["id"], "gpt-4o")

    def test_manifest_checkpoint_resume(self):
        task_id = "test_task_123"
        manifest = TaskManifest(task_id=task_id, input_type="code", sources=["src/main.py"], initial_budget=10.0)
        
        # Add progress
        manifest.update_progress(completed_units=2, total_units=10, current_unit="unit_3")
        manifest.add_completed_work("unit_1")
        manifest.add_completed_work("unit_2")
        
        # Save checkpoint
        self.checkpoint_manager.save_checkpoint(manifest)
        
        # Load checkpoint
        loaded = self.checkpoint_manager.load_checkpoint(task_id)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.task_id, task_id)
        self.assertEqual(loaded.progress["completed_units"], 2)
        self.assertIn("unit_1", loaded.completed_work)
        self.assertEqual(loaded.input_data["sources"], ["src/main.py"])

if __name__ == "__main__":
    unittest.main()
