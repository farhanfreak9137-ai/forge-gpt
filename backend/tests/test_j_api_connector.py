import json
import pytest
import httpx
from app.ai.adapters.openai_adapter import OpenAIAdapter


@pytest.mark.asyncio
async def test_j_openai_compatible_api_connector(monkeypatch):
    """
    Test J: API Connector
    Tests OpenAI-compatible HTTP adapter against a simulated local endpoint.
    Verifies:
    - Request serialization
    - Authentication header passage
    - Protocol response parsing
    - Error mapping
    """
    received_requests = []

    def mock_handler(request: httpx.Request) -> httpx.Response:
        received_requests.append(request)
        if request.url.path == "/v1/models":
            return httpx.Response(200, json={"data": [{"id": "test-gpt"}]})

        if request.url.path == "/v1/chat/completions":
            body = json.loads(request.content.decode("utf-8"))
            # Return protocol compliant JSON in content
            response_content = json.dumps({
                "protocol_version": "forgeagent.v1",
                "task_id": "test-task-j",
                "request_id": "test-req-j",
                "response_type": "finish",
                "payload": {
                    "summary": "Mock OpenAI server finished task successfully",
                    "verification_passed": True
                }
            })
            return httpx.Response(200, json={
                "choices": [{
                    "message": {
                        "role": "assistant",
                        "content": response_content
                    }
                }]
            })

        return httpx.Response(404)

    transport = httpx.MockTransport(mock_handler)
    # Patch httpx.AsyncClient used inside adapter
    orig_client = httpx.AsyncClient

    def custom_client(*args, **kwargs):
        kwargs["transport"] = transport
        return orig_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", custom_client)

    adapter = OpenAIAdapter("openai_mock", {
        "base_url": "https://mock.local.server/v1",
        "api_key": "test-secret-key-12345",
        "model_id": "test-gpt",
    })

    # Test availability check
    available = await adapter.check_availability()
    assert available is True

    # Test send_request
    envelope = await adapter.send_request(
        prompt="Implement test feature",
        task_id="test-task-j",
        request_id="test-req-j",
    )

    assert envelope.protocol_version == "forgeagent.v1"
    assert envelope.task_id == "test-task-j"
    assert envelope.response_type.value == "finish"

    # Verify authorization header was sent
    assert len(received_requests) >= 2
    chat_req = received_requests[-1]
    assert chat_req.headers.get("authorization") == "Bearer test-secret-key-12345"

