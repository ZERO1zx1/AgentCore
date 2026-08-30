"""Cross-task memory and route outcome metrics with honest cost attribution."""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Dict, Iterable, Mapping
from pathlib import Path
import json


@dataclass
class OutcomeMetrics:
    tasks: int = 0
    tasks_with_recall: int = 0
    recalled_lessons: int = 0
    accepted_lessons: int = 0
    helpful_lessons: int = 0
    avoided_failures: int = 0
    false_positive_recalls: int = 0
    stale_lessons: int = 0
    rejected_poisoning_attempts: int = 0
    estimated_cost_avoided: Decimal = Decimal("0")
    provider_confirmed_cost_avoided: Decimal = Decimal("0")
    path: Path | None = field(default=None, repr=False, compare=False)

    @classmethod
    def load(cls, path: str | Path) -> "OutcomeMetrics":
        target = Path(path)
        try:
            data = json.loads(target.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return cls(path=target)
        names = ("tasks", "tasks_with_recall", "recalled_lessons", "accepted_lessons", "helpful_lessons",
                 "avoided_failures", "false_positive_recalls", "stale_lessons", "rejected_poisoning_attempts")
        metrics = cls(**{name: int(data.get(name, 0)) for name in names},
                      estimated_cost_avoided=Decimal(str(data.get("estimated_cost_avoided", "0"))),
                      provider_confirmed_cost_avoided=Decimal(str(data.get("provider_confirmed_cost_avoided", "0"))),
                      path=target)
        return metrics

    def save(self) -> None:
        if not self.path:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fields = {name: value for name, value in self.__dict__.items() if name != "path"}
        payload = {key: str(value) if isinstance(value, Decimal) else value for key, value in fields.items()}
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        temporary.replace(self.path)

    def record_task(self, *, recalled: int = 0, accepted: int = 0, helpful: int = 0,
                    avoided_failures: int = 0, false_positives: int = 0,
                    estimated_cost_avoided: int | float | Decimal = 0,
                    provider_confirmed_cost_avoided: int | float | Decimal = 0) -> None:
        self.tasks += 1
        self.tasks_with_recall += int(recalled > 0)
        self.recalled_lessons += recalled
        self.accepted_lessons += accepted
        self.helpful_lessons += helpful
        self.avoided_failures += avoided_failures
        self.false_positive_recalls += false_positives
        self.estimated_cost_avoided += Decimal(str(estimated_cost_avoided))
        self.provider_confirmed_cost_avoided += Decimal(str(provider_confirmed_cost_avoided))
        self.save()

    def summary(self) -> Dict[str, Any]:
        ratio = lambda numerator, denominator: round(numerator / denominator, 4) if denominator else 0.0
        return {"tasks": self.tasks, "memory_recall_rate": ratio(self.tasks_with_recall, self.tasks),
                "memory_acceptance_rate": ratio(self.accepted_lessons, self.recalled_lessons),
                "memory_helpfulness_rate": ratio(self.helpful_lessons, self.accepted_lessons),
                "repeat_failure_avoidance": self.avoided_failures,
                "false_positive_recall_rate": ratio(self.false_positive_recalls, self.recalled_lessons),
                "stale_lessons": self.stale_lessons,
                "memory_poisoning_rejection_count": self.rejected_poisoning_attempts,
                "estimated_cost_avoided": str(self.estimated_cost_avoided),
                "provider_confirmed_cost_avoided": str(self.provider_confirmed_cost_avoided)}
