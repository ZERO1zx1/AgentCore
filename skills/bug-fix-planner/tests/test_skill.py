"""Focused tests for the bug-fix-planner skill.

Covers the deterministic triage gate (CRITICAL/HIGH confirmed -> fix,
reproducible MEDIUM -> fix, everything else -> unverified risk) and verifies
that SKILL.md documents the required Phase-10 gates so the prompt contract
cannot silently regress.
"""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

SKILL_ROOT = Path(__file__).resolve().parents[1]
SKILL_MD = SKILL_ROOT / "SKILL.md"
SCRIPT = SKILL_ROOT / "scripts" / "bug_fix_planner.py"

_spec = importlib.util.spec_from_file_location("bug_fix_planner", SCRIPT)
assert _spec and _spec.loader is not None
planner = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(planner)


def _finding(severity="HIGH", *, confirmed=True, reproducible=True, **overrides):
    data = {
        "id": "F1",
        "severity": severity,
        "confirmed": confirmed,
        "reproducible": reproducible,
        "files": ["src/core/engine.py"],
        "evidence": "reproduced via test script",
    }
    data.update(overrides)
    return data


class TestTriageGate:
    def test_confirmed_high_is_fix_target(self):
        assert planner.is_fix_target(_finding("HIGH")) is True

    def test_confirmed_critical_is_fix_target(self):
        assert planner.is_fix_target(_finding("CRITICAL")) is True

    def test_unconfirmed_high_is_not_fix_target(self):
        assert planner.is_fix_target(_finding("HIGH", confirmed=False)) is False

    def test_reproducible_medium_is_fix_target(self):
        assert planner.is_fix_target(_finding("MEDIUM", reproducible=True)) is True

    def test_non_reproducible_medium_is_not_fix_target(self):
        assert planner.is_fix_target(_finding("MEDIUM", reproducible=False)) is False

    def test_low_is_never_fix_target(self):
        assert planner.is_fix_target(_finding("LOW", reproducible=True)) is False

    def test_severity_is_case_insensitive(self):
        assert planner.is_fix_target(_finding("high")) is True
        assert planner.is_fix_target(_finding("medium", reproducible=True)) is True

    def test_triage_splits_findings(self):
        findings = [
            _finding("CRITICAL"),
            _finding("MEDIUM", reproducible=False),
            _finding("LOW"),
            _finding("HIGH", confirmed=False),
        ]
        to_fix, unverified = planner.triage(findings)
        assert [item["id"] for item in to_fix] == ["F1"]
        assert len(unverified) == 3

    def test_plan_summary_orders_fixes_first(self):
        summary = planner.plan_summary(
            [
                _finding("MEDIUM", reproducible=True, id="mid"),
                _finding("CRITICAL", id="crit"),
                _finding("LOW", id="low"),
            ]
        )
        assert summary["fix_count"] == 2
        assert summary["unverified_count"] == 1
        assert [item["id"] for item in summary["fix"]] == ["mid", "crit"]
        assert summary["unverified_risk"][0]["id"] == "low"
        assert "missing_evidence" in summary["unverified_risk"][0]


class TestSkillContract:
    def test_skill_md_exists_with_frontmatter(self):
        assert SKILL_MD.is_file()
        text = SKILL_MD.read_text(encoding="utf-8")
        assert text.startswith("---\n")
        assert "name: bug-fix-planner" in text
        assert "description:" in text

    def test_skill_documents_triage_gate(self):
        text = SKILL_MD.read_text(encoding="utf-8")
        assert "Critical" in text and "High" in text
        assert "reproducible" in text
        assert "unverified risk" in text.lower()

    def test_skill_documents_implementation_and_test_rules(self):
        text = SKILL_MD.read_text(encoding="utf-8")
        lower = text.lower()
        assert "smallest complete" in lower
        assert "focused" in lower and "test" in lower
        assert "do not modify" in lower
        assert "commit" in lower or "push" in lower

    def test_skill_references_the_triage_script(self):
        text = SKILL_MD.read_text(encoding="utf-8")
        assert "scripts/bug_fix_planner.py" in text

    def test_script_has_a_help_cli(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--help"],
            capture_output=True, text=True, timeout=30,
        )
        assert result.returncode == 0
        assert "--findings" in result.stdout

    def test_cli_triage_json_output(self, tmp_path):
        findings_file = tmp_path / "findings.json"
        findings_file.write_text(
            json.dumps(
                [
                    _finding("HIGH", id="f-high"),
                    _finding("MEDIUM", reproducible=False, id="f-medium"),
                ]
            ),
            encoding="utf-8",
        )
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--findings", str(findings_file), "--format", "json"],
            capture_output=True, text=True, timeout=30,
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["fix_count"] == 1
        assert data["unverified_count"] == 1
        assert data["fix"][0]["id"] == "f-high"