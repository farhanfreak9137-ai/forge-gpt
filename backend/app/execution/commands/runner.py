import asyncio
import os
import re
import shlex
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from app.config.settings import settings

MAX_OUTPUT_CHARS = 200_000

# Operators that are only meaningful to a shell; seen as a standalone token they indicate chaining.
SHELL_OPERATOR_TOKENS = [";", "&&", "||", "|", "`", "$("]

# Characters that are never legitimate in an argument for these tools. Several allowlisted
# tools resolve to .cmd/.bat shims on Windows (npm, ...) and cmd.exe would interpret them.
SHELL_METACHARS = re.compile(r"[&|;<>^%!`\r\n\x00]|\$\(")

# Environment variables that must never leak into code run by the agent.
_SECRET_ENV_NAME = re.compile(
    r"(^|_)(API_?KEY|ACCESS_?KEY|SECRET|TOKEN|PASSWORD|PASSWD|CREDENTIALS?)(_|$)", re.IGNORECASE
)
_SECRET_ENV_PREFIXES = ("FORGEAGENT_", "OPENAI_", "ANTHROPIC_", "AZURE_", "AWS_")

PYTHON_SAFE_FLAGS = {"-B", "-u", "-v", "-O", "-OO", "-E", "-s", "-S", "-I", "-q", "-b", "-bb"}
PYTHON_INFO_FLAGS = {"-V", "-VV", "--version", "-h", "--help"}
PYTHON_SAFE_MODULES = {"pytest", "unittest", "compileall", "py_compile", "pip"}

PIP_SUBCOMMANDS = {"install", "list", "freeze", "show", "check"}
PIP_DENIED_FLAGS = {
    "-i", "--index-url", "--extra-index-url", "-f", "--find-links", "--trusted-host", "--proxy",
    "--global-option", "--install-option", "--config-settings", "-C", "--index", "--default-index",
}
NPM_SUBCOMMANDS = {"test", "t", "run", "run-script", "start", "install", "i", "ci", "ls", "list", "outdated"}
NPM_DENIED_FLAGS = {
    "-g", "--global", "--registry", "--script-shell", "--userconfig", "--globalconfig", "--location",
}
UV_SUBCOMMANDS = {"pip", "sync", "venv", "lock", "tree", "add", "remove"}
GIT_SUBCOMMANDS = {
    "status", "diff", "log", "show", "add", "commit", "checkout", "switch", "branch", "restore",
    "stash", "init", "rev-parse", "ls-files", "rm", "mv", "reset", "tag", "blame", "push",
}
GIT_DENIED_FLAG_PREFIXES = ("--exec", "--upload-pack", "--receive-pack", "--output", "--open-files-in-pager")
CARGO_SUBCOMMANDS = {"build", "test", "check", "run", "fmt", "clippy", "clean", "doc", "bench", "tree"}
DOTNET_SUBCOMMANDS = {"build", "test", "run", "restore", "clean", "format"}
GO_SUBCOMMANDS = {"build", "test", "run", "vet", "fmt", "mod", "version", "list", "clean"}
VERSION_FLAGS = {"--version", "-V", "-v", "version", "--info", "--help", "-h"}


