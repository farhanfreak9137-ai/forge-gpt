# ForgeAgent V1

### Autonomous AI Software Development System (Local & Supervised)

ForgeAgent V1 is an autonomous AI coding agent designed to run locally on Windows hosts (with optional Docker container isolation). It coordinates software engineering tasks—project discovery, AI planning, structured code generation, atomic patching, build and test execution, failure diagnostics, iterative self-repair, and git rollback—around interchangeable external AI providers.

---

## Key Features

- **Decoupled 5-Engine Architecture**:
  1. **Orchestration Engine**: Owns the task lifecycle, durable state machine (16 discrete states), planning, and repair loops.
  2. **AI Communication Engine**: Unified interface connecting to OpenAI-compatible endpoints, local Ollama servers, manual browser handoff, and provider-permitted Playwright browser automation.
  3. **Context Engine**: Deterministic scanner, framework/language detector, `.gitignore` filtering, explainable relevance selection, and secret redaction.
  4. **Execution Engine**: Atomic file operations, path traversal/symlink guards, command allowlist runner, test executor, and git checkpoint rollback.
  5. **Persistence Engine**: SQLite with async SQLAlchemy 2.0, event bus with sequence-ordered WebSocket broadcast, and automatic crash recovery reconciliation.
- **Structured Communication Protocol (`forgeagent.v1`)**: Versioned JSON schema with Pydantic v2 validation supporting plans, context requests, code proposals, commands, and completion reports.
- **Supervised Autonomy**: Three-tiered permission model (Automatically Allowed, Task-Allowed, Explicit Approval Required) with an immediate emergency stop control.
- **Interactive Multi-Panel Dashboard**: React, TypeScript, Tailwind CSS, Lucide icons, and Monaco Editor with side-by-side diff inspection.

---

## Technology Stack

- **Backend**: Python 3.12+, FastAPI, Pydantic v2, SQLAlchemy 2.x, SQLite (`aiosqlite`), Playwright, AsyncIO.
- **Frontend**: React 18, TypeScript, Vite, Tailwind CSS, TanStack Query, Zustand, React Router, Monaco Editor.
- **Execution & Security**: Git, Safe Command Allowlist, Windows native sandbox, optional Docker multi-stage container.

---

## Project Structure

```text
forgeagent/
├── backend/
│   ├── app/
│   │   ├── main.py                    # FastAPI entrypoint, routes, lifespan
│   │   ├── config/settings.py         # App configuration & allowlist policy
│   │   ├── api/                       # REST /api/v1 & WebSocket endpoints
│   │   ├── core/                      # Orchestrator, state machine, permissions, recovery
│   │   ├── ai/                        # forgeagent.v1 protocol, context builder, connectors
│   │   ├── browser/                   # Playwright manager, local mock chatbot site
│   │   ├── workspace/                 # Safe file manager, patcher, git manager
│   │   ├── execution/                 # Safe command runner, test runner, diagnostics
│   │   ├── memory/                    # SQLAlchemy models, async SQLite DB engine
│   │   └── events/                    # EventBus with SQLite persistence & broadcast
│   ├── tests/                         # Mandatory Acceptance Tests A - L
│   ├── pyproject.toml
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/                # Navbar, Sidebar, Monaco editor & diff view
│   │   ├── features/                  # Dashboard overview, projects, workspace, activity, settings
│   │   ├── services/                  # REST API & auto-reconnecting WebSocket client
│   │   ├── stores/                    # Zustand application store
│   │   ├── types/                     # Shared TypeScript interfaces
│   │   ├── App.tsx
│   │   └── main.tsx
│   ├── package.json
│   └── vite.config.ts
├── docs/                              # Architecture, Connectors, Security, Acceptance Report
├── scripts/
│   ├── setup.ps1                      # Windows environment setup script
│   ├── start.ps1                      # Local startup launcher
│   └── test.ps1                       # Test suite runner
├── Dockerfile                         # Multi-stage production container
├── docker-compose.yml
├── .env.example
└── README.md
```

---

## Quickstart Guide (Windows)

### Prerequisites
- Windows 10/11
- PowerShell 5.1+ or PowerShell 7
- Git installed on PATH
- Node.js v20+ / npm

### Step 1: Automated Setup
Run the automated PowerShell setup script from the project root:
```powershell
.\scripts\setup.ps1
```
This script will:
1. Ensure Python 3.12 is installed (via `uv`).
2. Create `backend\.venv` and install backend packages.
3. Install the Playwright Chromium browser binary.
4. Install frontend npm dependencies and compile production assets.

### Step 2: Launch the System
```powershell
.\scripts\start.ps1
```
- **Backend API**: `http://127.0.0.1:8000` (Swagger docs at `/docs`)
- **Frontend Dashboard**: `http://localhost:5173`

---

## Running the Acceptance Test Suite (Tests A - L)

To execute all 14 end-to-end acceptance tests:
```powershell
.\scripts\test.ps1
```
Or directly via pytest in the backend virtualenv:
```powershell
cd backend
.\.venv\Scripts\python -m pytest tests -v
```

All 14 tests run in ~22 seconds with **100% pass rate**:
- **Test A**: New Project Creation & Scaffolding
- **Test B**: Existing Project Modification & Preservation
- **Test C**: Automatic Debugging & Repair Loop
- **Test D**: Git Rollback & Recovery
- **Test E**: Agent Crash Recovery & Reconciliation
- **Test F**: Invalid AI Response & Hash Rejection (2 tests)
- **Test G**: Playwright Browser Adapter with Local Mock Chatbot
- **Test H**: Supervised Approval Enforcement
- **Test I**: Live Event Stream & Reconnect Replay
- **Test J**: OpenAI-Compatible HTTP Connector
- **Test K**: Workspace Isolation (Path Traversal & Shell Chaining, 2 tests)
- **Test L**: Continuing Multi-Task Development Session

---

## Optional Docker Execution

To build and run ForgeAgent inside an isolated Docker container:
```bash
docker compose up --build
```
Access the application at `http://localhost:8000`.

---

## Documentation

- [System Architecture Specification](docs/ARCHITECTURE.md)
- [AI Connector Configuration Guide](docs/CONNECTORS.md)
- [Security Model & Sandboxing](docs/SECURITY.md)
- [Acceptance Test Verification Report](docs/ACCEPTANCE_REPORT.md)

