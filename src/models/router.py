"""Model Router and Registry for Credit-Safe Agent.
Selects the cheapest capable model tier based on task complexity and capabilities.
"""
from typing import Dict, Any, List, Optional

from src.models.registry import ModelRegistry, ModelSpec
from src.core.modes import ExecutionMode
from src.core.policy import ExecutionPolicy
from src.budget.state import BudgetState
from src.core.route_learning import CapabilityHealthRegistry

class ModelRouter:
    TASK_CAPABILITIES = {"parse":["parsing"], "test":["deterministic"], "code":["coding"], "analyze":["text"], "transform":["multimodal"], "output":["deterministic"]}

    def __init__(self, registry: Optional[ModelRegistry] = None,
                 health_registry: Optional[CapabilityHealthRegistry] = None):
        self.registry = registry or ModelRegistry()
        self.health_registry = health_registry or CapabilityHealthRegistry()

    def get_model_for_task(self, task_type: str, budget_state: str = "NORMAL", required_capabilities: Optional[List[str]] = None, execution_mode: str = "AUTO") -> Optional[ModelSpec]:
        caps = required_capabilities or self.TASK_CAPABILITIES.get(task_type, ["text"])
        try: state = BudgetState(budget_state)
        except ValueError: state = BudgetState.NORMAL
        preferred = ExecutionPolicy.adjust_routing(ExecutionMode.from_str(execution_mode), state, caps)
        static_choice = self.registry.select_best_model(caps, preferred)
        observed = {item.model_id: item for item in self.registry.list_enabled()
                    if set(caps).issubset(item.capabilities)
                    and self.health_registry.routes.get(item.model_id)
                    and self.health_registry.routes[item.model_id].attempts > 0}
        if observed:
            ranked = self.health_registry.rank(caps)
            learned = next((observed[item.route_id] for item in ranked if item.route_id in observed), None)
            if learned is not None:
                return learned
        return static_choice
