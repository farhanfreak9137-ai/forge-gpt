from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.ai.agent_loop.chat_orchestrator import ChatOrchestrator, chat_orchestrator
from app.ai.protocol.protocol import AIResponseEnvelope, ResponseType
from app.core.orchestrator.orchestrator import orchestrator
from app.core.permissions.policy import permission_policy
from app.main import app


def _reply(text: str) -> AIResponseEnvelope:
    return AIResponseEnvelope(
        task_id="chat-studio",
        request_id="scripted",
        response_type=ResponseType.REPORT_ANALYSIS,
        payload={"analysis": text},
    )


@pytest.fixture
def studio(tmp_path: Path):
    mock_adapter = orchestrator.get_connector("mock")
    mock_adapter.clear_queue()
    s = ChatOrchestrator()
    s.sessions_file = tmp_path / "studio_sessions.json"
    s.sessions = {"s": {"id": "s", "title": "t", "messages": []}}
    s.active_session_id = "s"
    yield s, mock_adapter
    mock_adapter.clear_queue()
    permission_policy.reset_emergency_stop()


HELLO_AND_RUN = (
    "### file: hello.py\n```python\nprint('hello from agent')\n```\n"
    "### run: python hello.py\n```bash\npython hello.py\n```"
)


@pytest.mark.asyncio
async def test_commands_are_not_executed_without_approval_by_default(studio, tmp_path):
    s, mock_adapter = studio
    mock_adapter.queue_response(_reply(HELLO_AND_RUN))

    reply = await s.send_user_message("Create hello.py and run it", workspace_path=str(tmp_path), connector_name="mock")

    assert (tmp_path / "hello.py").exists()            # file writes inside the sandbox still happen
    assert reply["executed_commands"] == []             # but nothing ran
    assert len(reply["pending_actions"]) == 1
    pending = reply["pending_actions"][0]
    assert pending["kind"] == "command" and pending["status"] == "PENDING_APPROVAL"
    assert pending["command"] == "python hello.py"


@pytest.mark.asyncio
async def test_approved_command_runs_and_rejected_command_does_not(studio, tmp_path):
    s, mock_adapter = studio
    mock_adapter.queue_response(_reply(HELLO_AND_RUN))
    reply = await s.send_user_message("Create hello.py and run it", workspace_path=str(tmp_path), connector_name="mock")
    action_id = reply["pending_actions"][0]["id"]

    result = await s.approve_pending_action(reply["id"], action_id)
    assert result["status"] == "EXECUTED"
    assert "hello from agent" in result["result"]["stdout"]
    assert reply["executed_commands"][-1]["command"] == "python hello.py"

    with pytest.raises(ValueError):                     # cannot be approved twice
        await s.approve_pending_action(reply["id"], action_id)

    mock_adapter.queue_response(_reply(HELLO_AND_RUN))
    second = await s.send_user_message("Run it again", workspace_path=str(tmp_path), connector_name="mock")
    rejected = s.reject_pending_action(second["id"], second["pending_actions"][0]["id"])
    assert rejected["status"] == "REJECTED"
    assert second["executed_commands"] == []


@pytest.mark.asyncio
async def test_auto_pilot_runs_only_allowed_and_policy_safe_commands(studio, tmp_path):
    s, mock_adapter = studio
    mock_adapter.queue_response(_reply(HELLO_AND_RUN))
    reply = await s.send_user_message("Create hello.py and run it", workspace_path=str(tmp_path), connector_name="mock", auto_pilot=True)
    assert reply["pending_actions"] == []
    assert reply["executed_commands"][0]["status"] == "EXECUTED"
    assert reply["executed_commands"][0]["passed"] is True

    # Package installs still need a human even with auto-pilot on.
    mock_adapter.queue_response(_reply("### run: pip install requests\n```bash\npip install requests\n```"))
    install = await s.send_user_message("Run pip install requests", workspace_path=str(tmp_path), connector_name="mock", auto_pilot=True)
    assert install["executed_commands"] == []
    assert install["pending_actions"][0]["command"] == "pip install requests"


@pytest.mark.asyncio
async def test_blocked_commands_are_never_queued_or_run(studio, tmp_path):
    s, mock_adapter = studio
    mock_adapter.queue_response(_reply(
        "### run: python -c \"open('pwned.txt','w').write('x')\"\n```bash\npython -c \"open('pwned.txt','w').write('x')\"\n```"
    ))
    reply = await s.send_user_message("Run it", workspace_path=str(tmp_path), connector_name="mock", auto_pilot=True)

    assert reply["pending_actions"] == []               # approval cannot unlock an allowlist violation
    assert reply["executed_commands"][0]["status"] == "BLOCKED"
    assert not (tmp_path / "pwned.txt").exists()


