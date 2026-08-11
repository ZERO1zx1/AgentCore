"""Model Router and Registry for Credit-Safe Agent.
Selects the cheapest capable model tier based on task complexity and capabilities.
"""
from typing import Dict, Any, List, Optional

class ModelRegistry:
    MODELS = {
        "tier0": {"id": "local-deterministic", "cost_per_token": 0.0, "capabilities": ["parsing", "deterministic"]},
        "tier1": {"id": "gpt-3.5-cheap", "cost_per_token": 0.000001, "capabilities": ["summarization", "classification", "simple_text"]},
        "tier2": {"id": "gpt-4o-mini", "cost_per_token": 0.000003, "capabilities": ["coding", "standard_reasoning"]},
        "tier3": {"id": "gpt-4o", "cost_per_token": 0.00001, "capabilities": ["complex_debugging", "architecture_reasoning"]},
        "tier4": {"id": "gpt-4o-reasoning", "cost_per_token": 0.00003, "capabilities": ["advanced_reasoning", "multimodal", "vision", "video"]}
    }

    @classmethod
    def get_model_for_task(cls, task_type: str, budget_state: str = "NORMAL") -> Dict[str, Any]:
        # If budget is CONSERVE or CRITICAL, downgrade tier when possible
        if task_type in ["parse", "classify", "summarize"]:
            tier = "tier1" if budget_state == "NORMAL" else "tier1"
        elif task_type in ["code", "debug", "refactor"]:
            tier = "tier3" if budget_state == "NORMAL" else "tier2"
        elif task_type in ["vision", "video", "complex_architecture"]:
            tier = "tier4" if budget_state in ["NORMAL", "CONSERVE"] else "tier3"
        else:
            tier = "tier2"
        return cls.MODELS[tier]
