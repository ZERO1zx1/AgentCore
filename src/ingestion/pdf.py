"""Real PDF Processor for Manus Mini v2.
Inspects PDF files, computes SHA-256 fingerprints, extracts text, and manages chunked processing.
"""
import os
import hashlib
from typing import List, Dict, Any, Optional

try:
    import pypdf
except ImportError:
    pypdf = None

class PDFProcessor:
    def __init__(self, task_id: str, state_dir: str = ".manus-mini/state"):
        self.task_id = task_id
        self.state_dir = os.path.join(state_dir, task_id, "pdf")
        os.makedirs(self.state_dir, exist_ok=True)

    def compute_fingerprint(self, pdf_path: str) -> str:
        hasher = hashlib.sha256()
        with open(pdf_path, "rb") as f:
            while chunk := f.read(8192):
                hasher.update(chunk)
        return hasher.hexdigest()

    def inspect(self, pdf_path: str) -> Dict[str, Any]:
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")
        
        fingerprint = self.compute_fingerprint(pdf_path)
        size_bytes = os.path.getsize(pdf_path)
        
        page_count = 0
        has_text = False
        
        if not pypdf:
            raise RuntimeError("BLOCKED: pypdf dependency unavailable. Install requirements.txt to enable PDF processing.")
        
        try:
            reader = pypdf.PdfReader(pdf_path)
            page_count = len(reader.pages)
            for page in reader.pages:
                if page.extract_text().strip():
                    has_text = True
                    break
        except Exception as e:
            raise RuntimeError(f"Failed to parse PDF: {e}")

        return {
            "path": pdf_path,
            "sha256": fingerprint,
            "page_count": page_count,
            "size_bytes": size_bytes,
            "has_text": has_text
        }

    def process_chunks(self, pdf_path: str, chunk_size: int = 10) -> List[Dict[str, Any]]:
        info = self.inspect(pdf_path)
        total_pages = info["page_count"]
        chunks = []
        
        for start in range(0, total_pages, chunk_size):
            end = min(total_pages, start + chunk_size)
            chunk_id = f"chunk_{start}_{end}"
            chunk_file = os.path.join(self.state_dir, f"{chunk_id}.txt")
            
            if not pypdf:
                raise RuntimeError("BLOCKED: pypdf dependency unavailable.")
            
            try:
                reader = pypdf.PdfReader(pdf_path)
                extracted = []
                for p in range(start, end):
                    extracted.append(reader.pages[p].extract_text() or "")
                text_content = "\n".join(extracted)
            except Exception as e:
                raise RuntimeError(f"Failed to extract PDF chunk text: {e}")

            with open(chunk_file, "w", encoding="utf-8") as f:
                f.write(text_content)

            chunks.append({
                "chunk_id": chunk_id,
                "start_page": start,
                "end_page": end,
                "output_file": chunk_file
            })
        return chunks
