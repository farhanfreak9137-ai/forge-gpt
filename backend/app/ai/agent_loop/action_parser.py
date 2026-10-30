import re
from enum import Enum
from typing import List, Optional, Tuple, Dict, Any
from pydantic import BaseModel, Field


class AgentActionType(str, Enum):
    CONVERSATION = "conversation"
    WRITE_FILE = "write_file"
    RUN_COMMAND = "run_command"


class FileAction(BaseModel):
    file_path: str
    content: str
    language: Optional[str] = None


class CommandAction(BaseModel):
    command: str


class ParsedAgentTurn(BaseModel):
    clean_message: str
    file_actions: List[FileAction] = Field(default_factory=list)
    command_actions: List[CommandAction] = Field(default_factory=list)
    has_actions: bool = False


SYSTEM_PROMPT_AGENT_HANDS = """You are the AI coding brain for ForgeAgent.
You are pair-programming with the user. You can chat normally, explain concepts, and write code.

When you want to create or edit a file, write the file inside a code block preceded by a header specifying the relative path:
### file: <relative_path>
```<language>
<complete file content>
```

When you want to execute a command or test suite, specify:
### run: <command>
```bash
<command>
```

When chatting normally, answering questions, or explaining code, write ordinary text without file or run headers.
Never use absolute paths or path traversal (no ..). Always use paths relative to the project workspace.
"""


