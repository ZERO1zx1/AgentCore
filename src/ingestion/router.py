"""Universal Input Router for Manus Mini v2.
Routes input files and sources to appropriate processors and builds a TaskContext.
"""
import os
from typing import Dict, Any, List, Optional
from src.core.context import TaskContext
from src.ingestion.pdf import PDFProcessor
from src.ingestion.repository import RepositoryProcessor
from src.ingestion.text import TextProcessor
from src.ingestion.structured import StructuredDataProcessor


class InputRouter:
    @staticmethod
    def route(task_id: str, sources: List[str], repository: Optional[str] = None) -> TaskContext:
        """Inspect all input sources and build a normalized TaskContext.
        Large content is persisted and referenced by path.
        """
        all_sources = list(sources)
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
                context.source_fingerprints[src] = f"repo:{src}:{inspection['file_count']}"
            elif src.endswith(".pdf"):
                processor = PDFProcessor(task_id)
                info = processor.inspect(src)
                context.source_types[src] = "pdf"
                context.input_sources.append(src)
                context.document_context[src] = info
                context.source_fingerprints[src] = info["sha256"]
            elif TextProcessor.is_supported(src):
                info = TextProcessor.process(src)
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
            else:
                results.append({
                    "source": src,
                    "type": "unknown",
                    "inspection": {"size": os.path.getsize(src) if os.path.exists(src) else 0}
                })
        return results