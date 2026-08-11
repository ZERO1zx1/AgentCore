"""Core Execution Engine for Manus Mini v2.
Orchestrates task execution with real input routing, planning, scheduling,
policy enforcement, executor injection, artifact management, and resume.
"""
from typing import Optional, Dict, Any, List
from decimal import Decimal
from src.core.task import TaskInput
from src.core.modes import ExecutionMode
from src.core.context import TaskContext
from src.core.execution_result import ExecutionResult
from src.budget.state import BudgetManager, BudgetState
from src.budget.estimator import CostEstimator
from src.checkpoint.manifest import TaskManifest
from src.checkpoint.manager import CheckpointManager
from src.models.registry import ModelRegistry
from src.core.planner import Planner, Scheduler, WorkUnit
from src.core.policy import ExecutionPolicy
from src.core.executor import OperationExecutor, FakeExecutor
from src.output.manager import OutputManager
from src.output.artifact_manager import ArtifactManager
from src.ingestion.router import InputRouter
import json


class ManusMiniEngine:
    def __init__(
        self,
        checkpoint_dir: str = ".manus-mini/checkpoints",
        executor: Optional[OperationExecutor] = None,
        model_registry: Optional[ModelRegistry] = None,
        artifact_manager: Optional[ArtifactManager] = None,
    ):
        self.checkpoint_manager = CheckpointManager(checkpoint_dir)
        self.executor = executor or FakeExecutor()
        self.model_registry = model_registry or ModelRegistry()
        self.artifact_manager = artifact_manager or ArtifactManager()
        self.budget_manager: Optional[BudgetManager] = None
        self.current_manifest: Optional[TaskManifest] = None
        self.current_context: Optional[TaskContext] = None
        self.work_units: List[WorkUnit] = []
        self.usage_history: List[Dict[str, Any]] = []

    def initialize_task(self, task_input: TaskInput) -> TaskManifest:
        if task_input.resume_task_id:
            manifest = self.checkpoint_manager.load_checkpoint(task_input.resume_task_id)
            if manifest:
                return self._resume_from_manifest(manifest, task_input)

        # --- NEW TASK FLOW ---

        # Step 1: Route inputs to processors and build TaskContext
        context = InputRouter.route(
            task_id=task_input.task_id,
            sources=task_input.files,
            repository=task_input.repository,
        )
        context.user_prompt = task_input.prompt
        context.execution_mode = task_input.execution_mode.value
        context.requested_output_type = task_input.output_type

        # Step 2: Create manifest
        manifest = TaskManifest(
            task_id=task_input.task_id,
            input_type=task_input.output_type,
            sources=task_input.files,
            initial_budget=task_input.budget,
            budget_unit=task_input.budget_unit,
            execution_mode=task_input.execution_mode.value,
        )
        manifest.input_data["repository"] = task_input.repository
        manifest.input_data["task_context_fingerprint"] = self._fingerprint_context(context)

        # Step 3: Rule-based planning with context
        work_units = Planner.plan_task(task_input.prompt, task_input.files, context)

        self.current_manifest = manifest
        self.current_context = context
        self.work_units = work_units
        self.budget_manager = BudgetManager(
            initial_budget=task_input.budget,
            budget_unit=task_input.budget_unit,
        )
        manifest.progress["total_units"] = len(work_units)
        manifest.pending_work = [u.id for u in work_units if u.status == "pending"]

        # Persist context reference in manifest
        self._persist_context_to_manifest(manifest)

        self.checkpoint_manager.save_checkpoint(manifest)
        return manifest

    def _resume_from_manifest(self, manifest: TaskManifest, task_input: TaskInput) -> TaskManifest:
        """Restore state from a saved manifest for resume."""
        self.current_manifest = manifest
        self.budget_manager = BudgetManager(
            initial_budget=manifest.budget_info.get("initial", 10.0),
            budget_unit=manifest.budget_info.get("unit", "USD"),
            emergency_reserve_ratio=manifest.budget_info.get("reserve_ratio", 0.15),
        )
        self.budget_manager.used_budget = Decimal(str(manifest.budget_info.get("used", "0")))

        # Restore context
        stored_context = getattr(manifest, "task_context_dict", None)
        if stored_context:
            self.current_context = TaskContext.from_dict(stored_context)
        else:
            self.current_context = TaskContext(
                task_id=manifest.task_id,
                user_prompt=task_input.prompt or "",
                execution_mode=manifest.execution_mode,
                requested_output_type=manifest.input_data.get("type", "text"),
            )

        # Restore WorkUnits from manifest
        stored_work_units = getattr(manifest, "work_units_data", None)
        if stored_work_units:
            self.work_units = [WorkUnit.from_dict(wd) for wd in stored_work_units]
        else:
            # Fallback: re-plan
            self.work_units = Planner.plan_task(
                self.current_context.user_prompt if hasattr(self.current_context, "user_prompt") else task_input.prompt,
                getattr(self.current_context, "input_sources", task_input.files),
                self.current_context,
            )

        # Recalculate remaining budget for resumed task (use provided budget if higher)
        if task_input.budget > manifest.budget_info.get("initial", 0):
            self.budget_manager.initial_budget = Decimal(str(task_input.budget))
            manifest.budget_info["initial"] = float(self.budget_manager.initial_budget)

        manifest.budget_info.update(self.budget_manager.to_dict())
        self._persist_context_to_manifest(manifest)
        self.checkpoint_manager.save_checkpoint(manifest)
        return manifest

    def _persist_context_to_manifest(self, manifest: TaskManifest):
        if self.current_context is not None:
            manifest.task_context_dict = self.current_context.to_dict()
            manifest.work_units_data = [u.to_dict() for u in self.work_units]

    @staticmethod
    def _fingerprint_context(context: TaskContext) -> str:
        """Simple fingerprint for source detection."""
        sources = sorted(context.source_fingerprints.items())
        return json.dumps(sources, sort_keys=True)

    def _check_source_fingerprints(self) -> bool:
        """Re-check source fingerprints. Returns True if unchanged."""
        if not self.current_context or not self.current_manifest:
            return False
        import hashlib
        import os
        for src_path in self.current_context.input_sources:
            if os.path.isfile(src_path) and not self.current_context.source_types.get(src_path) == "repository":
                old_fp = self.current_context.source_fingerprints.get(src_path, "")
                try:
                    with open(src_path, "rb") as f:
                        new_fp = hashlib.sha256(f.read()).hexdigest()
                except Exception:
                    new_fp = ""
                if old_fp and new_fp and old_fp != new_fp:
                    return False
        return True

    def run_next_unit(self) -> bool:
        if not self.budget_manager or not self.current_manifest:
            raise RuntimeError("Engine not initialized. Call initialize_task() first.")

        budget_state = self.budget_manager.evaluate_state()
        if budget_state == BudgetState.EXHAUSTED or budget_state == BudgetState.EMERGENCY:
            self.current_manifest.set_status("paused_budget")
            self.current_manifest.errors.append("Budget reached emergency or exhausted state.")
            self._persist_context_to_manifest(self.current_manifest)
            self.checkpoint_manager.save_checkpoint(self.current_manifest)
            return False

        eligible = Scheduler.get_eligible_units(
            self.work_units,
            self.current_manifest.completed_work,
            self.current_manifest.execution_mode,
            budget_state.value,
        )

        if not eligible:
            if len(self.current_manifest.completed_work) >= len([u for u in self.work_units if not u.optional]):
                self.current_manifest.set_status("completed")
                self._persist_context_to_manifest(self.current_manifest)
                self.checkpoint_manager.save_checkpoint(self.current_manifest)
            return False

        unit = eligible[0]
        self.current_manifest.progress["current_unit"] = unit.id
        unit.status = "in_progress"

        # Policy & Routing
        preferred_tier = ExecutionPolicy.adjust_routing(
            ExecutionMode.from_str(self.current_manifest.execution_mode),
            budget_state,
            unit.required_capabilities,
        )
        model = self.model_registry.select_best_model(unit.required_capabilities, preferred_tier)
        if not model:
            unit.status = "failed"
            self.current_manifest.errors.append(
                f"No capable model found for capabilities: {unit.required_capabilities}"
            )
            self._persist_context_to_manifest(self.current_manifest)
            self.checkpoint_manager.save_checkpoint(self.current_manifest)
            self.current_manifest.set_status("blocked")
            return False

        # Cost Estimation
        est_cost = CostEstimator.estimate_unit_cost(unit.type, model)

        # Budget check
        if not self.budget_manager.can_afford(est_cost, unit.optional):
            self.current_manifest.set_status("paused_budget")
            self.current_manifest.errors.append(
                f"Cannot afford unit {unit.id} with estimated cost {est_cost}"
            )
            self._persist_context_to_manifest(self.current_manifest)
            self.checkpoint_manager.save_checkpoint(self.current_manifest)
            return False

        # Build meaningful execution prompt
        prompt = self._build_execution_prompt(unit)

        # Execute
        exec_result = self.executor.execute(unit.type, model.model_id, prompt)

        # Record usage & cost
        self.usage_history.append({
            "work_unit_id": unit.id,
            "provider": exec_result.provider or model.provider,
            "model_id": exec_result.model_id or model.model_id,
            "estimated_cost": float(est_cost),
            "prompt_tokens": exec_result.usage.get("prompt_tokens", 0),
            "completion_tokens": exec_result.usage.get("completion_tokens", 0),
            "success": exec_result.success,
        })
        self.budget_manager.record_usage(est_cost)
        self.current_manifest.budget_info.update(self.budget_manager.to_dict())

        if not exec_result.success:
            unit.status = "failed"
            self.current_manifest.errors.append(exec_result.error or "Execution failed")
            self.current_manifest.model_history.append({
                "unit": unit.id,
                "provider": exec_result.provider,
                "model": exec_result.model_id,
                "usage": exec_result.usage,
                "success": False,
                "error": exec_result.error,
            })
            self._persist_context_to_manifest(self.current_manifest)
            self.checkpoint_manager.save_checkpoint(self.current_manifest)
            return False

        # --- SUCCESS: Create real artifact ---
        unit.status = "completed"
        self.current_manifest.add_completed_work(unit.id)
        self.current_manifest.progress["completed_units"] = len(self.current_manifest.completed_work)

        # Persist output as real artifact
        output_text = exec_result.output_text
        if output_text:
            if unit.type == "code":
                artifact_path = self.artifact_manager.write_code(
                    self.current_manifest.task_id, f"output_{unit.id}", output_text
                )
            elif unit.type in ("analyze", "summarization"):
                artifact_path = self.artifact_manager.write_text(
                    self.current_manifest.task_id, f"analysis_{unit.id}.md", output_text
                )
            else:
                artifact_path = self.artifact_manager.write_text(
                    self.current_manifest.task_id, f"result_{unit.id}.txt", output_text
                )
            self.current_manifest.add_output(artifact_path)
            unit.output_refs.append(artifact_path)

        self.current_manifest.model_history.append({
            "provider": exec_result.provider,
            "model_id": exec_result.model_id,
            "usage": exec_result.usage,
            "success": True,
        })

        self._persist_context_to_manifest(self.current_manifest)
        self.checkpoint_manager.save_checkpoint(self.current_manifest)
        return True

    def _build_execution_prompt(self, unit: WorkUnit) -> str:
        """Build a meaningful execution prompt containing context and instructions."""
        parts = []
        parts.append(f"User Goal: {self.current_context.user_prompt if self.current_context else '(unknown)'}")
        parts.append(f"Work Unit: {unit.id} ({unit.type})")
        parts.append(f"")
        parts.append(f"Instruction: {unit.instruction}")

        if unit.context_refs and self.current_context:
            if "repository_context" in unit.context_refs and self.current_context.repository_context:
                repo_ctx = self.current_context.repository_context
                parts.append(f"")
                parts.append(f"Repository Context:")
                parts.append(f"- Files: {repo_ctx.get('file_count', '?')}")
                if repo_ctx.get('files_top_level'):
                    parts.append(f"- Top-level files: {', '.join(repo_ctx['files_top_level'][:10])}")
                if repo_ctx.get('manifests'):
                    for mname, mcontent in list(repo_ctx['manifests'].items())[:3]:
                        parts.append(f"- {mname}: {mcontent[:500]}")
                if repo_ctx.get('entry_point_candidates'):
                    parts.append(f"- Entry points: {', '.join(repo_ctx['entry_point_candidates'])}")

            if "document_context" in unit.context_refs and self.current_context.document_context:
                for path, info in self.current_context.document_context.items():
                    parts.append(f"")
                    parts.append(f"Document: {path}")
                    parts.append(f"Type: {info.get('type', info.get('extension', 'document'))}")
                    parts.append(f"Size: {info.get('size_bytes', '?')} bytes")
                    parts.append(f"SHA-256: {info.get('sha256', '?')}")
                    if info.get('chunk_count'):
                        parts.append(f"Chunks: {info.get('chunk_count')}")
                    if info.get('page_count'):
                        parts.append(f"Pages: {info.get('page_count')}")

            if "structured_context" in unit.context_refs and self.current_context.structured_context:
                for path, info in self.current_context.structured_context.items():
                    parts.append(f"")
                    parts.append(f"Structured Data: {path}")
                    if info.get('headers'):
                        parts.append(f"Headers: {', '.join(info['headers'])}")
                    if info.get('row_count'):
                        parts.append(f"Rows: {info.get('row_count')} columns: {info.get('column_count')}")
                    if info.get('record_count'):
                        parts.append(f"Records: {info.get('record_count')}")
                    if info.get('top_level_keys'):
                        parts.append(f"Keys: {', '.join(info['top_level_keys'][:10])}")

        if unit.dependencies:
            parts.append(f"")
            parts.append(f"Dependencies (must be complete): {', '.join(unit.dependencies)}")
            completed = self.current_manifest.completed_work if self.current_manifest else []
            for dep_id in unit.dependencies:
                if dep_id in completed:
                    dep_unit = next((u for u in self.work_units if u.id == dep_id), None)
                    if dep_unit and dep_unit.output_refs:
                        parts.append(f"  - {dep_id}: completed, outputs: {', '.join(dep_unit.output_refs)}")
                    else:
                        parts.append(f"  - {dep_id}: completed")

        parts.append(f"")
        parts.append(f"Expected output: {self.current_context.requested_output_type if self.current_context else 'text'}")
        parts.append(f"Constraints: budget-safe, produce real file output")

        return "\n".join(parts)

    def run_to_completion(self) -> str:
        while self.run_next_unit():
            pass

        manifest = self.current_manifest
        completed = len(manifest.completed_work) if manifest else 0
        total = len([u for u in self.work_units if not u.optional]) if self.work_units else 0

        if manifest:
            if completed >= total or (all(
                u.status == "completed" for u in self.work_units if not u.optional
            )):
                manifest.set_status("completed")
                reason = "COMPLETED"
            elif manifest.status in ["paused_budget", "blocked", "failed"]:
                reason = f"{manifest.status.upper()}"
            else:
                manifest.set_status("partially_completed")
                reason = "PARTIALLY_COMPLETED"
        else:
            reason = "FAILED_NO_MANIFEST"

        if manifest:
            self._persist_context_to_manifest(manifest)
            self.checkpoint_manager.save_checkpoint(manifest)
        return OutputManager.generate_report(manifest, reason) if manifest else reason