"""Deterministic triage for the bug-fix-planner skill.

Applies the Phase-10 triage gate to a findings list:

    - CRITICAL / HIGH findings are fix targets only when "confirmed" is true.
    - MEDIUM findings are fix targets only when "confirmed" is true AND the
      finding is clearly reproducible ("reproducible": true).
    - Everything else is an unverified risk and must not drive code changes.

Dependency-free on purpose: this module only uses the standard library so the
skill can run in any local Python environment.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Dict, List, Sequence, Tuple


FIXABLE_SEVERITIES = frozenset({"CRITICAL", "HIGH"})


def is_fix_target(finding: Dict[str, Any]) -> bool:
    """Return True only for confirmed, fix-level findings.

    Severity is case-insensitive. A finding is a fix target when it is marked
    as confirmed AND either (a) its severity is CRITICAL/HIGH, or (b) it is a
    MEDIUM finding that is also clearly reproducible.
    """
    if not bool(finding.get("confirmed", False)):
        return False
    severity = str(finding.get("severity", "")).upper()
    if severity in FIXABLE_SEVERITIES:
        return True
    return severity == "MEDIUM" and bool(finding.get("reproducible", False))


def classification(finding: Dict[str, Any]) -> str:
    """Classify a finding as 'fix' or 'unverified-risk'."""
    return "fix" if is_fix_target(finding) else "unverified-risk"


def triage(findings: Sequence[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Split findings into (to_fix, unverified) using the triage gate."""
    findings = list(findings)
    to_fix = [item for item in findings if is_fix_target(item)]
    unverified = [item for item in findings if not is_fix_target(item)]
    return to_fix, unverified


def plan_summary(findings: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """Return an ordered plan summary: fixes first, then unverified risks."""
    to_fix, unverified = triage(findings)
    return {
        "fix": [
            {
                "id": str(item.get("id", "")),
                "severity": str(item.get("severity", "")).upper(),
                "files": list(item.get("files", []) or []),
            }
            for item in to_fix
        ],
        "unverified_risk": [
            {
                "id": str(item.get("id", "")),
                "severity": str(item.get("severity", "")).upper(),
                "missing_evidence": str(item.get("missing_evidence", ""))
                or "not confirmed; severity below gate or not reproducible",
            }
            for item in unverified
        ],
        "fix_count": len(to_fix),
        "unverified_count": len(unverified),
    }


def _load_findings(path: str) -> List[Dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("findings", "items", "results"):
            if key in data and isinstance(data[key], list):
                return data[key]
    raise ValueError("findings file must be a JSON list or an object with a 'findings' list")


def main(argv: Sequence[str] = ()) -> int:
    parser = argparse.ArgumentParser(prog="bug-fix-planner", description="Apply the bug-fix-planner triage gate.")
    parser.add_argument("--findings", help="JSON file: a list of finding dicts or a dict with a 'findings' list")
    parser.add_argument("--format", choices=["json", "table"], default="json")
    args = parser.parse_args(argv or None)

    findings = _load_findings(args.findings) if args.findings else []
    summary = plan_summary(findings)

    if args.format == "json":
        print(json.dumps(summary, indent=2, ensure_ascii=False))
        return 0

    print(f"FIX TARGETS ({summary['fix_count']}):")
    for item in summary["fix"]:
        print(f"  - [{item['severity']}] {item['id']}: {', '.join(item['files']) or '(files not listed)'}")
    print(f"\nUNVERIFIED RISKS ({summary['unverified_count']}):")
    for item in summary["unverified_risk"]:
        print(f"  - [{item['severity']}] {item['id']}: {item['missing_evidence']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))