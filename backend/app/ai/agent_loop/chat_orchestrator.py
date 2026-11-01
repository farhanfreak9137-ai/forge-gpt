import asyncio
import json
import logging
import re
import uuid
from datetime import datetime
from app.utils.clock import utcnow
from pathlib import Path
from typing import List, Dict, Any, Optional

from app.config.settings import settings
from app.events.event_bus import event_bus
from app.core.orchestrator.orchestrator import orchestrator
from app.core.permissions.policy import permission_policy, PermissionLevel
from app.workspace.files.file_manager import SafeFileManager
from app.workspace.git.git_manager import GitManager
from app.execution.commands.runner import SafeCommandRunner
from app.ai.agent_loop.action_parser import (
    ActionParser,
    ParsedAgentTurn,
    SYSTEM_PROMPT_AGENT_HANDS,
)

logger = logging.getLogger("forgeagent.ai.chat_orchestrator")


class ChatOrchestrator:
    """
    Manages conversational pair-programming sessions with ChatGPT Web / external AI.
    Handles natural language chatting, file writes, command executions, session persistence,
    and automatic synchronization with ChatGPT conversation history.
    """

    def __init__(self):
        self.sessions_file = settings.data_dir / "studio_sessions.json"
        self.sessions: Dict[str, Dict[str, Any]] = {}
        self.active_session_id: Optional[str] = None
        self._lock = asyncio.Lock()
        self._load_sessions()
        self._start_fresh_chat()

    def _start_fresh_chat(self) -> None:
        """Each server start opens on a clean chat instead of whichever one was left open last time.

        An existing empty chat is reused, so restarting repeatedly does not pile up blank chats. Nothing
        touches the browser here: Edge is only involved once a message is sent.
        """
        now = utcnow().isoformat()
        blanks = [s for s in self.sessions.values() if not s.get("messages") and not s.get("chatgpt_id")]
        if blanks:
            fresh = max(blanks, key=lambda s: s.get("updated_at", ""))
            fresh["updated_at"] = now
        else:
            new_id = f"session-{uuid.uuid4().hex[:8]}"
            fresh = {
                "id": new_id,
                "title": "New Chat",
                "created_at": now,
                "updated_at": now,
                "messages": [],
                "chatgpt_id": None,
            }
            self.sessions[new_id] = fresh
        self.active_session_id = fresh["id"]
        self._save_sessions()

    def _load_sessions(self):
        try:
            if self.sessions_file.exists():
                with open(self.sessions_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.sessions = data.get("sessions", {})
                    self.active_session_id = data.get("active_session_id")
        except Exception as e:
            logger.warning(f"Failed to load studio sessions: {e}")
            self.sessions = {}

        if not self.sessions:
            new_id = f"session-{uuid.uuid4().hex[:8]}"
            self.sessions[new_id] = {
                "id": new_id,
                "title": "New Chat",
                "created_at": utcnow().isoformat(),
                "updated_at": utcnow().isoformat(),
                "messages": [],
                "chatgpt_id": None,
            }
            self.active_session_id = new_id

        if not self.active_session_id or self.active_session_id not in self.sessions:
            self.active_session_id = list(self.sessions.keys())[0]

    def _save_sessions(self):
        try:
            self.sessions_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.sessions_file, "w", encoding="utf-8") as f:
                json.dump({
                    "sessions": self.sessions,
                    "active_session_id": self.active_session_id
                }, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save studio sessions: {e}")

    def get_active_session(self) -> Dict[str, Any]:
        if not self.active_session_id or self.active_session_id not in self.sessions:
            if self.sessions:
                self.active_session_id = list(self.sessions.keys())[0]
            else:
                new_id = f"session-{uuid.uuid4().hex[:8]}"
                self.sessions[new_id] = {
                    "id": new_id,
                    "title": "New Chat",
                    "created_at": utcnow().isoformat(),
                    "updated_at": utcnow().isoformat(),
                    "messages": [],
                    "chatgpt_id": None,
                }
                self.active_session_id = new_id
                self._save_sessions()
        return self.sessions[self.active_session_id]

    async def list_sessions(self, sync_chatgpt: bool = True) -> List[Dict[str, Any]]:
        """Returns all sessions, synchronizing with ChatGPT's saved threads if available."""
        if sync_chatgpt:
            try:
                from app.browser.manager.browser_manager import browser_manager
                chatgpt_chats = await browser_manager.get_chatgpt_conversations()
                for c in chatgpt_chats:
                    cid = c["id"]
                    # If not already present, create a session entry for it
                    if cid not in self.sessions and not any(s.get("chatgpt_id") == cid for s in self.sessions.values()):
                        self.sessions[cid] = {
                            "id": cid,
                            "title": c["title"],
                            "created_at": utcnow().isoformat(),
                            "updated_at": utcnow().isoformat(),
                            "messages": [],
                            "chatgpt_id": cid,
                        }
                self._save_sessions()
            except Exception as e:
                logger.debug(f"Syncing ChatGPT conversations skipped: {e}")

        # Return list sorted by updated_at descending
        sorted_list = sorted(
            self.sessions.values(),
            key=lambda s: s.get("updated_at", ""),
            reverse=True,
        )
        return [
            {
                "id": s["id"],
                "title": s.get("title", "Conversation"),
                "created_at": s.get("created_at"),
                "updated_at": s.get("updated_at"),
                "message_count": len(s.get("messages", [])),
                "is_active": s["id"] == self.active_session_id,
                "chatgpt_id": s.get("chatgpt_id"),
            }
            for s in sorted_list
        ]

    async def create_session(self, title: str = "New Chat") -> Dict[str, Any]:
        new_id = f"session-{uuid.uuid4().hex[:8]}"
        session = {
            "id": new_id,
            "title": title,
            "created_at": utcnow().isoformat(),
            "updated_at": utcnow().isoformat(),
            "messages": [],
            "chatgpt_id": None,
        }
        self.sessions[new_id] = session
        self.active_session_id = new_id
        self._save_sessions()

        # In Edge, navigate to clean new chat
        try:
            from app.browser.manager.browser_manager import browser_manager
            await browser_manager.navigate_to_chat("https://chatgpt.com/")
        except Exception:
            pass

        return session

    async def select_session(self, session_id: str) -> Dict[str, Any]:
        if session_id not in self.sessions:
            raise KeyError(f"Session {session_id} not found")
        self.active_session_id = session_id
        session = self.sessions[session_id]

        # If it has a chatgpt_id, navigate Edge to it
        chatgpt_id = session.get("chatgpt_id") or (session_id if len(session_id) > 20 else None)
        if chatgpt_id:
            try:
                from app.browser.manager.browser_manager import browser_manager
                await browser_manager.navigate_to_chat(f"https://chatgpt.com/c/{chatgpt_id}")
                # If session has no messages yet, extract from page
                if not session.get("messages"):
                    turns = await browser_manager.get_current_chat_messages()
                    if turns:
                        session["messages"] = turns
                        self._save_sessions()
            except Exception as e:
                logger.warning(f"Failed to navigate Edge to chat {chatgpt_id}: {e}")

        self._save_sessions()
        return session

    def delete_session(self, session_id: str) -> None:
        if session_id in self.sessions:
            del self.sessions[session_id]
            if self.active_session_id == session_id:
                if self.sessions:
                    self.active_session_id = list(self.sessions.keys())[0]
                else:
                    self.active_session_id = None
            self._save_sessions()

    def get_history(self) -> List[Dict[str, Any]]:
        active = self.get_active_session()
        return list(active.get("messages", []))

    def clear_history(self) -> None:
        active = self.get_active_session()
        active["messages"] = []
        active["updated_at"] = utcnow().isoformat()
        self._save_sessions()

    @staticmethod
    async def _run_command(cmd_runner: SafeCommandRunner, command: str) -> Dict[str, Any]:
        try:
            res = await cmd_runner.run(command)
            return {
                "command": command,
                "exit_code": res.get("exit_code"),
                "stdout": res.get("stdout", ""),
                "stderr": res.get("stderr", ""),
                "duration_ms": res.get("duration_ms", 0),
                "passed": res.get("exit_code") == 0,
                "status": "EXECUTED",
            }
        except Exception as e:
            logger.warning(f"Command execution error: {e}")
            return {
                "command": command,
                "exit_code": 1,
                "stdout": "",
                "stderr": f"Command error: {e}",
                "duration_ms": 0,
                "passed": False,
                "status": "EXECUTED",
            }

    def _find_pending_action(self, message_id: str, action_id: str):
        for session in self.sessions.values():
            for message in session.get("messages", []):
                if message.get("id") == message_id:
                    for action in message.get("pending_actions", []):
                        if action.get("id") == action_id:
                            return message, action
        raise KeyError(f"Pending action {action_id} not found on message {message_id}")

    async def approve_pending_action(self, message_id: str, action_id: str) -> Dict[str, Any]:
        """Run or apply an action the user has explicitly approved. The allowlist still applies."""
        message, action = self._find_pending_action(message_id, action_id)
        if action["status"] != "PENDING_APPROVAL":
            raise ValueError(f"Action already {action['status']}")
        if permission_policy.is_emergency_stop_active:
            raise PermissionError("Emergency stop is active; reset it before approving actions.")

        ws_path = Path(action["workspace_path"])
        if action["kind"] == "command":
            result = await self._run_command(SafeCommandRunner(str(ws_path)), action["command"])
            message.setdefault("executed_commands", []).append(result)
            action["status"] = "EXECUTED"
            action["result"] = result
            await event_bus.publish(
                event_type="STUDIO_COMMAND_FINISHED",
                message=f"Approved command finished with exit code {result.get('exit_code')}: {action['command']}",
                payload=result,
            )
        else:
            try:
                SafeFileManager(str(ws_path)).write_file_atomic(action["file_path"], action["content"])
                message.setdefault("executed_file_changes", []).append({
                    "path": action["file_path"],
                    "lines": len(action["content"].splitlines()),
                    "status": "APPLIED",
                })
                action["status"] = "APPLIED"
            except Exception as e:
                action["status"] = "FAILED"
                action["result"] = {"error": str(e)}
        self._save_sessions()
        return action

    def reject_pending_action(self, message_id: str, action_id: str) -> Dict[str, Any]:
        _, action = self._find_pending_action(message_id, action_id)
        if action["status"] != "PENDING_APPROVAL":
            raise ValueError(f"Action already {action['status']}")
        action["status"] = "REJECTED"
        self._save_sessions()
        return action

    def prune_sessions(self, keep_latest: int = 10, remove_empty: bool = True) -> Dict[str, int]:
        """Drop empty chats and everything older than the newest `keep_latest` (active chat is kept)."""
        ordered = sorted(self.sessions.values(), key=lambda s: s.get("updated_at", ""), reverse=True)
        removed = 0
        for index, sess in enumerate(ordered):
            if sess["id"] == self.active_session_id:
                continue
            empty = remove_empty and not sess.get("messages")
            if empty or index >= keep_latest:
                del self.sessions[sess["id"]]
                removed += 1
        self._save_sessions()
        return {"removed": removed, "remaining": len(self.sessions)}

    async def send_user_message(
        self,
        message: str,
        workspace_path: Optional[str] = None,
        auto_pilot: bool = False,
        connector_name: Optional[str] = None,
        max_repair_iterations: int = 3,
    ) -> Dict[str, Any]:
        """
        Processes a user message:
        1. Dispatches message to ChatGPT.
        2. Parses response for conversation vs code/command actions.
        3. Writes files; runs commands only when auto_pilot is on AND the permission policy and
           command allowlist both accept them. Everything else is queued as a pending action that
           the user must approve (see approve_pending_action).
        4. In auto_pilot mode, if tests fail, loops back to ChatGPT with error logs until resolved.
        """
        ws_path = Path(workspace_path or settings.workspace_dir).resolve()
        connector = orchestrator.get_connector(connector_name)
        file_mgr = SafeFileManager(str(ws_path))
        git_mgr = GitManager(str(ws_path))
        cmd_runner = SafeCommandRunner(str(ws_path))

        active_sess = self.get_active_session()

        # If this is the first message in a newly created chat, auto-update the title
        if active_sess.get("title") in ("New Chat", "Untitled", None, ""):
            active_sess["title"] = message[:35].strip()

        user_msg_id = str(uuid.uuid4())
        assistant_msg_id = str(uuid.uuid4())

        # 1. Record user message
        user_record = {
            "id": user_msg_id,
            "sender": "user",
            "text": message,
            "timestamp": utcnow().isoformat(),
        }
        active_sess.setdefault("messages", []).append(user_record)
        active_sess["updated_at"] = utcnow().isoformat()
        self._save_sessions()

        await event_bus.publish(
            event_type="CHAT_MESSAGE_SENT",
            message=message,
            payload=user_record,
        )

        # Build the prompt. For file/task requests, wrap with format instructions
        # so ChatGPT outputs parseable ### file: blocks that we can write to disk.
        FILE_FORMAT = (
            "When creating or editing files output EACH file in this exact format (no exceptions):\n"
            "### file: <relative/path/to/file.ext>\n"
            "```<language>\n"
            "<complete file content here>\n"
            "```\n"
            "Use only relative paths. Now do the following: "
        )
        # Heuristic: if the message sounds like a task (create, make, build, write, generate, add, update, fix)
        # inject the format prefix so ChatGPT knows to output code blocks.
        task_keywords = ["create", "make", "build", "write", "generate", "add", "update", "fix", "implement", "save", "put"]
        needs_format_hint = any(kw in message.lower() for kw in task_keywords)
        lower_message = message.lower()
        file_request_keywords = ("create", "make", "write", "generate", "save", "add", "update", "fix", "implement")
        mentions_file = bool(
            re.search(r"\bfiles?\b", lower_message)
            or re.search(r"\b[\w.-]+\.[a-z0-9]{1,8}\b", lower_message)
        )
        expects_file_output = mentions_file and any(
            re.search(rf"\b{keyword}\b", lower_message) for keyword in file_request_keywords
        )
        current_prompt = (FILE_FORMAT + message) if needs_format_hint else message
        file_action_retry_count = 0
        repair_iteration = 0
        executed_file_changes = []
        executed_commands = []
        action_errors = []
        pending_actions: List[Dict[str, Any]] = []
        final_reply_text = ""
        parsed = None

        while True:
            # 2. Query ChatGPT
            logger.info(f"Querying AI ({connector.name}) with prompt (length: {len(current_prompt)})...")
            req_id = f"chat-{uuid.uuid4().hex[:8]}"
            connector_error = None

            try:
                envelope = await connector.send_request(
                    prompt=current_prompt,
                    task_id="chat-studio",
                    request_id=req_id,
                )

                # Extract text from envelope payload
                if envelope.payload.get("analysis"):
                    raw_reply = str(envelope.payload.get("analysis"))
                elif envelope.payload.get("summary"):
                    raw_reply = str(envelope.payload.get("summary"))
                else:
                    raw_reply = envelope.model_dump_json()

            except Exception as e:
                logger.error(f"Error communicating with AI connector: {e}")
                connector_error = str(e)
                # If this looks like a browser/Playwright crash, reset state so the next
                # request gets a fresh browser context instead of reusing a dead one.
                err_str = str(e).lower()
                if any(kw in err_str for kw in ["browsercontext", "playwright", "target page", "browser has been closed"]):
                    try:
                        from app.browser.manager.browser_manager import browser_manager as _bm
                        await _bm.close()
                        logger.info("Browser manager reset after BrowserContext error.")
                    except Exception:
                        pass
                raw_reply = f"Error communicating with AI connector: {e}"

            # 3. Parse actions vs conversational text
            parsed = ActionParser.parse(raw_reply)
            final_reply_text = raw_reply

            if connector_error:
                if expects_file_output:
                    action_errors.append(
                        f"AI connector failed; requested files were not saved: {connector_error}"
                    )
                break

            if expects_file_output and not parsed.file_actions:
                if file_action_retry_count < 1:
                    file_action_retry_count += 1
                    current_prompt = (
                        f"{FILE_FORMAT}{message}\n\n"
                        "Your previous response did not include any file content, so no file was saved. "
                        "Now provide the complete contents for every requested file using the exact format above. "
                        "Do not acknowledge the request or describe what you would do; output the actual file block."
                    )
                    logger.warning("File request returned no file content; retrying once with explicit instructions.")
                    continue

                error = "No file content was provided after retry; the requested file was not saved."
                action_errors.append(error)
                logger.error(error)
                break

            # 4. If no actions (plain casual chat), we are done!
            if not parsed.has_actions:
                logger.info("Natural conversation response received without code actions.")
                break

            # 5. Apply File Actions ("The Hands")
            for fa in parsed.file_actions:
                if permission_policy.is_emergency_stop_active or permission_policy.is_sensitive_path(fa.file_path):
                    pending_actions.append({
                        "id": uuid.uuid4().hex[:12],
                        "kind": "file",
                        "status": "PENDING_APPROVAL",
                        "reason": f"Writing sensitive file '{fa.file_path}' requires explicit approval",
                        "file_path": fa.file_path,
                        "content": fa.content,
                        "workspace_path": str(ws_path),
                    })
                    continue
                try:
                    file_mgr.write_file_atomic(fa.file_path, fa.content)
                    executed_file_changes.append({
                        "path": fa.file_path,
                        "lines": len(fa.content.splitlines()),
                        "status": "APPLIED",
                    })
                    logger.info(f"Wrote file to workspace: {fa.file_path}")
                    await event_bus.publish(
                        event_type="STUDIO_FILE_WRITTEN",
                        message=f"Created/modified file: {fa.file_path}",
                        payload={"path": fa.file_path, "content": fa.content},
                    )
                except Exception as e:
                    logger.error(f"Failed to write file {fa.file_path}: {e}")
                    action_errors.append(f"Could not save {fa.file_path}: {e}")

            # Record Git checkpoint if files were touched
            if executed_file_changes:
                try:
                    await git_mgr.init_repo()
                    await git_mgr.create_checkpoint("chat-studio", f"Auto-checkpoint after message: {message[:30]}")
                except Exception as e:
                    logger.warning(f"Git checkpoint error: {e}")

            # 6. Execute Command Actions
            has_command_failure = False
            last_failure_output = ""

            for ca in parsed.command_actions:
                allowed, allow_reason = cmd_runner.is_command_allowed(ca.command)
                perm_level, perm_reason = permission_policy.evaluate_command(ca.command)

                if not allowed:
                    # Never runnable, with or without approval
                    logger.warning(f"Blocked command from AI: {ca.command} ({allow_reason})")
                    cmd_record = {
                        "command": ca.command,
                        "exit_code": None,
                        "stdout": "",
                        "stderr": allow_reason,
                        "duration_ms": 0,
                        "passed": False,
                        "status": "BLOCKED",
                    }
                    executed_commands.append(cmd_record)
                    await event_bus.publish(
                        event_type="STUDIO_COMMAND_BLOCKED",
                        message=f"Blocked: {ca.command} - {allow_reason}",
                        payload=cmd_record,
                    )
                    continue

                if not auto_pilot or perm_level != PermissionLevel.TASK_ALLOWED:
                    reason = perm_reason if perm_level != PermissionLevel.TASK_ALLOWED else (
                        "Auto-Pilot is off: commands suggested by the AI need your approval before they run"
                    )
                    pending = {
                        "id": uuid.uuid4().hex[:12],
                        "kind": "command",
                        "status": "PENDING_APPROVAL",
                        "reason": reason,
                        "command": ca.command,
                        "workspace_path": str(ws_path),
                    }
                    pending_actions.append(pending)
                    await event_bus.publish(
                        event_type="STUDIO_APPROVAL_REQUIRED",
                        message=f"Approval required: {ca.command}",
                        payload=pending,
                    )
                    continue

                logger.info(f"Executing command: {ca.command}")
                await event_bus.publish(
                    event_type="STUDIO_COMMAND_STARTED",
                    message=f"Executing: {ca.command}",
                    payload={"command": ca.command},
                )

                cmd_record = await self._run_command(cmd_runner, ca.command)
                executed_commands.append(cmd_record)

                await event_bus.publish(
                    event_type="STUDIO_COMMAND_FINISHED",
                    message=f"Command finished with exit code {cmd_record.get('exit_code')}: {ca.command}",
                    payload=cmd_record,
                )

                if not cmd_record["passed"]:
                    has_command_failure = True
                    last_failure_output = f"Command '{ca.command}' failed:\n{cmd_record.get('stderr') or cmd_record.get('stdout')}"

            # 7. Check if Auto-Pilot needs to loop back to fix errors
            if auto_pilot and has_command_failure and repair_iteration < max_repair_iterations:
                repair_iteration += 1
                logger.info(f"Auto-pilot detected command failure. Triggering repair iteration {repair_iteration}/{max_repair_iterations}...")
                current_prompt = (
                    f"The command execution produced the following failure:\n\n{last_failure_output}\n\n"
                    f"Please analyze this failure, fix the code, and output the corrected file blocks."
                )
                await event_bus.publish(
                    event_type="STUDIO_AUTOPILOT_REPAIR",
                    message=f"Auto-pilot fixing failure (Attempt {repair_iteration}/{max_repair_iterations})...",
                    payload={"attempt": repair_iteration, "error": last_failure_output},
                )
                continue  # Loop back to ChatGPT with failure diagnostics
            else:
                break

        # Ensure parsed is always set (fallback if loop never ran)
        if parsed is None:
            parsed = ActionParser.parse(final_reply_text)

        clean_message = parsed.clean_message
        if action_errors:
            outcome_notice = "File action failed: " + " ".join(action_errors)
            final_reply_text = f"{final_reply_text.rstrip()}\n\n{outcome_notice}".strip()
            clean_message = f"{clean_message.rstrip()}\n\n{outcome_notice}".strip()

        # 8. Record assistant reply
        assistant_record = {
            "id": assistant_msg_id,
            "sender": "assistant",
            "text": final_reply_text,
            "clean_message": clean_message,
            "file_actions": [f.model_dump() for f in parsed.file_actions],
            "executed_file_changes": executed_file_changes,
            "executed_commands": executed_commands,
            "action_errors": action_errors,
            "pending_actions": pending_actions,
            "repair_iterations": repair_iteration,
            "timestamp": utcnow().isoformat(),
        }
        active_sess.setdefault("messages", []).append(assistant_record)
        active_sess["updated_at"] = utcnow().isoformat()
        self._save_sessions()

        await event_bus.publish(
            event_type="CHAT_MESSAGE_RECEIVED",
            message=clean_message[:100],
            payload=assistant_record,
        )

        return assistant_record


chat_orchestrator = ChatOrchestrator()
