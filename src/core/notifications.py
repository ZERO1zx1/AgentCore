"""Notification and Git Operations for AgentCore.
Handles budget exhaustion notifications and automatic git push.
"""
import os
import subprocess
import json
from datetime import datetime, UTC
from typing import Optional, Dict, Any
from decimal import Decimal


class GitManager:
    """Manages git operations for checkpoint persistence."""
    
    def __init__(self, repo_root: str = "."):
        self.repo_root = os.path.abspath(repo_root)
    
    def is_git_repo(self) -> bool:
        """Check if current directory is a git repository."""
        git_dir = os.path.join(self.repo_root, ".git")
        return os.path.exists(git_dir)
    
    def has_uncommitted_changes(self) -> bool:
        """Check if there are uncommitted changes."""
        try:
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                timeout=10
            )
            return bool(result.stdout.strip())
        except Exception:
            return False
    
    def add_all(self) -> bool:
        """Stage all changes."""
        try:
            result = subprocess.run(
                ["git", "add", "-A"],
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                timeout=15
            )
            return result.returncode == 0
        except Exception:
            return False
    
    def commit(self, message: str) -> bool:
        """Create a commit with the given message."""
        try:
            result = subprocess.run(
                ["git", "commit", "-m", message],
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                timeout=15
            )
            return result.returncode == 0
        except Exception:
            return False
    
    def push(self, remote: str = "origin", branch: str = None) -> bool:
        """Push to remote repository."""
        try:
            if branch is None:
                # Get current branch
                result = subprocess.run(
                    ["git", "branch", "--show-current"],
                    cwd=self.repo_root,
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                branch = result.stdout.strip() or "main"
            
            result = subprocess.run(
                ["git", "push", remote, branch],
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                timeout=30
            )
            return result.returncode == 0
        except Exception:
            return False
    
    def push_checkpoint(self, task_id: str, budget_state: str, budget_info: Dict[str, Any]) -> Dict[str, Any]:
        """Push checkpoint with budget exhaustion info."""
        result = {
            "success": False,
            "steps": [],
            "error": None
        }
        
        if not self.is_git_repo():
            result["error"] = "Not a git repository"
            result["steps"].append("git repo check: FAILED")
            return result
        
        result["steps"].append("git repo check: OK")
        
        # Add all changes (including checkpoints)
        if self.add_all():
            result["steps"].append("git add: OK")
        else:
            result["error"] = "Failed to stage changes"
            result["steps"].append("git add: FAILED")
            return result
        
        # Create commit message with budget info
        timestamp = datetime.now(UTC).isoformat()
        commit_msg = (
            f"[AgentCore] Budget {budget_state} - Task: {task_id}\n\n"
            f"Budget: {budget_info.get('used', 0):.2f}/{budget_info.get('initial', 0):.2f} {budget_info.get('unit', 'USD')}\n"
            f"State: {budget_state}\n"
            f"Timestamp: {timestamp}\n"
            f"Auto-commit on budget exhaustion"
        )
        
        if self.commit(commit_msg):
            result["steps"].append("git commit: OK")
        else:
            # Check if there was nothing to commit
            if not self.has_uncommitted_changes():
                result["steps"].append("git commit: SKIPPED (no changes)")
                result["success"] = True
                return result
            result["error"] = "Failed to commit"
            result["steps"].append("git commit: FAILED")
            return result
        
        # Push to remote
        if self.push():
            result["steps"].append("git push: OK")
            result["success"] = True
        else:
            result["error"] = "Failed to push to remote"
            result["steps"].append("git push: FAILED")
        
        return result


class NotificationManager:
    """Manages notifications for budget events."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.webhook_url = self.config.get("webhook_url")
        self.email_config = self.config.get("email")
        self.console_enabled = self.config.get("console", True)
    
    def notify_budget_exhausted(
        self,
        task_id: str,
        budget_state: str,
        budget_info: Dict[str, Any],
        manifest: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Send notification when budget is exhausted."""
        result = {
            "console": False,
            "webhook": False,
            "email": False,
            "errors": []
        }
        
        message = self._format_budget_message(task_id, budget_state, budget_info, manifest)
        
        # Console notification
        if self.console_enabled:
            try:
                print("\n" + "=" * 60)
                print("⚠️  BUDGET EXHAUSTED NOTIFICATION")
                print("=" * 60)
                print(message)
                print("=" * 60 + "\n")
                result["console"] = True
            except Exception as e:
                result["errors"].append(f"Console notification failed: {e}")
        
        # Webhook notification
        if self.webhook_url:
            try:
                import urllib.request
                import urllib.error
                
                payload = json.dumps({
                    "event": "budget_exhausted",
                    "task_id": task_id,
                    "budget_state": budget_state,
                    "budget_info": budget_info,
                    "timestamp": datetime.now(UTC).isoformat(),
                    "message": message
                }).encode("utf-8")
                
                req = urllib.request.Request(
                    self.webhook_url,
                    data=payload,
                    headers={"Content-Type": "application/json"}
                )
                urllib.request.urlopen(req, timeout=10)
                result["webhook"] = True
            except Exception as e:
                result["errors"].append(f"Webhook notification failed: {e}")
        
        # Email notification (placeholder - would need SMTP config)
        if self.email_config:
            result["errors"].append("Email notification not implemented")
        
        return result
    
    def _format_budget_message(
        self,
        task_id: str,
        budget_state: str,
        budget_info: Dict[str, Any],
        manifest: Optional[Dict[str, Any]] = None
    ) -> str:
        """Format budget exhaustion message."""
        lines = [
            f"Task ID: {task_id}",
            f"Budget State: {budget_state}",
            f"Budget Used: {budget_info.get('used', 0):.2f} / {budget_info.get('initial', 0):.2f} {budget_info.get('unit', 'USD')}",
            f"Remaining: {budget_info.get('remaining', 0):.2f} {budget_info.get('unit', 'USD')}",
            f"Reserved (Emergency): {budget_info.get('reserved', 0):.2f} {budget_info.get('unit', 'USD')}",
            f"Execution Mode: {budget_info.get('execution_mode', 'AUTO')}",
        ]
        
        if manifest:
            lines.append(f"Progress: {manifest.get('progress', {}).get('completed_units', 0)}/{manifest.get('progress', {}).get('total_units', 0)} units completed")
            lines.append(f"Status: {manifest.get('status', 'unknown')}")
        
        lines.append("")
        lines.append("ACTION REQUIRED:")
        lines.append("- Add more budget to continue execution")
        lines.append("- Check .agentcore/checkpoints/ for resume manifest")
        lines.append("- Run with higher budget to resume: python -m src.core.engine --resume <task_id> --budget <amount>")
        
        return "\n".join(lines)


def create_budget_exhaustion_handler(
    repo_root: str = ".",
    notification_config: Optional[Dict[str, Any]] = None
) -> tuple[GitManager, NotificationManager]:
    """Factory function to create git and notification managers."""
    git_manager = GitManager(repo_root)
    notification_manager = NotificationManager(notification_config)
    return git_manager, notification_manager