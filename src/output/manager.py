"""Output and Rescue Manager for Manus Mini v2.
Handles final reports, partial rescue reports, and portable path formatting.
"""
import os
from typing import Dict, Any, List, Optional
from src.checkpoint.manifest import TaskManifest
from src.budget.state import BudgetManager

class OutputManager:
    @staticmethod
    def generate_report(manifest: TaskManifest, reason: str = "COMPLETED") -> str:
        report = []
        report.append(f"# Task Execution Report: {manifest.task_id}")
        report.append(f"**Status**: {manifest.status.upper()} — {reason}")
        report.append(f"**Execution Mode**: {manifest.execution_mode}")
        report.append(f"**Updated At**: {manifest.updated_at}\n")

        report.append("## Completed Work")
        if manifest.completed_work:
            for item in manifest.completed_work:
                report.append(f"- {item}")
        else:
            report.append("_No completed units recorded._")

        report.append("\n## Saved Artifacts")
        if manifest.outputs:
            for out in manifest.outputs:
                report.append(f"- {out}")
        else:
            report.append("_No artifacts saved._")

        report.append("\n## Validation Summary")
        if manifest.validation:
            for k, v in manifest.validation.items():
                report.append(f"- **{k}**: {v}")
        else:
            report.append("_Validation not run or not applicable._")

        report.append("\n## Budget Summary")
        b = manifest.budget_info
        unit = b.get("unit", "USD")
        bm = BudgetManager(initial_budget=b.get("initial", 10.0), budget_unit=unit)
        bm.used_budget = b.get("used", 0.0)

        report.append(f"- Budget Unit: {unit}")
        report.append(f"- Initial: {bm.format_amount(b.get('initial', 0))}")
        report.append(f"- Used: {bm.format_amount(b.get('used', 0))}")
        report.append(f"- Remaining: {bm.format_amount(b.get('remaining', 0))}")
        report.append(f"- Reserved: {bm.format_amount(b.get('reserved', 0))}")
        report.append(f"- Budget State: {b.get('state', 'NORMAL')}")

        if manifest.status != "completed":
            report.append("\n## Resume Information")
            report.append(f"To resume this task, load checkpoint manifest.")
            report.append(f"Next pending unit: {manifest.progress.get('current_unit', 'None')}")
            if manifest.errors:
                report.append("\n## Errors / Blockers")
                for err in manifest.errors:
                    report.append(f"- {err}")

        return "\n".join(report)

    @staticmethod
    def save_report(manifest: TaskManifest, output_dir: str = ".manus-mini/outputs") -> str:
        os.makedirs(output_dir, exist_ok=True)
        path = os.path.join(output_dir, f"{manifest.task_id}_report.md")
        content = OutputManager.generate_report(manifest)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return path
