"""Executor interface, FakeExecutor, and ProviderExecutor template for Manus Mini v2.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

class OperationExecutor(ABC):
    @abstractmethod
    def execute(self, unit_type: str, model_id: str, prompt: str) -> Dict[str, Any]:
        """Execute an operation unit using the specified model and prompt."""
        pass

class FakeExecutor(OperationExecutor):
    """FakeExecutor for deterministic testing and demo purposes only. Does not perform real LLM or tool execution."""
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
            "output": f"FakeExecutor output for {unit_type} using model {model_id}",
            "usage": {"prompt_tokens": 100, "completion_tokens": 50}
        }

class ProductionProviderExecutor(OperationExecutor):
    """Template/Example for a real provider-backed executor (e.g. OpenAI/Anthropic API).
    Applications wishing to perform real production execution must supply a configured provider adapter implementing OperationExecutor.
    """
    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        self.api_key = api_key
        self.base_url = base_url

    def execute(self, unit_type: str, model_id: str, prompt: str) -> Dict[str, Any]:
        # Implementation for real provider invocation would go here.
        raise NotImplementedError("ProductionProviderExecutor requires an active API client configuration.")
