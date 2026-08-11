"""Repository Processor for Manus Mini v2.
Inspects repository structure, manifests, and Git status.
"""
import os
import subprocess
from typing import Dict, Any, List

class RepositoryProcessor:
    @staticmethod
    def inspect(repo_path: str = ".") -> Dict[str, Any]:
        files = []
        for root, dirs, filenames in os.walk(repo_path):
            if ".git" in dirs:
                dirs.remove(".git")
            if ".manus-mini" in dirs:
                dirs.remove(".manus-mini")
            for f in filenames:
                files.append(os.path.join(root, f))

        has_package_json = os.path.exists(os.path.join(repo_path, "package.json"))
        has_pyproject = os.path.exists(os.path.join(repo_path, "pyproject.toml"))
        has_requirements = os.path.exists(os.path.join(repo_path, "requirements.txt"))

        git_status = ""
        try:
            res = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True, cwd=repo_path)
            git_status = res.stdout.strip()
        except Exception:
            pass

        return {
            "file_count": len(files),
            "has_package_json": has_package_json,
            "has_pyproject": has_pyproject,
            "has_requirements": has_requirements,
            "git_clean": len(git_status) == 0
        }
