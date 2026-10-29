import json
import logging
import httpx
from typing import Dict, Any, Optional, List
from app.ai.adapters.base import AIConnectorBase
from app.ai.protocol.protocol import AIResponseEnvelope

logger = logging.getLogger("forgeagent.ai.ollama")

SYSTEM_PROTOCOL_PROMPT = """You are ForgeAgent reasoning engine. You must communicate strictly using the forgeagent.v1 protocol.
Always respond with a single valid JSON object with the following top-level structure:
{
  "protocol_version": "forgeagent.v1",
  "task_id": "<TASK_ID>",
  "request_id": "<REQUEST_ID>",
  "response_type": "plan" | "request_context" | "propose_changes" | "propose_command" | "report_analysis" | "finish",
  "payload": { ... }
}
Do not include any prose or markdown wrappers outside the JSON. Return only the raw JSON string."""


class OllamaAdapter(AIConnectorBase):
    """Local Ollama model server connector."""

    def __init__(self, name: str = "ollama", config: Optional[Dict[str, Any]] = None):
        super().__init__(name, config)
        self.base_url = self.config.get("base_url", "http://127.0.0.1:11434").rstrip("/")
        self.model_id = self.config.get("model_id", "llama3")
        self.timeout = float(self.config.get("timeout_seconds", 120.0))

    async def initialize(self) -> bool:
        self.is_initialized = True
        return True

    async def check_availability(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                res = await client.get(f"{self.base_url}/api/tags")
                return res.status_code == 200
        except Exception:
            return False

    async def list_models(self) -> List[str]:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                res = await client.get(f"{self.base_url}/api/tags")
                if res.status_code == 200:
                    data = res.json()
                    return [m.get("name") for m in data.get("models", [])]
        except Exception as e:
            logger.warning(f"Failed to list Ollama models: {e}")
        return []

    async def get_capabilities(self) -> Dict[str, Any]:
        available = await self.check_availability()
        models = await self.list_models() if available else []
        return {
            "provider": "ollama",
            "base_url": self.base_url,
            "current_model": self.model_id,
            "available": available,
            "models": models,
        }

    async def send_request(
        self,
        prompt: str,
        task_id: str,
        request_id: str,
        system_instruction: Optional[str] = None,
        context_data: Optional[Dict[str, Any]] = None,
    ) -> AIResponseEnvelope:
        sys_prompt = system_instruction or SYSTEM_PROTOCOL_PROMPT
        sys_prompt += f"\nActive Task ID: {task_id}\nActive Request ID: {request_id}"

        payload = {
            "model": self.model_id,
            "messages": [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": prompt},
            ],
            "format": "json",
            "stream": False,
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                res = await client.post(f"{self.base_url}/api/chat", json=payload)
                res.raise_for_status()
                data = res.json()
                raw_text = data.get("message", {}).get("content", "")
                parsed_json = json.loads(raw_text)
                parsed_json["task_id"] = task_id
                parsed_json["request_id"] = request_id
                return AIResponseEnvelope.model_validate(parsed_json)
        except Exception as e:
            logger.error(f"Ollama request error: {e}")
            raise RuntimeError(f"Ollama execution failed: {e}")
