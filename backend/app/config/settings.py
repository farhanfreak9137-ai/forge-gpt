import os
from pathlib import Path
from typing import List, Optional, Any
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # App Information
    app_name: str = "ForgeAgent"
    version: str = "1.0.0"
    debug: bool = False
    environment: str = "development"

    # Server Binding (Strict loopback by default)
    host: str = "127.0.0.1"
    port: int = 8000
    cors_origins: List[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ]

    # Storage and Base Paths
    base_dir: Path = Path(__file__).resolve().parent.parent.parent
    data_dir: Path = base_dir / "data"
    database_url: str = f"sqlite+aiosqlite:///{base_dir / 'data' / 'forgeagent.db'}"
    browser_profile_dir: Path = base_dir / "data" / "browser_profile"
    # Default sandbox for Studio chat: keeps agent output (and edits) out of ForgeAgent's own source tree
    workspace_dir: Path = base_dir.parent / "workspace"

    # Execution Engine Config
    execution_mode: str = "native"  # "native" or "docker"
    command_timeout_seconds: int = 60
    max_repair_attempts: int = 4
    response_retry_limit: int = 2

    # Command Allowlist for Native Windows Execution
    allowed_command_prefixes: List[str] = [
        "git",
        "python",
        "py",
        "pytest",
        "node",
        "npm",
        "pip",
        "uv",
        "cargo",
        "dotnet",
        "go",
    ]  # shells (cmd, powershell) and package runners (npx) are deliberately absent

    # AI Connector Default Settings
    default_ai_connector: str = "chatgpt_edge"  # "mock", "openai", "ollama", "browser_handoff", "browser_automation", "chatgpt_edge"
    chatgpt_edge_url: str = "https://chatgpt.com"
    browser_headless: bool = False  # Set to False to watch Edge open and type live
    # False (default): the ChatGPT window stays visible but never grabs focus or jumps in front of your work.
    edge_steal_focus: bool = False
    openai_base_url: str = "https://api.openai.com/v1"
    openai_api_key: Optional[str] = None
    openai_model_id: str = "gpt-4o"
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model_id: str = "llama3"

    # Security & Redaction Patterns
    redact_keys: List[str] = [
        "api_key",
        "token",
        "secret",
        "password",
        "authorization",
        "cookie",
        "bearer",
    ]

    @field_validator("debug", mode="before")
    @classmethod
    def parse_debug_flag(cls, v: Any) -> bool:
        if isinstance(v, bool):
            return v
        if isinstance(v, str):
            return v.lower() in ("1", "true", "yes", "on", "debug")
        return False

    model_config = SettingsConfigDict(
        env_prefix="FORGEAGENT_",
        env_file=str(Path(__file__).resolve().parent.parent.parent / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
os.makedirs(settings.data_dir, exist_ok=True)
os.makedirs(settings.browser_profile_dir, exist_ok=True)
os.makedirs(settings.workspace_dir, exist_ok=True)
