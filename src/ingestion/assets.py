"""Bounded metadata inspection for image, audio, video, slide, and binary assets."""
import hashlib
import mimetypes
import os
from pathlib import Path
from typing import Any, Dict

ASSET_EXTENSIONS = {
    ".png":"image", ".jpg":"image", ".jpeg":"image", ".gif":"image", ".webp":"image", ".svg":"image",
    ".mp3":"audio", ".wav":"audio", ".flac":"audio", ".m4a":"audio", ".ogg":"audio",
    ".mp4":"video", ".mov":"video", ".mkv":"video", ".webm":"video", ".avi":"video",
    ".ppt":"slide", ".pptx":"slide", ".doc":"document", ".docx":"document", ".xls":"spreadsheet", ".xlsx":"spreadsheet",
}


class AssetProcessor:
    @staticmethod
    def asset_type(path: str) -> str:
        return ASSET_EXTENSIONS.get(Path(path).suffix.lower(), "")

    @staticmethod
    def is_supported(path: str) -> bool:
        return bool(AssetProcessor.asset_type(path))

    @staticmethod
    def inspect(path: str) -> Dict[str, Any]:
        if not os.path.isfile(path): raise FileNotFoundError(path)
        hasher = hashlib.sha256()
        with open(path, "rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""): hasher.update(chunk)
        return {"path":path, "asset_type":AssetProcessor.asset_type(path), "extension":Path(path).suffix.lower(), "mime_type":mimetypes.guess_type(path)[0] or "application/octet-stream", "size":os.path.getsize(path), "sha256":hasher.hexdigest()}
