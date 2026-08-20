"""Planner and Scheduler for AgentCore.
Manages work units, priorities (P0-P4), dependency scheduling, and rule-based planning.
"""
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Set
from decimal import Decimal
from src.core.context import TaskContext


@dataclass
class WorkUnit:
    id: str
    type: str
    priority: str = "P0"  # P0, P1, P2, P3, P4
    instruction: str = ""
    required_capabilities: List[str] = field(default_factory=list)
    estimated_cost: float = 0.1
    dependencies: List[str] = field(default_factory=list)
    optional: bool = False
    status: str = "pending"  # pending, completed, skipped, failed
    input_refs: List[str] = field(default_factory=list)
    source_refs: List[str] = field(default_factory=list)
    context_refs: List[str] = field(default_factory=list)
    output_refs: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "priority": self.priority,
            "instruction": self.instruction,
            "required_capabilities": list(self.required_capabilities),
            "estimated_cost": self.estimated_cost,
            "dependencies": list(self.dependencies),
            "optional": self.optional,
            "status": self.status,
            "input_refs": list(self.input_refs),
            "source_refs": list(self.source_refs),
            "context_refs": list(self.context_refs),
            "output_refs": list(self.output_refs),
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorkUnit":
        return cls(
            id=data.get("id", "unknown"),
            type=data.get("type", "unknown"),
            priority=data.get("priority", "P0"),
            instruction=data.get("instruction", ""),
            required_capabilities=data.get("required_capabilities", []),
            estimated_cost=data.get("estimated_cost", 0.1),
            dependencies=data.get("dependencies", []),
            optional=data.get("optional", False),
            status=data.get("status", "pending"),
            input_refs=data.get("input_refs", []),
            source_refs=data.get("source_refs", []),
            context_refs=data.get("context_refs", []),
            output_refs=data.get("output_refs", []),
            metadata=data.get("metadata", {}),
        )


