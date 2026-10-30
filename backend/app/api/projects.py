import os
from pathlib import Path
from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.memory.database import get_db
from app.memory.models.models import Project, ProjectSession, CheckpointRecord
from app.schemas.schemas import ProjectCreate, ProjectResponse, SessionCreate, SessionResponse, CheckpointResponse
from app.ai.context.scanner import ProjectScanner
from app.workspace.git.git_manager import GitManager

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", response_model=ProjectResponse)
async def create_project(data: ProjectCreate, db: AsyncSession = Depends(get_db)):
    proj_path = Path(data.path).resolve()

    if data.is_new:
        os.makedirs(proj_path, exist_ok=True)
        git_mgr = GitManager(str(proj_path))
        await git_mgr.init_repo()
    else:
        if not proj_path.exists() or not proj_path.is_dir():
            raise HTTPException(status_code=400, detail=f"Directory does not exist: {data.path}")

    # Check if already registered
    existing = await db.execute(select(Project).where(Project.path == str(proj_path)))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Project path is already registered")

    # Initial scan
    scanner = ProjectScanner(str(proj_path))
    manifest = scanner.scan()

    project = Project(
        name=data.name,
        path=str(proj_path),
        description=data.description,
        project_metadata=manifest,
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)

    # Automatically create initial default session
    session = ProjectSession(project_id=project.id, title="Default Session")
    db.add(session)
    await db.commit()

    return project


@router.get("", response_model=List[ProjectResponse])
async def list_projects(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Project).order_by(Project.created_at.desc()))
    return result.scalars().all()


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(project_id: str, db: AsyncSession = Depends(get_db)):
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Refresh scan metadata
    try:
        scanner = ProjectScanner(project.path)
        project.project_metadata = scanner.scan()
        await db.commit()
    except Exception:
        pass

    return project


@router.get("/{project_id}/files")
async def get_project_files(project_id: str, db: AsyncSession = Depends(get_db)):
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    scanner = ProjectScanner(project.path)
    manifest = scanner.scan()
    return {"files": manifest["files"], "total": manifest["total_files"]}


@router.get("/{project_id}/git-status")
async def get_project_git_status(project_id: str, db: AsyncSession = Depends(get_db)):
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    git_mgr = GitManager(project.path)
    return await git_mgr.get_status()


@router.get("/{project_id}/checkpoints", response_model=List[CheckpointResponse])
async def list_project_checkpoints(project_id: str, db: AsyncSession = Depends(get_db)):
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    git_mgr = GitManager(project.path)
    history = await git_mgr.get_checkpoint_history()
    return [
        CheckpointResponse(
            id=item["commit_hash"],
            git_ref=item["commit_hash"],
            description=item["message"],
            files_affected=[],
            created_at=item.get("date") or "2026-01-01T00:00:00",
        )
        for item in history
    ]


@router.get("/{project_id}/sessions", response_model=List[SessionResponse])
async def list_project_sessions(project_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ProjectSession)
        .where(ProjectSession.project_id == project_id)
        .order_by(ProjectSession.created_at.desc())
    )
    return result.scalars().all()


@router.post("/{project_id}/sessions", response_model=SessionResponse)
async def create_project_session(
    project_id: str,
    data: SessionCreate,
    db: AsyncSession = Depends(get_db),
):
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    session = ProjectSession(
        project_id=project_id,
        title=data.title,
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session

