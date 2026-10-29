import re
from pathlib import Path
from typing import Dict, Any, List, Optional
from app.ai.context.scanner import ProjectScanner
from app.config.settings import settings


SECRET_PATTERNS = [
    re.compile(r"(api[_-]?key|secret[_-]?key|auth[_-]?token|password|bearer)\s*[:=]\s*['\"]([^'\"]+)['\"]", re.IGNORECASE),
    re.compile(r"(ghp_[a-zA-Z0-9]{36}|sk-[a-zA-Z0-9]{48}|AIza[0-9A-Za-z-_]{35})"),
]


class ContextBuilder:
    """Builds focused, redacted, bounded context payloads for AI requests."""

    def __init__(self, workspace_path: str, max_total_chars: int = 50000, max_lines_per_file: int = 400):
        self.workspace_path = Path(workspace_path).resolve()
        self.max_total_chars = max_total_chars
        self.max_lines_per_file = max_lines_per_file
        self.scanner = ProjectScanner(str(self.workspace_path))

    def redact_secrets(self, text: str) -> str:
        """Mask potential secrets, API keys, and sensitive tokens."""
        result = text
        for pattern in SECRET_PATTERNS:
            result = pattern.sub(r"\1: [REDACTED_SECRET]", result)
        return result

    def select_relevant_files(self, prompt: str, error_trace: Optional[str] = None) -> List[str]:
        """Explainable heuristic selection based on prompt words, mentions, and error traces."""
        manifest = self.scanner.scan()
        all_files = [f["path"] for f in manifest["files"]]
        selected: List[str] = []

        tokens = set(re.findall(r"[a-zA-Z0-9_.-]+", prompt.lower()))
        if error_trace:
            tokens.update(re.findall(r"[a-zA-Z0-9_.-]+", error_trace.lower()))

        # Prioritize files explicitly named in prompt or trace
        for f in all_files:
            file_name = Path(f).name.lower()
            rel_lower = f.lower()
            if file_name in tokens or rel_lower in tokens:
                selected.append(f)

        # Include entry points if few files selected
        if len(selected) < 3:
            for ep in manifest.get("entry_points", []):
                if ep not in selected:
                    selected.append(ep)

        # Include top configuration files
        for config_file in ("pyproject.toml", "package.json", "requirements.txt"):
            if config_file in all_files and config_file not in selected and len(selected) < 5:
                selected.append(config_file)

        return selected[:6]

    def build_context(
        self,
        prompt: str,
        explicit_paths: Optional[List[str]] = None,
        error_trace: Optional[str] = None,
    ) -> Dict[str, Any]:
        manifest = self.scanner.scan()
        selected_paths = list(explicit_paths or self.select_relevant_files(prompt, error_trace))

        collected_files = {}
        total_chars = 0

        for rel_path in selected_paths:
            full_path = (self.workspace_path / rel_path).resolve()
            if not full_path.exists() or not full_path.is_file():
                continue

            try:
                # Security: ensure file is inside workspace
                full_path.relative_to(self.workspace_path)
            except ValueError:
                continue

            try:
                content = full_path.read_text(encoding="utf-8", errors="ignore")
                lines = content.splitlines()
                truncated = False
                if len(lines) > self.max_lines_per_file:
                    content = "\n".join(lines[: self.max_lines_per_file]) + "\n... [truncated]"
                    truncated = True

                redacted = self.redact_secrets(content)
                if total_chars + len(redacted) > self.max_total_chars:
                    break

                collected_files[rel_path] = {
                    "content": redacted,
                    "truncated": truncated,
                    "lines_count": min(len(lines), self.max_lines_per_file),
                }
                total_chars += len(redacted)
            except Exception:
                pass

        return {
            "project_name": manifest["project_name"],
            "languages": manifest["languages"],
            "frameworks": manifest["frameworks"],
            "scripts": manifest["scripts"],
            "file_manifest": [f["path"] for f in manifest["files"]],
            "relevant_files": collected_files,
            "error_trace": self.redact_secrets(error_trace) if error_trace else None,
        }
