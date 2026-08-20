"""Skill Security Scanner for AgentCore plugin.

Static, dependency-free skill vetting inspired by Snyk agent-scan and
NVIDIA SkillSpector. Detects prompt injection, anti-refusal, exfiltration,
secret handling, dangerous command execution, and obfuscation before a skill
is installed into any AI agent.

Scoring (SkillSpector-style):
    CRITICAL +50, HIGH +25, MEDIUM +10, LOW +5; executable multiplier 1.3.
    score 0-20 LOW/SAFE, 21-50 MEDIUM/CAUTION, 51-80 HIGH, 81-100 CRITICAL.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

SCAN_VERSION = "1.0.0"


@dataclass
class Finding:
    id: str
    category: str
    severity: str
    location: str
    evidence: str
    confidence: float = 0.5
    explanation: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "category": self.category,
            "severity": self.severity,
            "location": self.location,
            "evidence": self.evidence,
            "confidence": round(self.confidence, 2),
            "explanation": self.explanation,
        }


@dataclass
class ScanReport:
    target: str
    scanned_at: str
    score: int = 0
    severity: str = "LOW"
    recommendation: str = "SAFE"
    findings: List[Finding] = field(default_factory=list)
    components: List[Dict[str, Any]] = field(default_factory=list)
    has_executable_scripts: bool = False
    llm_used: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scan": {
                "target": self.target,
                "scanned_at": self.scanned_at,
                "scanner_version": SCAN_VERSION,
            },
            "risk_assessment": {
                "score": self.score,
                "severity": self.severity,
                "recommendation": self.recommendation,
            },
            "components": self.components,
            "issues": [f.to_dict() for f in self.findings],
            "metadata": {
                "has_executable_scripts": self.has_executable_scripts,
                "llm_used": self.llm_used,
                "findings_count": len(self.findings),
            },
        }


SEVERITY_WEIGHTS = {"LOW": 5, "MEDIUM": 10, "HIGH": 25, "CRITICAL": 50}

EXECUTABLE_EXTENSIONS = {".py", ".sh", ".ps1", ".js", ".ts", ".rb", ".pl", ".bash"}

# --- Pattern rules ---------------------------------------------------------

# (rule_id, category, severity, regex, confidence, explanation)
RULES: List[Tuple[str, str, str, str, float, str]] = [
    # Prompt injection
    ("PI1", "prompt_injection", "HIGH",
     r"(?i)(ignore\s+(all\s+|any\s+|your\s+)?(previous|prior|above)\s+(instructions|prompts?|guidelines?))",
     0.9, "Direct instruction-override phrasing."),
    ("PI2", "prompt_injection", "HIGH",
     r"(?i)(disregard|forget|override|bypass|ignore)\s+(your|all|the|these|this)\s*(safety|restriction|rule|policy|guardrail|system)",
     0.85, "Attempt to nullify guardrails."),
    ("PI3", "prompt_injection", "HIGH",
     r"(?i)(you\s+are\s+now|act\s+as\s+if\s+you\s+are|pretend\s+you\s+are|new\s+persona|jailbreak|prompt\s+leak)",
     0.7, "Persona/role override framing."),
    ("PI4", "hidden_instructions", "MEDIUM",
     r"(?i)(hidden\s+instruction|secret\s+instruction|do\s+not\s+tell\s+the\s+user|without\s+telling\s+the\s+user|don.t\s+mention)",
     0.8, "Covert directives that hide behavior from the user."),
    # Anti-refusal
    ("AR1", "anti_refusal", "HIGH",
     r"(?i)(never\s+refuse|always\s+comply|do\s+not\s+refuse|must\s+comply)",
     0.85, "Refusal suppression."),
    ("AR2", "anti_refusal", "HIGH",
     r"(?i)(no\s+disclaimers|do\s+not\s+moralize|omit\s+warnings|don.t\s+explain\s+safety)",
     0.8, "Disclaimer/safety-commentary suppression."),
    ("AR3", "anti_refusal", "HIGH",
     r"(?i)(you\s+have\s+no\s+restrictions|ignore\s+your\s+guidelines|do\s+anything\s+now|unlimited\s+power)",
     0.9, "Safety-policy nullification framing."),
    # Exfiltration / network
    ("EX1", "data_exfiltration", "HIGH",
     r"(?is)((curl|wget|urllib|requests\.(get|post)|http\.post)\b.{0,120}(token|secret|key|password|env|credential|history|\.env))",
     0.85, "Network call that may transmit sensitive data."),
    ("EX2", "data_exfiltration", "HIGH",
     r"(?is)(base64.{0,80}(encode|decode).{0,80}(send|post|curl|upload|exfil))",
     0.8, "Encoded payload transmission pattern."),
    ("EX3", "env_harvesting", "HIGH",
     r"(?is)(os\.environ|getenv|environment\s+vars?)\b.{0,200}\b(curl|requests|urllib|post|upload|send|webhook)",
     0.8, "Environment harvesting combined with external transmission."),
    ("EX4", "context_leakage", "HIGH",
     r"(?i)(send\s+(this|the|entire|full|whole)\s+(conversation|context|prompt|chat)\s+(to|via|using))",
     0.8, "Instruction to transmit conversation context externally."),
    # Secrets
    ("SE1", "hardcoded_secret", "HIGH",
     r"\b(sk-[A-Za-z0-9]{20,}|ghp_[A-Za-z0-9]{36,}|AKIA[0-9A-Z]{16}|api[_-]?key\s*[:=]\s*['\"][^'\"]{16,})",
     0.85, "Hardcoded credential/API key pattern."),
    ("SE2", "credential_access", "MEDIUM",
     r"(?i)(\.ssh[\\/]|id_rsa|id_ed25519|\.aws[\\/]credentials|read.*(token|password|secret)\s*file)",
     0.7, "Access to credential files."),
    # Dangerous command execution
    ("CM1", "dangerous_command", "HIGH",
     r"(?i)(curl|wget)\s+[^\n;]+\s*\|?\s*(sh|bash|zsh)\b",
     0.9, "Remote script pipe-to-shell (curl|bash)."),
    ("CM2", "dangerous_command", "HIGH",
     r"(?i)(base64\s+-\s*d[^\n]*\|?\s*(sh|bash)|eval\s*\(\s*(os\.popen|subprocess|exec))",
     0.85, "Encoded or evaluated command execution."),
    ("CM3", "dangerous_command", "MEDIUM",
     r"(?i)(sudo\b|os\.system\b|subprocess\.(call|run|popen|check_output)\b|Popen\b)",
     0.6, "Privileged or subprocess execution."),
    ("CM4", "self_modification", "CRITICAL",
     r"(?i)(crontab\b|schtasks\b|startup\s+(folder|script)|write.*(itself|own\s+code)|self\s+modif|patch\s+own)",
     0.8, "Unauthorized persistence or self-modification."),
    # Obfuscation
    ("OB1", "obfuscation", "HIGH",
     r"[A-Za-z0-9+/]{120,}={0,2}",
     0.6, "Large base64/encoded blob (possible hidden payload)."),
    ("OB2", "obfuscation", "MEDIUM",
     r"(?i)(eval\(|exec\(|(?<!re\.)compile\s*\(|__import__\(|getattr\(os|\\\\x[0-9a-f]{2})",
     0.65, "Dynamic/reflective code execution primitive."),
    ("OB3", "obfuscation", "MEDIUM",
     r"(?i)([\u202e\u202d\u2066\u2067\u2069])",
     0.8, "Unicode bidi/isolate override characters."),
]

# --- File discovery --------------------------------------------------------

def _is_ignored(rel: str) -> bool:
    parts = set(rel.replace("\\", "/").split("/"))
    ignored = {"node_modules", "__pycache__", ".git", ".venv", "venv", ".pytest_cache"}
    return bool(parts & ignored)


def _is_analysis_target(rel: str) -> bool:
    name = rel.lower()
    if name.endswith((".pyc", ".pyo", ".class", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".wav", ".mp3")):
        return False
    if _is_ignored(rel):
        return False
    return True


def discover_components(target: Path) -> List[Dict[str, Any]]:
    components: List[Dict[str, Any]] = []
    if target.is_file():
        components.append(_component_for(target, Path(target.name)))
        return components
    for root, dirs, files in os.walk(target):
        dirs[:] = [d for d in dirs if d not in {"node_modules", "__pycache__", ".git", ".venv", "venv", ".pytest_cache"}]
        for name in files:
            full = Path(root) / name
            rel = full.relative_to(target)
            if not _is_analysis_target(str(rel)):
                continue
            components.append(_component_for(full, rel))
    components.sort(key=lambda c: c["path"])
    return components


def _component_for(full: Path, rel: Path) -> Dict[str, Any]:
    ext = rel.suffix.lower()
    try:
        lines = sum(1 for _ in open(full, "r", encoding="utf-8", errors="replace"))
    except Exception:
        lines = 0
    try:
        size = full.stat().st_size
    except OSError:
        size = 0
    return {
        "path": str(rel).replace("\\", "/"),
        "type": "python" if ext == ".py" else "shell" if ext in {".sh", ".bash", ".ps1"} else "markdown" if ext == ".md" else "text",
        "lines": lines,
        "size_bytes": size,
        "executable": ext in EXECUTABLE_EXTENSIONS,
    }


# --- Scanner engine --------------------------------------------------------

class SkillScanner:
    def __init__(self, target: str, max_file_bytes: int = 1024 * 1024):
        self.target = Path(target).resolve()
        self.max_file_bytes = max_file_bytes

    def _iter_content(self):
        files = [self.target] if self.target.is_file() else [
            Path(root) / name
            for root, _, names in os.walk(self.target)
            for name in names
            if _is_analysis_target(str((Path(root) / name).relative_to(self.target)))
        ]
        for path in files:
            try:
                if path.stat().st_size > self.max_file_bytes:
                    continue
                with open(path, "r", encoding="utf-8", errors="replace") as fh:
                    yield path, fh.read()
            except (OSError, UnicodeDecodeError):
                continue

    def scan(self) -> ScanReport:
        from datetime import datetime, UTC
        components = discover_components(self.target)
        findings: List[Finding] = []
        compiled = [(rid, cat, sev, re.compile(pat), conf, expl) for rid, cat, sev, pat, conf, expl in RULES]

        for path, content in self._iter_content():
            rel = str(path.relative_to(self.target)).replace("\\", "/") if path != self.target else self.target.name
            for rid, cat, sev, pattern, conf, expl in compiled:
                m = pattern.search(content)
                if not m:
                    continue
                start = max(0, m.start() - 40)
                evidence = content[start:m.end() + 40].replace("\n", " ").strip()
                findings.append(Finding(
                    id=rid,
                    category=cat,
                    severity=sev,
                    location=f"{rel}:{content[:m.start()].count(chr(10)) + 1}",
                    evidence=evidence[:200],
                    confidence=conf,
                    explanation=expl,
                ))

        has_exec = any(c["executable"] for c in components)
        score = 0
        for f in findings:
            score += SEVERITY_WEIGHTS.get(f.severity, 0)
        if has_exec and score:
            score = int(score * 1.3)
        score = max(0, min(100, score))

        if score <= 20:
            severity, recommendation = "LOW", "SAFE"
        elif score <= 50:
            severity, recommendation = "MEDIUM", "CAUTION"
        elif score <= 80:
            severity, recommendation = "HIGH", "DO_NOT_INSTALL"
        else:
            severity, recommendation = "CRITICAL", "DO_NOT_INSTALL"

        return ScanReport(
            target=str(self.target),
            scanned_at=datetime.now(UTC).isoformat(),
            score=score,
            severity=severity,
            recommendation=recommendation,
            findings=findings,
            components=components,
            has_executable_scripts=has_exec,
            llm_used=False,
        )

    @staticmethod
    def recommendation_exit_code(recommendation: str) -> int:
        if recommendation == "DO_NOT_INSTALL":
            return 1
        return 0


def _format_terminal(report: ScanReport) -> str:
    lines = [
        f"SkillScanner Security Report  v{SCAN_VERSION}",
        f"Target: {report.target}",
        f"Scanned: {report.scanned_at}",
        "",
        "        Risk Assessment",
        f" Metric          Value",
        f" Score           {report.score}/100",
        f" Severity        {report.severity}",
        f" Recommendation  {report.recommendation}",
        "",
        f"        Components ({len(report.components)})",
    ]
    for c in report.components[:20]:
        lines.append(f" {c['path']:<36} {c['type']:<9} {c['lines']:>6}  {'EXEC' if c['executable'] else '    '}")
    if len(report.components) > 20:
        lines.append(f" ... and {len(report.components) - 20} more")
    lines.append("")
    lines.append(f"Issues ({len(report.findings)})")
    for f in report.findings:
        lines.append(f"")
        lines.append(f"  {f.severity}: {f.category} ({f.id})")
        lines.append(f"    Location: {f.location}")
        lines.append(f"    Finding: {f.evidence}")
        lines.append(f"    Confidence: {int(f.confidence * 100)}%")
        lines.append(f"    {f.explanation}")
    if not report.findings:
        lines.append("  (none)")
    return "\n".join(lines)


def main(argv: Optional[List[str]] = None) -> int:
    import argparse
    import sys

    parser = argparse.ArgumentParser(prog="agentcore-scan", description="Scan AgentCore skills for security risks.")
    parser.add_argument("target", nargs="?", default="skills", help="Skill file or directory to scan (default: skills/)")
    parser.add_argument("-f", "--format", choices=["terminal", "json"], default="terminal")
    parser.add_argument("-o", "--output", help="Output file path")
    parser.add_argument("--ci", action="store_true", help="Exit non-zero on DO_NOT_INSTALL")
    args = parser.parse_args(argv)

    target = Path(args.target).resolve()
    if not target.exists():
        print(f"error: target does not exist: {target}", file=sys.stderr)
        return 2

    report = SkillScanner(str(target)).scan()

    if args.format == "json":
        output = json.dumps(report.to_dict(), indent=2)
    else:
        output = _format_terminal(report)

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(output + "\n", encoding="utf-8")
    else:
        print(output)

    if args.ci:
        return SkillScanner.recommendation_exit_code(report.recommendation)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())