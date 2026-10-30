import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from app.config.settings import settings
from app.memory.database import init_db
from app.core.recovery.recovery import crash_recovery_manager
from app.browser.mock_chatbot.html_template import MOCK_CHATBOT_HTML

from app.api.projects import router as projects_router
from app.api.tasks import router as tasks_router
from app.api.connectors import router as connectors_router
from app.api.approvals import router as approvals_router
from app.api.files import router as files_router
from app.api.events import router as events_router
from app.api.settings_api import router as settings_router
from app.api.websocket import router as ws_router

# Setup structured logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("forgeagent")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing ForgeAgent V1 database...")
    await init_db()
    logger.info("Database initialized. Running crash recovery scan...")
    recovered = await crash_recovery_manager.scan_and_recover()
    if recovered:
        logger.info(f"Crash recovery reconciled {len(recovered)} tasks.")
    logger.info("ForgeAgent V1 startup sequence complete.")
    yield
    logger.info("ForgeAgent V1 shutting down...")


app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    description="Autonomous AI Software Development System",
    lifespan=lifespan,
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API Routers under /api/v1
api_prefix = "/api/v1"
app.include_router(projects_router, prefix=api_prefix)
app.include_router(tasks_router, prefix=api_prefix)
app.include_router(connectors_router, prefix=api_prefix)
app.include_router(approvals_router, prefix=api_prefix)
app.include_router(files_router, prefix=api_prefix)
app.include_router(events_router, prefix=api_prefix)
app.include_router(settings_router, prefix=api_prefix)
app.include_router(ws_router, prefix=api_prefix)


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "app": settings.app_name,
        "version": settings.version,
        "execution_mode": settings.execution_mode,
    }


@app.get("/")
async def root():
    return {
        "message": f"Welcome to {settings.app_name} V1 API",
        "docs_url": "/docs",
        "health_url": "/health",
        "api_v1": "/api/v1",
    }


@app.get("/mock-chatbot", response_class=HTMLResponse)
async def serve_mock_chatbot():
    """Serves the local mock chatbot page for automated Playwright connector tests."""
    return HTMLResponse(content=MOCK_CHATBOT_HTML)

