"""Execution Policy enforcement for AUTO, FULL, and CREDIT_SAFE modes.
"""
from typing import Dict, Any, List
from src.core.modes import ExecutionMode
from src.budget.state import BudgetState

class ExecutionPolicy:
    nutshell = "Enforces mode-specific routing and checkpoint rules."

    @staticmethod
    def adjust_routing(execution_mode: ExecutionMode, budget_state: BudgetState, required_capabilities: List[str]) -> str:
        # Determine preferred tier based on mode and budget
        if execution_mode == ExecutionMode.FULL and budget_state in [BudgetState.NORMAL, BudgetState.CONSERVE]:
            return "tier3" if "coding" in required_capabilities else "tier2"
        elif execution_mode == ExecutionMode.CREDIT_SAFE:
            return "tier1" if "coding" not in required_capabilities else "tier2"
        else:
            # AUTO mode
            if budget_state == BudgetState.NORMAL:
                return "tier2"
            elif budget_state == BudgetState.CONSERVE:
                return "tier1"
            else:
                return "tier1"

    @staticmethod
    def should_skip_optional(execution_mode: ExecutionMode, budget_state: BudgetState) -> bool:
        if execution_mode == ExecutionMode.FULL and budget_state == BudgetState.NORMAL:
            return False
        if budget_state in [BudgetState.CRITICAL, BudgetState.EMERGENCY, BudgetState.EXHAUSTED]:
            return True
        if execution_mode == ExecutionMode.CREDIT_SAFE and budget_state != BudgetState.NORMAL:
            return True
        return False
