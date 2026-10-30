import asyncio
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

from app.config.settings import settings
from app.events.event_bus import event_bus
from app.core.orchestrator.orchestrator import orchestrator
from app.workspace.files.file_manager import SafeFileManager
from app.workspace.git.git_manager import GitManager
from app.execution.commands.runner import SafeCommandRunner
from app.ai.agent_loop.action_parser import (
    ActionParser,
    ParsedAgentTurn,
    SYSTEM_PROMPT_AGENT_HANDS,
)

logger = logging.getLogger("forgeagent.ai.chat_orchestrator")


class ChatMessage(Dict[str, Any]):
    pass


class ChatOrchestrator:
    """
    Manages conversational pair-programming sessions with ChatGPT Web / external AI.
    Handles natural language chatting, file writes, command executions, and autonomous repair loops.
    """

    def __init__(self):
        self.conversation_history: List[Dict[str, Any]] = []
        self._lock = asyncio.Lock()

    def get_history(self) -> List[Dict[str, Any]]:
        return list(self.conversation_history)

    def clear_history(self) -> None:
        self.conversation_history.clear()

    async def send_user_message(
        self,
        message: str,
        workspace_path: Optional[str] = None,
        auto_pilot: bool = True,
        connector_name: Optional[str] = None,
        max_repair_iterations: int = 3,
    ) -> Dict[str, Any]:
        """
        Processes a user message:
        1. Dispatches message to ChatGPT.
        2. Parses response for conversation vs code/command actions.
        3. Executes actions (writes files, runs commands).
        4. In auto_pilot mode, if tests fail, loops back to ChatGPT with error logs until resolved.
        """
        ws_path = Path(workspace_path or settings.base_dir).resolve()
        connector = orchestrator.get_connector(connector_name)
        file_mgr = SafeFileManager(str(ws_path))
        git_mgr = GitManager(str(ws_path))
        cmd_runner = SafeCommandRunner(str(ws_path))

        user_msg_id = str(uuid.uuid4())
        assistant_msg_id = str(uuid.uuid4())

        # 1. Record user message
        user_record = {
            "id": user_msg_id,
            "sender": "user",
            "text": message,
            "timestamp": datetime.utcnow().isoformat(),
        }
        self.conversation_history.append(user_record)
        await event_bus.publish(
            event_type="CHAT_MESSAGE_SENT",
            message=message,
            payload=user_record,
        )

        # Send the user's exact message directly without any intrusive system prompts or metadata
        current_prompt = message
        repair_iteration = 0
        executed_file_changes = []
        executed_commands = []
        final_reply_text = ""

        while True:
            # 2. Query ChatGPT
            logger.info(f"Querying AI ({connector.name}) with prompt (length: {len(current_prompt)})...")
            req_id = f"chat-{uuid.uuid4().hex[:8]}"
            
            try:
                envelope = await connector.send_request(
                    prompt=current_prompt,
                    task_id="chat-studio",
                    request_id=req_id,
                )
                
                # Extract text
                if envelope.payload.get("analysis"):
                    raw_reply = str(envelope.payload.get("analysis"))
                elif envelope.payload.get("summary"):
                    raw_reply = str(envelope.payload.get("summary"))
                else:
                    raw_reply = envelope.model_dump_json()
            except Exception as e:
                raw_reply = f"Error communicating with AI connector: {e}"
                logger.error(raw_reply)

            # 3. Parse actions vs conversational text
            parsed: ParsedAgentTurn = ActionParser.parse(raw_reply)
            final_reply_text = raw_reply

            # 4. If no actions (plain casual chat), we are done!
            if not parsed.has_actions:
                logger.info("Natural conversation response received without code actions.")
                break

            # 5. Apply File Actions ("The Hands")
            for fa in parsed.file_actions:
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
                logger.info(f"Executing command: {ca.command}")
                await event_bus.publish(
                    event_type="STUDIO_COMMAND_STARTED",
                    message=f"Executing: {ca.command}",
                    payload={"command": ca.command},
                )
                
                try:
                    res = await cmd_runner.run(ca.command)
                    passed = res.get("exit_code") == 0
                    cmd_record = {
                        "command": ca.command,
                        "exit_code": res.get("exit_code"),
                        "stdout": res.get("stdout", ""),
                        "stderr": res.get("stderr", ""),
                        "duration_ms": res.get("duration_ms", 0),
                        "passed": passed,
                    }
                except Exception as e:
                    logger.warning(f"Command execution error: {e}")
                    passed = False
                    cmd_record = {
                        "command": ca.command,
                        "exit_code": 1,
                        "stdout": "",
                        "stderr": f"Command error: {e}",
                        "duration_ms": 0,
                        "passed": False,
                    }

                executed_commands.append(cmd_record)

                await event_bus.publish(
                    event_type="STUDIO_COMMAND_FINISHED",
                    message=f"Command finished with exit code {cmd_record.get('exit_code')}: {ca.command}",
                    payload=cmd_record,
                )

                if not passed:
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

        # 8. Record assistant reply
        assistant_record = {
            "id": assistant_msg_id,
            "sender": "assistant",
            "text": final_reply_text,
            "clean_message": parsed.clean_message,
            "file_actions": [f.model_dump() for f in parsed.file_actions],
            "executed_file_changes": executed_file_changes,
            "executed_commands": executed_commands,
            "repair_iterations": repair_iteration,
            "timestamp": datetime.utcnow().isoformat(),
        }
        self.conversation_history.append(assistant_record)

        await event_bus.publish(
            event_type="CHAT_MESSAGE_RECEIVED",
            message=parsed.clean_message[:100],
            payload=assistant_record,
        )

        return assistant_record


chat_orchestrator = ChatOrchestrator()

