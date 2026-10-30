import json
import logging
import httpx
from typing import Dict, Any, Optional
from app.ai.adapters.base import AIConnectorBase
from app.ai.protocol.protocol import AIResponseEnvelope

logger = logging.getLogger("forgeagent.ai.openai")

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


class OpenAIAdapter(AIConnectorBase):
    """OpenAI-compatible HTTP connector (works with OpenAI, LocalAI, vLLM, LMStudio, etc.)."""

    def __init__(self, name: str = "openai", config: Optional[Dict[str, Any]] = None):
        super().__init__(name, config)
        self.base_url = self.config.get("base_url", "https://api.openai.com/v1").rstrip("/")
        self.api_key = self.config.get("api_key", "")
        self.model_id = self.config.get("model_id", "gpt-4o")
        self.timeout = float(self.config.get("timeout_seconds", 60.0))
        self.temperature = float(self.config.get("temperature", 0.2))

    async def initialize(self) -> bool:
        self.is_initialized = True
        return True

    async def check_availability(self) -> bool:
        try:
            headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
            async with httpx.AsyncClient(timeout=5.0) as client:
                res = await client.get(f"{self.base_url}/models", headers=headers)
                return res.status_code in (200, 401)  # 200 or 401 means server is reachable
        except Exception as e:
            logger.warning(f"OpenAI endpoint check failed: {e}")
            return False

    async def get_capabilities(self) -> Dict[str, Any]:
        return {
            "provider": "openai_compatible",
            "base_url": self.base_url,
            "model_id": self.model_id,
            "streaming": False,
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

        messages = [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": prompt},
        ]

        payload = {
            "model": self.model_id,
            "messages": messages,
            "temperature": self.temperature,
            "response_format": {"type": "json_object"},
        }

        headers = {
            "Content-Type": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
                raw_content = data["choices"][0]["message"]["content"]
                
                # Parse JSON
                parsed_json = json.loads(raw_content)
                # Ensure ids match
                parsed_json["task_id"] = task_id
                parsed_json["request_id"] = request_id
                
                # Validate against protocol
                envelope = AIResponseEnvelope.model_validate(parsed_json)
                return envelope
        except httpx.HTTPStatusError as e:
            logger.error(f"OpenAI API error: {e.response.status_code} - {e.response.text}")
            raise RuntimeError(f"OpenAI API error {e.response.status_code}: {e.response.text}")
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response from AI: {e}")
            raise ValueError(f"AI returned invalid JSON: {e}")
        except Exception as e:
            logger.error(f"OpenAI adapter request failed: {e}")
            raise

