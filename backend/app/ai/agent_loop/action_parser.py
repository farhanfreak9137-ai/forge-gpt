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

        # 1. Regex to match "### file: <path>\n```<lang>\n<content>\n```"
        # Also handles ```language file="path" or ````filename=path
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

            # Clean path
            cleaned_path = path.replace("\\", "/").strip().lstrip("/")
            if cleaned_path and ".." not in cleaned_path.split("/") and ":" not in cleaned_path:
                file_actions.append(FileAction(file_path=cleaned_path, content=content))

        # 2. Regex to match "### run: <command>" or "```bash\n# run: <cmd>"
        run_pattern = re.compile(
            r"(?:###\s*run:\s*([^\r\n]+))|(?:```(?:bash|sh|cmd|powershell)\s*\r?\n(?:#\s*run:\s*)?([^\r\n]+)\r?\n```)",
            re.IGNORECASE,
        )

        for match in run_pattern.finditer(response_text):
            cmd = match.group(1) or match.group(2)
            if cmd:
                clean_cmd = cmd.strip()
                if clean_cmd and not clean_cmd.startswith("#") and clean_cmd not in [c.command for c in command_actions]:
                    command_actions.append(CommandAction(command=clean_cmd))

        # 3. Create clean conversational prose by stripping the technical action blocks for human readability
        clean_text = response_text
        clean_text = file_pattern.sub(r"[Writing file: \1\3\4\5]", clean_text)
        clean_text = run_pattern.sub(r"[Running: \1\2]", clean_text)
        clean_text = clean_text.strip()

        has_actions = len(file_actions) > 0 or len(command_actions) > 0

        return ParsedAgentTurn(
            clean_message=response_text if not has_actions else clean_text,
            file_actions=file_actions,
            command_actions=command_actions,
            has_actions=has_actions,
        )

