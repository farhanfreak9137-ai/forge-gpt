MOCK_CHATBOT_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>ForgeAgent Permitted Mock Chatbot</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #0f172a; color: #f8fafc; padding: 20px; }
        .container { max-width: 800px; margin: 0 auto; background: #1e293b; border-radius: 8px; padding: 20px; border: 1px solid #334155; }
        #chat-messages { min-height: 250px; max-height: 400px; overflow-y: auto; border: 1px solid #334155; border-radius: 6px; padding: 15px; margin-bottom: 15px; background: #0b1120; }
        .message { margin-bottom: 12px; padding: 10px; border-radius: 6px; }
        .user-message { background: #1e3a8a; border-left: 4px solid #3b82f6; }
        .bot-message { background: #0f2e24; border-left: 4px solid #10b981; }
        .error-message { background: #450a0a; border-left: 4px solid #ef4444; color: #fca5a5; }
        .input-bar { display: flex; gap: 10px; }
        textarea { flex: 1; height: 70px; background: #0f172a; color: #fff; border: 1px solid #334155; border-radius: 6px; padding: 10px; font-family: monospace; resize: none; }
        button { background: #2563eb; color: #fff; border: none; padding: 0 20px; border-radius: 6px; cursor: pointer; font-weight: bold; }
        button:hover { background: #1d4ed8; }
        button:disabled { background: #475569; cursor: not-allowed; }
        .status-badge { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: bold; }
        .status-streaming { background: #ca8a04; color: #fef08a; }
        .status-done { background: #15803d; color: #bbf7d0; }
    </style>
</head>
<body>
    <div class="container">
        <h2>ForgeAgent Permitted Mock Chatbot Service</h2>
        <p style="color: #94a3b8; font-size: 13px;">This local endpoint models an external chatbot website with streaming outputs and protocol compliance.</p>
        <div id="chat-messages">
            <div class="message bot-message">Ready for prompts. Submit your task or command.</div>
        </div>
        <div class="input-bar">
            <textarea id="prompt-input" placeholder="Type prompt or paste ForgeAgent request here..."></textarea>
            <button id="send-button" onclick="handleSubmit()">Send</button>
        </div>
    </div>

    <script>
        let isStreaming = false;

        async function handleSubmit() {
            const input = document.getElementById('prompt-input');
            const prompt = input.value.trim();
            if (!prompt || isStreaming) return;

            const sendBtn = document.getElementById('send-button');
            sendBtn.disabled = true;
            isStreaming = true;

            const chatMessages = document.getElementById('chat-messages');

            // Add user message
            const userMsg = document.createElement('div');
            userMsg.className = 'message user-message';
            userMsg.textContent = prompt;
            chatMessages.appendChild(userMsg);
            input.value = '';

            // Extract task_id and request_id if present
            let taskId = "test-task-1";
            let reqId = "test-req-1";
            const taskMatch = prompt.match(/task-([a-zA-Z0-9_-]+)/i);
            if (taskMatch) taskId = taskMatch[0];
            const reqMatch = prompt.match(/req-([a-zA-Z0-9_-]+)/i);
            if (reqMatch) reqId = reqMatch[0];

            if (prompt.includes("trigger_browser_error")) {
                const errMsg = document.createElement('div');
                errMsg.className = 'message error-message';
                errMsg.id = 'error-box';
                errMsg.textContent = "Error: Chatbot service simulated internal failure 500.";
                chatMessages.appendChild(errMsg);
                sendBtn.disabled = false;
                isStreaming = false;
                return;
            }

            // Create streaming bot message element
            const botMsg = document.createElement('div');
            botMsg.className = 'message bot-message';
            botMsg.id = 'active-bot-response';
            botMsg.setAttribute('data-status', 'streaming');
            chatMessages.appendChild(botMsg);

            // Generate payload based on prompt
            let responsePayload;
            if (prompt.toLowerCase().includes("plan")) {
                responsePayload = {
                    protocol_version: "forgeagent.v1",
                    task_id: taskId,
                    request_id: reqId,
                    response_type: "plan",
                    payload: {
                        summary: "Browser mock generated plan",
                        steps: [{ step_number: 1, title: "Initialize structure", description: "Create mock files", expected_files: ["browser_app.py"], dependencies: [] }],
                        acceptance_criteria: ["Files created successfully"]
                    }
                };
            } else {
                responsePayload = {
                    protocol_version: "forgeagent.v1",
                    task_id: taskId,
                    request_id: reqId,
                    response_type: "finish",
                    payload: {
                        summary: "Browser mock finished execution successfully",
                        verification_passed: true,
                        notes_for_user: "Browser adapter verification passed."
                    }
                };
            }

            const jsonString = JSON.stringify(responsePayload, null, 2);
            let index = 0;
            const interval = setInterval(() => {
                index += 15;
                if (index < jsonString.length) {
                    botMsg.textContent = jsonString.slice(0, index) + "...";
                } else {
                    clearInterval(interval);
                    botMsg.textContent = jsonString;
                    botMsg.setAttribute('data-status', 'completed');
                    botMsg.classList.add('completed-response');
                    sendBtn.disabled = false;
                    isStreaming = false;
                }
                chatMessages.scrollTop = chatMessages.scrollHeight;
            }, 30);
        }
    </script>
</body>
</html>
"""
