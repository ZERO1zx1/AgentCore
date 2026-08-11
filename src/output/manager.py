"""Output and Rescue Manager for Credit-Safe Agent.
Handles final outputs, partial outputs on budget exhaustion, and resume manifests.
"""
import os
import json
from typing import Dict, Any, List, Optional
from src.checkpoint.manifest import TaskManifest

class OutputManager:
    @staticmethod
    def generate_report(manifest: TaskManifest, reason: str = "COMPLETED") -> str:
        report = []
        report.append(f"# Task Execution Report: {manifest.task_id}")
        report.append(f"**Status**: {manifest.status.upper()} — {reason}")
        report.append(f"**Updated At**: {manifest.updated_at}\n")

        report.append("## Completed Work")
        if manifest.completed_work:
            for item in manifest.completed_work:
                report.append(f"- {item}")
        else:
            report.append("_No completed units recorded._")

        report.append("\n## Saved Outputs")
        if manifest.outputs:
            for out in manifest.outputs:
                report.append(f"- {out}")
        else:
            report.append("_No outputs saved._")

        report.append("\n## Validation Status")
        if manifest.validation:
            for k, v in manifest.validation.items():
                report.append(f"- **{k}**: {v}")
        else:
            report.append("_Validation not run or not applicable._")

        report.append("\n## Budget State")
        b = manifest.budget_info
        report.append(f"- Initial: ${b.get('initial', 0):.4f}")
        report.append(f"- Used: ${b.get('used', 0):.4f}")
        report.append(f"- Remaining: ${b.get('remaining', 0):.4f}")
        report.append(f"- State: {b.get('state', 'NORMAL')}")

        if manifest.status != "completed":
            report.append("\n## Resume Information")
            report.append(f"To resume this task, load checkpoint manifest from `.checkpoints/{manifest.task_id}_manifest.json`.")
            report.append(f"Next pending unit: {manifest.progress.get('current_unit', 'None')}")

        return "\n".join(report)

    @staticmethod
    def save_report(manifest: TaskManifest, output_dir: str = ".manus-mini/outputs") -> str:
        os.makedirs(output_dir, exist_ok=True)
        path = os.path.join(output_dir, f"{manifest.task_id}_report.md")
        content = OutputManager.generate_report(manifest)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return path
