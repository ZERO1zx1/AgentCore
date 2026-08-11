"""Universal Input Router for Manus Mini v2.
Routes input files and sources to appropriate processors.
"""
import os
from typing import Dict, Any, List, Optional
from src.ingestion.pdf import PDFProcessor
from src.ingestion.repository import RepositoryProcessor

class InputRouter:
    @staticmethod
    def inspect_sources(sources: List[str], task_id: str) -> List[Dict[str, Any]]:
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
            else:
                results.append({
                    "source": src,
                    "type": "text",
                    "inspection": {"size": os.path.getsize(src) if os.path.exists(src) else 0}
                })
        return results
