"""Prompt-injection filtering for untrusted web/repository content.

Web pages and repository instructions are *data*, never instructions. This
module classifies and strips known injection / anti-refusal / dangerous command
fragments so memory stores only filtered reference content.
"""

from __future__ import annotations

import re
from typing import Dict, List, Tuple

# (rule_id, category, pattern)
INJECTION_PATTERNS: List[Tuple[str, str, re.Pattern]] = [
    ("override", "instruction_override",
     re.compile(r"(?i)\b(?:ignore|disregard|forget|override|bypass)\s+(?:all\s+|any\s+|your\s+|previous\s+|prior\s+|above\s+)?(?:previous|prior|above|the)?\s*(?:instructions?|prompts?|guidelines?|policies?|rules?)")),
    ("persona", "persona_override",
     re.compile(r"(?i)\b(?:you are now|act as if|pretend you are|new persona|jailbreak|developer mode)\b")),
    ("anti_refusal", "anti_refusal",
     re.compile(r"(?i)\b(?:never refuse|do not refuse|cannot refuse|ignore safety|disable safety|no restrictions)\b")),
    ("dangerous_exec", "dangerous_command",
     re.compile(r"(?i)(?:curl|wget).{0,80}(?:\||;|&&).\s*(?:bash|sh|zsh|python)\b")),
    ("rm_rf", "destructive_command",
     re.compile(r"\brm\s+-rf\s+(?:/\s*|\*|~|/\*|/home)")),
    ("exfil", "exfiltration",
     re.compile(r"(?i)\b(?:send|upload|exfiltrate|post)\s+(?:my\s+|the\s+)?(?:api|secret|token|password|keys?|credentials?|environment)\b")),
    ("code_eval", "remote_code_exec",
     re.compile(r"(?i)\b(?:eval|exec|subprocess)\s*\(.*?(?:key|token|password|secret)")),
]


def scan_injection(text: str) -> List[Dict[str, str]]:
    """Return a list of injection findings: [{"id", "category"}, ...]."""
    findings: List[Dict[str, str]] = []
    for rule_id, category, pattern in INJECTION_PATTERNS:
        if pattern.search(text):
            findings.append({"id": rule_id, "category": category})
    return findings


def strip_dangerous_segments(text: str) -> Tuple[str, int]:
    """Remove lines that carry known injection/dangerous patterns.

    Returns (cleaned_text, removed_line_count). Conservative: a flagged line is
    removed, but surrounding text is preserved so citation context survives.
    """
    if not scan_injection(text):
        return text, 0
    cleaned: List[str] = []
    removed = 0
    for line in text.splitlines():
        if any(pattern.search(line) for _, _, pattern in INJECTION_PATTERNS):
            removed += 1
            continue
        cleaned.append(line)
    return "\n".join(cleaned), removed