def sanitized_environment(extra: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    """Process environment with credentials removed so agent-run code cannot read them."""
    env = {
        k: v
        for k, v in os.environ.items()
        if not _SECRET_ENV_NAME.search(k) and not k.upper().startswith(_SECRET_ENV_PREFIXES)
    }
    if extra:
        env.update(extra)
    return env


class SafeCommandRunner:
    """Executes validated allowlisted commands inside workspace directory.

    Validation is per tool, not just per executable name: inline code (`python -c`, `node -e`),
    stdin scripts, package execution (`npx`, `npm exec`, `uv run`), shells, custom package
    indexes, global git options and any path argument leaving the workspace are rejected.
    Commands are executed without a shell, with secrets stripped from the environment.
    """

    def __init__(self, workspace_path: str, execution_mode: Optional[str] = None):
        self.workspace_path = Path(workspace_path).resolve()
        self.execution_mode = execution_mode or settings.execution_mode

    # ------------------------------------------------------------------ parsing helpers

    @staticmethod
    def _split(command: str) -> List[str]:
        parts = shlex.split(command.strip(), posix=False)
        return [p.strip('"\'') for p in parts]

    @staticmethod
    def _is_trusted_interpreter(token: str) -> bool:
        try:
            return Path(token).resolve() == Path(sys.executable).resolve()
        except OSError:
            return False

    def _inside_workspace(self, value: str) -> bool:
        if value.startswith("~"):
            return False
        try:
            target = (self.workspace_path / value).resolve()  # absolute `value` replaces the base
            target.relative_to(self.workspace_path)
            return True
        except (ValueError, OSError):
            return False

    @staticmethod
    def _looks_like_path(value: str) -> bool:
        return (
            "/" in value
            or "\\" in value
            or value.startswith((".", "~"))
            or re.match(r"^[A-Za-z]:", value) is not None
        )

    def _check_path_args(self, args: List[str]) -> Optional[str]:
        """Reject URLs, response files and any path-like argument that escapes the workspace."""
        for arg in args:
            value = arg.split("=", 1)[1] if arg.startswith("-") and "=" in arg else arg
            if arg.startswith("-") and "=" not in arg:
                continue
            if not value:
                continue
            if "://" in value or value.startswith("git+"):
                return f"URL arguments are not permitted: {value}"
            candidate = value.split("::", 1)[0]  # pytest node ids: path::test
            if self._looks_like_path(candidate) and not self._inside_workspace(candidate):
                return f"Path argument escapes the workspace: {value}"
        return None

    @staticmethod
    def _check_package_specs(args: List[str]) -> Optional[str]:
        """Package specs must be plain names; no URLs, VCS refs, or `scheme:` redirects."""
        for arg in args:
            if arg.startswith("-"):
                continue
            if ":" in arg or arg.startswith("git+"):
                return f"Package source '{arg}' is not permitted; use plain package names."
        return None

    @staticmethod
    def _denied_flag(args: List[str], denied: set) -> Optional[str]:
        for arg in args:
            flag = arg.split("=", 1)[0]
            if flag in denied:
                return f"Flag '{flag}' is not permitted."
        return None

    # ------------------------------------------------------------------ per-tool validators

    def _validate_python(self, args: List[str]) -> Optional[str]:
        i = 0
        while i < len(args) and args[i].startswith("-"):
            flag = args[i]
            if flag in PYTHON_INFO_FLAGS:
                return None if len(args) == 1 else f"'{flag}' cannot be combined with other arguments."
            if flag in PYTHON_SAFE_FLAGS:
                i += 1
            elif flag in ("-W", "-X"):
                i += 2
            elif flag.startswith(("-W", "-X")):
                i += 1
            elif flag == "-m":
                if i + 1 >= len(args):
                    return "'-m' requires a module name."
                module = args[i + 1]
                if module not in PYTHON_SAFE_MODULES:
                    return f"Python module '{module}' is not permitted (allowed: {sorted(PYTHON_SAFE_MODULES)})."
                rest = args[i + 2:]
                if module == "pip":
                    return self._validate_pip(rest)
                if module == "pytest":
                    return self._validate_pytest(rest)
                return self._check_path_args(rest)
            else:
                return f"Python option '{flag}' is not permitted (no inline code, stdin or custom startup)."
        if i >= len(args):
            return "Interactive Python sessions are not permitted."
        script = args[i]
        if not script.lower().endswith((".py", ".pyw")):
            return f"Only .py scripts can be executed: {script}"
        return self._check_path_args(args[i:])

    def _validate_pytest(self, args: List[str]) -> Optional[str]:
        i = 0
        while i < len(args):
            arg = args[i]
            if arg.startswith("@"):
                return "Response files are not permitted."
            if arg == "-p" or (arg.startswith("-p") and not arg.startswith("--") and len(arg) > 2):
                value = args[i + 1] if arg == "-p" and i + 1 < len(args) else arg[2:]
                if not value.startswith("no:"):
                    return "Loading pytest plugins via -p is not permitted."
            i += 1
        return self._check_path_args(args)

    def _validate_pip(self, args: List[str]) -> Optional[str]:
        sub = next((a for a in args if not a.startswith("-")), None)
        if sub is None:
            return None if all(a in VERSION_FLAGS for a in args) else "pip requires a subcommand."
        if sub not in PIP_SUBCOMMANDS:
            return f"pip subcommand '{sub}' is not permitted (allowed: {sorted(PIP_SUBCOMMANDS)})."
        reason = self._denied_flag(args, PIP_DENIED_FLAGS)
        if reason:
            return reason
        specs = [
            a for idx, a in enumerate(args)
            if not a.startswith("-") and a != sub and not (idx > 0 and args[idx - 1] in ("-r", "-c", "-e", "--requirement", "--constraint", "--editable"))
        ]
        return self._check_package_specs(specs) or self._check_path_args(args)

    def _validate_node(self, args: List[str]) -> Optional[str]:
        if args and args[0] in VERSION_FLAGS and len(args) == 1:
            return None
        i = 0
        while i < len(args) and args[i].startswith("-"):
            if args[i] != "--test":
                return f"Node option '{args[i]}' is not permitted (no inline code, requires or loaders)."
            i += 1
        if i >= len(args):
            return "Interactive Node sessions are not permitted."
        if not args[i].lower().endswith((".js", ".mjs", ".cjs")):
            return f"Only .js/.mjs/.cjs scripts can be executed: {args[i]}"
        return self._check_path_args(args[i:])

    def _validate_npm(self, args: List[str]) -> Optional[str]:
        if args and args[0] in VERSION_FLAGS and len(args) == 1:
            return None
        sub = next((a for a in args if not a.startswith("-")), None)
        if sub is None or sub not in NPM_SUBCOMMANDS:
            return f"npm subcommand '{sub}' is not permitted (allowed: {sorted(NPM_SUBCOMMANDS)})."
        reason = self._denied_flag(args, NPM_DENIED_FLAGS)
        if reason:
            return reason
        if sub in ("install", "i"):
            specs = [a for a in args if not a.startswith("-") and a != sub]
            reason = self._check_package_specs(specs)
            if reason:
                return reason
        return self._check_path_args(args)

    def _validate_uv(self, args: List[str]) -> Optional[str]:
        if args and args[0] in VERSION_FLAGS and len(args) == 1:
            return None
        sub = args[0] if args else None
        if sub not in UV_SUBCOMMANDS:
            return f"uv subcommand '{sub}' is not permitted (allowed: {sorted(UV_SUBCOMMANDS)})."
        reason = self._denied_flag(args, PIP_DENIED_FLAGS)
        if reason:
            return reason
        if sub == "pip":
            return self._validate_pip(args[1:])
        if sub in ("add", "remove"):
            reason = self._check_package_specs([a for a in args[1:] if not a.startswith("-")])
            if reason:
                return reason
        return self._check_path_args(args[1:])

    def _validate_git(self, args: List[str]) -> Optional[str]:
        if not args:
            return "git requires a subcommand."
        if args[0].startswith("-"):
            if args == ["--version"]:
                return None
            return f"Global git option '{args[0]}' is not permitted."
        if args[0] not in GIT_SUBCOMMANDS:
            return f"git subcommand '{args[0]}' is not permitted (allowed: {sorted(GIT_SUBCOMMANDS)})."
        for arg in args[1:]:
            if arg.startswith(GIT_DENIED_FLAG_PREFIXES):
                return f"git option '{arg}' is not permitted."
        return self._check_path_args(args[1:])

    def _validate_subcommand_tool(self, name: str, allowed: set, args: List[str]) -> Optional[str]:
        if args and args[0] in VERSION_FLAGS and len(args) == 1:
            return None
        if not args or args[0] not in allowed:
            return f"{name} subcommand '{args[0] if args else ''}' is not permitted (allowed: {sorted(allowed)})."
        return self._check_path_args(args[1:])

    def _validate_arguments(self, executable: str, args: List[str]) -> Optional[str]:
        if executable in ("python", "py", "python3"):
            return self._validate_python(args)
        if executable == "pytest":
            return self._validate_pytest(args)
        if executable == "pip":
            return self._validate_pip(args)
        if executable == "node":
            return self._validate_node(args)
        if executable == "npm":
            return self._validate_npm(args)
        if executable == "uv":
            return self._validate_uv(args)
        if executable == "git":
            return self._validate_git(args)
        if executable == "cargo":
            return self._validate_subcommand_tool("cargo", CARGO_SUBCOMMANDS, args)
        if executable == "dotnet":
            return self._validate_subcommand_tool("dotnet", DOTNET_SUBCOMMANDS, args)
        if executable == "go":
            return self._validate_subcommand_tool("go", GO_SUBCOMMANDS, args)
        return f"No argument policy exists for '{executable}'; refusing to run it."

    # ------------------------------------------------------------------ public API

    def is_command_allowed(self, command: str) -> Tuple[bool, str]:
        """Check if command passes the strict allowlist and safety policy."""
        stripped = command.strip()
        if not stripped:
            return False, "Command is empty"

        if re.search(r"[\r\n\x00]", stripped):
            return False, "Multi-line commands are not permitted."

        try:
            parts = self._split(stripped)
        except Exception as e:
            return False, f"Failed to parse command syntax: {e}"

        if not parts:
            return False, "No command tokens found"

        head = parts[0]
        trusted = self._is_trusted_interpreter(head)
        if not trusted:
            # Only a bare tool name (optionally .exe) is acceptable: a path or a .bat/.cmd name
            # would let a file written into the workspace masquerade as an allowlisted tool.
            if "/" in head or "\\" in head or head.lower().endswith((".cmd", ".bat", ".com", ".ps1", ".sh")):
                return False, f"Executable '{head}' must be a bare allowlisted tool name, not a path or script."
            executable = head.lower()
            if executable.endswith(".exe"):
                executable = executable[:-4]
        else:
            executable = "python"

        if executable not in settings.allowed_command_prefixes and not trusted:
            return False, f"Executable '{executable}' is not in the allowed command allowlist."

        for token in SHELL_OPERATOR_TOKENS:
            if token in parts:
                return False, f"Shell operator '{token}' is prohibited in safe native execution."
        for token in parts[1:]:
            if SHELL_METACHARS.search(token):
                return False, f"Shell metacharacters are prohibited in arguments: {token}"

        reason = self._validate_arguments(executable, parts[1:])
        if reason:
            return False, f"Argument policy rejected command: {reason}"

        return True, "Command is permitted"

    def _resolve_executable(self, head: str) -> str:
        if self._is_trusted_interpreter(head):
            return str(Path(head).resolve())
        name = head.lower()
        search_dirs = []
        for entry in os.environ.get("PATH", "").split(os.pathsep):
            if not entry or entry == ".":
                continue
            try:
                Path(entry).resolve().relative_to(self.workspace_path)
                continue  # never resolve tools from inside the workspace
            except (ValueError, OSError):
                search_dirs.append(entry)
        found = shutil.which(name, path=os.pathsep.join(search_dirs))
        if not found or not os.path.isabs(found):
            raise FileNotFoundError(f"Executable '{head}' was not found on PATH.")
        try:
            Path(found).resolve().relative_to(self.workspace_path)
            raise PermissionError(f"Refusing to run '{found}' from inside the workspace.")
        except ValueError:
            pass
        return found

    @staticmethod
    async def _kill_tree(proc: "asyncio.subprocess.Process") -> None:
        if sys.platform == "win32" and proc.pid:
            await asyncio.to_thread(
                subprocess.run,
                ["taskkill", "/T", "/F", "/PID", str(proc.pid)],
                capture_output=True,
            )
        else:
            proc.kill()

    async def run(
        self,
        command: str,
        timeout_seconds: Optional[int] = None,
        env_vars: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        timeout = timeout_seconds or settings.command_timeout_seconds
        allowed, reason = self.is_command_allowed(command)
        if not allowed:
            raise PermissionError(f"Security policy rejected command: {reason}")

        start_time = time.time()
        env = sanitized_environment(env_vars)

        try:
            parts = self._split(command)
            exe = self._resolve_executable(parts[0])
            proc = await asyncio.create_subprocess_exec(
                exe,
                *parts[1:],
                cwd=str(self.workspace_path),
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )

            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=float(timeout),
                )
                exit_code = proc.returncode or 0
                timed_out = False
            except asyncio.TimeoutError:
                await self._kill_tree(proc)
                stdout_bytes, stderr_bytes = await proc.communicate()
                exit_code = -1
                timed_out = True

            duration_ms = int((time.time() - start_time) * 1000)

            return {
                "command": command,
                "exit_code": exit_code,
                "stdout": stdout_bytes.decode("utf-8", errors="replace")[:MAX_OUTPUT_CHARS],
                "stderr": stderr_bytes.decode("utf-8", errors="replace")[:MAX_OUTPUT_CHARS],
                "duration_ms": duration_ms,
                "timed_out": timed_out,
                "execution_mode": self.execution_mode,
            }

        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            return {
                "command": command,
                "exit_code": -1,
                "stdout": "",
                "stderr": str(e),
                "duration_ms": duration_ms,
                "timed_out": False,
                "execution_mode": self.execution_mode,
            }
