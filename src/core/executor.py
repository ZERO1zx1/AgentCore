"""Executor interface and FakeExecutor for Manus Mini v2 tests and execution.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

class OperationExecutor(ABC):
    @abstractmethod
    def execute(self, unit_type: str, model_id: str, prompt: str) -> Dict[str, Any]:
        pass

class FakeExecutor(OperationExecutor):
    def __init__(self, should_fail: bool = False):
        self.should_fail = should_fail
        self.execution_count = 0

    def execute(self, unit_type: str, model_id: str, prompt: str) -> Dict[str, Any]:
        self.execution_count += 1
        if self.should_fail:
            return {
                "success": False,
                "output": None,
                "usage": {"prompt_tokens": 10, "completion_tokens": 10},
                "error": "Simulated execution failure"
            }
        return {
            "success": True,
            "output": f"Simulated output for {unit_type} using {model_id}",
            "usage": {"prompt_tokens": 100, "completion_tokens": 50}
        }
