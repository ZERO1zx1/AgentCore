"""Context Resolver for AgentCore.
Resolves real relevant content from TaskContext for WorkUnit execution prompts.
Deterministic, size-limited, provider-agnostic.
"""
import os
import json
import hashlib
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
            elif ref == "asset_context" and task_context.asset_context:
                content = self._resolve_assets(task_context, limit - used)
                if content:
                    parts.append(content); used += len(content)

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

    def resolve_attachments(self, task_context: TaskContext, work_unit) -> List[Dict[str, Any]]:
        """Return verified path-based multimodal parts for provider adapters.

        Binary data is deliberately not copied into the text prompt.  A provider
        adapter may stream/read each absolute path and translate it to its native
        image/audio/video content-part format.
        """
        if "asset_context" not in getattr(work_unit, "context_refs", []):
            return []

        mode = (task_context.execution_mode or "AUTO").upper()
        byte_limit = {
            "CREDIT_SAFE": self.config.max_attachment_bytes_credit_safe,
            "FULL": self.config.max_attachment_bytes_full,
        }.get(mode, self.config.max_attachment_bytes_auto)
        supported_modalities = {"image", "audio", "video"}
        attachments: List[Dict[str, Any]] = []
        used = 0

        for source_path, info in task_context.asset_context.items():
            if len(attachments) >= self.config.max_attachment_count:
                break
            modality = info.get("asset_type", "")
            if modality not in supported_modalities:
                continue
            path = os.path.abspath(source_path)
            if not os.path.isfile(path):
                continue
            size = os.path.getsize(path)
            if size > byte_limit - used:
                continue
            expected_hash = info.get("sha256", "")
            actual_hash = self._sha256(path)
            if expected_hash and expected_hash != actual_hash:
                continue
            attachments.append({
                "type": "input_attachment",
                "content_mode": "path",
                "path": path,
                "mime_type": info.get("mime_type", "application/octet-stream"),
                "modality": modality,
                "size": size,
                "sha256": actual_hash,
            })
            used += size
        return attachments

    @staticmethod
    def _sha256(path: str) -> str:
        hasher = hashlib.sha256()
        with open(path, "rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                hasher.update(chunk)
        return hasher.hexdigest()

    def _resolve_assets(self, task_context: TaskContext, budget: int) -> str:
        """Expose bounded metadata; binary content stays out of text prompts."""
        content = json.dumps(task_context.asset_context, ensure_ascii=False, indent=2)
        return ("ASSET METADATA:\n" + content)[:budget]
