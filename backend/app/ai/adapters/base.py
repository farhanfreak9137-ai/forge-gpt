from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from app.ai.protocol.protocol import AIResponseEnvelope


class AIConnectorBase(ABC):
    """Normalized interface for all AI connectors in ForgeAgent."""

    def __init__(self, name: str, config: Optional[Dict[str, Any]] = None):
        self.name = name
        self.config = config or {}
        self.is_initialized = False

    @abstractmethod
    async def initialize(self) -> bool:
        """Initialize connection, authenticate, or prepare resources."""
        pass

    @abstractmethod
    async def send_request(
        self,
        prompt: str,
        task_id: str,
        request_id: str,
        system_instruction: Optional[str] = None,
        context_data: Optional[Dict[str, Any]] = None,
    ) -> AIResponseEnvelope:
        """Send prompt and receive validated AIResponseEnvelope."""
        pass

    @abstractmethod
    async def check_availability(self) -> bool:
        """Check if provider endpoint or service is healthy and available."""
        pass

    @abstractmethod
    async def get_capabilities(self) -> Dict[str, Any]:
        """Return provider capabilities (e.g. streaming, vision, local, etc.)."""
        pass

    async def cancel(self, request_id: str) -> bool:
        """Cancel an in-flight request if supported by provider."""
        return False

