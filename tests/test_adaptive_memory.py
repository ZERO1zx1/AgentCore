"""Adaptive Memory and Research Learning System - Comprehensive Test Suite.

Covers all 47 test points from the spec:
- memory creation, approval, retrieval, relevance ranking
- project scoping, cross-chat retrieval, stale handling, conflicting memories
- memory correction, deletion, clear-all, disabled mode
- secret redaction, sensitive-data rejection, prompt-injection filtering
- web-source metadata, freshness, conflict handling, feedback scoring
- task-related memory cleanup, checkpoint path sanitization
- export/import, failure recovery, concurrent access
"""

import json
import os
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from datetime import datetime, timezone

# Ensure src is importable
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from src.adaptive.schema import (
    MemoryRecord,
    MemoryValidationError,
    MemoryDisabledError,
    SensitiveMemoryRejected,
    new_memory_id,
    SCHEMA_VERSION,
    MEMORY_CATEGORIES,
    MEMORY_STATUSES,
    SOURCE_TYPES,
    safe_component,
    fingerprint,
    utc_now,
    parse_time,
    DEFAULT_TTL_DAYS,
)

from src.adaptive.store import AdaptiveMemoryStore
from src.adaptive.redaction import (
    redact_secrets,
    assert_not_sensitive,
    inspect_sensitive,
    contains_secret,
    REDACTED,
)

from src.adaptive.injection import (
    scan_injection,
    strip_dangerous_segments,
    INJECTION_PATTERNS,
)

from src.adaptive.retrieval import (
    detect_task_scope,
    rank,
    build_citation,
    freshness_score,
    is_stale,
    MemoryRecallReport,
)

from src.adaptive.feedback import (
    FEEDBACK_VERDICTS,
    apply_confidence,
    is_negative,
    durable_reject,
    CONFIDENCE_DELTAS,
    NEGATIVE_VERDICTS,
)

from src.adaptive.evaluation import AdaptiveEvaluation, DEFAULTS
from src.adaptive.research import (
    ResearchSource,
    ResearchMetadataStore,
    detect_conflicts,
    source_id,
)
