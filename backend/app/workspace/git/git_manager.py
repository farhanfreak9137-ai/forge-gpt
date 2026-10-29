import asyncio
import os
import shutil
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple


class GitManager:
    """Manages git checkpoints, diffs, status, and rollback in project workspace."""

    def __init__(self, workspace_path: str):
        self.workspace_path = Path(workspace_path).resolve()

    async def _run_git(self, *args: str) -> Tuple[int, str, str]:
        proc = await asyncio.create_subprocess_exec(
            "git",
            *args,
            cwd=str(self.workspace_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        return (
            proc.returncode or 0,
            stdout.decode("utf-8", errors="replace"),
            stderr.decode("utf-8", errors="replace"),
        )

    def is_git_repo(self) -> bool:
        return (self.workspace_path / ".git").is_dir()

    async def init_repo(self) -> bool:
        if self.is_git_repo():
            return True
        code, out, err = await self._run_git("init")
        if code == 0:
            # Set local user config so commits succeed in automated environments
            await self._run_git("config", "user.name", "ForgeAgent")
            await self._run_git("config", "user.email", "forgeagent@local.system")
            # Create initial commit if empty
            await self._run_git("add", "-A")
            await self._run_git("commit", "-m", "Initial commit by ForgeAgent", "--allow-empty")
            return True
        return False

    async def get_status(self) -> Dict[str, Any]:
        if not self.is_git_repo():
            return {"is_repo": False, "clean": True, "files": []}

        code, out, _ = await self._run_git("status", "--porcelain")
        files = []
        for line in out.splitlines():
            line = line.strip()
            if line:
                status_code = line[:2].strip()
                file_path = line[3:].strip()
                files.append({"status": status_code, "path": file_path})

        return {
            "is_repo": True,
            "clean": len(files) == 0,
            "files": files,
        }

    async def get_diff(self, commit_ref: Optional[str] = None) -> str:
        if not self.is_git_repo():
            return ""
        if commit_ref:
            code, out, _ = await self._run_git("diff", f"{commit_ref}^", commit_ref)
        else:
            code, out, _ = await self._run_git("diff", "HEAD")
        return out

    async def create_checkpoint(self, task_id: str, description: str) -> Optional[str]:
        """Creates a Git checkpoint commit and returns the commit hash."""
        if not self.is_git_repo():
            await self.init_repo()

        # Add all workspace modifications
        await self._run_git("add", "-A")
        msg = f"forgeagent-checkpoint: [{task_id}] {description}"
        code, out, err = await self._run_git("commit", "-m", msg, "--allow-empty")

        # Get latest commit sha
        code, rev, _ = await self._run_git("rev-parse", "HEAD")
        return rev.strip() if code == 0 else None

    async def rollback_to_checkpoint(self, commit_ref: str) -> bool:
        """Restores working tree to the state of commit_ref."""
        if not self.is_git_repo():
            return False

        # Reset hard to commit_ref to restore exact files
        code, out, err = await self._run_git("reset", "--hard", commit_ref)
        # Clean any newly created untracked files
        await self._run_git("clean", "-fd")
        return code == 0

    async def get_checkpoint_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        if not self.is_git_repo():
            return []

        code, out, _ = await self._run_git(
            "log",
            f"-n{limit}",
            "--pretty=format:%H|%an|%ad|%s",
            "--date=iso",
        )
        if code != 0:
            return []

        history = []
        for line in out.splitlines():
            parts = line.split("|", 3)
            if len(parts) == 4:
                sha, author, date, subject = parts
                history.append({
                    "commit_hash": sha,
                    "author": author,
                    "date": date,
                    "message": subject,
                    "is_forge_checkpoint": "forgeagent-checkpoint" in subject,
                })
        return history