class ActionParser:
    """Parses ChatGPT natural language stream to separate conversational prose from file writes and command executions."""

    @staticmethod
    def parse(response_text: str) -> ParsedAgentTurn:
        file_actions: List[FileAction] = []
        command_actions: List[CommandAction] = []
        seen_paths = set()

        # 1. Primary Regex: match "### file: <path>\n```<lang>\n<content>\n```" or ```lang file="path"
        file_pattern = re.compile(
            r"(?:###\s*file:\s*([^\r\n]+)\s*\r?\n```(?:[a-zA-Z0-9_-]+)?\r?\n(.*?)\r?\n```)"
            r"|(?:```[a-zA-Z0-9_-]+(?:\s+file=[\"']([^\"']+)[\"']|\s+filename=[\"']([^\"']+)[\"']|\s+:([^\r\n]+))\r?\n(.*?)\r?\n```)",
            re.DOTALL | re.IGNORECASE,
        )

        for match in file_pattern.finditer(response_text):
            if match.group(1) is not None:
                path = match.group(1).strip()
                content = match.group(2)
            else:
                path = (match.group(3) or match.group(4) or match.group(5) or "").strip()
                content = match.group(6) or ""

            cleaned_path = path.replace("\\", "/").strip().lstrip("/")
            if (
                cleaned_path
                and ".." not in cleaned_path.split("/")
                and ":" not in cleaned_path
                and "<" not in cleaned_path
                and ">" not in cleaned_path
                and cleaned_path not in seen_paths
            ):
                seen_paths.add(cleaned_path)
                file_actions.append(FileAction(file_path=cleaned_path, content=content))

        # 1.5 Robust fallback scan: Detect natural ChatGPT code blocks preceded by file headers
        # e.g.: ### 1. my-portfolio/index.html, **style.css**, or <!-- script.js -->
        valid_exts = {
            "html", "htm", "css", "js", "jsx", "ts", "tsx", "json",
            "py", "md", "sh", "sql", "yaml", "yml", "txt", "bat"
        }
        generic_block_pattern = re.compile(
            r"```(?:([a-zA-Z0-9_-]+)(?:\s+file=[\"']([^\"']+)[\"'])?)?\s*\r?\n(.*?)\r?\n```",
            re.DOTALL,
        )
        for match in generic_block_pattern.finditer(response_text):
            content = match.group(3) or ""
            detected_path = None

            # Check preceding lines
            preceding = response_text[:match.start()].strip()
            lines = preceding.splitlines()
            for line in reversed(lines[-4:]):
                clean_line = re.sub(r"^[#*\s\d\.\-:`'\"]+|[*\s:`'\"]+$", "", line).strip()
                m = re.search(r"([a-zA-Z0-9_\-\./\\]+\.[a-zA-Z0-9]+)", clean_line)
                if m:
                    cand = m.group(1).replace("\\", "/").strip().lstrip("/")
                    ext = cand.split(".")[-1].lower()
                    if ext in valid_exts and "<" not in cand and ">" not in cand and ".." not in cand:
                        detected_path = cand
                        break

            # Check first line inside code block
            if not detected_path:
                first_line = content.strip().splitlines()[0] if content.strip() else ""
                m = re.search(r"(?:<!--|//|/\*|#)\s*([a-zA-Z0-9_\-\./\\]+\.[a-zA-Z0-9]+)", first_line)
                if m:
                    cand = m.group(1).replace("\\", "/").strip().lstrip("/")
                    ext = cand.split(".")[-1].lower()
                    if ext in valid_exts and "<" not in cand and ">" not in cand and ".." not in cand:
                        detected_path = cand

            if detected_path and detected_path not in seen_paths:
                seen_paths.add(detected_path)
                file_actions.append(FileAction(file_path=detected_path, content=content))

        # ChatGPT may render file cards without Markdown fences, with a filename
        # header followed by a language label and the raw file content.
        file_headers = list(re.finditer(
            r"(?im)^[ \t]*(?:#{1,6}[ \t]*)?file:[ \t]*([^\r\n]+?)[ \t]*$",
            response_text,
        ))
        language_labels = {
            "html", "htm", "css", "javascript", "js", "typescript", "ts", "tsx",
            "jsx", "python", "py", "plain text", "text", "json", "yaml", "yml",
            "markdown", "md", "bash", "sh", "sql", "xml",
        }
        for index, header in enumerate(file_headers):
            path = header.group(1).strip().strip("`\"'")
            cleaned_path = path.replace("\\", "/").lstrip("/")
            content_start = header.end()
            if response_text[content_start:content_start + 2] == "\r\n":
                content_start += 2
            elif response_text[content_start:content_start + 1] == "\n":
                content_start += 1
            content_end = file_headers[index + 1].start() if index + 1 < len(file_headers) else len(response_text)
            content = response_text[content_start:content_end].strip("\r\n")
            first_line, separator, remaining_content = content.partition("\n")
            if first_line.strip().casefold() in language_labels:
                content = remaining_content if separator else ""
            content = content.strip("\r\n")

            if (
                not cleaned_path
                or ".." in cleaned_path.split("/")
                or ":" in cleaned_path
                or "<" in cleaned_path
                or ">" in cleaned_path
                or cleaned_path in seen_paths
            ):
                continue

            if content.strip():
                seen_paths.add(cleaned_path)
                file_actions.append(FileAction(file_path=cleaned_path, content=content))

        # 2. Regex to match explicit "### run: <command>" or "```bash\n# run: <cmd>"
        run_pattern = re.compile(
            r"(?:###\s*run:\s*([^\r\n]+))|(?:```(?:bash|sh|cmd|powershell)\s*\r?\n#\s*run:\s*([^\r\n]+)\r?\n```)",
            re.IGNORECASE,
        )

        for match in run_pattern.finditer(response_text):
            cmd = match.group(1) or match.group(2)
            if cmd:
                clean_cmd = cmd.strip()
                if (
                    clean_cmd
                    and not clean_cmd.startswith("#")
                    and "<" not in clean_cmd
                    and ">" not in clean_cmd
                    and clean_cmd not in [c.command for c in command_actions]
                ):
                    command_actions.append(CommandAction(command=clean_cmd))

        has_actions = len(file_actions) > 0 or len(command_actions) > 0

        return ParsedAgentTurn(
            clean_message=response_text.strip(),
            file_actions=file_actions,
            command_actions=command_actions,
            has_actions=has_actions,
        )
