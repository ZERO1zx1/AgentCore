"""Provider-aware route health, learning, and deterministic fallback policy."""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Dict, Iterable, Mapping, Sequence
from pathlib import Path
import json


@dataclass
class RouteStats:
    route_id: str
    capabilities: tuple[str, ...]
    attempts: int = 0
    successes: int = 0
    total_latency_ms: Decimal = Decimal("0")
    provider_confirmed_cost: Decimal = Decimal("0")
    estimated_cost: Decimal = Decimal("0")
    recent_failures: int = 0
    available: bool = True

    @property
    def success_rate(self) -> Decimal:
        return Decimal(self.successes) / Decimal(self.attempts) if self.attempts else Decimal("0")

    @property
    def average_latency_ms(self) -> Decimal:
        return self.total_latency_ms / Decimal(self.attempts) if self.attempts else Decimal("0")

    def record(self, *, success: bool, latency_ms: int | float | Decimal,
               cost: int | float | Decimal = 0, cost_source: str = "unknown") -> None:
        self.attempts += 1
        self.successes += int(success)
        self.recent_failures = 0 if success else self.recent_failures + 1
        self.total_latency_ms += Decimal(str(latency_ms))
        if cost_source == "provider_confirmed":
            self.provider_confirmed_cost += Decimal(str(cost))
        elif cost_source == "estimated":
            self.estimated_cost += Decimal(str(cost))

    def score(self, required_capabilities: Sequence[str]) -> Decimal:
        if not self.available or not set(required_capabilities).issubset(self.capabilities):
            return Decimal("-1")
        reliability = self.success_rate if self.attempts else Decimal("0.5")
        latency_penalty = min(Decimal("0.25"), self.average_latency_ms / Decimal("120000"))
        failure_penalty = min(Decimal("0.35"), Decimal(self.recent_failures) * Decimal("0.08"))
        return reliability - latency_penalty - failure_penalty

    def to_dict(self) -> Dict[str, Any]:
        return {"route_id": self.route_id, "capabilities": list(self.capabilities), "attempts": self.attempts,
                "successes": self.successes, "success_rate": str(self.success_rate),
                "average_latency_ms": str(self.average_latency_ms),
                "provider_confirmed_cost": str(self.provider_confirmed_cost),
                "estimated_cost": str(self.estimated_cost), "recent_failures": self.recent_failures,
                "available": self.available}


class CapabilityHealthRegistry:
    def __init__(self, path: str | Path | None = None):
        self.routes: Dict[str, RouteStats] = {}
        self.path = Path(path) if path else None
        self._load()

    def _load(self) -> None:
        if not self.path or not self.path.exists():
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            for item in data.get("routes", []):
                stats = RouteStats(
                    route_id=str(item["route_id"]), capabilities=tuple(item.get("capabilities", [])),
                    attempts=int(item.get("attempts", 0)), successes=int(item.get("successes", 0)),
                    total_latency_ms=Decimal(str(item.get("total_latency_ms", "0"))),
                    provider_confirmed_cost=Decimal(str(item.get("provider_confirmed_cost", "0"))),
                    estimated_cost=Decimal(str(item.get("estimated_cost", "0"))),
                    recent_failures=int(item.get("recent_failures", 0)), available=bool(item.get("available", True)),
                )
                self.routes[stats.route_id] = stats
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
            self.routes = {}

    def save(self) -> None:
        if not self.path:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"schema_version": "1.0", "routes": [
            {**stats.to_dict(), "total_latency_ms": str(stats.total_latency_ms)}
            for stats in sorted(self.routes.values(), key=lambda item: item.route_id)
        ]}
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        temporary.replace(self.path)

    def register(self, route_id: str, capabilities: Sequence[str]) -> RouteStats:
        return self.routes.setdefault(route_id, RouteStats(route_id, tuple(sorted(set(capabilities)))))

    def record(self, route_id: str, capabilities: Sequence[str], **outcome: Any) -> RouteStats:
        stats = self.register(route_id, capabilities)
        stats.record(**outcome)
        self.save()
        return stats

    def rank(self, required_capabilities: Sequence[str]) -> list[RouteStats]:
        capable = [stats for stats in self.routes.values() if stats.score(required_capabilities) > Decimal("-1")]
        return sorted(capable, key=lambda item: (item.score(required_capabilities), item.success_rate, -item.average_latency_ms), reverse=True)


@dataclass(frozen=True)
class FallbackDecision:
    route_id: str | None
    reason: str
    blocked: bool


class DeterministicFallbackPolicy:
    """Choose a capable changed route; never repeat an unchanged paid failure."""

    @staticmethod
    def choose(candidates: Sequence[RouteStats], required_capabilities: Sequence[str],
               attempted_routes: Sequence[str], failure_hypothesis_changed: bool,
               reserve_available: bool) -> FallbackDecision:
        attempted = set(attempted_routes)
        for stats in candidates:
            if not set(required_capabilities).issubset(stats.capabilities) or not stats.available:
                continue
            if stats.route_id in attempted and not failure_hypothesis_changed:
                continue
            if not reserve_available and stats.route_id not in attempted:
                return FallbackDecision(None, "reserve is unavailable for a new paid route", True)
            return FallbackDecision(stats.route_id, "selected next capable route with a changed path", False)
        return FallbackDecision(None, "no untried capable route remains", True)
