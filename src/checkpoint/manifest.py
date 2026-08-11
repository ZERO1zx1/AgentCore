"""Task Manifest and Resumability Manager (v2) for AgentCore.
Tracks task progress, units of work, inputs, outputs, validation status, and resume state with schema versioning.
"""
import os
import json
from datetime import datetime, UTC
from typing import Dict, Any, List, Optional
from decimal import Decimal

class TaskManifest:
    SCHEMA_VERSION = "2.0"

    def __init__(
        self,
        task_id: str,
        input_type: str,
        sources: List[str],
        initial_budget: float | Decimal = 10.0,
        budget_unit: str = "USD",
        execution_mode: str = "AUTO"
    ):
        self.schema_version = self.SCHEMA_VERSION
        self.task_id = task_id
        self.status = "in_progress"  # in_progress | completed | partially_completed | paused_budget | blocked | failed
        self.execution_mode = execution_mode
        self.input_data = {
            "type": input_type,
            "sources": sources
        }
        self.progress = {
            "completed_units": 0,
            "total_units": 0,
            "current_unit": None
        }
        self.budget_info = {
            "schema_version": self.SCHEMA_VERSION,
            "initial": float(initial_budget),
            "used": 0.0,
            "remaining": float(initial_budget),
            "reserved": float(Decimal(str(initial_budget)) * Decimal("0.15")),
            "reserve_ratio": 0.15,
            "unit": budget_unit,
            "state": "NORMAL"
        }
        self.outputs: List[str] = []
        self.validation: Dict[str, Any] = {}
        self.model_history: List[Dict[str, Any]] = []
        self.completed_work: List[str] = []
        self.pending_work: List[str] = []
        self.next_actions: List[str] = []
        self.errors: List[str] = []
        self.reason: str = "NONE"
        self.usage_history: List[Dict[str, Any]] = []
        self.task_context_dict: Dict[str, Any] = {}
        self.work_units_data: List[Dict[str, Any]] = []
        self.updated_at = datetime.now(UTC).isoformat()
        self.created_at = self.updated_at

    def update_progress(self, completed_units: int, total_units: int, current_unit: Optional[str] = None):
        self.progress["completed_units"] = completed_units
        self.progress["total_units"] = total_units
        self.progress["current_unit"] = current_unit
        self.updated_at = datetime.now(UTC).isoformat()

    def add_completed_work(self, item: str):
        if item not in self.completed_work:
            self.completed_work.append(item)
        self.updated_at = datetime.now(UTC).isoformat()

    def add_output(self, output_path: str):
        if output_path not in self.outputs:
            self.outputs.append(output_path)
        self.updated_at = datetime.now(UTC).isoformat()

    def set_status(self, status: str):
        self.status = status
        self.updated_at = datetime.now(UTC).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "task_id": self.task_id,
            "status": self.status,
            "execution_mode": self.execution_mode,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "input": self.input_data,
            "progress": self.progress,
            "budget": self.budget_info,
            "outputs": self.outputs,
            "validation": self.validation,
            "model_history": self.model_history,
            "completed_work": self.completed_work,
            "pending_work": self.pending_work,
            "errors": self.errors,
            "reason": self.reason,
            "usage_history": self.usage_history,
            "next_actions": self.next_actions,
            "task_context": self.task_context_dict,
            "work_units": self.work_units_data
        }

    def save(self, filepath: str):
        os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)

    @classmethod
    def load(cls, filepath: str) -> "TaskManifest":
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        b_info = data.get("budget", {})
        init_b = b_info.get("initial", 10.0)
        b_unit = b_info.get("unit", "USD")
        exec_mode = data.get("execution_mode", "AUTO")

        manifest = cls(
            task_id=data.get("task_id", "unknown"),
            input_type=data.get("input", {}).get("type", "unknown"),
            sources=data.get("input", {}).get("sources", []),
            initial_budget=init_b,
            budget_unit=b_unit,
            execution_mode=exec_mode
        )
        manifest.schema_version = data.get("schema_version", cls.SCHEMA_VERSION)
        manifest.status = data.get("status", "in_progress")
        manifest.created_at = data.get("created_at", manifest.created_at)
        manifest.progress = data.get("progress", manifest.progress)
        manifest.budget_info = b_info
        manifest.outputs = data.get("outputs", [])
        manifest.validation = data.get("validation", {})
        manifest.model_history = data.get("model_history", [])
        manifest.completed_work = data.get("completed_work", [])
        manifest.pending_work = data.get("pending_work", [])
        manifest.errors = data.get("errors", [])
        manifest.reason = data.get("reason", "NONE")
        manifest.usage_history = data.get("usage_history", [])
        manifest.next_actions = data.get("next_actions", [])
        manifest.task_context_dict = data.get("task_context", {})
        manifest.work_units_data = data.get("work_units", [])
        manifest.updated_at = data.get("updated_at", datetime.now(UTC).isoformat())
        return manifest
