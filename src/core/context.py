"""Typed TaskContext for Manus Mini v2.
Holds normalized context about the task, its input sources, and persisted context references.
Large normalized content is persisted to disk and referenced by path, not copied repeatedly.
"""
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional


@dataclass
class TaskContext:
    task_id: str
    user_prompt: str
    execution_mode: str
    requested_output_type: str
    input_sources: List[str] = field(default_factory=list)
    source_types: Dict[str, str] = field(default_factory=dict)
    source_fingerprints: Dict[str, str] = field(default_factory=dict)
    repository_context: Dict[str, Any] = field(default_factory=dict)
    document_context: Dict[str, Any] = field(default_factory=dict)
    structured_context: Dict[str, Any] = field(default_factory=dict)
    relevant_files: List[str] = field(default_factory=list)
    persisted_context_paths: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    # Backward-compatible aliases
    @property
    def sources(self) -> List[str]:
        return self.input_sources

    @sources.setter
    def sources(self, value: List[str]):
        self.input_sources = value

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "user_prompt": self.user_prompt,
            "execution_mode": self.execution_mode,
            "requested_output_type": self.requested_output_type,
            "input_sources": self.input_sources,
            "source_types": self.source_types,
            "source_fingerprints": self.source_fingerprints,
            "repository_context": self.repository_context,
            "document_context": self.document_context,
            "structured_context": self.structured_context,
            "relevant_files": self.relevant_files,
            "persisted_context_paths": self.persisted_context_paths,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TaskContext":
        return cls(
            task_id=data.get("task_id", "unknown"),
            user_prompt=data.get("user_prompt", ""),
            execution_mode=data.get("execution_mode", "AUTO"),
            requested_output_type=data.get("requested_output_type", "text"),
            input_sources=data.get("input_sources", data.get("sources", [])),
            source_types=data.get("source_types", {}),
            source_fingerprints=data.get("source_fingerprints", {}),
            repository_context=data.get("repository_context", {}),
            document_context=data.get("document_context", {}),
            structured_context=data.get("structured_context", {}),
            relevant_files=data.get("relevant_files", []),
            persisted_context_paths=data.get("persisted_context_paths", {}),
            metadata=data.get("metadata", {}),
        )