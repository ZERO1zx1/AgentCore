"""Planner and Scheduler for Manus Mini v2.
Manages work units, priorities (P0-P4), and dependency scheduling.
"""
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from decimal import Decimal

@dataclass
class WorkUnit:
    id: str
    type: str
    priority: str = "P0"  # P0, P1, P2, P3, P4
    required_capabilities: List[str] = field(default_factory=list)
    estimated_cost: float = 0.1
    dependencies: List[str] = field(default_factory=list)
    optional: bool = False
    status: str = "pending"  # pending, completed, skipped, failed
    input_refs: List[str] = field(default_factory=list)
    output_refs: List[str] = field(default_factory=list)

class Planner:
    @staticmethod
    def plan_task(prompt: str, input_sources: List[str]) -> List[WorkUnit]:
        units = []
        # Default planning logic: Ingestion -> Analysis -> Execution -> Validation
        units.append(WorkUnit(
            id="unit_inspect",
            type="parse",
            priority="P0",
            required_capabilities=["parsing"],
            estimated_cost=0.05
        ))
        units.append(WorkUnit(
            id="unit_core_work",
            type="code",
            priority="P0",
            required_capabilities=["coding"],
            estimated_cost=0.5,
            dependencies=["unit_inspect"]
        ))
        units.append(WorkUnit(
            id="unit_validation",
            type="test",
            priority="P2",
            required_capabilities=["deterministic"],
            estimated_cost=0.1,
            dependencies=["unit_core_work"]
        ))
        units.append(WorkUnit(
            id="unit_polish",
            type="polish",
            priority="P4",
            required_capabilities=["summarization"],
            estimated_cost=0.1,
            dependencies=["unit_validation"],
            optional=True
        ))
        return units

class Scheduler:
    @staticmethod
    def get_eligible_units(units: List[WorkUnit], completed_ids: List[str], execution_mode: str, budget_state: str) -> List[WorkUnit]:
        eligible = []
        for u in units:
            if u.status in ["completed", "skipped"]:
                continue
            
            # Check dependencies
            deps_met = all(dep in completed_ids for dep in u.dependencies)
            if not deps_met:
                continue

            # Check execution mode and budget constraints
            if budget_state in ["CRITICAL", "EMERGENCY"] and u.priority in ["P3", "P4"]:
                u.status = "skipped"
                continue
            if execution_mode == "CREDIT_SAFE" and u.optional and budget_state != "NORMAL":
                u.status = "skipped"
                continue

            eligible.append(u)
        
        # Sort by priority: P0, P1, P2, P3, P4
        priority_order = {"P0": 0, "P1": 1, "P2": 2, "P3": 3, "P4": 4}
        eligible.sort(key=lambda x: priority_order.get(x.priority, 5))
        return eligible
