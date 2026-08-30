"""Notification and Git Operations for AgentCore.
Handles budget exhaustion notifications and automatic git push with full automation.
"""
import os
import subprocess
import json
import shutil
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from decimal import Decimal


class GitManager:
    """Manages git operations for checkpoint persistence with full automation."""
    
    def __init__(self, repo_root: str = "."):
        self.repo_root = os.path.abspath(repo_root)
        self._fallback_dir = os.path.join(self.repo_root, ".agentcore", "git_fallback")
        os.makedirs(self._fallback_dir, exist_ok=True)
    
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
    
    def stage_checkpoint(self, checkpoint_path: str) -> bool:
        """Stage only the explicit checkpoint file, never unrelated user work."""
        absolute = os.path.abspath(checkpoint_path)
        try:
            relative = os.path.relpath(absolute, self.repo_root)
        except ValueError:
            return False
        if relative == os.pardir or relative.startswith(os.pardir + os.sep):
            return False
        try:
            result = subprocess.run(
                ["git", "add", "--", relative],
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                timeout=15
            )
            return result.returncode == 0
        except Exception:
            return False

    def has_staged_changes(self) -> bool:
        try:
            result = subprocess.run(["git", "diff", "--cached", "--quiet", "--exit-code"], cwd=self.repo_root, capture_output=True, text=True, timeout=10)
            return result.returncode == 1
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
    
    def _save_fallback(self, task_id: str, budget_state: str, budget_info: Dict[str, Any], commit_msg: str) -> str:
        """Save checkpoint data to fallback directory when git fails."""
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        fallback_file = os.path.join(self._fallback_dir, f"{task_id}_{budget_state}_{timestamp}.json")
        
        fallback_data = {
            "task_id": task_id,
            "budget_state": budget_state,
            "budget_info": budget_info,
            "commit_message": commit_msg,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "fallback_reason": "git_push_failed"
        }
        
        with open(fallback_file, "w", encoding="utf-8") as f:
            json.dump(fallback_data, f, indent=2)
        
        return fallback_file
    
    def push_checkpoint(self, task_id: str, budget_state: str, budget_info: Dict[str, Any], checkpoint_path: Optional[str] = None) -> Dict[str, Any]:
        """Push checkpoint with budget exhaustion info. Fully automated with fallback."""
        result = {
            "success": False,
            "steps": [],
            "error": None,
            "fallback_file": None
        }
        
        if not self.is_git_repo():
            result["error"] = "Not a git repository"
            result["steps"].append("git repo check: FAILED")
            # Save to fallback anyway
            timestamp = datetime.now(timezone.utc).isoformat()
            commit_msg = f"[AgentCore] Budget {budget_state} - Task: {task_id}"
            fallback_file = self._save_fallback(task_id, budget_state, budget_info, commit_msg)
            result["fallback_file"] = fallback_file
            result["steps"].append(f"fallback saved: {fallback_file}")
            return result
        
        result["steps"].append("git repo check: OK")
        
        checkpoint_path = checkpoint_path or os.path.join(self.repo_root, ".agentcore", "checkpoints", f"{task_id}_manifest.json")
        if self.stage_checkpoint(checkpoint_path):
            result["steps"].append("git add checkpoint: OK")
        else:
            result["error"] = "Failed to stage changes"
            result["steps"].append("git add: FAILED")
            # Save to fallback
            timestamp = datetime.now(timezone.utc).isoformat()
            commit_msg = f"[AgentCore] Budget {budget_state} - Task: {task_id}"
            fallback_file = self._save_fallback(task_id, budget_state, budget_info, commit_msg)
            result["fallback_file"] = fallback_file
            result["steps"].append(f"fallback saved: {fallback_file}")
            return result

        if not self.has_staged_changes():
            result["steps"].append("git commit: SKIPPED (checkpoint unchanged)")
            result["success"] = True
            return result
        
        # Create commit message with budget info
        timestamp = datetime.now(timezone.utc).isoformat()
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
            if not self.has_staged_changes():
                result["steps"].append("git commit: SKIPPED (no changes)")
                result["success"] = True
                return result
            result["error"] = "Failed to commit"
            result["steps"].append("git commit: FAILED")
            # Save to fallback
            fallback_file = self._save_fallback(task_id, budget_state, budget_info, commit_msg)
            result["fallback_file"] = fallback_file
            result["steps"].append(f"fallback saved: {fallback_file}")
            return result
        
        # Push to remote
        if self.push():
            result["steps"].append("git push: OK")
            result["success"] = True
        else:
            result["error"] = "Failed to push to remote"
            result["steps"].append("git push: FAILED")
            # Save to fallback
            fallback_file = self._save_fallback(task_id, budget_state, budget_info, commit_msg)
            result["fallback_file"] = fallback_file
            result["steps"].append(f"fallback saved: {fallback_file}")
        
        return result
    
    def get_fallback_files(self) -> list[str]:
        """Get list of fallback files for manual recovery."""
        if os.path.exists(self._fallback_dir):
            return sorted([
                os.path.join(self._fallback_dir, f)
                for f in os.listdir(self._fallback_dir)
                if f.endswith(".json")
            ])
        return []


