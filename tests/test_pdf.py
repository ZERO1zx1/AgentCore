import unittest
import os
import shutil
from src.ingestion.pdf import PDFProcessor
from reportlab.pdfgen import canvas

class TestPDFProcessor(unittest.TestCase):
    def setUp(self):
        self.test_dir = ".test_pdf_processor"
        os.makedirs(self.test_dir, exist_ok=True)
        self.pdf_path = os.path.join(self.test_dir, "test.pdf")
        
        # Create a 5-page test PDF
        c = canvas.Canvas(self.pdf_path)
        for i in range(5):
            c.drawString(100, 750, f"This is page {i+1} of the test PDF.")
            c.showPage()
        c.save()
        
        self.processor = PDFProcessor("pdf_test_task", state_dir=os.path.join(self.test_dir, "state"))

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_pdf_inspection(self):
        info = self.processor.inspect(self.pdf_path)
        self.assertEqual(info["page_count"], 5)
        self.assertTrue(info["has_text"])
        self.assertIn("sha256", info)

    def test_pdf_chunking(self):
        chunks = self.processor.process_chunks(self.pdf_path, chunk_size=2)
        # 5 pages, chunk_size 2 -> 3 chunks (0-2, 2-4, 4-5)
        self.assertEqual(len(chunks), 3)
        self.assertTrue(os.path.exists(chunks[0]["output_file"]))
        
        with open(chunks[0]["output_file"], "r") as f:
            content = f.read()
            self.assertIn("page 1", content)
            self.assertIn("page 2", content)

if __name__ == "__main__":
    unittest.main()
