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
    auto_pilot: bool = False  # AI-suggested commands need approval unless the user opts in
    connector_name: Optional[str] = None


class SaveFileRequest(BaseModel):
    file_path: str
    content: str
    workspace_path: Optional[str] = None


class CreateSessionRequest(BaseModel):
    title: Optional[str] = "New Chat"


class PruneSessionsRequest(BaseModel):
    keep_latest: int = Field(default=10, ge=1)
    remove_empty: bool = True


@router.get("/sessions")
async def list_chat_sessions(sync: bool = True):
    """Retrieve all chat sessions, syncing with logged-in ChatGPT in Edge."""
    return await chat_orchestrator.list_sessions(sync_chatgpt=sync)


@router.post("/sessions")
async def create_chat_session(data: Optional[CreateSessionRequest] = None):
    """Create a new chat session (and navigates Edge to fresh chat)."""
    title = data.title if data and data.title else "New Chat"
    return await chat_orchestrator.create_session(title=title)


@router.get("/sessions/{session_id}")
async def get_chat_session(session_id: str):
    """Get a specific chat session with its messages."""
    if session_id not in chat_orchestrator.sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    return chat_orchestrator.sessions[session_id]


@router.post("/sessions/{session_id}/select")
async def select_chat_session(session_id: str):
    """Activate and switch to a chat session (switches ChatGPT tab in Edge)."""
    try:
        session = await chat_orchestrator.select_session(session_id)
        return session
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/sessions/{session_id}")
async def delete_chat_session(session_id: str):
    """Delete a chat session."""
    chat_orchestrator.delete_session(session_id)
    return {"status": "DELETED", "session_id": session_id}


@router.post("/sessions/prune")
async def prune_chat_sessions(data: Optional[PruneSessionsRequest] = None):
    """Remove empty chats and old chats beyond the newest N (the active chat is always kept)."""
    data = data or PruneSessionsRequest()
    return chat_orchestrator.prune_sessions(keep_latest=data.keep_latest, remove_empty=data.remove_empty)


@router.post("/messages/{message_id}/actions/{action_id}/approve")
async def approve_pending_action(message_id: str, action_id: str):
    """Approve a command or sensitive file write the AI proposed. The command allowlist still applies."""
    try:
        return await chat_orchestrator.approve_pending_action(message_id, action_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except (ValueError, PermissionError) as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.post("/messages/{message_id}/actions/{action_id}/reject")
async def reject_pending_action(message_id: str, action_id: str):
    try:
        return chat_orchestrator.reject_pending_action(message_id, action_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.post("/chat")
async def chat_with_agent(data: ChatRequest):
    """Send natural language message to the agent / ChatGPT and auto-execute code/commands."""
    try:
        reply = await chat_orchestrator.send_user_message(
            message=data.message,
            workspace_path=data.workspace_path or str(settings.workspace_dir),
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


@router.post("/open-browser")
async def open_edge_browser():
    """Launch visible Microsoft Edge browser on user desktop to allow logging into ChatGPT."""
    from app.browser.manager.browser_manager import browser_manager
    edge_path = browser_manager.find_edge_path() or "msedge"
    profile_dir = settings.browser_profile_dir
    os.makedirs(profile_dir, exist_ok=True)

    cmd = [
        edge_path,
        "--remote-debugging-port=9222",
        f"--user-data-dir={profile_dir}",
        "https://chatgpt.com",
    ]
    try:
        import subprocess
        subprocess.Popen(cmd)
        return {"status": "OPENED", "message": "Microsoft Edge opened on your desktop. You may log in."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to open Microsoft Edge: {e}")


@router.delete("/history")
async def clear_chat_history():
    """Clear conversation history (New Chat)."""
    chat_orchestrator.clear_history()
    return {"status": "CLEARED"}


@router.get("/files")
async def get_workspace_files(workspace_path: Optional[str] = Query(None)):
    """Retrieve scanned workspace file list and directory tree for the IDE panel."""
    target_path = Path(workspace_path or settings.workspace_dir).resolve()
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
    target_ws = Path(workspace_path or settings.workspace_dir).resolve()
    fm = SafeFileManager(str(target_ws))
    try:
        content = fm.read_file(path)
        return {"path": path, "content": content}
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/save-file")
async def save_file_content(data: SaveFileRequest):
    """Directly save file modifications from Monaco editor."""
    target_ws = Path(data.workspace_path or settings.workspace_dir).resolve()
    fm = SafeFileManager(str(target_ws))
    try:
        hash_val = fm.write_file_atomic(data.file_path, data.content)
        return {"status": "SAVED", "path": data.file_path, "sha256": hash_val}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

