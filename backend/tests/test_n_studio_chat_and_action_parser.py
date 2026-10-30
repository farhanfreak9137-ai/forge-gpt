import pytest
import shutil
from pathlib import Path
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.ai.agent_loop.action_parser import ActionParser
from app.ai.agent_loop.chat_orchestrator import ChatOrchestrator, chat_orchestrator
from app.ai.protocol.protocol import AIResponseEnvelope, ResponseType
from app.core.orchestrator.orchestrator import orchestrator
from app.workspace.files.file_manager import SafeFileManager


def test_action_parser_casual_chat():
    """Verify casual chat (e.g., 'how are you?') produces clean text and no file/command actions."""
    casual_text = "I am doing well, thank you for asking! How can I assist you with your project today?"
    parsed = ActionParser.parse(casual_text)

    assert parsed.has_actions is False
    assert len(parsed.file_actions) == 0
    assert len(parsed.command_actions) == 0
    assert parsed.clean_message == casual_text


def test_action_parser_file_and_run_blocks():
    """Verify parser extracts files and run commands cleanly from ChatGPT output."""
    chatgpt_reply = (
        "Sure! Here is a simple python script to calculate fibonacci numbers:\n\n"
        "### file: scripts/fib.py\n"
        "```python\n"
        "def fib(n):\n"
        "    return n if n <= 1 else fib(n-1) + fib(n-2)\n"
        "```\n\n"
        "And here is how to run it:\n\n"
        "### run: python scripts/fib.py\n"
        "```bash\n"
        "python scripts/fib.py\n"
        "```\n\n"
        "Let me know if you need more features!"
    )

    parsed = ActionParser.parse(chatgpt_reply)

    assert parsed.has_actions is True
    assert len(parsed.file_actions) == 1
    assert parsed.file_actions[0].file_path == "scripts/fib.py"
    assert "def fib(n):" in parsed.file_actions[0].content

    assert len(parsed.command_actions) == 1
    assert parsed.command_actions[0].command == "python scripts/fib.py"

    assert "Sure! Here is a simple python script" in parsed.clean_message
    assert "Let me know if you need more features!" in parsed.clean_message


def test_action_parser_natural_chatgpt_website_blocks():
    """Verify parser extracts files from natural ChatGPT headers like ### 1. my-portfolio/index.html."""
    natural_reply = (
        "Here is the modern personal portfolio website:\n\n"
        "### 1. `my-portfolio/index.html`\n"
        "```html\n"
        "<!DOCTYPE html>\n<html><head><title>Portfolio</title></head><body><h1>Hello</h1></body></html>\n"
        "```\n\n"
        "### 2. `my-portfolio/style.css`\n"
        "```css\n"
        "body { background: #0f172a; color: white; }\n"
        "```\n\n"
        "### 3. `my-portfolio/script.js`\n"
        "```javascript\n"
        "console.log('Portfolio initialized');\n"
        "```\n"
    )

    parsed = ActionParser.parse(natural_reply)
    assert parsed.has_actions is True
    assert len(parsed.file_actions) == 3
    paths = [f.file_path for f in parsed.file_actions]
    assert "my-portfolio/index.html" in paths
    assert "my-portfolio/style.css" in paths
    assert "my-portfolio/script.js" in paths


def test_action_parser_chatgpt_plain_text_file_card():
    parsed = ActionParser.parse("file: farhan.txt\nPlain text\nfarhan")

    assert parsed.has_actions is True
    assert len(parsed.file_actions) == 1
    assert parsed.file_actions[0].file_path == "farhan.txt"
    assert parsed.file_actions[0].content == "farhan"


