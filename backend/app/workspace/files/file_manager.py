import hashlib
import os
import shutil
import tempfile
from pathlib import Path
from typing import Dict, Any, Optional


class SafeFileManager:
    """Safe, atomic file operations strictly constrained to workspace directory."""

    def __init__(self, workspace_path: str):
        self.workspace_path = Path(workspace_path).resolve()
        if not self.workspace_path.exists():
            os.makedirs(self.workspace_path, exist_ok=True)

    def resolve_safe_path(self, relative_path: str) -> Path:
        """Resolve canonical path and strictly enforce workspace containment."""
        cleaned = relative_path.replace("\\", "/").strip().lstrip("/")
        if ".." in cleaned.split("/"):
            raise PermissionError(f"Directory traversal prohibited: {relative_path}")

        target = (self.workspace_path / cleaned).resolve()

        # Enforce containment
        try:
            target.relative_to(self.workspace_path)
        except ValueError:
            raise PermissionError(f"Target path escapes workspace containment: {relative_path}")

        # Check for symlink escaping workspace
        if target.is_symlink():
            real_target = target.resolve()
            try:
                real_target.relative_to(self.workspace_path)
            except ValueError:
                raise PermissionError(f"Symlink target escapes workspace: {relative_path}")

        return target

    def compute_hash(self, relative_path: str) -> Optional[str]:
        target = self.resolve_safe_path(relative_path)
        if not target.exists() or not target.is_file():
            return None
        hasher = hashlib.sha256()
        with open(target, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        return hasher.hexdigest()

    def read_file(self, relative_path: str) -> str:
        target = self.resolve_safe_path(relative_path)
        if not target.exists():
            raise FileNotFoundError(f"File not found: {relative_path}")
        return target.read_text(encoding="utf-8", errors="replace")

    def write_file_atomic(self, relative_path: str, content: str) -> str:
        """Atomically write content to file within workspace."""
        target = self.resolve_safe_path(relative_path)
        target.parent.mkdir(parents=True, exist_ok=True)

        # Write to temporary file in same directory then atomically replace
        temp_file = tempfile.NamedTemporaryFile(
            mode="w",
            dir=target.parent,
            delete=False,
            encoding="utf-8",
            newline="",
        )
        try:
            temp_file.write(content)
            temp_file.flush()
            os.fsync(temp_file.fileno())
            temp_file.close()

            # Atomic replace (Windows supports os.replace)
            os.replace(temp_file.name, target)
        except Exception:
            if os.path.exists(temp_file.name):
                os.remove(temp_file.name)
            raise

        return self.compute_hash(relative_path) or ""

    def move_file(self, source_rel: str, dest_rel: str) -> None:
        src = self.resolve_safe_path(source_rel)
        dst = self.resolve_safe_path(dest_rel)
        if not src.exists():
            raise FileNotFoundError(f"Source file not found: {source_rel}")
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))

    def delete_file(self, relative_path: str) -> None:
        target = self.resolve_safe_path(relative_path)
        if not target.exists():
            return
        if target.is_file() or target.is_symlink():
            target.unlink()
        elif target.is_dir():
            shutil.rmtree(target)

