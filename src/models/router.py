"""Model Router and Registry for Credit-Safe Agent.
Selects the cheapest capable model tier based on task complexity and capabilities.
"""
from typing import Dict, Any, List, Optional

from src.models.registry import ModelRegistry as Registry

class ModelRouter:
    @staticmethod
    def get_model_for_task(task_type: str, budget_state: str = "NORMAL") -> Dict[str, Any]:
        return Registry.get_model_for_task(task_type, budget_state)
