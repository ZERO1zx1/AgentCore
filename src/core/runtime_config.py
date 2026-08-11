"""Portable Runtime Configuration for Manus Mini v2.
Centralizes deterministic context limits and artifact/checkpoint roots.
No provider secrets here.
"""
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class RuntimeConfig:
    max_context_chars: int = 20000
    max_file_chars: int = 4000
    max_chunk_count: int = 5
    max_dependency_chars: int = 2000
    artifact_root: str = ".manus-mini/tasks"
    checkpoint_root: str = ".manus-mini/checkpoints"
    retry_limit: int = 2
    max_attempts: int = 2