class NotificationManager:
    """Manages notifications for budget events with full automation."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.webhook_url = self.config.get("webhook_url")
        self.webhook_timeout = self.config.get("webhook_timeout", 10)
        self.email_config = self.config.get("email")
        self.console_enabled = self.config.get("console", True)
        self._notification_log = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".agentcore", "notifications.log")
        os.makedirs(os.path.dirname(self._notification_log), exist_ok=True)
    
    def notify_budget_exhausted(
        self,
        task_id: str,
        budget_state: str,
        budget_info: Dict[str, Any],
        manifest: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Send notification when budget is exhausted. Fully automated."""
        result = {
            "console": False,
            "webhook": False,
            "email": False,
            "file_log": False,
            "errors": []
        }
        
        message = self._format_budget_message(task_id, budget_state, budget_info, manifest)
        
        # Console notification (always works)
        if self.console_enabled:
            try:
                print("\n" + "=" * 60)
                print("⚠️  AGENTCORE BUDGET EXHAUSTED NOTIFICATION")
                print("=" * 60)
                print(message)
                print("=" * 60 + "\n")
                result["console"] = True
            except Exception as e:
                result["errors"].append(f"Console notification failed: {e}")
        
        # File log notification (always works as fallback)
        try:
            log_entry = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "event": "budget_exhausted",
                "task_id": task_id,
                "budget_state": budget_state,
                "budget_info": budget_info,
                "manifest_summary": {
                    "progress": manifest.get('progress', {}) if manifest else {},
                    "status": manifest.get('status', 'unknown') if manifest else 'unknown',
                    "completed_units": len(manifest.get('completed_work', [])) if manifest else 0
                } if manifest else None,
                "message": message
            }
            with open(self._notification_log, "a", encoding="utf-8") as f:
                f.write(json.dumps(log_entry) + "\n")
            result["file_log"] = True
        except Exception as e:
            result["errors"].append(f"File log notification failed: {e}")
        
        # Webhook notification (if configured)
        if self.webhook_url:
            try:
                import urllib.request
                import urllib.error
                
                payload = json.dumps({
                    "event": "budget_exhausted",
                    "task_id": task_id,
                    "budget_state": budget_state,
                    "budget_info": budget_info,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "message": message
                }).encode("utf-8")
                
                req = urllib.request.Request(
                    self.webhook_url,
                    data=payload,
                    headers={"Content-Type": "application/json"}
                )
                urllib.request.urlopen(req, timeout=self.webhook_timeout)
                result["webhook"] = True
            except Exception as e:
                result["errors"].append(f"Webhook notification failed: {e}")
        
        # Email notification (placeholder - would need SMTP config)
        if self.email_config:
            result["errors"].append("Email notification not implemented - configure SMTP to enable")
        
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
        lines.append("AUTOMATED ACTIONS TAKEN:")
        lines.append("- Checkpoint saved to .agentcore/checkpoints/")
        lines.append("- Git commit attempted (see .agentcore/git_fallback/ if failed)")
        lines.append("- Notification logged to .agentcore/notifications.log")
        lines.append("")
        lines.append("TO RESUME:")
        lines.append(f"  python -m src.core.engine --resume {task_id} --budget <new_amount>")
        lines.append("  Or add budget and restart the task")
        
        return "\n".join(lines)
    
    def get_notification_log(self, limit: int = 50) -> list[Dict[str, Any]]:
        """Get recent notification log entries."""
        if not os.path.exists(self._notification_log):
            return []
        entries = []
        with open(self._notification_log, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        entries.append(json.loads(line))
                    except Exception:
                        pass
        return entries[-limit:]


def create_budget_exhaustion_handler(
    repo_root: str = ".",
    notification_config: Optional[Dict[str, Any]] = None
) -> tuple[GitManager, NotificationManager]:
    """Factory function to create git and notification managers."""
    git_manager = GitManager(repo_root)
    notification_manager = NotificationManager(notification_config)
    return git_manager, notification_manager
