import pytest
from app.ai.adapters.chatgpt_edge_adapter import ChatGPTEdgeAdapter
from app.browser.manager.browser_manager import browser_manager


@pytest.mark.asyncio
async def test_m_chatgpt_edge_live_interaction():
    """
    Test M: Microsoft Edge Playwright Interaction with ChatGPT
    1. Verify Edge detection and availability.
    2. Open Edge browser context via Playwright.
    3. Navigate to ChatGPT (https://chatgpt.com).
    4. Submit a verification prompt.
    5. Detect and extract the live assistant response.
    6. Verify protocol envelope compliance.
    """
    adapter = ChatGPTEdgeAdapter("chatgpt_edge", {
        "website_url": "https://chatgpt.com",
        "timeout_ms": 45000,
    })

    # 1. Check Edge availability on host
    is_available = await adapter.check_availability()
    assert is_available is True, "Microsoft Edge was not detected on Windows host"

    capabilities = await adapter.get_capabilities()
    assert capabilities["provider"] == "chatgpt_edge"
    assert "Edge" in capabilities["browser"]

    # 2. Perform live prompt exchange with ChatGPT
    envelope = await adapter.send_request(
        prompt="Hello from ForgeAgent test suite! Please reply with: Edge test confirmed.",
        task_id="test-task-edge-1",
        request_id="test-req-edge-1",
    )

    # 3. Verify returned envelope
    assert envelope.protocol_version == "forgeagent.v1"
    assert envelope.task_id == "test-task-edge-1"
    assert envelope.request_id == "test-req-edge-1"
    
    # 4. Verify content extracted from ChatGPT
    analysis_text = envelope.payload.get("analysis", "") or envelope.payload.get("summary", "")
    assert len(analysis_text) > 0, "No response text extracted from ChatGPT in Edge"
    print(f"\n[Test M] Live reply captured from ChatGPT via Microsoft Edge:\n{analysis_text}\n")

