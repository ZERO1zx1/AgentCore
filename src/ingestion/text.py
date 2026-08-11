"""Deterministic Text Processor for Manus Mini v2.
Handles .txt and .md files: validation, safe reading, size, SHA-256 fingerprint,
encoding handling, and chunking for large files. No AI model involved.
"""
import os
import hashlib
from typing import Dict, Any, List, Optional

SUPPORTED_TEXT_EXTENSIONS = {".txt", ".md"}


class TextProcessor:
    @staticmethod
    def is_supported(path: str) -> bool:
        return os.path.splitext(path)[1].lower() in SUPPORTED_TEXT_EXTENSIONS

    @staticmethod
    def compute_fingerprint(path: str) -> str:
        hasher = hashlib.sha256()
        with open(path, "rb") as f:
            while chunk := f.read(8192):
                hasher.update(chunk)
        return hasher.hexdigest()

    @staticmethod
    def read_text(path: str) -> str:
        """Safely read a text file, trying UTF-8 then latin-1 fallback."""
        if not os.path.exists(path):
            raise FileNotFoundError(f"Text file not found: {path}")
        try:
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        except UnicodeDecodeError:
            with open(path, "r", encoding="latin-1") as f:
                return f.read()

    @staticmethod
    def inspect(path: str) -> Dict[str, Any]:
        """Return deterministic metadata for a text file."""
        if not os.path.exists(path):
            raise FileNotFoundError(f"Text file not found: {path}")
        size_bytes = os.path.getsize(path)
        content = TextProcessor.read_text(path)
        return {
            "path": path,
            "extension": os.path.splitext(path)[1].lower(),
            "sha256": TextProcessor.compute_fingerprint(path),
            "size_bytes": size_bytes,
            "char_count": len(content),
            "line_count": content.count("\n") + 1,
        }

    @staticmethod
    def chunk_text(text: str, chunk_size: int = 8000, overlap: int = 200) -> List[str]:
        """Split text into overlapping chunks of approximately chunk_size characters."""
        if len(text) <= chunk_size:
            return [text]
        chunks = []
        start = 0
        while start < len(text):
            end = min(len(text), start + chunk_size)
            chunks.append(text[start:end])
            if end >= len(text):
                break
            start = max(end - overlap, start + 1)
        return chunks

    @staticmethod
    def process(path: str, chunk_size: int = 8000) -> Dict[str, Any]:
        """Full deterministic processing pipeline for a text file."""
        info = TextProcessor.inspect(path)
        content = TextProcessor.read_text(path)
        chunks = TextProcessor.chunk_text(content, chunk_size)
        info["chunk_count"] = len(chunks)
        info["preview"] = content[:500]
        return info