@pytest.mark.asyncio
async def test_sensitive_file_writes_wait_for_approval(studio, tmp_path):
    s, mock_adapter = studio
    mock_adapter.queue_response(_reply("### file: .env\n```text\nSECRET=1\n```\n### file: notes.txt\n```text\nok\n```"))
    reply = await s.send_user_message("Write file .env and notes.txt", workspace_path=str(tmp_path), connector_name="mock")

    assert (tmp_path / "notes.txt").exists()
    assert not (tmp_path / ".env").exists()
    pending = reply["pending_actions"][0]
    assert pending["kind"] == "file" and pending["file_path"] == ".env"

    await s.approve_pending_action(reply["id"], pending["id"])
    assert (tmp_path / ".env").read_text(encoding="utf-8") == "SECRET=1"


@pytest.mark.asyncio
async def test_git_metadata_writes_from_ai_are_refused(studio, tmp_path):
    s, mock_adapter = studio
    mock_adapter.queue_response(_reply("### file: .git/hooks/pre-commit\n```bash\ncalc\n```"))
    reply = await s.send_user_message("Write file .git/hooks/pre-commit", workspace_path=str(tmp_path), connector_name="mock")
    assert not (tmp_path / ".git" / "hooks" / "pre-commit").exists()
    assert reply["executed_file_changes"] == [] or all(c["path"] != ".git/hooks/pre-commit" for c in reply["executed_file_changes"])


@pytest.mark.asyncio
async def test_emergency_stop_blocks_approvals(studio, tmp_path):
    s, mock_adapter = studio
    mock_adapter.queue_response(_reply(HELLO_AND_RUN))
    reply = await s.send_user_message("Create hello.py and run it", workspace_path=str(tmp_path), connector_name="mock")
    permission_policy.trigger_emergency_stop()
    with pytest.raises(PermissionError):
        await s.approve_pending_action(reply["id"], reply["pending_actions"][0]["id"])


def test_prune_sessions_keeps_active_and_newest(tmp_path):
    s = ChatOrchestrator()
    s.sessions_file = tmp_path / "studio_sessions.json"
    s.sessions = {
        f"s{i}": {"id": f"s{i}", "title": f"chat {i}", "updated_at": f"2026-01-{i + 1:02d}", "messages": [{"id": "m"}]}
        for i in range(6)
    }
    s.sessions["empty"] = {"id": "empty", "title": "New Chat", "updated_at": "2026-02-01", "messages": []}
    s.active_session_id = "s0"  # oldest, but active

    outcome = s.prune_sessions(keep_latest=3, remove_empty=True)

    assert "s0" in s.sessions and "empty" not in s.sessions
    assert outcome["remaining"] == len(s.sessions) <= 4


@pytest.mark.asyncio
async def test_studio_http_defaults_to_manual_approval(tmp_path, monkeypatch):
    mock_adapter = orchestrator.get_connector("mock")
    mock_adapter.clear_queue()
    mock_adapter.queue_response(_reply(HELLO_AND_RUN))
    monkeypatch.setattr(chat_orchestrator, "sessions_file", tmp_path / "studio_sessions.json")
    monkeypatch.setattr(chat_orchestrator, "sessions", {"s": {"id": "s", "title": "t", "messages": []}})
    monkeypatch.setattr(chat_orchestrator, "active_session_id", "s")

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            res = await client.post("/api/v1/studio/chat", json={
                "message": "Create hello.py and run it",
                "workspace_path": str(tmp_path),
                "connector_name": "mock",
            })
            assert res.status_code == 200
            body = res.json()
            assert body["executed_commands"] == []
            action = body["pending_actions"][0]

            approve = await client.post(f"/api/v1/studio/messages/{body['id']}/actions/{action['id']}/approve")
            assert approve.status_code == 200 and approve.json()["status"] == "EXECUTED"

            again = await client.post(f"/api/v1/studio/messages/{body['id']}/actions/{action['id']}/approve")
            assert again.status_code == 409
            missing = await client.post(f"/api/v1/studio/messages/{body['id']}/actions/nope/approve")
            assert missing.status_code == 404
    finally:
        mock_adapter.clear_queue()
