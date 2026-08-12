"""Cost Estimator for AgentCore.
Estimates input/output tokens, model costs, and operation expenses.
"""
from typing import Dict, Any, Optional
from decimal import Decimal
from src.models.registry import ModelRegistry, ModelSpec

class CostEstimator:
    @staticmethod
    def estimate_unit_cost(unit_type: str, model: ModelSpec, prompt_length: int = 500) -> Decimal:
        estimated_input_tokens = max(50, prompt_length // 4)
        estimated_output_tokens = 200 if unit_type in ["code", "analyze"] else 50
        
        input_cost = (Decimal(estimated_input_tokens) / Decimal(1000)) * model.input_price
        output_cost = (Decimal(estimated_output_tokens) / Decimal(1000)) * model.output_price
        
        total = input_cost + output_cost
        return max(Decimal("0.01"), total)
