import os
from pathlib import Path
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Query, Body
from pydantic import BaseModel, Field

from app.config.settings import settings
from app.ai.agent_loop.chat_orchestrator import chat_orchestrator
from app.workspace.files.file_manager import SafeFileManager
from app.ai.context.scanner import ProjectScanner

router = APIRouter(prefix="/studio", tags=["studio"])


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    workspace_path: Optional[str] = None
    auto_pilot: bool = True
    connector_name: Optional[str] = None


class SaveFileRequest(BaseModel):
    file_path: str
    content: str
    workspace_path: Optional[str] = None


@router.post("/chat")
async def chat_with_agent(data: ChatRequest):
    """Send natural language message to the agent / ChatGPT and auto-execute code/commands."""
    try:
        reply = await chat_orchestrator.send_user_message(
            message=data.message,
            workspace_path=data.workspace_path or str(settings.base_dir),
            auto_pilot=data.auto_pilot,
            connector_name=data.connector_name,
        )
        return reply
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history")
async def get_chat_history():
    """Retrieve current studio chat session history."""
    return chat_orchestrator.get_history()


@router.delete("/history")
async def clear_chat_history():
    """Clear conversation history (New Chat)."""
    chat_orchestrator.clear_history()
    return {"status": "CLEARED"}


@router.get("/files")
async def get_workspace_files(workspace_path: Optional[str] = Query(None)):
    """Retrieve scanned workspace file list and directory tree for the IDE panel."""
    target_path = Path(workspace_path or settings.base_dir).resolve()
    if not target_path.exists():
        raise HTTPException(status_code=404, detail="Workspace directory not found")

    scanner = ProjectScanner(str(target_path))
    manifest = scanner.scan()
    return {
        "root_path": str(target_path),
        "project_name": target_path.name,
        "files": manifest.get("files", []),
        "total_files": manifest.get("total_files", 0),
        "languages": manifest.get("languages", []),
    }


@router.get("/file-content")
async def get_file_content(path: str = Query(...), workspace_path: Optional[str] = Query(None)):
    """Read a specific file in the workspace to display in Monaco editor."""
    target_ws = Path(workspace_path or settings.base_dir).resolve()
    fm = SafeFileManager(str(target_ws))
    try:
        content = fm.read_file(path)
        return {"path": path, "content": content}
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/save-file")
async def save_file_content(data: SaveFileRequest):
    """Directly save file modifications from Monaco editor."""
    target_ws = Path(data.workspace_path or settings.base_dir).resolve()
    fm = SafeFileManager(str(target_ws))
    try:
        hash_val = fm.write_file_atomic(data.file_path, data.content)
        return {"status": "SAVED", "path": data.file_path, "sha256": hash_val}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
