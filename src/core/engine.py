"""Core Execution Engine for Manus Mini v2.
Orchestrates task execution with real planner, scheduler, policy enforcement, and executor.
"""
from typing import Optional, Dict, Any, List
from decimal import Decimal
from src.core.task import TaskInput
from src.core.modes import ExecutionMode
from src.budget.state import BudgetManager, BudgetState
from src.budget.estimator import CostEstimator
from src.checkpoint.manifest import TaskManifest
from src.checkpoint.manager import CheckpointManager
from src.models.registry import ModelRegistry
from src.core.planner import Planner, Scheduler, WorkUnit
from src.core.policy import ExecutionPolicy
from src.core.executor import OperationExecutor, FakeExecutor
from src.output.manager import OutputManager

class ManusMiniEngine:
    def __init__(self, checkpoint_dir: str = ".manus-mini/checkpoints", executor: Optional[OperationExecutor] = None):
        self.checkpoint_manager = CheckpointManager(checkpoint_dir)
        self.executor = executor or FakeExecutor()
        self.model_registry = ModelRegistry()
        self.budget_manager: Optional[BudgetManager] = None
        self.current_manifest: Optional[TaskManifest] = None
        self.work_units: List[WorkUnit] = []

    def initialize_task(self, task_input: TaskInput) -> TaskManifest:
        if task_input.resume_task_id:
            manifest = self.checkpoint_manager.load_checkpoint(task_input.resume_task_id)
            if manifest:
                self.current_manifest = manifest
                self.budget_manager = BudgetManager(
                    initial_budget=manifest.budget_info["initial"],
                    budget_unit=manifest.budget_info.get("unit", "USD"),
                    emergency_reserve_ratio=manifest.budget_info.get("reserve_ratio", 0.15)
                )
                self.budget_manager.used_budget = Decimal(str(manifest.budget_info["used"]))
                self.work_units = Planner.plan_task(task_input.prompt, task_input.files)
                return manifest

        manifest = TaskManifest(
            task_id=task_input.task_id,
            input_type=task_input.output_type,
            sources=task_input.files,
            initial_budget=task_input.budget,
            budget_unit=task_input.budget_unit,
            execution_mode=task_input.execution_mode.value
        )
        
        self.current_manifest = manifest
        self.budget_manager = BudgetManager(
            initial_budget=task_input.budget,
            budget_unit=task_input.budget_unit
        )
        self.work_units = Planner.plan_task(task_input.prompt, task_input.files)
        manifest.progress["total_units"] = len(self.work_units)
        self.checkpoint_manager.save_checkpoint(manifest)
        return manifest

    def run_next_unit(self) -> bool:
        if not self.budget_manager or not self.current_manifest:
            raise RuntimeError("Engine not initialized.")

        budget_state = self.budget_manager.evaluate_state()
        if budget_state == BudgetState.EXHAUSTED or budget_state == BudgetState.EMERGENCY:
            self.current_manifest.set_status("paused_budget")
            self.current_manifest.errors.append("Budget reached emergency or exhausted state.")
            self.checkpoint_manager.save_checkpoint(self.current_manifest)
            return False

        eligible = Scheduler.get_eligible_units(
            self.work_units,
            self.current_manifest.completed_work,
            self.current_manifest.execution_mode,
            budget_state.value
        )

        if not eligible:
            # Check if all done
            if len(self.current_manifest.completed_work) >= len(self.work_units):
                self.current_manifest.set_status("completed")
                self.checkpoint_manager.save_checkpoint(self.current_manifest)
            return False

        unit = eligible[0]
        self.current_manifest.progress["current_unit"] = unit.id

        # Policy & Routing
        preferred_tier = ExecutionPolicy.adjust_routing(
            ExecutionMode.from_str(self.current_manifest.execution_mode),
            budget_state,
            unit.required_capabilities
        )
        model = self.model_registry.select_best_model(unit.required_capabilities, preferred_tier)
        if not model:
            unit.status = "failed"
            self.current_manifest.errors.append(f"No capable model found for capabilities: {unit.required_capabilities}")
            self.checkpoint_manager.save_checkpoint(self.current_manifest)
            return False

        # Cost Estimation
        est_cost = CostEstimator.estimate_unit_cost(unit.type, model)

        # Budget check
        if not self.budget_manager.can_afford(est_cost, unit.optional):
            self.current_manifest.set_status("paused_budget")
            self.current_manifest.errors.append(f"Cannot afford unit {unit.id} with estimated cost {est_cost}")
            self.checkpoint_manager.save_checkpoint(self.current_manifest)
            return False

        # Execute
        res = self.executor.execute(unit.type, model.model_id, f"Execute work unit {unit.id}")
        if not res["success"]:
            unit.status = "failed"
            self.current_manifest.errors.append(res.get("error", "Execution failed"))
            self.checkpoint_manager.save_checkpoint(self.current_manifest)
            return False

        # Record usage & cost
        self.budget_manager.record_usage(est_cost)
        self.current_manifest.budget_info.update(self.budget_manager.to_dict())
        
        unit.status = "completed"
        self.current_manifest.add_completed_work(unit.id)
        self.current_manifest.progress["completed_units"] = len(self.current_manifest.completed_work)
        self.current_manifest.outputs.append(f"artifact_{unit.id}.py")
        
        self.checkpoint_manager.save_checkpoint(self.current_manifest)
        return True

    def run_to_completion(self) -> str:
        while self.run_next_unit():
            pass
        
        if len(self.current_manifest.completed_work) >= len(self.work_units):
            self.current_manifest.set_status("completed")
            reason = "COMPLETED"
        else:
            self.current_manifest.set_status("partially_completed")
            reason = "PARTIALLY_COMPLETED — BUDGET LIMIT OR PAUSED"

        self.checkpoint_manager.save_checkpoint(self.current_manifest)
        return OutputManager.generate_report(self.current_manifest, reason)
