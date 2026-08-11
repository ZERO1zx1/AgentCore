"""Core Execution Engine for Manus Mini.
Orchestrates the task flow from input to output with budget awareness.
"""
from typing import Optional, Dict, Any
from src.core.task import TaskInput
from src.core.modes import ExecutionMode
from src.budget.state import BudgetManager, BudgetState
from src.checkpoint.manifest import TaskManifest
from src.checkpoint.manager import CheckpointManager
from src.models.router import ModelRouter as ModelRegistry
from src.output.manager import OutputManager

class ManusMiniEngine:
    def __init__(self, checkpoint_dir: str = ".manus-mini/checkpoints"):
        self.checkpoint_manager = CheckpointManager(checkpoint_dir)
        self.budget_manager: Optional[BudgetManager] = None
        self.current_manifest: Optional[TaskManifest] = None

    def initialize_task(self, task_input: TaskInput) -> TaskManifest:
        # Try to resume if requested
        if task_input.resume_task_id:
            manifest = self.checkpoint_manager.load_checkpoint(task_input.resume_task_id)
            if manifest:
                self.current_manifest = manifest
                self.budget_manager = BudgetManager(
                    initial_budget=manifest.budget_info["initial"],
                    emergency_reserve_ratio=manifest.budget_info.get("reserve_ratio", 0.15)
                )
                self.budget_manager.used_budget = manifest.budget_info["used"]
                return manifest

        # Create new manifest
        manifest = TaskManifest(
            task_id=task_input.task_id,
            input_type=task_input.output_type,
            sources=task_input.files,
            initial_budget=task_input.budget
        )
        manifest.budget_info["unit"] = task_input.budget_unit
        manifest.budget_info["execution_mode"] = task_input.execution_mode.value
        
        self.current_manifest = manifest
        self.budget_manager = BudgetManager(initial_budget=task_input.budget)
        return manifest

    def execute_step(self, unit_name: str, task_type: str, estimated_cost: float, is_optional: bool = False):
        if not self.budget_manager or not self.current_manifest:
            raise RuntimeError("Engine not initialized with a task.")

        # Check budget before execution
        if not self.budget_manager.can_afford(estimated_cost, is_optional):
            self.current_manifest.set_status("paused_budget")
            self.checkpoint_manager.checkpoint_unit(self.current_manifest, unit_name, completed=False)
            return False

        # Select model
        budget_state = self.budget_manager.evaluate_state(estimated_cost)
        model = ModelRegistry.get_model_for_task(task_type, budget_state.value)
        
        # Simulate execution and record usage
        # In real scenario, this would call the actual model/tool
        self.budget_manager.record_usage(estimated_cost)
        self.current_manifest.budget_info.update(self.budget_manager.to_dict())
        
        # Checkpoint progress
        self.checkpoint_manager.checkpoint_unit(self.current_manifest, unit_name, completed=True)
        return True

    def finalize(self, reason: str = "COMPLETED"):
        if self.current_manifest:
            self.current_manifest.set_status("completed" if reason == "COMPLETED" else "partially_completed")
            self.checkpoint_manager.save_checkpoint(self.current_manifest)
            return OutputManager.generate_report(self.current_manifest, reason)
        return "No active task to finalize."
