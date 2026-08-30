"""Privacy checks for lessons persisted by Adaptive Omni Agent."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, Mapping


SENSITIVE_PATTERNS = (
    ("private_key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----", re.I)),
    ("credential_assignment", re.compile(r"(?:api[_-]?key|token|password|secret)\s*[:=]\s*\S+", re.I)),
    ("provider_token", re.compile(r"(?:ghp|github_pat|sk)-[A-Za-z0-9_-]{12,}", re.I)),
    ("email_address", re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)),
)

POISONING_PATTERNS = (
    ("instruction_override", re.compile(r"(?:ignore|override|bypass).{0,40}(?:instruction|policy|safety|rule)", re.I)),
    ("validation_suppression", re.compile(r"(?:skip|disable|do not run|never run).{0,30}(?:test|validation|scan)", re.I)),
    ("secret_exposure", re.compile(r"(?:print|log|send|upload|exfiltrate).{0,35}(?:secret|token|credential|environment)", re.I)),
    ("unbounded_authority", re.compile(r"(?:without|no).{0,20}(?:permission|approval|confirmation)", re.I)),
)


@dataclass(frozen=True)
class SensitiveDataFinding:
    category: str
    field: str


class SensitiveDataGate:
    """Reject lesson content that may disclose credentials or personal data."""

    @classmethod
    def inspect(cls, values: Mapping[str, object]) -> list[SensitiveDataFinding]:
        findings: list[SensitiveDataFinding] = []
        for field, value in values.items():
            text = str(value)
            for category, pattern in SENSITIVE_PATTERNS:
                if pattern.search(text):
                    findings.append(SensitiveDataFinding(category, str(field)))
        return findings

    @classmethod
    def assert_safe(cls, values: Mapping[str, object]) -> None:
        findings = cls.inspect(values)
        if findings:
            labels = ", ".join(f"{item.category} in {item.field}" for item in findings)
            raise ValueError(f"lesson contains sensitive data: {labels}")


class MemoryPoisoningGate:
    """Detect lessons that attempt to weaken AgentCore policy or validation."""

    @classmethod
    def inspect(cls, values: Mapping[str, object]) -> list[SensitiveDataFinding]:
        findings: list[SensitiveDataFinding] = []
        for field, value in values.items():
            text = str(value)
            for category, pattern in POISONING_PATTERNS:
                if pattern.search(text):
                    findings.append(SensitiveDataFinding(category, str(field)))
        return findings

    @classmethod
    def assert_safe(cls, values: Mapping[str, object]) -> None:
        findings = cls.inspect(values)
        if findings:
            labels = ", ".join(f"{item.category} in {item.field}" for item in findings)
            raise ValueError(f"lesson contains policy-poisoning instructions: {labels}")


def lesson_fields_are_safe(values: Mapping[str, object]) -> bool:
    return not SensitiveDataGate.inspect(values) and not MemoryPoisoningGate.inspect(values)
