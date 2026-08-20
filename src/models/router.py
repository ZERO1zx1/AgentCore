"""Model Router and Registry for Credit-Safe Agent.
Selects the cheapest capable model tier based on task complexity and capabilities.
"""
from typing import Dict, Any, List, Optional

from src.models.registry import ModelRegistry, ModelSpec
from src.core.modes import ExecutionMode
from src.core.policy import ExecutionPolicy
from src.budget.state import BudgetState

class ModelRouter:
    TASK_CAPABILITIES = {"parse":["parsing"], "test":["deterministic"], "code":["coding"], "analyze":["text"], "transform":["multimodal"], "output":["deterministic"]}

    def __init__(self, registry: Optional[ModelRegistry] = None): self.registry = registry or ModelRegistry()

    def get_model_for_task(self, task_type: str, budget_state: str = "NORMAL", required_capabilities: Optional[List[str]] = None, execution_mode: str = "AUTO") -> Optional[ModelSpec]:
        caps = required_capabilities or self.TASK_CAPABILITIES.get(task_type, ["text"])
        try: state = BudgetState(budget_state)
        except ValueError: state = BudgetState.NORMAL
        preferred = ExecutionPolicy.adjust_routing(ExecutionMode.from_str(execution_mode), state, caps)
        return self.registry.select_best_model(caps, preferred)