class Planner:
    @staticmethod
    def plan_task(prompt: str, input_sources: List[str], context: Optional[TaskContext] = None, orchestration: Optional[Dict[str, Any]] = None) -> List[WorkUnit]:
        """Rule-based planning that adapts to input types and task characteristics."""
        # Detect task types from context
        has_repo = False
        has_pdf = False
        has_text = False
        has_structured = False
        has_assets = False
        source_types: Set[str] = set()
        if context:
            for src_type in context.source_types.values():
                source_types.add(src_type)
            has_repo = "repository" in source_types
            has_pdf = "pdf" in source_types
            has_text = "text" in source_types
            has_structured = "structured" in source_types
            has_assets = bool(source_types & {"image", "audio", "video", "slide", "spreadsheet", "document"})
        else:
            for src in input_sources:
                import os
                if os.path.isdir(src):
                    has_repo = True
                elif src.endswith(".pdf"):
                    has_pdf = True
                elif src.endswith((".txt", ".md")):
                    has_text = True
                elif src.endswith((".json", ".csv")):
                    has_structured = True

        # Also detect from prompt keywords
        prompt_lower = prompt.lower()
        repo_keywords = ["repository", "repo", "code", "project", "source"]
        pdf_keywords = ["pdf", "document", "report"]

        if any(kw in prompt_lower for kw in repo_keywords):
            has_repo = True if context and "repository" in (context.repository_context or {}) else has_repo
        if any(kw in prompt_lower for kw in pdf_keywords):
            has_pdf = True

        units = []

        if has_repo:
            units.extend(Planner._repo_plan(context))
        elif has_assets:
            units.extend(Planner._asset_plan(context, source_types))
        elif has_pdf:
            units.extend(Planner._pdf_plan(context))
        elif has_structured:
            units.extend(Planner._structured_plan(context, prompt_lower))
        elif has_text:
            units.extend(Planner._text_plan(context, prompt_lower))
        else:
            units.extend(Planner._text_plan(context, prompt_lower))

        # Add final output unit
        units.append(WorkUnit(
            id="unit_output",
            type="output",
            priority="P1",
            instruction="Produce final output based on previous work unit results",
            required_capabilities=["deterministic"],
            estimated_cost=0.05,
            dependencies=[u.id for u in units if u.id != "unit_output"],
            optional=False,
        ))

        Planner._apply_orchestration(units, orchestration or (context.orchestration if context else {}))
        return units

    @staticmethod
    def _apply_orchestration(units: List[WorkUnit], profile: Dict[str, Any]):
        for unit in units:
            if unit.type in {"parse", "output"}: role = "adaptive-omni-agent"
            elif unit.type in {"code", "analyze", "transform"}: role = "code-engineer"
            else: role = "credit-safe-agent"
            unit.metadata.setdefault("skill_role", role)
            unit.metadata.setdefault("active_skills", profile.get("active_skills", []))
            unit.metadata.setdefault("artifact_types", profile.get("artifact_types", []))
            unit.metadata.setdefault("validation_routes", profile.get("validation_routes", []))

    @staticmethod
    def _asset_plan(context: Optional[TaskContext], source_types: Set[str]) -> List[WorkUnit]:
        modalities = sorted(source_types & {"image", "audio", "video"})
        semantic_caps = ["multimodal"] + modalities if modalities else ["text"]
        return [
            WorkUnit(id="unit_inspect", type="parse", priority="P0", instruction="Inspect asset metadata, format, size, and requested transformation", required_capabilities=["parsing"], estimated_cost=.05, context_refs=["asset_context"]),
            WorkUnit(id="unit_transform", type="transform", priority="P1", instruction="Analyze or transform the supplied artifact according to the user objective", required_capabilities=semantic_caps, estimated_cost=.4, dependencies=["unit_inspect"], context_refs=["asset_context"]),
            WorkUnit(id="unit_validation", type="test", priority="P1", instruction="Validate the result in its rendered or playable form", required_capabilities=["deterministic"], estimated_cost=.1, dependencies=["unit_transform"], context_refs=["asset_context"]),
        ]

    @staticmethod
    def _repo_plan(context: Optional[TaskContext] = None) -> List[WorkUnit]:
        units = []
        units.append(WorkUnit(
            id="unit_inspect",
            type="parse",
            priority="P0",
            instruction="Inspect repository structure, manifests, and relevant source files",
            required_capabilities=["parsing"],
            estimated_cost=0.05,
            context_refs=["repository_context"],
        ))
        units.append(WorkUnit(
            id="unit_implementation",
            type="code",
            priority="P0",
            instruction="Implement changes based on repository analysis and user requirements",
            required_capabilities=["coding"],
            estimated_cost=0.5,
            dependencies=["unit_inspect"],
            context_refs=["repository_context"],
        ))
        units.append(WorkUnit(
            id="unit_validation",
            type="test",
            priority="P2",
            instruction="Validate implementation: run tests, verify correctness",
            required_capabilities=["deterministic"],
            estimated_cost=0.1,
            dependencies=["unit_implementation"],
        ))
        units.append(WorkUnit(
            id="unit_polish",
            type="polish",
            priority="P4",
            instruction="Polish output, add documentation or formatting if needed",
            required_capabilities=["summarization"],
            estimated_cost=0.1,
            dependencies=["unit_validation"],
            optional=True,
        ))
        return units

    @staticmethod
    def _pdf_plan(context: Optional[TaskContext] = None) -> List[WorkUnit]:
        parts = []
        parts.append(WorkUnit(
            id="unit_inspect",
            type="parse",
            priority="P0",
            instruction="Inspect PDF structure: page count, text chunks, fingerprints",
            required_capabilities=["parsing"],
            estimated_cost=0.05,
            context_refs=["document_context"],
        ))
        parts.append(WorkUnit(
            id="unit_analysis",
            type="analyze",
            priority="P0",
            instruction="Analyze PDF content: extract key information from text chunks",
            required_capabilities=["summarization", "text"],
            estimated_cost=0.3,
            dependencies=["unit_inspect"],
            context_refs=["document_context"],
        ))
        parts.append(WorkUnit(
            id="unit_aggregate",
            type="analyze",
            priority="P1",
            instruction="Aggregate analysis results into a coherent output",
            required_capabilities=["summarization"],
            estimated_cost=0.1,
            dependencies=["unit_analysis"],
        ))
        return parts

    @staticmethod
    def _structured_plan(context: Optional[TaskContext], prompt_lower: str) -> List[WorkUnit]:
        parts = []
        parts.append(WorkUnit(
            id="unit_inspect",
            type="parse",
            priority="P0",
            instruction="Parse structured data: inspect schema, headers, record count, sample subset",
            required_capabilities=["parsing", "deterministic"],
            estimated_cost=0.05,
            context_refs=["structured_context"],
        ))
        parts.append(WorkUnit(
            id="unit_process",
            type="analyze",
            priority="P0",
            instruction="Process structured data: filter, transform, or analyze based on user request",
            required_capabilities=["deterministic"],
            estimated_cost=0.2,
            dependencies=["unit_inspect"],
            context_refs=["structured_context"],
        ))
        # If it's about code generation from data
        if "code" in prompt_lower or "implement" in prompt_lower:
            parts.append(WorkUnit(
                id="unit_generate",
                type="code",
                priority="P1",
                instruction="Generate code or implementation from processed structured data",
                required_capabilities=["coding"],
                estimated_cost=0.3,
                dependencies=["unit_process"],
            ))
        return parts

    @staticmethod
    def _text_plan(context: Optional[TaskContext], prompt_lower: str) -> List[WorkUnit]:
        parts = []
        parts.append(WorkUnit(
            id="unit_inspect",
            type="parse",
            priority="P0",
            instruction="Inspect and chunk text input file(s)",
            required_capabilities=["parsing"],
            estimated_cost=0.05,
            context_refs=["document_context"],
        ))
        semantic_keywords = ["summarize", "analyze", "explain", "extract", "translate", "review"]
        if any(kw in prompt_lower for kw in semantic_keywords):
            parts.append(WorkUnit(
                id="unit_analysis",
                type="analyze",
                priority="P0",
                instruction="Perform semantic analysis on the text content",
                required_capabilities=["summarization", "text"],
                estimated_cost=0.3,
                dependencies=["unit_inspect"],
                context_refs=["document_context"],
            ))
        else:
            parts.append(WorkUnit(
                id="unit_process",
                type="analyze",
                priority="P0",
                instruction="Process text content according to user requirements",
                required_capabilities=["text"],
                estimated_cost=0.2,
                dependencies=["unit_inspect"],
                context_refs=["document_context"],
            ))
        return parts


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
