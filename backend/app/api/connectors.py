from typing import List, Dict, Any
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.memory.database import get_db
from app.memory.models.models import AIConnectorConfig
from app.schemas.schemas import AIConnectorConfigResponse, AIConnectorConfigCreate, BrowserHandoffSubmitRequest
from app.core.orchestrator.orchestrator import orchestrator
from app.ai.adapters.browser_handoff_adapter import BrowserHandoffAdapter

router = APIRouter(prefix="/connectors", tags=["connectors"])


@router.get("", response_model=List[Dict[str, Any]])
async def list_connectors():
    result = []
    for name, conn in orchestrator.active_connectors.items():
        avail = await conn.check_availability()
        caps = await conn.get_capabilities()
        result.append({
            "name": name,
            "provider_type": caps.get("provider", name),
            "available": avail,
            "capabilities": caps,
        })
    return result


@router.post("/{name}/test")
async def test_connector(name: str):
    if name not in orchestrator.active_connectors:
        raise HTTPException(status_code=404, detail=f"Connector '{name}' not found")

    conn = orchestrator.active_connectors[name]
    available = await conn.check_availability()
    caps = await conn.get_capabilities()
    return {
        "name": name,
        "available": available,
        "capabilities": caps,
    }


@router.post("/browser_handoff/submit")
async def submit_browser_handoff_response(data: BrowserHandoffSubmitRequest):
    handoff_adapter = orchestrator.active_connectors.get("browser_handoff")
    if not isinstance(handoff_adapter, BrowserHandoffAdapter):
        raise HTTPException(status_code=400, detail="Browser handoff connector is not active")

    try:
        envelope = handoff_adapter.submit_user_response(data.request_id, data.response_text)
        return {"status": "SUCCESS", "response_type": envelope.response_type.value}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

