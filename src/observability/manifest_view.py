"""Canonical, read-only projections of a TaskManifest.

Keeping these projections in one place prevents the CLI, MCP bridge, and web
dashboard from inventing incompatible names for the same manifest fields.
"""

from __future__ import annotations

from typing import Any, Dict

from src.checkpoint.manifest import TaskManifest


def manifest_prompt(manifest: TaskManifest) -> str:
    """Return the best persisted prompt/description available for a task."""
    legacy_prompt = getattr(manifest, "task_prompt", None)
    if legacy_prompt:
        return str(legacy_prompt)

    context = manifest.task_context_dict or {}
    if context.get("user_prompt"):
        return str(context["user_prompt"])
    if context.get("prompt"):
        return str(context["prompt"])

    units = manifest.work_units_data or []
    if units:
        return str(units[0].get("instruction") or "Autonomous Task")
    return "Autonomous Task"


def manifest_timestamp(manifest: TaskManifest) -> str:
    return str(
        getattr(manifest, "updated_at", None)
        or getattr(manifest, "created_at", None)
        or getattr(manifest, "timestamp", "")
    )


def budget_view(manifest: TaskManifest) -> Dict[str, Any]:
    """Return canonical budget keys while preserving the engine snapshot."""
    raw = dict(manifest.budget_info or {})
    initial = raw.get("initial", raw.get("budget_limit", 0))
    used = raw.get("used", raw.get("budget_spent", 0))
    remaining = raw.get("remaining", raw.get("remaining_budget", 0))
    reserved = raw.get("reserved", raw.get("reserve_amount", 0))
    total_tokens = sum(int(item.get("total_tokens", 0) or 0) for item in (manifest.usage_history or []))
    raw.update(
        {
            "initial": initial,
            "used": used,
            "remaining": remaining,
            "reserved": reserved,
            "total_tokens": total_tokens,
        }
    )
    return raw


def task_summary(manifest: TaskManifest, *, active_in_memory: bool) -> Dict[str, Any]:
    budget = budget_view(manifest)
    orchestration = manifest.orchestration or {}
    return {
        "task_id": manifest.task_id,
        "prompt": manifest_prompt(manifest),
        "status": manifest.status,
        "source": orchestration.get("source", "unknown"),
        "active_in_memory": active_in_memory,
        "completed_units": len(manifest.completed_work),
        "total_units": len(manifest.work_units_data or []),
        "budget_spent": float(budget.get("used", 0)),
        "budget_limit": float(budget.get("initial", 0)),
        "timestamp": manifest_timestamp(manifest),
    }
