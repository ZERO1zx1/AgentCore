"""Deterministic local full-scan report generator.

This is a static triage tool. It never claims that a finding is a runtime
failure; runtime validation belongs to the paired code-engineer workflow.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import json
import re
import os
from datetime import datetime
from typing import Iterable


@dataclass(frozen=True)
class Finding:
    title: str
    location: str
    severity: str
    finding_class: str
    root_cause_proven: str
    root_cause_hypothesis: str
    confidence: float
    impact: str
    reproduce: str
    fix: str
    revalidate: str
    expected: str
    actual: str
    status: str = "STATIC-RISK"
    proposed_by: str = "ai-agent"
    confirmed_by: str = "PENDING"
    evidence: str = "static source evidence"
    boundary_note: str = ""


_SKIP_DIRS = {".git", ".venv", "venv", "__pycache__", "node_modules", ".agentcore", ".pytest_cache", ".test-temp", ".agent-memory", "dist", "build"}
_SECRET_RE = re.compile(r"(?i)(api[_-]?key|password|secret|access[_-]?token)\s*[:=]\s*['\"][^'\"]+['\"]")


def _files(root: Path, mode: str) -> Iterable[Path]:
    def walk():
        for directory, dirs, names in os.walk(root, followlinks=False):
            dirs[:] = sorted(name for name in dirs if name not in _SKIP_DIRS and not (Path(directory) / name).is_symlink())
            for name in sorted(names):
                path = Path(directory) / name
                if path.is_symlink() or not path.is_file():
                    continue
                relative = path.relative_to(root).parts
                if len(relative) > 2 and relative[0] == "docs" and re.fullmatch(r"\d{4}-\d{2}-\d{2}", relative[1]):
                    continue
                yield path
    paths = walk()
    if mode == "diff":
        # Diff filtering is intentionally conservative: callers can pass a
        # pre-filtered root when they need exact changed-file scope.
        paths = (p for p in paths if p.suffix.lower() in {".py", ".js", ".ts", ".tsx", ".json", ".yml", ".yaml", ".toml"})
    return paths


def scan(root: str | Path = ".", mode: str = "strict") -> list[Finding]:
    base = Path(root).resolve()
    findings: list[Finding] = []
    for path in _files(base, mode):
        if path.suffix.lower() not in {".py", ".js", ".ts", ".tsx", ".json", ".yml", ".yaml", ".toml", ".md"}:
            continue
        try:
            if path.stat().st_size > 2_000_000:
                continue
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        rel = path.relative_to(base).as_posix()
        for number, line in enumerate(lines, 1):
            if _SECRET_RE.search(line) and "getenv" not in line.lower() and "example" not in line.lower():
                findings.append(Finding(
                    "Possible hardcoded secret", f"{rel}:{number}", "HIGH", "STATIC-RISK",
                    "A credential-like assignment is present in source.", "The value may be a test/example value.", 0.72,
                    "Scope=file | Blast=all readers | Timing=on next deploy | Recovery=rotate secret",
                    f"rg -n -i 'api[_-]?key|password|secret|token' {rel}",
                    "Move the value to environment/secret storage and rotate any real credential.",
                    f"rg -n -i 'api[_-]?key|password|secret|token' {rel}",
                    "No credential-like literal", "[REDACTED credential-like assignment]", boundary_note="Secret validity requires external credential review.",
                ))
            if re.search(r"except\s+(Exception|BaseException)\s*:", line):
                findings.append(Finding(
                    "Broad exception handler", f"{rel}:{number}", "MEDIUM", "STATIC-RISK",
                    "The code catches a broad exception class without visible classification.", "The handler may intentionally be a boundary guard.", 0.58,
                    "Scope=module | Blast=all callers | Timing=on failure | Recovery=manual review",
                    f"Get-Content {rel} | Select-Object -Skip {max(0, number-3)} -First 8",
                    "Catch the narrow exception types and preserve useful error context.",
                    f"python -m compileall {rel}",
                    "No broad catch at this boundary", line.strip(),
                ))
            if "TODO" in line or "FIXME" in line:
                findings.append(Finding(
                    "Unresolved implementation marker", f"{rel}:{number}", "LOW", "STATIC-RISK",
                    "The source contains an explicit follow-up marker.", "It may be documentation rather than unfinished behavior.", 0.45,
                    "Scope=file | Blast=unknown | Timing=unknown | Recovery=manual review",
                    f"rg -n 'TODO|FIXME' {rel}", "Resolve or document the marker.", f"rg -n 'TODO|FIXME' {rel}",
                    "No unresolved marker", line.strip(),
                ))
    if mode == "fast":
        findings = [item for item in findings if item.severity in {"CRITICAL", "HIGH"}]
    return findings


def render(findings: list[Finding], *, root: str, mode: str, json_output: bool = False) -> str:
    payload = {"root": str(Path(root).resolve()), "mode": mode, "finding_count": len(findings), "findings": [asdict(item) for item in findings]}
    if json_output:
        return json.dumps(payload, indent=2, ensure_ascii=False)
    lines = [f"Full Scan | root={payload['root']} | mode={mode} | findings={len(findings)}", ""]
    if not findings:
        return "\n".join(lines + ["PASS: No configured static findings."])
    for index, item in enumerate(findings, 1):
        lines.extend([f"### [{index}] {item.title}", f"- Location: {item.location}", f"- Severity: {item.severity}", f"- Class: {item.finding_class}", f"- Root Cause proven: {item.root_cause_proven}", f"- Root Cause hypoth.: {item.root_cause_hypothesis}", f"- Confidence: {item.confidence:.2f}", f"- Impact: {item.impact}", f"- Reproduce: {item.reproduce}", f"- Fix: {item.fix}", f"- Re-validate: {item.revalidate}", f"- Expected / Actual: {item.expected} / {item.actual}", f"- Status: {item.status}", f"- Proposed by: {item.proposed_by}", f"- Confirmed by: {item.confirmed_by}", f"- Evidence: {item.evidence}", f"- Boundary Note: {item.boundary_note}", ""])
    return "\n".join(lines)


def write_report_bundle(
    findings: list[Finding],
    *,
    root: str,
    mode: str,
    output_dir: str | Path | None = None,
    now: datetime | None = None,
) -> tuple[Path, Path]:
    """Write one stable, organized human/CI report pair for a scan run."""
    timestamp = now or datetime.now()
    base = Path(output_dir) if output_dir else Path(root) / "docs"
    report_dir = base / timestamp.strftime("%Y-%m-%d") / "reports" / mode
    report_dir.mkdir(parents=True, exist_ok=True)
    date_dir = report_dir.parent.parent
    readme_path = date_dir / "README.md"
    if not readme_path.exists():
        readme_path.write_text(
            f"# Full-scan artifacts — {timestamp:%Y-%m-%d}\n\n"
            "This folder contains the artifacts for one scan date.\n\n"
            "- `reports/` — human-readable and machine-readable scan results\n"
            "- `dependencies/` — dependency and advisory checks\n"
            "- `frontend/` — frontend probes and build checks\n"
            "- `backend/` — backend tests and runtime checks\n"
            "- `database/` — SQL probes and regression results\n"
            "- `scripts/` — scripts used to produce these artifacts\n",
            encoding="utf-8",
        )
    markdown_path = report_dir / "report.md"
    json_path = report_dir / "report.json"
    markdown_path.write_text(render(findings, root=root, mode=mode), encoding="utf-8")
    json_path.write_text(render(findings, root=root, mode=mode, json_output=True), encoding="utf-8")
    return markdown_path, json_path
