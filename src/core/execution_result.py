"""Typed ExecutionResult contract for AgentCore.
Standardizes executor output across FakeExecutor, ProductionProviderExecutor, and custom executors.
"""
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional


@dataclass
class ExecutionResult:
    success: bool
    output_text: str = ""
    artifacts: List[str] = field(default_factory=list)
    usage: Dict[str, Any] = field(default_factory=dict)
    provider: str = ""
    model_id: str = ""
    provider_request_id: str = ""
    error: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "output_text": self.output_text,
            "artifacts": self.artifacts,
            "usage": self.usage,
            "provider": self.provider,
            "model_id": self.model_id,
            "provider_request_id": self.provider_request_id,
            "error": self.error,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExecutionResult":
        return cls(
            success=data.get("success", False),
            output_text=data.get("output_text", ""),
            artifacts=data.get("artifacts", []),
            usage=data.get("usage", {}),
            provider=data.get("provider", ""),
            model_id=data.get("model_id", ""),
            provider_request_id=data.get("provider_request_id", ""),
            error=data.get("error", ""),
            metadata=data.get("metadata", {}),
        )