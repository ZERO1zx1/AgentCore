"""Model Registry and Specification for AgentCore.
Injectable model specs with capability filtering before cost optimization.
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
    input_modalities: List[str] = field(default_factory=lambda: ["text"])
    output_modalities: List[str] = field(default_factory=lambda: ["text"])
    context_size: Optional[int] = 128000
    enabled: bool = True

class ModelRegistry:
    def __init__(self):
        self._models: Dict[str, ModelSpec] = {
            "fake-local": ModelSpec("local", "fake-local", "tier0", Decimal("0"), Decimal("0"), ["parsing", "deterministic"], ["text"], ["text"]),
            "fake-economy": ModelSpec("fake", "fake-economy", "tier1", Decimal("0.0001"), Decimal("0.0003"), ["summarization", "classification", "text"], ["text"], ["text"]),
            "fake-standard": ModelSpec("fake", "fake-standard", "tier2", Decimal("0.001"), Decimal("0.003"), ["coding", "standard_reasoning", "text"], ["text"], ["text"]),
            "fake-strong": ModelSpec("fake", "fake-strong", "tier3", Decimal("0.005"), Decimal("0.015"), ["complex_debugging", "architecture", "coding", "text"], ["text"], ["text"]),
            "fake-vision": ModelSpec("fake", "fake-vision", "tier4", Decimal("0.01"), Decimal("0.03"), ["multimodal", "vision", "text"], ["text", "image"], ["text"]),
        }

    def register_model(self, name: str, spec: ModelSpec):
        self._models[name] = spec

    def get_model(self, name: str) -> Optional[ModelSpec]:
        return self._models.get(name)

    def select_best_model(self, required_capabilities: List[str], preferred_tier: str = "tier2") -> Optional[ModelSpec]:
        # 1. Capability filtering BEFORE cost optimization
        capable_models = []
        for model in self._models.values():
            if not model.enabled:
                continue
            if all(cap in model.capabilities for cap in required_capabilities):
                capable_models.append(model)

        if not capable_models:
            return None

        # 2. Match preferred tier or fallback to cheapest capable
        tier_matches = [m for m in capable_models if m.tier == preferred_tier]
        if tier_matches:
            return tier_matches[0]

        # Fallback to cheapest among capable models (by avg price)
        capable_models.sort(key=lambda m: (m.input_price + m.output_price))
        return capable_models[0]
