"""Universal Input Router for AgentCore.
Routes input files and sources to appropriate processors and builds a TaskContext.
Persists large normalized content and references it by path.
"""
import os
from typing import Dict, Any, List, Optional
from src.core.context import TaskContext
from src.ingestion.pdf import PDFProcessor
from src.ingestion.repository import RepositoryProcessor
from src.ingestion.text import TextProcessor
from src.ingestion.structured import StructuredDataProcessor
from src.ingestion.assets import AssetProcessor


class InputDependencyError(RuntimeError):
    """A required local parser/decoder is unavailable."""


class InputRouter:
    @staticmethod
    def route(
        task_id: str,
        sources: List[str],
        repository: Optional[str] = None,
        context_dir: Optional[str] = None,
    ) -> TaskContext:
        """Inspect all input sources and build a normalized TaskContext.
        Large content is persisted and referenced by path.
        """
        all_sources = list(sources)
        if context_dir:
            os.makedirs(context_dir, exist_ok=True)
        if repository and repository not in all_sources:
            all_sources.append(repository)

        context = TaskContext(task_id=task_id, user_prompt="", execution_mode="AUTO", requested_output_type="text")
        for src in all_sources:
            if os.path.isdir(src) or src == "." or (repository and os.path.abspath(src) == os.path.abspath(repository)):
                inspection = RepositoryProcessor.inspect(src)
                context.source_types[src] = "repository"
                context.input_sources.append(src)
                context.repository_context = inspection
                context.relevant_files = RepositoryProcessor.relevant_source_files(src)
                context.source_fingerprints[src] = RepositoryProcessor.fingerprint_repository(src)
            elif src.endswith(".pdf"):
                processor = PDFProcessor(task_id)
                try:
                    info = processor.inspect(src)
                except RuntimeError as exc:
                    if str(exc).startswith("BLOCKED:"):
                        raise InputDependencyError(str(exc)) from exc
                    raise
                # Persist extracted chunks to context dir
                if context_dir:
                    info = processor.extract_and_persist(src, context_dir)
                context.source_types[src] = "pdf"
                context.input_sources.append(src)
                context.document_context[src] = info
                context.source_fingerprints[src] = info["sha256"]
            elif TextProcessor.is_supported(src):
                info = TextProcessor.process(src)
                # Persist text chunks to context dir
                if context_dir:
                    content = TextProcessor.read_text(src)
                    chunks = TextProcessor.chunk_text(content)
                    chunk_files = []
                    for i, chunk in enumerate(chunks[:5]):
                        chunk_file = os.path.join(context_dir, f"text_{os.path.basename(src)}_{i}.txt")
                        with open(chunk_file, "w", encoding="utf-8") as f:
                            f.write(chunk)
                        chunk_files.append(chunk_file)
                    info["chunk_file"] = chunk_files[0] if chunk_files else None
                    info["chunk_files"] = chunk_files
                context.source_types[src] = "text"
                context.input_sources.append(src)
                context.document_context[src] = info
                context.source_fingerprints[src] = info["sha256"]
            elif StructuredDataProcessor.is_supported(src):
                info = StructuredDataProcessor.inspect(src)
                subset = StructuredDataProcessor.subset(src)
                context.source_types[src] = "structured"
                context.input_sources.append(src)
                context.structured_context[src] = info
                context.structured_context[src]["subset"] = subset.get("subset")
                context.source_fingerprints[src] = info["sha256"]
            elif AssetProcessor.is_supported(src):
                info = AssetProcessor.inspect(src)
                context.source_types[src] = info["asset_type"]
                context.input_sources.append(src)
                context.asset_context[src] = info
                context.source_fingerprints[src] = info["sha256"]
            else:
                raise ValueError(f"Unsupported input source: {src}")
        return context

    @staticmethod
    def inspect_sources(sources: List[str], task_id: str) -> List[Dict[str, Any]]:
        """Backward-compatible lightweight inspection."""
        results = []
        for src in sources:
            if os.path.isdir(src) or src == ".":
                results.append({
                    "source": src,
                    "type": "repository",
                    "inspection": RepositoryProcessor.inspect(src)
                })
            elif src.endswith(".pdf"):
                processor = PDFProcessor(task_id)
                results.append({
                    "source": src,
                    "type": "pdf",
                    "inspection": processor.inspect(src)
                })
            elif TextProcessor.is_supported(src):
                results.append({
                    "source": src,
                    "type": "text",
                    "inspection": TextProcessor.process(src)
                })
            elif StructuredDataProcessor.is_supported(src):
                results.append({
                    "source": src,
                    "type": "structured",
                    "inspection": StructuredDataProcessor.subset(src)
                })
            elif AssetProcessor.is_supported(src):
                results.append({"source": src, "type": AssetProcessor.asset_type(src), "inspection": AssetProcessor.inspect(src)})
            else:
                results.append({
                    "source": src,
                    "type": "unknown",
                    "inspection": {"size": os.path.getsize(src) if os.path.exists(src) else 0}
                })
        return results
