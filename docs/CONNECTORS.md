# AI Connector Setup and Configuration Guide

ForgeAgent V1 supports 5 interchangeable AI providers accessed through one normalized interface.

---

## 1. Deterministic Mock Provider (`mock`)
- **Use Case**: Offline local development, unit tests, automated CI/CD runs, and demonstrations without credentials.
- **Capabilities**: Pre-scripted protocol generation, intelligent fallbacks for code generation, test failure repair, and completion.
- **Configuration**: Always available with zero configuration.

---

## 2. OpenAI-Compatible HTTP Connector (`openai`)
- **Use Case**: Connecting to OpenAI (e.g. `gpt-4o`, `o1`), OpenRouter, or local servers such as vLLM, LMStudio, LocalAI, or text-generation-webui.
- **Configuration Settings**:
  - `FORGEAGENT_OPENAI_BASE_URL`: API Base URL (e.g. `https://api.openai.com/v1` or `http://127.0.0.1:1234/v1`).
  - `FORGEAGENT_OPENAI_API_KEY`: API Key (optional for local unauthenticated servers).
  - `FORGEAGENT_OPENAI_MODEL_ID`: Model identifier (e.g. `gpt-4o` or `meta-llama-3-8b`).
- **Security**: API keys are encrypted/redacted and never exposed in REST responses or activity logs.

---

## 3. Local Ollama Model Connector (`ollama`)
- **Use Case**: Free, private, local model execution via Ollama.
- **Capabilities**:
  - Automatic detection of running server (`/api/tags`).
  - Listing installed models.
  - Native JSON schema mode.
- **Configuration Settings**:
  - `FORGEAGENT_OLLAMA_BASE_URL`: Default `http://127.0.0.1:11434`.
  - `FORGEAGENT_OLLAMA_MODEL_ID`: Model tag (e.g. `llama3:latest`, `codellama`, `deepseek-coder`).

---

## 4. Manual Browser Handoff (`browser_handoff`)
- **Use Case**: Developing with web-based chatbots (ChatGPT Web, Claude Web, Gemini Web) without requiring API keys or browser automation.
- **Workflow**:
  1. Agent prepares structured prompt including task ID and `forgeagent.v1` protocol instructions.
  2. User copies prompt with one click from dashboard and pastes it into their browser chatbot.
  3. User copies the chatbot's response JSON and pastes it into the ForgeAgent input box.
  4. System validates the payload with Pydantic and automatically resumes execution.

---

## 5. Provider-Permitted Browser Automation (`browser_automation`)
- **Use Case**: Automated browser-driven interaction with chatbot websites that explicitly permit automation.
- **Safety Policy**:
  - Remains disabled by default until permitted status is explicitly verified.
  - Operates via Playwright with a persistent Chromium profile.
  - Detects streaming progress, waits for response completion signals, and extracts structured output.
  - Fully tested against ForgeAgent's built-in local mock chatbot (`http://127.0.0.1:8000/mock-chatbot`).
