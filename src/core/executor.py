"""Executor interface, FakeExecutor, and ProviderExecutor template for AgentCore.
All executors return the typed ExecutionResult contract.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from src.core.execution_result import ExecutionResult


class OperationExecutor(ABC):
    @abstractmethod
    def execute(self, unit_type: str, model_id: str, prompt: str, context: Optional[Dict[str, Any]] = None) -> ExecutionResult:
        """Execute an operation unit using the specified model and prompt."""
        pass


class FakeExecutor(OperationExecutor):
    """FakeExecutor for deterministic testing and demo purposes only. Does not perform real LLM or tool execution."""

    def __init__(self, should_fail: bool = False):
        self.should_fail = should_fail
        self.execution_count = 0
        self.last_prompt = ""
        self.last_context: Dict[str, Any] = {}

    def execute(self, unit_type: str, model_id: str, prompt: str, context: Optional[Dict[str, Any]] = None) -> ExecutionResult:
        self.execution_count += 1
        self.last_prompt = prompt
        self.last_context = context or {}
        if self.should_fail:
            return ExecutionResult(
                success=False,
                usage={"input_tokens": 10, "output_tokens": 10, "total_tokens": 20},
                error="Simulated execution failure",
                provider="fake",
                model_id=model_id,
            )
        return ExecutionResult(
            success=True,
            output_text=f"FakeExecutor output for {unit_type} using model {model_id}",
            usage={"input_tokens": 100, "output_tokens": 50, "total_tokens": 150},
            provider="fake",
            model_id=model_id,
        )


class ProductionProviderExecutor(OperationExecutor):
    """Template/Example for a real provider-backed executor (e.g. OpenAI/Anthropic API).
    Applications wishing to perform real production execution must supply a configured provider adapter implementing OperationExecutor.
    """

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        self.api_key = api_key
        self.base_url = base_url

    def execute(self, unit_type: str, model_id: str, prompt: str, context: Optional[Dict[str, Any]] = None) -> ExecutionResult:
        # Translate context["attachments"] path descriptors to the provider's
        # native image/audio/video content parts.  The engine never puts binary
        # or base64 data into the text prompt.
        raise NotImplementedError("ProductionProviderExecutor requires an active API client configuration.")
