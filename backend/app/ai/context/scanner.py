import os
import json
from pathlib import Path
from typing import Dict, Any, List, Set

EXCLUDED_DIRS = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    "dist",
    "build",
    "coverage",
    ".idea",
    ".vscode",
}

EXCLUDED_EXTENSIONS = {
    ".pyc",
    ".pyo",
    ".pyd",
    ".exe",
    ".dll",
    ".so",
    ".dylib",
    ".bin",
    ".iso",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".ico",
    ".pdf",
    ".zip",
    ".tar",
    ".gz",
    ".sqlite",
    ".db",
}


class ProjectScanner:
    """Scans and analyzes a project workspace to build a compact manifest."""

    def __init__(self, workspace_path: str):
        self.workspace_path = Path(workspace_path).resolve()

    def parse_gitignore(self) -> Set[str]:
        patterns = set()
        gitignore_path = self.workspace_path / ".gitignore"
        if gitignore_path.exists():
            try:
                with open(gitignore_path, "r", encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#"):
                            patterns.add(line.rstrip("/"))
            except Exception:
                pass
        return patterns

    def scan(self) -> Dict[str, Any]:
        if not self.workspace_path.exists() or not self.workspace_path.is_dir():
            raise FileNotFoundError(f"Project directory does not exist: {self.workspace_path}")

        files_list: List[Dict[str, Any]] = []
        languages: Set[str] = set()
        frameworks: Set[str] = set()
        scripts: Dict[str, str] = {}
        has_git = (self.workspace_path / ".git").exists()
        gitignore_patterns = self.parse_gitignore()

        for root, dirs, files in os.walk(self.workspace_path):
            # Prune excluded directories
            dirs[:] = [
                d for d in dirs
                if d not in EXCLUDED_DIRS and d not in gitignore_patterns
            ]

            rel_root = Path(root).relative_to(self.workspace_path)

            for file in files:
                file_path = Path(root) / file
                rel_path = str(rel_root / file) if str(rel_root) != "." else file
                ext = file_path.suffix.lower()

                if ext in EXCLUDED_EXTENSIONS:
                    continue
                if file in gitignore_patterns:
                    continue

                try:
                    stat = file_path.stat()
                    size = stat.st_size
                except Exception:
                    size = 0

                files_list.append({
                    "path": rel_path.replace("\\", "/"),
                    "size_bytes": size,
                    "extension": ext,
                })

                # Language detection
                if ext in (".py", ".pyw"):
                    languages.add("python")
                elif ext in (".js", ".jsx", ".mjs"):
                    languages.add("javascript")
                elif ext in (".ts", ".tsx"):
                    languages.add("typescript")
                elif ext == ".rs":
                    languages.add("rust")
                elif ext == ".go":
                    languages.add("go")
                elif ext in (".cs", ".csproj"):
                    languages.add("csharp")

                # Framework and configuration detection
                if file == "package.json":
                    try:
                        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                            pkg_data = json.load(f)
                            deps = {**pkg_data.get("dependencies", {}), **pkg_data.get("devDependencies", {})}
                            if "react" in deps:
                                frameworks.add("react")
                            if "vue" in deps:
                                frameworks.add("vue")
                            if "vite" in deps:
                                frameworks.add("vite")
                            if "express" in deps:
                                frameworks.add("express")
                            if "next" in deps:
                                frameworks.add("next.js")
                            for s_name, s_cmd in pkg_data.get("scripts", {}).items():
                                scripts[f"npm run {s_name}"] = s_cmd
                    except Exception:
                        pass
                elif file in ("pyproject.toml", "requirements.txt", "Pipfile"):
                    try:
                        content = file_path.read_text(encoding="utf-8", errors="ignore").lower()
                        if "fastapi" in content:
                            frameworks.add("fastapi")
                        if "flask" in content:
                            frameworks.add("flask")
                        if "django" in content:
                            frameworks.add("django")
                        if "pytest" in content:
                            scripts["pytest"] = "pytest"
                    except Exception:
                        pass

        # Identify likely entry points
        entry_points = []
        for f in files_list:
            p = f["path"]
            if p in ("main.py", "app.py", "index.ts", "index.js", "src/main.tsx", "src/index.tsx", "src/App.tsx"):
                entry_points.append(p)

        return {
            "root_path": str(self.workspace_path),
            "project_name": self.workspace_path.name,
            "has_git": has_git,
            "languages": sorted(list(languages)),
            "frameworks": sorted(list(frameworks)),
            "scripts": scripts,
            "entry_points": entry_points,
            "total_files": len(files_list),
            "files": sorted(files_list, key=lambda x: x["path"]),
        }
