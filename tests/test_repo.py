import unittest
import os
import shutil
from src.ingestion.repository import RepositoryProcessor

class TestRepositoryProcessor(unittest.TestCase):
    def setUp(self):
        self.test_dir = ".test_repo_processor"
        os.makedirs(self.test_dir, exist_ok=True)
        
        # Create a mock repo structure
        os.makedirs(os.path.join(self.test_dir, "src"), exist_ok=True)
        with open(os.path.join(self.test_dir, "package.json"), "w") as f:
            f.write("{}")
        with open(os.path.join(self.test_dir, "src/main.py"), "w") as f:
            f.write("print('hello')")

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_repo_inspection(self):
        info = RepositoryProcessor.inspect(self.test_dir)
        self.assertTrue(info["has_package_json"])
        self.assertFalse(info["has_pyproject"])
        self.assertEqual(info["file_count"], 2)

if __name__ == "__main__":
    unittest.main()
