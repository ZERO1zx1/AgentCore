"""Budget State Machine and Estimator for AgentCore.
Manages budget states with Decimal safety and support for abstract budget units.
"""
from decimal import Decimal
from enum import Enum
from typing import Dict, Any, Optional

class BudgetState(str, Enum):
    NORMAL = "NORMAL"
    CONSERVE = "CONSERVE"
    CRITICAL = "CRITICAL"
    EMERGENCY = "EMERGENCY"
    EXHAUSTED = "EXHAUSTED"

class BudgetManager:
    def __init__(
        self,
        initial_budget: float | Decimal = 10.0,
        budget_unit: str = "USD",
        emergency_reserve_ratio: float | Decimal = 0.15,
        conserve_threshold: float | Decimal = 0.50,
        critical_threshold: float | Decimal = 0.25,
        emergency_threshold: float | Decimal = 0.10,
    ):
        self.initial_budget = Decimal(str(initial_budget))
        self.budget_unit = budget_unit
        self.used_budget = Decimal("0.0")
        self.reserve_ratio = Decimal(str(emergency_reserve_ratio))
        self.conserve_threshold = Decimal(str(conserve_threshold))
        self.critical_threshold = Decimal(str(critical_threshold))
        self.emergency_threshold = Decimal(str(emergency_threshold))

    @property
    def reserved_budget(self) -> Decimal:
        return self.initial_budget * self.reserve_ratio

    @property
    def remaining_budget(self) -> Decimal:
        return max(Decimal("0.0"), self.initial_budget - self.used_budget)

    @property
    def usable_budget(self) -> Decimal:
        return max(Decimal("0.0"), self.remaining_budget - self.reserved_budget)

    def record_usage(self, cost: float | Decimal) -> BudgetState:
        self.used_budget += Decimal(str(cost))
        return self.evaluate_state()

    def evaluate_state(self, estimated_next_cost: float | Decimal = 0.0) -> BudgetState:
        rem = self.remaining_budget
        if rem <= Decimal("0.0"):
            return BudgetState.EXHAUSTED
        
        next_cost = Decimal(str(estimated_next_cost))
        if rem <= self.reserved_budget or (rem - next_cost) <= self.reserved_budget:
            return BudgetState.EMERGENCY

        ratio = rem / self.initial_budget
        if ratio <= self.emergency_threshold:
            return BudgetState.EMERGENCY
        elif ratio <= self.critical_threshold:
            return BudgetState.CRITICAL
        elif ratio <= self.conserve_threshold:
            return BudgetState.CONSERVE
        else:
            return BudgetState.NORMAL

    def can_afford(self, estimated_cost: float | Decimal, is_optional: bool = False) -> bool:
        cost = Decimal(str(estimated_cost))
        state = self.evaluate_state(cost)
        if state == BudgetState.EXHAUSTED:
            return False
        if state == BudgetState.EMERGENCY:
            return False
        if state == BudgetState.CRITICAL and is_optional:
            return False
        
        rem_after = self.remaining_budget - cost
        if is_optional and rem_after < self.reserved_budget:
            return False
        return True

    def format_amount(self, amount: float | Decimal) -> str:
        d = Decimal(str(amount))
        if self.budget_unit.upper() == "USD":
            return f"${d:.2f}"
        else:
            return f"{d:.2f} {self.budget_unit}"

    def to_dict(self) -> Dict[str, Any]:
        state = self.evaluate_state()
        return {
            "initial": float(self.initial_budget),
            "used": float(self.used_budget),
            "remaining": float(self.remaining_budget),
            "reserved": float(self.reserved_budget),
            "usable": float(self.usable_budget),
            "unit": self.budget_unit,
            "reserve_ratio": float(self.reserve_ratio),
            "state": state.value,
        }
