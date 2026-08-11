"""Model Registry and Specification for Manus Mini.
Defines model capabilities, pricing, and tiers.
"""
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from decimal import Decimal

@dataclass
class ModelSpec:
    provider: str
    model_id: str
    tier: str
    input_price: Decimal  # per 1k tokens
    output_price: Decimal # per 1k tokens
    capabilities: List[str] = field(default_factory=list)
    context_size: Optional[int] = None
    enabled: bool = True

class ModelRegistry:
    _MODELS: Dict[str, ModelSpec] = {
        "tier0": ModelSpec("local", "deterministic", "tier0", Decimal("0"), Decimal("0"), ["parsing", "deterministic"]),
        "tier1": ModelSpec("openai", "gpt-4o-mini", "tier1", Decimal("0.00015"), Decimal("0.0006"), ["summarization", "classification"]),
        "tier2": ModelSpec("openai", "gpt-4o", "tier2", Decimal("0.005"), Decimal("0.015"), ["coding", "standard_reasoning"]),
        "tier3": ModelSpec("openai", "o1-preview", "tier3", Decimal("0.015"), Decimal("0.06"), ["complex_debugging", "architecture"]),
        "tier4": ModelSpec("openai", "o1", "tier4", Decimal("0.015"), Decimal("0.06"), ["advanced_reasoning", "multimodal"])
    }

    @classmethod
    def get_model(cls, tier: str) -> Optional[ModelSpec]:
        return cls._MODELS.get(tier)

    @classmethod
    def get_model_for_task(cls, task_type: str, budget_state: str = "NORMAL") -> Dict[str, Any]:
        # Logic to select tier based on task and budget
        if task_type in ["parse", "classify"]:
            tier = "tier1"
        elif task_type in ["code", "debug"]:
            tier = "tier3" if budget_state == "NORMAL" else "tier2"
        elif task_type in ["vision", "complex"]:
            tier = "tier4" if budget_state == "NORMAL" else "tier3"
        else:
            tier = "tier2"
        
        spec = cls.get_model(tier)
        return {
            "id": spec.model_id,
            "provider": spec.provider,
            "cost_per_token": float((spec.input_price + spec.output_price) / 2000), # Rough avg
            "capabilities": spec.capabilities
        }
