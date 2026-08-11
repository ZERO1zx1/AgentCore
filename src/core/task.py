"""Task Model and Input Routing for AgentCore.
Defines the universal task structure and input processing.
"""
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from src.core.modes import ExecutionMode
import hashlib
import os

@dataclass
class TaskInput:
    prompt: str
    task_id: str
    files: List[str] = field(default_factory=list)
    repository: Optional[str] = None
    output_type: str = "text"
    execution_mode: ExecutionMode = ExecutionMode.AUTO
    budget: float = 10.0
    budget_unit: str = "USD"
    metadata: Dict[str, Any] = field(default_factory=dict)
    resume_task_id: Optional[str] = None

    def get_source_fingerprints(self) -> Dict[str, str]:
        fingerprints = {}
        for f in self.files:
            if os.path.exists(f):
                with open(f, "rb") as file:
                    fingerprints[f] = hashlib.sha256(file.read()).hexdigest()
        return fingerprints
