"""Context Resolver for Manus Mini v2.
Resolves real relevant content from TaskContext for WorkUnit execution prompts.
Deterministic, size-limited, provider-agnostic.
"""
import os
import json
from typing import Dict, Any, List, Optional
from src.core.context import TaskContext
from src.core.runtime_config import RuntimeConfig


class ContextResolver:
    def __init__(self, config: Optional[RuntimeConfig] = None):
        self.config = config or RuntimeConfig()

    def resolve_context(
        self,
        task_context: TaskContext,
        work_unit,
        max_chars: Optional[int] = None,
    ) -> str:
        """Resolve selected relevant normalized context for a WorkUnit."""
        limit = max_chars or self.config.max_context_chars
        parts: List[str] = []
        used = 0

        for ref in getattr(work_unit, "context_refs", []):
            if used >= limit:
                break
            if ref == "repository_context" and task_context.repository_context:
                content = self._resolve_repository(task_context, limit - used)
                if content:
                    parts.append(content)
                    used += len(content)
            elif ref == "document_context" and task_context.document_context:
                content = self._resolve_documents(task_context, limit - used)
                if content:
                    parts.append(content)
                    used += len(content)
            elif ref == "structured_context" and task_context.structured_context:
                content = self._resolve_structured(task_context, limit - used)
                if content:
                    parts.append(content)
                    used += len(content)

        # Dependency artifact content
        dep_content = self._resolve_dependencies(task_context, work_unit, limit - used)
        if dep_content:
            parts.append(dep_content)

        return "\n\n".join(parts)

    def _resolve_repository(self, task_context: TaskContext, budget: int) -> str:
        """Read selected relevant source files from the repository."""
        repo_ctx = task_context.repository_context
        if not repo_ctx:
            return ""
        repo_path = repo_ctx.get("path", ".")
        relevant = task_context.relevant_files or []
        if not relevant:
            return ""

        parts: List[str] = []
        used = 0
        for rel_path in relevant[: self.config.max_chunk_count]:
            if used >= budget:
                break
            full = os.path.join(repo_path, rel_path)
            if not os.path.isfile(full):
                continue
            try:
                with open(full, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read(self.config.max_file_chars)
            except Exception:
                continue
            if not content.strip():
                continue
            block = f"FILE: {rel_path}\n{content}"
            if used + len(block) > budget:
                block = block[: budget - used]
            parts.append(block)
            used += len(block)
        return "\n\n".join(parts)

    def _resolve_documents(self, task_context: TaskContext, budget: int) -> str:
        """Resolve document content (PDF/text) from persisted context or direct read."""
        parts: List[str] = []
        used = 0
        for path, info in task_context.document_context.items():
            if used >= budget:
                break
            # Try persisted chunk file first
            chunk_file = info.get("chunk_file")
            if chunk_file and os.path.exists(chunk_file):
                try:
                    with open(chunk_file, "r", encoding="utf-8", errors="replace") as f:
                        content = f.read(self.config.max_file_chars)
                except Exception:
                    content = ""
            else:
                # Fallback: read text file directly
                content = ""
                if os.path.isfile(path) and path.endswith((".txt", ".md")):
                    try:
                        with open(path, "r", encoding="utf-8", errors="replace") as f:
                            content = f.read(self.config.max_file_chars)
                    except Exception:
                        content = ""
            if not content.strip():
                continue
            block = f"DOCUMENT: {path}\n{content}"
            if used + len(block) > budget:
                block = block[: budget - used]
            parts.append(block)
            used += len(block)
        return "\n\n".join(parts)

    def _resolve_structured(self, task_context: TaskContext, budget: int) -> str:
        """Resolve selected structured data content."""
        parts: List[str] = []
        used = 0
        for path, info in task_context.structured_context.items():
            if used >= budget:
                break
            subset = info.get("subset")
            if subset is None:
                continue
            try:
                block = f"DATA: {path}\n{json.dumps(subset, indent=2, ensure_ascii=False)[: self.config.max_file_chars]}"
            except Exception:
                continue
            if used + len(block) > budget:
                block = block[: budget - used]
            parts.append(block)
            used += len(block)
        return "\n\n".join(parts)

    def _resolve_dependencies(self, task_context: TaskContext, work_unit, budget: int) -> str:
        """Load small relevant dependency artifact contents."""
        deps = getattr(work_unit, "dependencies", [])
        if not deps:
            return ""
        # We need access to completed work output refs — passed via metadata
        dep_outputs = getattr(work_unit, "metadata", {}).get("dependency_outputs", {})
        parts: List[str] = []
        used = 0
        for dep_id in deps:
            if used >= budget:
                break
            out_paths = dep_outputs.get(dep_id, [])
            for out_path in out_paths:
                if not out_path or not os.path.isfile(out_path):
                    continue
                try:
                    with open(out_path, "r", encoding="utf-8", errors="replace") as f:
                        content = f.read(self.config.max_dependency_chars)
                except Exception:
                    continue
                if not content.strip():
                    continue
                block = f"PREVIOUS RESULT ({dep_id}): {out_path}\n{content}"
                if used + len(block) > budget:
                    block = block[: budget - used]
                parts.append(block)
                used += len(block)
        return "\n\n".join(parts)