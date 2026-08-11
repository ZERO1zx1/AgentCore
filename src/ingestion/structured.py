"""Deterministic Structured Data Processor for Manus Mini v2.
Handles JSON and CSV files: local parsing, structure metadata, SHA-256 fingerprints,
and simple relevant-subset support. No LLM involved for parsing/counting.
"""
import os
import json
import csv
import hashlib
from typing import Dict, Any, List, Optional

SUPPORTED_STRUCTURED_EXTENSIONS = {".json", ".csv"}


def _sha256_file(path: str) -> str:
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(8192):
            hasher.update(chunk)
    return hasher.hexdigest()


class StructuredDataProcessor:
    @staticmethod
    def is_supported(path: str) -> bool:
        return os.path.splitext(path)[1].lower() in SUPPORTED_STRUCTURED_EXTENSIONS

    @staticmethod
    def inspect(path: str) -> Dict[str, Any]:
        if not os.path.exists(path):
            raise FileNotFoundError(f"Structured data file not found: {path}")

        ext = os.path.splitext(path)[1].lower()
        if ext == ".json":
            return StructuredDataProcessor._inspect_json(path)
        elif ext == ".csv":
            return StructuredDataProcessor._inspect_csv(path)
        else:
            raise ValueError(f"Unsupported structured data extension: {ext}")

    @staticmethod
    def _inspect_json(path: str) -> Dict[str, Any]:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        top_type = type(data).__name__
        info = {
            "path": path,
            "extension": ".json",
            "sha256": _sha256_file(path),
            "size_bytes": os.path.getsize(path),
            "top_level_type": top_type,
        }

        if isinstance(data, dict):
            info["top_level_keys"] = list(data.keys())[:50]
            info["key_count"] = len(data)
        elif isinstance(data, list):
            info["record_count"] = len(data)
            if data and isinstance(data[0], dict):
                info["top_level_keys"] = list(data[0].keys())[:50]
        else:
            info["value"] = data

        return info

    @staticmethod
    def _inspect_csv(path: str) -> Dict[str, Any]:
        row_count = 0
        headers: List[str] = []
        column_count = 0
        try:
            with open(path, "r", encoding="utf-8", newline="") as f:
                reader = csv.reader(f)
                for i, row in enumerate(reader):
                    if i == 0:
                        headers = row
                        column_count = len(row)
                    else:
                        row_count += 1
        except UnicodeDecodeError:
            with open(path, "r", encoding="latin-1", newline="") as f:
                reader = csv.reader(f)
                for i, row in enumerate(reader):
                    if i == 0:
                        headers = row
                        column_count = len(row)
                    else:
                        row_count += 1

        return {
            "path": path,
            "extension": ".csv",
            "sha256": _sha256_file(path),
            "size_bytes": os.path.getsize(path),
            "headers": headers,
            "row_count": row_count,
            "column_count": column_count,
        }

    @staticmethod
    def subset(path: str, max_rows: int = 50) -> Dict[str, Any]:
        """Return a small relevant subset of the structured data for context."""
        ext = os.path.splitext(path)[1].lower()
        info = StructuredDataProcessor.inspect(path)
        if ext == ".json":
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                info["subset"] = data[:max_rows]
            elif isinstance(data, dict):
                info["subset"] = dict(list(data.items())[:max_rows])
            else:
                info["subset"] = data
        elif ext == ".csv":
            rows = []
            try:
                with open(path, "r", encoding="utf-8", newline="") as f:
                    reader = csv.reader(f)
                    for i, row in enumerate(reader):
                        if i > max_rows:
                            break
                        rows.append(row)
            except UnicodeDecodeError:
                with open(path, "r", encoding="latin-1", newline="") as f:
                    reader = csv.reader(f)
                    for i, row in enumerate(reader):
                        if i > max_rows:
                            break
                        rows.append(row)
            info["subset"] = rows
        return info