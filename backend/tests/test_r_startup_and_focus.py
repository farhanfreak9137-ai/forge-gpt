"""A server start opens a clean chat, and Edge never steals focus unless explicitly allowed."""
import json
import subprocess
from pathlib import Path

import pytest

from app.ai.agent_loop.chat_orchestrator import ChatOrchestrator
from app.browser.manager.browser_manager import BrowserManager
from app.config.settings import settings


def _orchestrator_with(tmp_path: Path, sessions: dict, active: str) -> ChatOrchestrator:
    """Simulate a server restart: sessions already on disk, then a new orchestrator is created."""
    sessions_file = tmp_path / "studio_sessions.json"
    sessions_file.write_text(json.dumps({"sessions": sessions, "active_session_id": active}), encoding="utf-8")
    original = settings.data_dir
    object.__setattr__(settings, "data_dir", tmp_path)
    try:
        return ChatOrchestrator()
    finally:
        object.__setattr__(settings, "data_dir", original)


def _session(sid: str, messages: list, chatgpt_id=None, updated="2026-01-01T00:00:00") -> dict:
    return {"id": sid, "title": sid, "created_at": updated, "updated_at": updated, "messages": messages, "chatgpt_id": chatgpt_id}


def test_restart_opens_a_new_chat_not_the_one_left_behind(tmp_path):
    left_behind = _session("old", [{"id": "m1", "sender": "user", "text": "hi"}])
    s = _orchestrator_with(tmp_path, {"old": left_behind}, active="old")

    assert s.active_session_id != "old"
    assert s.get_active_session()["messages"] == []
    assert s.get_active_session()["title"] == "New Chat"
    assert s.sessions["old"]["messages"], "the old chat must be kept, just not opened"


def test_restart_reuses_an_empty_chat_instead_of_piling_up_blank_ones(tmp_path):
    sessions = {
        "old": _session("old", [{"id": "m1", "sender": "user", "text": "hi"}]),
        "blank": _session("blank", []),
    }
    s = _orchestrator_with(tmp_path, sessions, active="old")
    assert s.active_session_id == "blank"
    assert len(s.sessions) == 2

    # restarting again still does not add another one
    s2 = _orchestrator_with(tmp_path, s.sessions, active=s.active_session_id)
    assert len(s2.sessions) == 2


def test_an_imported_chatgpt_chat_is_not_mistaken_for_a_blank_one(tmp_path):
    sessions = {"imported": _session("imported", [], chatgpt_id="abc123")}
    s = _orchestrator_with(tmp_path, sessions, active="imported")
    assert s.active_session_id != "imported"
    assert len(s.sessions) == 2


def test_the_fresh_chat_is_saved_so_the_ui_sees_it(tmp_path):
    s = _orchestrator_with(tmp_path, {"old": _session("old", [{"id": "m", "sender": "user", "text": "x"}])}, active="old")
    saved = json.loads((tmp_path / "studio_sessions.json").read_text(encoding="utf-8"))
    assert saved["active_session_id"] == s.active_session_id != "old"


def test_focus_is_not_stolen_by_default(monkeypatch):
    assert settings.edge_steal_focus is False
    calls = []
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: calls.append(a))
    BrowserManager(use_cdp=False).focus_edge_window()
    assert calls == [], "no PowerShell AppActivate when focus stealing is off"


@pytest.mark.asyncio
async def test_pages_are_not_brought_to_front_by_default():
    class FakePage:
        raised = 0

        async def bring_to_front(self):
            self.raised += 1

    page = FakePage()
    manager = BrowserManager(use_cdp=False)
    await manager._surface(page)
    assert page.raised == 0


@pytest.mark.asyncio
async def test_focus_stealing_can_be_switched_back_on(monkeypatch):
    class FakePage:
        raised = 0

        async def bring_to_front(self):
            self.raised += 1

    monkeypatch.setattr(settings, "edge_steal_focus", True)
    page = FakePage()
    await BrowserManager(use_cdp=False)._surface(page)
    assert page.raised == 1
