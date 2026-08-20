"""Portable Runtime Configuration for AgentCore.
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
    max_attachment_bytes_credit_safe: int = 5 * 1024 * 1024
    max_attachment_bytes_auto: int = 25 * 1024 * 1024
    max_attachment_bytes_full: int = 100 * 1024 * 1024
    max_attachment_count: int = 8
    artifact_root: str = ".agentcore/tasks"
    checkpoint_root: str = ".agentcore/checkpoints"
    retry_limit: int = 2
    max_attempts: int = 2
