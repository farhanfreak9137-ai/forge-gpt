import pytest
import tempfile
from pathlib import Path
from app.browser.mock_chatbot.html_template import MOCK_CHATBOT_HTML
from app.ai.adapters.browser_automation_adapter import BrowserAutomationAdapter
from app.browser.manager.browser_manager import browser_manager


@pytest.mark.asyncio
async def test_g_browser_adapter_with_mock_site():
    """
    Test G: Browser Adapter
    Uses the local mock chatbot site.
    Verifies:
    - Prompt submission
    - Streaming detection & wait for completion
    - Protocol JSON extraction & validation
    - Error detection
    """
    # Create local temporary HTML file for mock chatbot
    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8") as f:
        f.write(MOCK_CHATBOT_HTML)
        mock_file_path = Path(f.name).as_uri()

    adapter = BrowserAutomationAdapter("browser_automation", {
        "target_url": mock_file_path,
        "timeout_ms": 15000,
        "is_permitted": True,
    })

    try:
        # 1. Successful submission and completion detection
        envelope = await adapter.send_request(
            prompt="Plan calculator implementation",
            task_id="test-task-1",
            request_id="test-req-1",
        )
        assert envelope.protocol_version == "forgeagent.v1"
        assert envelope.response_type.value == "plan"
        assert envelope.payload["summary"] == "Browser mock generated plan"

        # 2. Error detection on chatbot failure
        with pytest.raises(RuntimeError) as exc_info:
            await adapter.send_request(
                prompt="trigger_browser_error in chatbot",
                task_id="test-task-2",
                request_id="test-req-2",
            )
        assert "Chatbot indicated error state" in str(exc_info.value)

    finally:
        await browser_manager.close()
        try:
            Path(mock_file_path).unlink(missing_ok=True)
        except Exception:
            pass
