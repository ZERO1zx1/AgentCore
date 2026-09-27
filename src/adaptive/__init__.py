"""Adaptive Memory and Research Learning System for AgentCore.

Privacy-first, local-by-default memory that improves future responses through
approved local memories, validated web research, past task outcomes, and
explicit user feedback. This is not model fine-tuning and never silently
changes the model: it is a controlled local context and retrieval system.
"""

from __future__ import annotations

from .schema import (
    MEMORY_CATEGORIES,
    MEMORY_STATUSES,
    MemoryDisabledError,
    MemoryError,
    MemoryRecord,
    MemoryValidationError,
    SensitiveMemoryRejected,
    SCHEMA_VERSION,
    fingerprint,
)
from .store import AdaptiveMemoryStore
from .retrieval import detect_task_scope
from .feedback import FEEDBACK_VERDICTS

__all__ = [
    "AdaptiveMemoryStore",
    "MemoryRecord",
    "SCHEMA_VERSION",
    "MEMORY_CATEGORIES",
    "MEMORY_STATUSES",
    "MemoryError",
    "MemoryDisabledError",
    "MemoryValidationError",
    "SensitiveMemoryRejected",
    "detect_task_scope",
    "FEEDBACK_VERDICTS",
    "fingerprint",
]
