"""Task Manifest and Resumability Manager for Credit-Safe Agent.
Tracks task progress, units of work, inputs, outputs, validation status, and resume state.
"""
import os
import json
from datetime import datetime, UTC
from typing import Dict, Any, List, Optional

class TaskManifest:
    def __init__(self, task_id: str, input_type: str, sources: List[str], initial_budget: float = 10.0):
        self.task_id = task_id
        self.status = "in_progress"  # in_progress | completed | paused_budget | blocked | failed
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
            "initial": initial_budget,
            "used": 0.0,
            "remaining": initial_budget,
            "reserved": initial_budget * 0.15,
            "state": "NORMAL"
        }
        self.outputs: List[str] = []
        self.validation: Dict[str, Any] = {}
        self.model_history: List[Dict[str, Any]] = []
        self.completed_work: List[str] = []
        self.pending_work: List[str] = []
        self.next_actions: List[str] = []
        self.updated_at = datetime.now(UTC).isoformat()

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
            "task_id": self.task_id,
            "status": self.status,
            "input": self.input_data,
            "progress": self.progress,
            "budget": self.budget_info,
            "outputs": self.outputs,
            "validation": self.validation,
            "model_history": self.model_history,
            "completed_work": self.completed_work,
            "pending_work": self.pending_work,
            "next_actions": self.next_actions,
            "updated_at": self.updated_at
        }

    def save(self, filepath: str):
        os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)

    @classmethod
    def load(cls, filepath: str) -> "TaskManifest":
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        manifest = cls(
            task_id=data.get("task_id", "unknown"),
            input_type=data.get("input", {}).get("type", "unknown"),
            sources=data.get("input", {}).get("sources", []),
            initial_budget=data.get("budget", {}).get("initial", 10.0)
        )
        manifest.status = data.get("status", "in_progress")
        manifest.progress = data.get("progress", manifest.progress)
        manifest.budget_info = data.get("budget", manifest.budget_info)
        manifest.outputs = data.get("outputs", [])
        manifest.validation = data.get("validation", {})
        manifest.model_history = data.get("model_history", [])
        manifest.completed_work = data.get("completed_work", [])
        manifest.pending_work = data.get("pending_work", [])
        manifest.next_actions = data.get("next_actions", [])
        manifest.updated_at = data.get("updated_at", datetime.now(UTC).isoformat())
        return manifest
