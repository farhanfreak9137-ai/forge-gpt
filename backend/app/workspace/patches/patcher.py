import difflib
import logging
from typing import Optional, Tuple
from app.workspace.files.file_manager import SafeFileManager
from app.ai.protocol.protocol import CodeChangeItem, ChangeOperation

logger = logging.getLogger("forgeagent.workspace.patcher")


class PatchApplicator:
    """Applies code changes and unified diffs safely with pre-flight validation."""

    def __init__(self, file_manager: SafeFileManager):
        self.file_manager = file_manager

    def compute_diff(self, relative_path: str, new_content: str) -> str:
        """Generate a unified diff between current file content and proposed content."""
        try:
            old_content = self.file_manager.read_file(relative_path)
        except FileNotFoundError:
            old_content = ""

        old_lines = old_content.splitlines(keepends=True)
        new_lines = new_content.splitlines(keepends=True)

        diff = difflib.unified_diff(
            old_lines,
            new_lines,
            fromfile=f"a/{relative_path}",
            tofile=f"b/{relative_path}",
        )
        return "".join(diff)

    def apply_change(self, change: CodeChangeItem) -> Tuple[bool, str, Optional[str]]:
        """
        Applies a validated CodeChangeItem.
        Returns: (success: bool, message: str, diff: Optional[str])
        """
        rel_path = change.path

        # 1. Stale hash check if expected_hash was provided
        if change.expected_hash:
            current_hash = self.file_manager.compute_hash(rel_path)
            if current_hash and current_hash != change.expected_hash:
                err = f"Stale file error: {rel_path} current hash {current_hash} != expected {change.expected_hash}"
                logger.error(err)
                return False, err, None

        # 2. Operations
        try:
            if change.operation == ChangeOperation.CREATE:
                diff = self.compute_diff(rel_path, change.content or "")
                self.file_manager.write_file_atomic(rel_path, change.content or "")
                return True, f"Created {rel_path}", diff

            elif change.operation == ChangeOperation.REPLACE:
                diff = self.compute_diff(rel_path, change.content or "")
                self.file_manager.write_file_atomic(rel_path, change.content or "")
                return True, f"Replaced {rel_path}", diff

            elif change.operation == ChangeOperation.PATCH:
                # If direct new content was provided
                if change.content is not None:
                    diff = self.compute_diff(rel_path, change.content)
                    self.file_manager.write_file_atomic(rel_path, change.content)
                    return True, f"Patched {rel_path}", diff
                else:
                    return False, "Patch diff application without content is not yet supported", None

            elif change.operation == ChangeOperation.DELETE:
                diff = self.compute_diff(rel_path, "")
                self.file_manager.delete_file(rel_path)
                return True, f"Deleted {rel_path}", diff

            elif change.operation == ChangeOperation.MOVE:
                if not change.destination_path:
                    return False, "Move requires destination_path", None
                self.file_manager.move_file(rel_path, change.destination_path)
                return True, f"Moved {rel_path} to {change.destination_path}", None

            return False, f"Unsupported operation: {change.operation}", None

        except Exception as e:
            logger.error(f"Failed to apply change to {rel_path}: {e}")
            return False, str(e), None

