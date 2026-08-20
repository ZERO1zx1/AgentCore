"""Core Execution Engine for AgentCore.
Orchestrates task execution with real input routing, planning, scheduling,
policy enforcement, executor injection, artifact management, and resume.
Provider-agnostic: the engine only knows prompt, capabilities, result, usage, artifacts.
"""
from typing import Optional, Dict, Any, List
from decimal import Decimal
from src.core.task import TaskInput
from src.core.modes import ExecutionMode
from src.core.context import TaskContext
from src.core.execution_result import ExecutionResult
from src.core.runtime_config import RuntimeConfig
from src.core.context_resolver import ContextResolver
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
from src.ingestion.repository import RepositoryProcessor
from src.core.notifications import GitManager, NotificationManager, create_budget_exhaustion_handler
import json
import os


class AgentCoreEngine:
    def __init__(
        self,
        checkpoint_dir: str = ".agentcore/checkpoints",
        executor: Optional[OperationExecutor] = None,
        model_registry: Optional[ModelRegistry] = None,
        artifact_manager: Optional[ArtifactManager] = None,
        runtime_config: Optional[RuntimeConfig] = None,
        repo_root: str = ".",
        notification_config: Optional[Dict[str, Any]] = None,
    ):
        self.runtime_config = runtime_config or RuntimeConfig()
        self.checkpoint_manager = CheckpointManager(checkpoint_dir or self.runtime_config.checkpoint_root)
        self.executor = executor or FakeExecutor()
        self.model_registry = model_registry or ModelRegistry()
        self.artifact_manager = artifact_manager or ArtifactManager(base_dir=self.runtime_config.artifact_root)
        self.context_resolver = ContextResolver(self.runtime_config)
        self.budget_manager: Optional[BudgetManager] = None
        self.current_manifest: Optional[TaskManifest] = None
        self.current_context: Optional[TaskContext] = None
        self.work_units: List[WorkUnit] = []
        self.usage_history: List[Dict[str, Any]] = []
        
        # Budget exhaustion handlers
        self.git_manager = GitManager(repo_root)
        self.notification_manager = NotificationManager(notification_config)

    def initialize_task(self, task_input: TaskInput) -> TaskManifest:
        if task_input.resume_task_id:
            manifest = self.checkpoint_manager.load_checkpoint(task_input.resume_task_id)
            if manifest:
                return self._resume_from_manifest(manifest, task_input)

        # --- NEW TASK FLOW ---

        # Step 1: Route inputs to processors and build TaskContext
        context_dir = os.path.join(self.artifact_manager.task_dir(task_input.task_id), "context")
        os.makedirs(context_dir, exist_ok=True)
        context = InputRouter.route(
            task_id=task_input.task_id,
            sources=task_input.files,
            repository=task_input.repository,
            context_dir=context_dir,
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
        self._assign_source_refs(work_units, context)

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
            self.work_units = Planner.plan_task(
                self.current_context.user_prompt if hasattr(self.current_context, "user_prompt") else task_input.prompt,
                getattr(self.current_context, "input_sources", task_input.files),
                self.current_context,
            )

        # Restore usage history so resume continues accurately
        stored_usage = getattr(manifest, "usage_history", None)
        if stored_usage:
            self.usage_history = list(stored_usage)

        # Granular source fingerprint invalidation (only affected units)
        self._invalidate_changed_sources()

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
        # Persist usage history so resume restores it
        manifest.usage_history = list(self.usage_history)

    @staticmethod
    def _assign_source_refs(work_units: List[WorkUnit], context: TaskContext):
        """Assign source_refs to each WorkUnit based on its context_refs."""
        source_by_ref = {}
        for src_path, src_type in context.source_types.items():
            key = {
                "repository": "repository_context",
                "pdf": "document_context",
                "text": "document_context",
                "structured": "structured_context",
            }.get(src_type)
            if key:
                source_by_ref.setdefault(key, []).append(src_path)

        for unit in work_units:
            refs = []
            for ref in unit.context_refs:
                refs.extend(source_by_ref.get(ref, []))
            # Also add all input sources by default (best-effort coverage)
            if not refs:
                refs = list(context.input_sources)
            unit.source_refs = sorted(set(refs))

    @staticmethod
    def _fingerprint_context(context: TaskContext) -> str:
        """Simple fingerprint for source detection."""
        sources = sorted(context.source_fingerprints.items())
        return json.dumps(sources, sort_keys=True)

    def _compute_source_fingerprints(self) -> Dict[str, str]:
        """Recompute current fingerprints for all sources."""
        if not self.current_context:
            return {}
        import hashlib
        result = {}
        for src_path in self.current_context.input_sources:
            src_type = self.current_context.source_types.get(src_path, "")
            if src_type == "repository":
                try:
                    result[src_path] = RepositoryProcessor.fingerprint_repository(src_path)
                except Exception:
                    result[src_path] = ""
            elif os.path.isfile(src_path):
                try:
                    with open(src_path, "rb") as f:
                        result[src_path] = hashlib.sha256(f.read()).hexdigest()
                except Exception:
                    result[src_path] = ""
            else:
                result[src_path] = self.current_context.source_fingerprints.get(src_path, "")
        return result

    def _find_changed_sources(self) -> List[str]:
        """Return source paths whose fingerprints changed since planning."""
        if not self.current_context:
            return []
        current = self._compute_source_fingerprints()
        old = self.current_context.source_fingerprints
        changed = []
        for src_path in self.current_context.input_sources:
            old_fp = old.get(src_path, "")
            new_fp = current.get(src_path, "")
            if old_fp and new_fp and old_fp != new_fp:
                changed.append(src_path)
            elif not old_fp and new_fp:
                # New source appeared
                changed.append(src_path)
        return changed

    def _invalidate_changed_sources(self):
        """Granular, dependency-aware invalidation.

        Only units whose source_refs intersect changed sources are invalidated,
        plus units that transitively depend on an invalidated unit.
        Unrelated completed units remain completed.
        """
        if not self.current_context or not self.current_manifest:
            return

        changed = set(self._find_changed_sources())
        if not changed:
            return

        # Update stored fingerprints to current values (so no repeated invalidation)
        current = self._compute_source_fingerprints()
        self.current_context.source_fingerprints.update(current)

        # 1. Directly affected units: completed and referencing a changed source
        invalidated = set()
        for unit in self.work_units:
            if unit.status == "completed" and unit.source_refs:
                if changed & set(unit.source_refs):
                    invalidated.add(unit.id)

        # 2. Transitive: any pending/completed unit depending on an invalidated unit
        changed = True
        while changed:
            changed = False
            for unit in self.work_units:
                if unit.id in invalidated:
                    continue
                if any(dep in invalidated for dep in unit.dependencies):
                    invalidated.add(unit.id)
                    changed = True

        # 3. Apply invalidation
        for unit in self.work_units:
            if unit.id in invalidated and unit.status == "completed":
                unit.status = "pending"
                if unit.id in self.current_manifest.completed_work:
                    self.current_manifest.completed_work.remove(unit.id)
        self.current_manifest.progress["completed_units"] = len(self.current_manifest.completed_work)
        if invalidated:
            self.current_manifest.reason = "SOURCE_CHANGED"

    def _handle_budget_exhaustion(self, budget_state: BudgetState):
        """Handle budget exhaustion: save checkpoint, push to git, notify."""
        self.current_manifest.set_status("PARTIALLY_COMPLETED")
        self.current_manifest.reason = "BUDGET_LIMIT"
        self.current_manifest.errors.append(f"Budget reached {budget_state.value} state.")
        self._persist_context_to_manifest(self.current_manifest)
        self.checkpoint_manager.save_checkpoint(self.current_manifest)
        
        # Push checkpoint to git
        git_result = self.git_manager.push_checkpoint(
            task_id=self.current_manifest.task_id,
            budget_state=budget_state.value,
            budget_info=self.budget_manager.to_dict()
        )
        if git_result["success"]:
            self.current_manifest.errors.append(f"Git push: {', '.join(git_result['steps'])}")
        else:
            self.current_manifest.errors.append(f"Git push failed: {git_result['error']}; Steps: {', '.join(git_result['steps'])}")
        
        # Send notification
        notify_result = self.notification_manager.notify_budget_exhausted(
            task_id=self.current_manifest.task_id,
            budget_state=budget_state.value,
            budget_info=self.budget_manager.to_dict(),
            manifest=self.current_manifest.to_dict()
        )
        if notify_result["console"] or notify_result["webhook"]:
            self.current_manifest.errors.append("Notification sent: console=True" if notify_result["console"] else "")
            if notify_result["webhook"]:
                self.current_manifest.errors.append("Notification sent: webhook=True")
        if notify_result["errors"]:
            for err in notify_result["errors"]:
                self.current_manifest.errors.append(f"Notification error: {err}")

    def run_next_unit(self) -> bool:
        if not self.budget_manager or not self.current_manifest:
            raise RuntimeError("Engine not initialized. Call initialize_task() first.")

        budget_state = self.budget_manager.evaluate_state()
        if budget_state == BudgetState.EXHAUSTED or budget_state == BudgetState.EMERGENCY:
            self._handle_budget_exhaustion(budget_state)
            return False

        eligible = Scheduler.get_eligible_units(
            self.work_units,
            self.current_manifest.completed_work,
            self.current_manifest.execution_mode,
            budget_state.value,
        )

        if not eligible:
            if len(self.current_manifest.completed_work) >= len([u for u in self.work_units if not u.optional]):
                self.current_manifest.set_status("COMPLETED")
                self.current_manifest.reason = "NONE"
                self._persist_context_to_manifest(self.current_manifest)
                self.checkpoint_manager.save_checkpoint(self.current_manifest)
            return False

        unit = eligible[0]
        self.current_manifest.progress["current_unit"] = unit.id
        unit.status = "in_progress"

        # Retry limit check
        attempts = unit.metadata.get("attempt_count", 0)
        if attempts >= self.runtime_config.max_attempts:
            unit.status = "failed"
            self.current_manifest.errors.append(f"Unit {unit.id} exceeded max attempts ({self.runtime_config.max_attempts})")
            self.current_manifest.set_status("FAILED")
            self.current_manifest.reason = "EXECUTION_ERROR"
            self._persist_context_to_manifest(self.current_manifest)
            self.checkpoint_manager.save_checkpoint(self.current_manifest)
            return False

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
            self.current_manifest.set_status("BLOCKED")
            self.current_manifest.reason = "PROVIDER_NOT_CONFIGURED"
            self._persist_context_to_manifest(self.current_manifest)
            self.checkpoint_manager.save_checkpoint(self.current_manifest)
            return False

        # Cost Estimation (before execution)
        est_cost = CostEstimator.estimate_unit_cost(unit.type, model)

        # Budget check
        if not self.budget_manager.can_afford(est_cost, unit.optional):
            self.current_manifest.set_status("PARTIALLY_COMPLETED")
            self.current_manifest.reason = "BUDGET_LIMIT"
            self.current_manifest.errors.append(
                f"Cannot afford unit {unit.id} with estimated cost {est_cost}"
            )
            self._persist_context_to_manifest(self.current_manifest)
            self.checkpoint_manager.save_checkpoint(self.current_manifest)
            return False

        # Build meaningful execution prompt with real context
        prompt = self._build_execution_prompt(unit)

        # Execute
        exec_result = self.executor.execute(unit.type, model.model_id, prompt)

        # Normalize usage
        usage = self._normalize_usage(exec_result.usage)

        # Cost accounting: separate estimate from actual
        actual_cost = exec_result.metadata.get("actual_cost")
        cost_source = "provider" if actual_cost is not None else "estimate"
        charged_cost = float(actual_cost) if actual_cost is not None else float(est_cost)

        # Record usage & cost
        self.usage_history.append({
            "work_unit_id": unit.id,
            "provider": exec_result.provider or model.provider,
            "model_id": exec_result.model_id or model.model_id,
            "estimated_cost": float(est_cost),
            "charged_cost": charged_cost,
            "actual_cost": float(actual_cost) if actual_cost is not None else None,
            "cost_source": cost_source,
            "input_tokens": usage.get("input_tokens", 0),
            "output_tokens": usage.get("output_tokens", 0),
            "total_tokens": usage.get("total_tokens", 0),
            "provider_request_id": exec_result.provider_request_id,
            "success": exec_result.success,
        })
        self.budget_manager.record_usage(charged_cost)
        self.current_manifest.budget_info.update(self.budget_manager.to_dict())

        if not exec_result.success:
            unit.status = "failed"
            unit.metadata["attempt_count"] = attempts + 1
            self.current_manifest.errors.append(exec_result.error or "Execution failed")
            self.current_manifest.model_history.append({
                "work_unit_id": unit.id,
                "provider": exec_result.provider,
                "model_id": exec_result.model_id,
                "estimated_cost": float(est_cost),
                "charged_cost": charged_cost,
                "actual_cost": float(actual_cost) if actual_cost is not None else None,
                "cost_source": cost_source,
                "input_tokens": usage.get("input_tokens", 0),
                "output_tokens": usage.get("output_tokens", 0),
                "total_tokens": usage.get("total_tokens", 0),
                "provider_request_id": exec_result.provider_request_id,
                "success": False,
                "error": exec_result.error,
            })
            self._persist_context_to_manifest(self.current_manifest)
            self.checkpoint_manager.save_checkpoint(self.current_manifest)
            return False

        # --- SUCCESS: Create real artifact ---
        unit.status = "completed"
        unit.metadata["attempt_count"] = attempts + 1
        self.current_manifest.add_completed_work(unit.id)
        self.current_manifest.progress["completed_units"] = len(self.current_manifest.completed_work)

        # Persist output as real artifact
        output_text = exec_result.output_text
        if output_text:
            # Check for explicit target path in metadata
            target_path = unit.metadata.get("target_path")
            if target_path and self._is_safe_target(target_path):
                artifact_path = self._write_to_target(target_path, output_text)
            elif unit.type == "code":
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
            "work_unit_id": unit.id,
            "provider": exec_result.provider,
            "model_id": exec_result.model_id,
            "estimated_cost": float(est_cost),
            "charged_cost": charged_cost,
            "actual_cost": float(actual_cost) if actual_cost is not None else None,
            "cost_source": cost_source,
            "input_tokens": usage.get("input_tokens", 0),
            "output_tokens": usage.get("output_tokens", 0),
            "total_tokens": usage.get("total_tokens", 0),
            "provider_request_id": exec_result.provider_request_id,
            "success": True,
            "error": "",
        })

        self._persist_context_to_manifest(self.current_manifest)
        self.checkpoint_manager.save_checkpoint(self.current_manifest)
        return True

    def _normalize_usage(self, usage: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize provider usage to canonical internal model."""
        input_tokens = usage.get("input_tokens", usage.get("prompt_tokens", 0))
        output_tokens = usage.get("output_tokens", usage.get("completion_tokens", 0))
        total = usage.get("total_tokens", input_tokens + output_tokens)
        return {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total,
        }

    def _is_safe_target(self, target_path: str) -> bool:
        """Prevent path traversal and absolute escapes."""
        if os.path.isabs(target_path):
            return False
        if ".." in target_path.split(os.sep):
            return False
        return True

    def _write_to_target(self, target_path: str, content: str) -> str:
        """Write to a safe relative target path."""
        os.makedirs(os.path.dirname(target_path) or ".", exist_ok=True)
        with open(target_path, "w", encoding="utf-8") as f:
            f.write(content)
        return os.path.abspath(target_path)

    def _build_execution_prompt(self, unit: WorkUnit) -> str:
        """Build a meaningful execution prompt containing real context and instructions."""
        parts = []
        parts.append(f"User Goal: {self.current_context.user_prompt if self.current_context else '(unknown)'}")
        parts.append(f"Work Unit: {unit.id} ({unit.type})")
        parts.append(f"")
        parts.append(f"Instruction: {unit.instruction}")

        # Resolve real context content
        if self.current_context:
            resolved = self.context_resolver.resolve_context(self.current_context, unit)
            if resolved:
                parts.append(f"")
                parts.append(f"--- RELEVANT CONTEXT ---")
                parts.append(resolved)
                parts.append(f"--- END CONTEXT ---")

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
                manifest.set_status("COMPLETED")
                manifest.reason = "NONE"
                reason = "COMPLETED"
            elif manifest.status in ["BLOCKED", "FAILED"]:
                reason = f"{manifest.status}"
            else:
                manifest.set_status("PARTIALLY_COMPLETED")
                if not manifest.reason:
                    manifest.reason = "BUDGET_LIMIT"
                reason = "PARTIALLY_COMPLETED"
        else:
            reason = "FAILED_NO_MANIFEST"

        if manifest:
            self._persist_context_to_manifest(manifest)
            self.checkpoint_manager.save_checkpoint(manifest)
        return OutputManager.generate_report(manifest, reason) if manifest else reason


# Backward-compatible alias for legacy imports
ManusMiniEngine = AgentCoreEngine
