from typing import Dict, Any
from fastapi import APIRouter, Body
from app.config.settings import settings
from app.core.permissions.policy import permission_policy

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("")
async def get_settings():
    return {
        "app_name": settings.app_name,
        "version": settings.version,
        "execution_mode": settings.execution_mode,
        "default_ai_connector": settings.default_ai_connector,
        "openai_base_url": settings.openai_base_url,
        "openai_model_id": settings.openai_model_id,
        "has_openai_key": bool(settings.openai_api_key),
        "ollama_base_url": settings.ollama_base_url,
        "ollama_model_id": settings.ollama_model_id,
        "command_timeout_seconds": settings.command_timeout_seconds,
        "max_repair_attempts": settings.max_repair_attempts,
        "emergency_stop_active": permission_policy.is_emergency_stop_active,
    }


@router.post("/emergency-stop")
async def toggle_emergency_stop(active: bool = Body(..., embed=True)):
    if active:
        permission_policy.trigger_emergency_stop()
    else:
        permission_policy.reset_emergency_stop()
    return {"emergency_stop_active": permission_policy.is_emergency_stop_active}


@router.put("")
async def update_settings(updates: Dict[str, Any]):
    if "execution_mode" in updates:
        settings.execution_mode = str(updates["execution_mode"])
    if "default_ai_connector" in updates:
        settings.default_ai_connector = str(updates["default_ai_connector"])
    if "openai_base_url" in updates:
        settings.openai_base_url = str(updates["openai_base_url"])
    if "openai_model_id" in updates:
        settings.openai_model_id = str(updates["openai_model_id"])
    if "openai_api_key" in updates and updates["openai_api_key"]:
        settings.openai_api_key = str(updates["openai_api_key"])
    if "ollama_base_url" in updates:
        settings.ollama_base_url = str(updates["ollama_base_url"])
    if "ollama_model_id" in updates:
        settings.ollama_model_id = str(updates["ollama_model_id"])
    if "max_repair_attempts" in updates:
        settings.max_repair_attempts = int(updates["max_repair_attempts"])

    return {"status": "UPDATED"}

