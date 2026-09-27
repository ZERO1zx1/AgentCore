"""Secret redaction and sensitive-data rejection for Adaptive Memory.

Guards every memory/research write path. Secrets are redacted in place with an
unambiguous marker; highly sensitive personal information (SSN, payment card
numbers, IBAN) causes the write to be rejected so the caller can ask the user
for approval instead of persisting risk.
"""

from __future__ import annotations

import re
from typing import List, Tuple

REDACTED = "[REDACTED]"

# (category, pattern) — matched text is replaced with REDACTED.
SECRET_PATTERNS: List[Tuple[str, re.Pattern]] = [
    ("api_key", re.compile(r"(?i)\b(?:api[_-]?key|api[_-]?secret|access[_-]?token|auth[_-]?token)\s*[:=]\s*['\"]?[^\s'\";,]+")),
    ("password", re.compile(r"(?i)\b(?:password|passwd|pwd|secret)\s*[:=]\s*['\"]?[^\s'\";,]+")),
    ("bearer_token", re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]{8,}")),
    ("jwt", re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b")),
    ("github_token", re.compile(r"\b(?:ghp|gho|ghu|ghs|github_pat)_[A-Za-z0-9_]{12,}")),
    ("aws_key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("private_key", re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----")),
    ("authorization_header", re.compile(r"(?i)\bAuthorization\s*[:=]\s*['\"]?[^\s'\";,]+")),
    ("cookie", re.compile(r"(?i)\b(?:sessionid|connect\.sid|cookie)\s*[:=]\s*['\"]?[^\s'\";,]+")),
    ("stripe_key", re.compile(r"\b(?:sk|pk)_(?:test|live)_[A-Za-z0-9]{16,}")),
]

# Highly sensitive data that must never be persisted: raise and require approval.
SENSITIVE_REJECT_PATTERNS: List[Tuple[str, re.Pattern]] = [
    ("ssn", re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
    ("credit_card", re.compile(r"\b(?:4\d{3}|5[1-5]\d{2}|3[47]\d{2}|6(?:011|5\d{2}))[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b")),
    ("iban", re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{11,30}\b")),
]


def redact_secrets(text: str) -> Tuple[str, List[str]]:
    """Replace known secret patterns, return (redacted_text, findings)."""
    findings: List[str] = []
    for category, pattern in SECRET_PATTERNS:
        if pattern.search(text):
            findings.append(category)
            text = pattern.sub(REDACTED, text)
    return text, sorted(set(findings))


def inspect_sensitive(text: str) -> List[str]:
    findings: List[str] = []
    for category, pattern in SENSITIVE_REJECT_PATTERNS:
        if pattern.search(text):
            findings.append(category)
    return findings


def assert_not_sensitive(text: str) -> None:
    """Raise SensitiveMemoryRejected when highly sensitive data is present."""
    from src.adaptive.schema import SensitiveMemoryRejected

    findings = inspect_sensitive(text)
    if findings:
        raise SensitiveMemoryRejected(
            "content contains highly sensitive personal information: "
            + ", ".join(sorted(findings))
        )


def contains_secret(text: str) -> bool:
    return any(pattern.search(text) for _, pattern in SECRET_PATTERNS)