@pytest.mark.asyncio
async def test_studio_retries_file_request_and_saves_file(tmp_path):
    mock_adapter = orchestrator.get_connector("mock")
    mock_adapter.clear_queue()
    mock_adapter.queue_response(AIResponseEnvelope(
        task_id="chat-studio",
        request_id="acknowledgment",
        response_type=ResponseType.REPORT_ANALYSIS,
        payload={"analysis": "Understood. I'll create that file."},
    ))
    mock_adapter.queue_response(AIResponseEnvelope(
        task_id="chat-studio",
        request_id="file-content",
        response_type=ResponseType.REPORT_ANALYSIS,
        payload={"analysis": "### file: farhan.txt\n```text\nfarhan\n```"},
    ))

    studio = ChatOrchestrator()
    studio.sessions_file = tmp_path / "studio_sessions.json"
    studio.sessions = {
        "test-session": {
            "id": "test-session",
            "title": "Create farhan.txt",
            "messages": [],
        }
    }
    studio.active_session_id = "test-session"

    try:
        reply = await studio.send_user_message(
            "Create and save a txt file called farhan with farhan written in it",
            workspace_path=str(tmp_path),
            connector_name="mock",
        )

        assert (tmp_path / "farhan.txt").read_text(encoding="utf-8") == "farhan"
        assert [change["path"] for change in reply["executed_file_changes"]] == ["farhan.txt"]
        assert reply["action_errors"] == []
        assert len(mock_adapter.call_history) >= 2
        assert "previous response did not include any file content" in mock_adapter.call_history[-1]["prompt"]
    finally:
        mock_adapter.clear_queue()


@pytest.mark.asyncio
async def test_studio_reports_file_request_failure_after_retry(tmp_path):
    mock_adapter = orchestrator.get_connector("mock")
    mock_adapter.clear_queue()
    acknowledgment = AIResponseEnvelope(
        task_id="chat-studio",
        request_id="acknowledgment",
        response_type=ResponseType.REPORT_ANALYSIS,
        payload={"analysis": "Understood. I'll create that file."},
    )
    mock_adapter.queue_response(acknowledgment)
    mock_adapter.queue_response(acknowledgment)

    studio = ChatOrchestrator()
    studio.sessions_file = tmp_path / "studio_sessions.json"
    studio.sessions = {
        "test-session": {
            "id": "test-session",
            "title": "Create farhan.txt",
            "messages": [],
        }
    }
    studio.active_session_id = "test-session"

    try:
        reply = await studio.send_user_message(
            "Create and save a txt file called farhan with farhan written in it",
            workspace_path=str(tmp_path),
            connector_name="mock",
        )

        assert not (tmp_path / "farhan.txt").exists()
        assert len(reply["action_errors"]) == 1
        assert "file was not saved" in reply["clean_message"]
    finally:
        mock_adapter.clear_queue()


@pytest.mark.asyncio
async def test_studio_api_full_workflow(tmp_path):
    """
    Test N: Antigravity / Cursor Pair-Programming Studio API Endpoints
    1. Clear chat history
    2. Send casual greeting 'how are you?' -> clean reply, no project creation
    3. Check history
    4. Save file via Studio Editor API
    5. Read file via Studio File Content API
    6. List workspace files via Studio Files API
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Clear chat history
        clear_res = await client.delete("/api/v1/studio/history")
        assert clear_res.status_code == 200
        assert clear_res.json()["status"] == "CLEARED"

        # 2. Send casual greeting with mock connector
        chat_res = await client.post(
            "/api/v1/studio/chat",
            json={
                "message": "how are you?",
                "workspace_path": str(tmp_path),
                "auto_pilot": True,
                "connector_name": "mock",
            },
        )
        assert chat_res.status_code == 200
        reply_data = chat_res.json()
        assert reply_data["sender"] == "assistant"
        assert len(reply_data["text"]) > 0

        # 3. Verify history
        hist_res = await client.get("/api/v1/studio/history")
        assert hist_res.status_code == 200
        history = hist_res.json()
        assert len(history) >= 2  # user + assistant

        # 4. Save a file from Monaco editor via studio API
        test_file_path = "src/hello.py"
        test_content = "print('Hello from ForgeAgent Studio!')\n"
        save_res = await client.post(
            "/api/v1/studio/save-file",
            json={
                "file_path": test_file_path,
                "content": test_content,
                "workspace_path": str(tmp_path),
            },
        )
        assert save_res.status_code == 200
        assert save_res.json()["status"] == "SAVED"

        # 5. Read back file content via studio API
        read_res = await client.get(
            f"/api/v1/studio/file-content?path={test_file_path}&workspace_path={tmp_path}"
        )
        assert read_res.status_code == 200
        assert read_res.json()["content"] == test_content

        # 6. List workspace files
        files_res = await client.get(
            f"/api/v1/studio/files?workspace_path={tmp_path}"
        )
        assert files_res.status_code == 200
        manifest = files_res.json()
        assert manifest["total_files"] >= 1
        assert any(f["path"] == test_file_path for f in manifest["files"])
