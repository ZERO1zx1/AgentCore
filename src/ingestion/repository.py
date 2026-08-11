"""Repository Processor for AgentCore.
Inspects repository structure, manifests, file tree, and Git status.
Collects useful deterministic context without sending the entire repository to the executor.
"""
import os
import subprocess
from typing import Dict, Any, List, Set

IGNORED_DIRS = {".git", ".manus-mini", ".agentcore", ".venv", "venv", "env", "__pycache__", ".pytest_cache", "node_modules", ".mypy_cache", ".idea", ".vscode"}
IGNORED_EXTENSIONS = {".pyc", ".pyo", ".class", ".o", ".so", ".dll", ".exe", ".obj", ".log"}

ENTRY_POINT_CANDIDATES = ["main.py", "app.py", "cli.py", "manage.py", "index.js", "index.ts", "main.ts", "server.js", "server.ts"]
TEST_DIRS = ["tests", "test", "spec", "__tests__"]


class RepositoryProcessor:
    @staticmethod
    def inspect(repo_path: str = ".") -> Dict[str, Any]:
        files: List[str] = []
        for root, dirs, filenames in os.walk(repo_path):
            # Prune ignored dirs in-place
            dirs[:] = [d for d in dirs if d not in IGNORED_DIRS]
            for f in filenames:
                ext = os.path.splitext(f)[1].lower()
                if ext in IGNORED_EXTENSIONS:
                    continue
                full = os.path.join(root, f)
                rel = os.path.relpath(full, repo_path)
                files.append(rel)

        extensions: Dict[str, int] = {}
        for f in files:
            ext = os.path.splitext(f)[1].lower() or "(none)"
            extensions[ext] = extensions.get(ext, 0) + 1

        has_package_json = os.path.exists(os.path.join(repo_path, "package.json"))
        has_pyproject = os.path.exists(os.path.join(repo_path, "pyproject.toml"))
        has_requirements = os.path.exists(os.path.join(repo_path, "requirements.txt"))
        has_setup_py = os.path.exists(os.path.join(repo_path, "setup.py"))

        entry_points = [f for f in files if os.path.basename(f) in ENTRY_POINT_CANDIDATES]
        test_dirs = [d for d in TEST_DIRS if os.path.isdir(os.path.join(repo_path, d))]

        git_status = ""
        git_clean = True
        try:
            res = subprocess.run(
                ["git", "status", "--porcelain"],
                capture_output=True, text=True, cwd=repo_path,
                timeout=10
            )
            git_status = res.stdout.strip()
            git_clean = len(git_status) == 0
        except Exception:
            pass

        manifests: Dict[str, Any] = {}
        for manifest_name in ["package.json", "pyproject.toml", "requirements.txt", "setup.py", "setup.cfg"]:
            p = os.path.join(repo_path, manifest_name)
            if os.path.exists(p):
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        content = f.read()
                    manifests[manifest_name] = content[:4000]
                except Exception:
                    manifests[manifest_name] = "(unreadable)"

        return {
            "path": repo_path,
            "file_count": len(files),
            "files_top_level": [f for f in files if os.sep not in f][:100],
            "file_tree": files[:500],
            "extensions": dict(sorted(extensions.items(), key=lambda kv: kv[1], reverse=True)[:30]),
            "has_package_json": has_package_json,
            "has_pyproject": has_pyproject,
            "has_requirements": has_requirements,
            "has_setup_py": has_setup_py,
            "entry_point_candidates": entry_points,
            "test_directories": test_dirs,
            "manifests": manifests,
            "git_clean": git_clean,
            "git_status": git_status,
        }

    @staticmethod
    def fingerprint_repository(repo_path: str = ".") -> str:
        """Deterministic repository fingerprint from relevant source files.
        Excludes .git, .manus-mini, __pycache__, node_modules, venv, build artifacts.
        """
        import hashlib
        info = RepositoryProcessor.inspect(repo_path)
        tree = sorted(info.get("file_tree", []))
        hasher = hashlib.sha256()
        for rel in tree:
            full = os.path.join(repo_path, rel)
            if not os.path.isfile(full):
                continue
            try:
                with open(full, "rb") as f:
                    file_hash = hashlib.sha256(f.read(65536)).hexdigest()
            except Exception:
                continue
            hasher.update(rel.encode("utf-8"))
            hasher.update(b"\0")
            hasher.update(file_hash.encode("utf-8"))
            hasher.update(b"\0")
        return hasher.hexdigest()

    @staticmethod
    def relevant_source_files(repo_path: str, max_files: int = 20) -> List[str]:
        """Select a bounded set of relevant source files for executor context."""
        info = RepositoryProcessor.inspect(repo_path)
        tree = info["file_tree"]
        code_extensions = {".py", ".js", ".ts", ".tsx", ".jsx", ".go", ".rs", ".java", ".c", ".cpp", ".h", ".md", ".sh"}
        candidates = [f for f in tree if os.path.splitext(f)[1].lower() in code_extensions]
        # Prefer entry points and test files, then top-level files
        ranked = []
        for f in candidates:
            base = os.path.basename(f)
            if base in ENTRY_POINT_CANDIDATES:
                ranked.append((0, f))
            elif any(f == d or f.startswith(d + os.sep) for d in TEST_DIRS):
                ranked.append((1, f))
            else:
                ranked.append((2, f))
        ranked.sort(key=lambda x: (x[0], x[1]))
        return [f for _, f in ranked[:max_files]]