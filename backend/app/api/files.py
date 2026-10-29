from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.memory.database import get_db
from app.memory.models.models import Project
from app.workspace.files.file_manager import SafeFileManager
from app.workspace.git.git_manager import GitManager

router = APIRouter(prefix="/files", tags=["files"])


@router.get("/content")
async def get_file_content(
    project_id: str = Query(...),
    path: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    try:
        fm = SafeFileManager(project.path)
        content = fm.read_file(path)
        return {"path": path, "content": content}
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"File not found: {path}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/diff")
async def get_diff(
    project_id: str = Query(...),
    commit_ref: str = Query(None),
    db: AsyncSession = Depends(get_db),
):
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    git_mgr = GitManager(project.path)
    diff_text = await git_mgr.get_diff(commit_ref)
    return {"diff": diff_text}
