from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

@dataclass
class TaskContext:
    task_id: str
    user_prompt: str
    execution_mode: str
    requested_output_type: str
    sources: List[str] = field(default_factory=list)
    source_fingerprints: Dict[str, str] = field(default_factory=dict)
    source_types: Dict[str, str] = field(default_factory=dict)
    normalized_context: Dict[str, Any] = field(default_factory=dict)
    persisted_context_paths: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
